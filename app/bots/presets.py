"""The three shipped bots, one per objective (app/objectives.py ENGINE DIRECTIVE: each has its own books, sizing and risk governor; none is tuned with another's priorities).

  Objective A  Evaluation Passer      Open Drive x1 + Ind Rule 15m x3 + Context Drive long-only x1 (NQ); progress-tapering governor with pace sizing, combined day stop
                                      40% of the soft limit
  Objective B  Payout Hunter          (rev 5, 2026-11-21) LucidFlex 50K. Ind Rule 15m x2 + Open Drive x0.25 (NQ) + Open Drive x0.25 + Compression ORB x0.5 (ES);
                                      risk capped at 10% of the cushion, full size once funded, stand down once the day already counts toward the payout
                                      (five $150 days). Beat the rev-4 Payout Hunter on the sealed 2025-01..2026-02 holdout: first payout inside 30 funded
                                      days 36.5% vs 14.6% of start days, no breach before a payout (docs/T58_NEW_BOTS_2026-11-21.md)
  Objective C  Net Profit Compounder  six intraday sleeves at 2x (Ind Rule 15m, Open Drive, Liquidity Sweep Reclaim, Context Drive long-only on NQ; Context Drive long-only and
                                      Ind Rule 30m A on ES) + the Gate 27 US500 / Gold swing basket with the re-tuned parameters (SMA 150, vol window 40, 1.0%/day);
                                      compounding with a drawdown throttle on a rule-free account (overnight allowed)

How they were chosen, with every number: docs/T58_BOT_AB_COMBOS_2026-11-19.md (the 2026-11-19 Payout Hunter book and the A / B books tested with it, scored after the scorer's lookahead fix),
docs/T58_STRATEGY_EVALUATION_2026-11.md and the PDF next to it. Reproduce with scripts/run_objective_study.py (trades),
scripts/run_objective_scores.py (selection: train picks, validation confirms, the locked 2025-01..2026-11 test is read once), scripts/run_gate27_study.py and
scripts/run_objective_c_final.py. Only strategy files that exist in strategies/ may be used here (tests/bots/test_store_models.py checks it)."""
from __future__ import annotations

from app.bots.models import AccountLink, BotConfig, BotLeg
from app.bots.risk_governor import GovernorConfig

PRESET_REV = 5     # bump when a shipped bot's legs or governor change: stopped, untouched copies in the bots database are refreshed (store._seed)

def _od(w: float, prio: int) -> BotLeg:
    return BotLeg("python/OpenDrive_NQ_5m_v1.py", "Open Drive", "NQ", w, prio, 45, "Opening-drive continuation, one shot a day.")


def _ir(w: float, prio: int) -> BotLeg:
    return BotLeg("python/IndRule_NQ_15m_v1.py", "Ind Rule", "NQ", w, prio, 15, "Trend rule on 15m; also trades Globex.")


def _ir30(w: float, prio: int) -> BotLeg:
    return BotLeg("python/IndRuleA_NQ_30m_v1.py", "Ind Rule 30m", "NQ", w, prio, 30, "Second timeframe of the Ind Rule: long-only, afternoon window.")


def _od_light(w: float, prio: int) -> BotLeg:
    return BotLeg("python/OpenDrive_NQ_5m_v1.py", "Open Drive", "NQ", w, prio, 45, "Opening-drive continuation, one shot a day, at a quarter size so it adds winning days without adding risk.")


def _od_es(w: float, prio: int) -> BotLeg:
    return BotLeg("python/OpenDrive_NQ_5m_v1.py", "Open Drive ES", "ES", w, prio, 45,
                  "Opening-drive continuation on the S&P 500 future, one shot a day, at a quarter size: more ordinary winning days.")


def _cob(w: float, prio: int) -> BotLeg:
    return BotLeg("python/CompressionORB_ES_5m_v1.py", "Compression ORB", "ES", w, prio, 30,
                  "S&P 500 opening-range breakout after a quiet day; about six trades a month, at a quarter size.")


def _cad_long(w: float, prio: int) -> BotLeg:
    return BotLeg("python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long", "NQ", w, prio, 500,
                  "Drive aligned with higher-timeframe context, long side only (needs ~500 days of history to warm up).")


GATE27_TUNED = {"sma_window": 150, "vol_window": 40, "daily_vol_target_pct": 1.0, "leverage_cap": 5.0, "phase_in_days": 3}


