"""The three shipped bots. Each is the winning book for its goal from the T58 hypothesis study (docs/T58_HYPOTHESIS_REPORT.md; reproduce with
scripts/run_t58_hypotheses.py, scripts/run_t58_bot_replays.py and scripts/run_t58_engine_grid.py). Books were shortlisted in the research lab on 2019-10..2024-12
and then sized and confirmed inside the real bot engine (whole-contract sizing matters: a 0.5x leg with a 140-point stop cannot trade one micro).

  Evaluation Passer (A)       Open Drive x1 + Ind Rule 15m x3 + Context Drive long-only x1, progress-tapering governor
  Payout Hunter (B)           Ind Rule 15m x1 + Context Drive long-only x1, risk capped at a quarter of the cushion, 0.6x size once funded
  Net Profit Compounder (NET) Ind Rule 15m x1 + Context Drive long-only x1 + the Gate 27 swing basket (US500 + Gold) x1, compounding with a drawdown throttle,
                              on a sandbox account with no prop-firm rules (Gate 27 holds overnight)

Only strategy files that exist in strategies/ may be used here (tests/bots/test_store_models.py checks it)."""
from __future__ import annotations

from app.bots.models import AccountLink, BotConfig, BotLeg
from app.bots.risk_governor import GovernorConfig

def _od(w: float, prio: int) -> BotLeg:
    return BotLeg("python/NQ1! Open Drive Continuation 5m.py", "Open Drive", "NQ", w, prio, 45, "Opening-drive continuation, one shot a day.")


def _ir(w: float, prio: int) -> BotLeg:
    return BotLeg("python/NQ1! Ind Rule 15m.py", "Ind Rule", "NQ", w, prio, 15, "Trend rule on 15m; also trades Globex.")


def _ir30(w: float, prio: int) -> BotLeg:
    return BotLeg("python/NQ1! Ind Rule 30m A.py", "Ind Rule 30m", "NQ", w, prio, 30, "Second timeframe of the Ind Rule: long-only, afternoon window.")


def _cad_long(w: float, prio: int) -> BotLeg:
    return BotLeg("python/NQ1! Context Aligned Drive 1m v2 Long.py", "Context Drive Long", "NQ", w, prio, 500,
                  "Drive aligned with higher-timeframe context, long side only (needs ~500 days of history to warm up).")


def _gate27(w: float, prio: int) -> list:
    note = "Monthly trend gate on US500 and Gold, volatility-sized, held overnight (rule-free accounts only)."
    return [BotLeg("builtin/Gate 27 swing basket (US500 + Gold)", "Gate 27 US500", "ES", w, prio, 400, note, kind="gate27"),
            BotLeg("builtin/Gate 27 swing basket (US500 + Gold)", "Gate 27 Gold", "GC", w, prio, 400, note, kind="gate27")]


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
                  tagline="Pass the prop-firm evaluation fast.",
                  description="Open Drive, Ind Rule at triple size and a long-only Context Drive. Full size early, trimming as the target nears; risk is "
                              "capped by the cushion above the drawdown floor and the day stops at 40% of the daily limit.",
                  legs=[_od(1.0, 0), _ir(3.0, 1), _cad_long(1.0, 2)], governor=gov_a.to_dict(), account=_acct()),
        BotConfig(id="bot-payout", name="Payout Hunter", objective="B", preset_key="payout",
                  tagline="Get to the first payout without busting.",
                  description="Ind Rule and a long-only Context Drive at normal size. Risk is limited to a quarter of the cushion, "
                              "the day stop is tighter, and size drops to 60% once funded. Built for payouts per year, not speed.",
                  legs=[_ir(1.0, 0), _cad_long(1.0, 1)], governor=gov_b.to_dict(), account=_acct()),
        BotConfig(id="bot-profit", name="Net Profit Compounder", objective="NET", preset_key="profit",
                  tagline="Maximise net profit per unit of drawdown.",
                  description="Ind Rule and a long-only Context Drive for the day, plus the Gate 27 US500 + Gold swing basket. "
                              "Size follows equity and shrinks as drawdown deepens. Runs on a sandbox account with no prop-firm limits: "
                              "Gate 27 holds overnight, which a prop evaluation would not allow.",
                  legs=[_ir(1.0, 0), _cad_long(1.0, 1)] + _gate27(1.0, 2), governor=gov_n.to_dict(), account=_acct_live()),
    ]
