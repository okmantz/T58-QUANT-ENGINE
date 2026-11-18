"""The three shipped bots, one per objective (app/objectives.py ENGINE DIRECTIVE: each has its own books, sizing and risk governor; none is tuned with another's priorities).

  Objective A  Evaluation Passer      Open Drive x1 + Ind Rule 15m x3 + Context Drive long-only x1 (NQ); progress-tapering governor, combined day stop 40% of the soft limit
  Objective B  Payout Hunter          Ind Rule 15m x1 + Context Drive long-only x1 (NQ); risk capped at a quarter of the cushion, 0.6x size once funded
  Objective C  Net Profit Compounder  six intraday sleeves at 2x (Ind Rule 15m, Open Drive, Liquidity Sweep Reclaim, Context Drive long-only on NQ; Context Drive long-only and
                                      Ind Rule 30m A on ES) + the Gate 27 US500 / Gold swing basket with the re-tuned parameters (SMA 150, vol window 40, 1.0%/day);
                                      compounding with a drawdown throttle on a rule-free account (overnight allowed)

How they were chosen, with every number: docs/T58_STRATEGY_EVALUATION_2026-11.md and the PDF next to it. Reproduce with scripts/run_objective_study.py (trades),
scripts/run_objective_scores.py (selection: train picks, validation confirms, the locked 2025-01..2026-11 test is read once), scripts/run_gate27_study.py and
scripts/run_objective_c_final.py. Only strategy files that exist in strategies/ may be used here (tests/bots/test_store_models.py checks it)."""
from __future__ import annotations

from app.bots.models import AccountLink, BotConfig, BotLeg
from app.bots.risk_governor import GovernorConfig

def _od(w: float, prio: int) -> BotLeg:
    return BotLeg("python/OpenDrive_NQ_5m_v1.py", "Open Drive", "NQ", w, prio, 45, "Opening-drive continuation, one shot a day.")


def _ir(w: float, prio: int) -> BotLeg:
    return BotLeg("python/IndRule_NQ_15m_v1.py", "Ind Rule", "NQ", w, prio, 15, "Trend rule on 15m; also trades Globex.")


def _ir30(w: float, prio: int) -> BotLeg:
    return BotLeg("python/IndRuleA_NQ_30m_v1.py", "Ind Rule 30m", "NQ", w, prio, 30, "Second timeframe of the Ind Rule: long-only, afternoon window.")


def _cad_long(w: float, prio: int) -> BotLeg:
    return BotLeg("python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long", "NQ", w, prio, 500,
                  "Drive aligned with higher-timeframe context, long side only (needs ~500 days of history to warm up).")


GATE27_TUNED = {"sma_window": 150, "vol_window": 40, "daily_vol_target_pct": 1.0, "leverage_cap": 5.0, "phase_in_days": 3}


def _gate27(w: float, prio: int, params: dict | None = None) -> list:
    note = "Monthly trend gate on US500 and Gold, volatility-sized, held overnight (rule-free accounts only)."
    return [BotLeg("builtin/Gate 27 swing basket (US500 + Gold)", "Gate 27 US500", "ES", w, prio, 400, note, kind="gate27", params=dict(params or {})),
            BotLeg("builtin/Gate 27 swing basket (US500 + Gold)", "Gate 27 Gold", "GC", w, prio, 400, note, kind="gate27", params=dict(params or {}))]


def _on(path: str, label: str, sym: str, w: float, prio: int, lookback: int, note: str) -> BotLeg:
    return BotLeg(path, label, sym, w, prio, lookback, note)


def _net_legs() -> list:
    """Objective C intraday book, in selection order (earlier legs keep a contested slot). Chosen by scripts/run_objective_scores.py on 2019-10..2023-12 and confirmed on 2024."""
    return [
        _on("python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long ES", "ES", 2.0, 0, 500, "Context Drive long-only on the S&P 500 future."),
        _on("python/IndRule_NQ_15m_v1.py", "Ind Rule", "NQ", 2.0, 1, 15, "Trend rule on 15m; also trades Globex."),
        _on("python/OpenDrive_NQ_5m_v1.py", "Open Drive", "NQ", 2.0, 2, 45, "Opening-drive continuation, one shot a day."),
        _on("python/LiquiditySweepReclaim_NQ_5m_v1.py", "Liquidity Sweep Reclaim", "NQ", 2.0, 3, 30, "Failed-breakout reversal at the prior-session and overnight levels."),
        _on("python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long", "NQ", 2.0, 4, 500, "Context Drive long-only on Nasdaq-100."),
        _on("python/IndRuleA_NQ_30m_v1.py", "Ind Rule 30m ES", "ES", 2.0, 5, 30, "Second timeframe of the Ind Rule on the S&P 500 future."),
    ]


def _acct() -> AccountLink:
    return AccountLink(venue="demo", account_id="t58-demo", size=50_000.0, broker_symbol="MNQ", preset_key="lucid_50k")


def _acct_live() -> AccountLink:
    """A sandbox account with no prop-firm rules: the net-profit bot has nothing to pass, so Gate 27's overnight holds are allowed."""
    return AccountLink(venue="paper", account_id="t58-paper", size=50_000.0, broker_symbol="MNQ", preset_key="")


def preset_configs() -> list[BotConfig]:
    gov_a = GovernorConfig(objective="A", base_risk_pct=1.0, early_mult=1.0, mid_mult=1.0, late_mult=0.7,
                           need_risk_mult=1.0, day_stop_frac=0.40)
    gov_b = GovernorConfig(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.25, day_stop_frac=0.30, funded_mult=0.6)
    gov_n = GovernorConfig(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0)
    return [
        BotConfig(id="bot-pass", name="Evaluation Passer", objective="A", preset_key="pass",
                  tagline="Objective A: pass the prop-firm evaluation, 30 days target, 60 days at most.",
                  description="Open Drive, Ind Rule at triple size and a long-only Context Drive. Full size early, trimming as the target nears; risk is "
                              "capped by the cushion above the drawdown floor and the day stops at 40% of the daily limit. The goal is to pass, not to preserve the account.",
                  legs=[_od(1.0, 0), _ir(3.0, 1), _cad_long(1.0, 2)], governor=gov_a.to_dict(), account=_acct()),
        BotConfig(id="bot-payout", name="Payout Hunter", objective="B", preset_key="payout",
                  tagline="Objective B: get paid and keep the account alive.",
                  description="Ind Rule and a long-only Context Drive at normal size. Risk is limited to a quarter of the cushion, "
                              "the day stop is tighter, and size drops to 60% once funded. Built for payouts without a breach, not speed.",
                  legs=[_ir(1.0, 0), _cad_long(1.0, 1)], governor=gov_b.to_dict(), account=_acct()),
        BotConfig(id="bot-profit", name="Net Profit Compounder", objective="NET", preset_key="profit",
                  tagline="Objective C: grow capital and maximise net wealth.",
                  description="Six intraday sleeves on Nasdaq-100 and the S&P 500 plus the Gate 27 US500 + Gold swing basket (re-tuned: 150-day trend, 40-day volatility, 1% a day). "
                              "Size follows equity (capped at $250K of sizing equity) and shrinks as drawdown deepens. Runs on a sandbox account with no prop-firm limits: "
                              "Gate 27 holds overnight, which a prop evaluation would not allow.",
                  legs=_net_legs() + _gate27(1.0, 6, GATE27_TUNED), governor=gov_n.to_dict(), account=_acct_live(),
                  max_open_positions=3, max_trades_per_day=20),
    ]