def _cdlb_nq(w: float, prio: int) -> BotLeg:
    return BotLeg("python/ContextDriveLongBracket_NQ_1m_v1.py", "Context Drive Long Bracket", "NQ", w, prio, 500,
                  "Context Drive long-only entries, stop 0.2 x the 14-day range, target 3x the stop, at half size (needs ~500 days of history).")


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
    gov_a = GovernorConfig(objective="A", base_risk_pct=0.75, early_mult=1.3, mid_mult=1.0, late_mult=0.7,
                           need_risk_mult=1.0, day_stop_frac=0.40, cushion_risk_frac=0.75,
                           pace_max_mult=1.5, pace_min_mult=0.85)
    gov_b = GovernorConfig(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.10, day_stop_frac=0.30, funded_mult=1.0,
                           early_mult=1.0, mid_mult=1.0, late_mult=1.0, low_cushion_mult=1.0, streak_mult=None,
                           pace_max_mult=1.3, pace_min_mult=0.85, win_day_lock_mult=1.0)
    gov_n = GovernorConfig(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0,
                           streak_mult=0.7, streak_after=3, pace_max_mult=1.25)
    return [
        BotConfig(id="bot-pass", name="Evaluation Passer", objective="A", preset_key="pass",
                  tagline="Objective A: pass the prop-firm evaluation, 30 days target, 60 days at most.",
                  description="Open Drive, Ind Rule at triple size and a long-only Context Drive. Full size early, trimming as the target nears; risk is "
                              "capped by the cushion above the drawdown floor and the day stops at 40% of the daily limit. The goal is to pass, not to preserve the account.",
                  legs=[_od(1.0, 0), _ir(3.0, 1), _cad_long(1.0, 2)], governor=gov_a.to_dict(), account=_acct(), preset_rev=PRESET_REV),
        BotConfig(id="bot-payout", name="Payout Hunter", objective="B", preset_key="payout",
                  tagline="Objective B: first payout inside 30 funded days on a LucidFlex 50K account, without a breach.",
                  description="Paid under LucidFlex's rule: five days of $150 or more since the last payout, not necessarily in a row, with the cycle net "
                              "positive. Ind Rule at double size on Nasdaq-100 plus three small legs that add ordinary winning days (Open Drive on both "
                              "indices at a quarter size, Compression ORB on the S&P 500 at half size). Risk is capped at 10% of the cushion above the floor, "
                              "full size once funded, and the bot stands down for the day once the day already counts toward the payout. "
                              "Link it to the LucidFlex 50K rule set (lucid_flex_50k): on the Pro payout rule it rarely pays inside 30 days.",
                  legs=[_od_light(0.25, 0), _ir(2.0, 1), _od_es(0.25, 2), _cob(0.5, 3)], governor=gov_b.to_dict(),
                  account=AccountLink(venue="demo", account_id="t58-demo", size=50_000.0, broker_symbol="MNQ", preset_key="lucid_flex_50k"),
                  preset_rev=PRESET_REV),
        BotConfig(id="bot-profit", name="Net Profit Compounder", objective="NET", preset_key="profit",
                  tagline="Objective C: grow capital and maximise net wealth.",
                  description="Six intraday sleeves on Nasdaq-100 and the S&P 500 plus the Gate 27 US500 + Gold swing basket (re-tuned: 150-day trend, 40-day volatility, 1% a day). "
                              "Size follows equity (capped at $250K of sizing equity) and shrinks as drawdown deepens. Runs on a sandbox account with no prop-firm limits: "
                              "Gate 27 holds overnight, which a prop evaluation would not allow.",
                  legs=_net_legs() + _gate27(1.0, 6, GATE27_TUNED), governor=gov_n.to_dict(), account=_acct_live(),
                  max_open_positions=3, max_trades_per_day=20, preset_rev=PRESET_REV),
    ]


def _orbc(sym: str, w: float, prio: int) -> BotLeg:
    return BotLeg("python/ORBCompression_ESNQ_15m_v1.py", f"Compression ORB 15m {sym}", sym, w, prio, 30,
                  "Opening-range breakout on days after a compressed session (prior range < 0.7 x its 14-day mean), 2R target, flat by 16:00 ET.")


def research_configs() -> list[BotConfig]:
    """The three objective-specific research bots of 2026-11-20 (t58-three-bots, research/FROZEN_PICKS.md). They are NOT seeded as presets:
    the comparison report says which, if any, beat the shipped bots on the sealed Mar-Nov 2026 holdout. Load one with
    ``next(c for c in research_configs() if c.id == "bot-a-evaluation-passer")``."""
    gov_a = GovernorConfig(objective="A", base_risk_pct=0.6, early_mult=1.0, mid_mult=1.0, late_mult=1.0, low_cushion_mult=1.0, crit_cushion_mult=1.0,
                           need_risk_mult=1.0, day_stop_frac=1.0, cushion_risk_frac=0.9, pace_max_mult=1.4, pace_min_mult=0.85, pace_gain=3.0)
    gov_b = GovernorConfig(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.15, day_stop_frac=0.30, funded_mult=1.0, late_mult=0.6,
                           pace_max_mult=1.3, pace_min_mult=0.85, win_day_lock_mult=0.5)
    gov_n = GovernorConfig(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0,
                           streak_mult=0.7, streak_after=3, pace_max_mult=1.25)
    c_w = {"cdl_es": 0.35, "ir": 1.18, "od": 0.31, "lsr": 0.20, "cdl_nq": 0.20, "ira_es": 0.14, "orb_es": 0.64, "orb_nq": 0.32, "g27_es": 0.16, "g27_gc": 0.28}
    net = _net_legs()
    for lg, k in zip(net, ("cdl_es", "ir", "od", "lsr", "cdl_nq", "ira_es")):
        lg.weight = c_w[k]
    g27 = _gate27(1.0, 8, GATE27_TUNED)
    g27[0].weight, g27[1].weight = c_w["g27_es"], c_w["g27_gc"]
    return [
        BotConfig(id="bot-a-evaluation-passer", name="BOT_A_EVALUATION_PASSER", objective="A", preset_key="research-a",
                  tagline="Research: pass the Lucid 50K Pro evaluation inside 30 days.",
                  description="The shipped Evaluation Passer legs plus the Compression ORB 15m on Nasdaq-100 and the S&P 500 (last in priority). Flat sizing at "
                              "0.6% a trade up to 90% of the cushion, no day stop before the soft limit, a tapered last stretch to the target and up to 1.4x "
                              "when behind the 30-day clock. It beat the shipped bot on 2020-23 only, and LOST to it on the sealed 2026 holdout: keep the "
                              "Evaluation Passer for a real evaluation.",
                  legs=[_od(1.0, 0), _ir(3.0, 1), _cad_long(1.0, 2), _orbc("NQ", 1.0, 3), _orbc("ES", 1.0, 4)], governor=gov_a.to_dict(), account=_acct(),
                  preset_rev=PRESET_REV),
        BotConfig(id="bot-b-payout-hunter", name="BOT_B_PAYOUT_HUNTER", objective="B", preset_key="research-b",
                  tagline="Research: first and repeat payouts on a Lucid 50K Flex account without a breach.",
                  description="The shipped Payout Hunter legs on the LucidFlex payout rule (five $150 days). Full size once funded (no 0.6x funded cut), "
                              "risk capped at 15% of the cushion and trimmed to 0.6x once the cycle is 70% of the way to a payout. On Flex, P(first payout "
                              "inside 90 funded days) was 89 / 93 / 85% on 2020-23 / 2024 / 2025-26 vs 84 / 96 / 95% for the shipped governor: not better.",
                  legs=[_ir(1.0, 0), _cob(0.25, 1), _od_light(0.25, 2), _cdlb_nq(0.5, 3)], governor=gov_b.to_dict(),
                  account=AccountLink(venue="demo", account_id="t58-demo", size=50_000.0, broker_symbol="MNQ", preset_key="lucid_flex_50k"), preset_rev=PRESET_REV),
        BotConfig(id="bot-c-net-profit-compounder", name="BOT_C_NET_PROFIT_COMPOUNDER", objective="NET", preset_key="research-c",
                  tagline="Research: compound net wealth on an unrestricted account.",
                  description="The shipped compounder's sleeves re-weighted by shrunk inverse-covariance (half-Kelly shape) from 2020-23 daily returns, "
                              "plus the Compression ORB 15m on both indices, scaled to about 20% annual volatility (leg weight = % of equity risked per "
                              "trade; Gate 27 weight = multiple of its 1% daily volatility target). Drawdown throttle as shipped. Sandbox account only.",
                  legs=net + [_orbc("ES", c_w["orb_es"], 6), _orbc("NQ", c_w["orb_nq"], 7)] + g27, governor=gov_n.to_dict(), account=_acct_live(),
                  max_open_positions=3, max_trades_per_day=20, preset_rev=PRESET_REV),
    ]
