"""The three shipped bots, one per objective (app/objectives.py ENGINE DIRECTIVE: each has its own book, sizing and risk governor).

  Objective A  Evaluation Passer      T58 final bot A, round 6 (2026-11-25, pick A59): pass a Lucid Pro 50K evaluation. Seven legs on NQ / ES / GC (Context Drive Long,
                                      ORB15 compression, Ind Rule, Open Drive, Prior-day break), risk $920 a trade at full size. docs/T58_FINAL_BOTS_ROUND6_2026-11-25.md
  Objective B  Payout Hunter          T58 final bot B (round-4 pick, confirmed best again in rounds 5 and 6): first and repeat payouts on a LucidFlex 50K account.
                                      Twelve legs on NQ / ES / GC, small fixed risk. docs/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md
  Objective C  Net Profit Compounder  BOT_C (2026-11-20): six intraday sleeves + Gate 27 on a rule-free account, Kelly-shaped weights, drawdown throttle.
                                      docs/T58_THREE_BOTS_2026-11-20.md (the only 2026-11-20 pick that beat its predecessor on the sealed holdout)

Every sizing number and entry filter of A and B is kept in ``T58_PICKS`` exactly as the research engine froze it (research/t58_final_bots/BOT-A|B/params.json).
The GovernorConfig built from them here is the closest setting of the repo's own governor; it has NOT been validated and will not reproduce the research
numbers exactly, and the live runtime applies neither ``T58_ENTRY_FILTERS`` (A) nor the crash / regime filters (B). Use research/t58_final_bots/run_bot.py for the
exact policy. Only strategy files that exist in strategies/ may be used here (tests/bots/test_presets.py checks it)."""
from __future__ import annotations

from app.bots.models import AccountLink, BotConfig, BotLeg
from app.bots.risk_governor import GovernorConfig

PRESET_REV = 6     # bump when a shipped bot's legs or governor change: stopped, untouched copies in the bots database are refreshed (store._seed)

# ---------------------------------------------------------------------------------------------------- objectives A and B (T58 final bots)
T58_PICKS = {
  "A": {
    "plan": "pro50",
    "max_open": 2,
    "spec": None,
    "legs": {"CDL_NQ": 1, "CDL_ES": 1, "ORB15C_NQ": 1, "ORB15C_ES": 1, "IR_NQ": 1, "OD_NQ": 0.5, "PDLB_GC": 0.5},
    "policy": {"r_eval": 919.9999999999999, "f_cush": 0.4, "k_need": 1.0, "day_stop": 650, "fund_day_stop": 400, "r_fund": 300, "fund_day_cap": 500, "fund_f_cush": 0.3, "cons_k": 0.55, "cons_min": 300, "cons_g": 0.2, "cons_R": 2.5, "dd_lvl": 1200, "dd_k": 0.25, "cush_a": 0.5, "prog_b": -0.3, "pace_c": 0},
    "fspec": {"CDL_NQ": [["vix_chg5", "skip_low", 0.9581]], "CDL_ES": [["vix_term", "skip_low", 0.8354]], "ORB15C_NQ": [["tick_dir", "skip_low", -113.0]], "ORB15C_ES": [["va_dir", "skip_with", 1.0]], "OD_NQ": [["gap_abs", "skip_low", 0.1944]]},
    "rm": 1.15,
    "cid": "A59",
    "k100": 1.75,
  },
  "B": {
    "plan": "flex50",
    "max_open": 4,
    "spec": {"crash": 0.5, "one_per_inst": False},
    "legs": {"CDL_NQ": 1, "CDL_ES": 1, "ORB15C_NQ": 1, "ORB15C_ES": 1, "IR_NQ": 1, "VWPB_NQ": 0.5, "ORB30T_NQ": 0.5, "OD_ES": 0.5, "PDLB_GC": 1.0, "OD_NQ": 0.25, "CORB_ES": 0.5, "GAP_GC": 0.5},
    "policy": {"r_eval": 300, "f_cush": 0.4, "k_need": 1.0, "day_stop": 300, "fund_day_stop": 300, "r_fund": 250, "fund_day_cap": 200, "fund_f_cush": 0.3, "eval_day_cap": 1100, "dd_lvl": 400, "dd_k": 0.25, "floor_x": 3.0},
    "rspec": {"ORB15C_ES": {"eq": 10}},
  },
}
T58_POLICY = {k: v["policy"] for k, v in T58_PICKS.items()}                 # exact sizing used in research (research/t58_final_bots/engine/policy.py)
T58_FILTERS = {k: v.get("spec") for k, v in T58_PICKS.items()}              # crash: size x0.5 when the 504-day return < 0 and 126-day vol > its median
T58_REGIME = {k: v.get("rspec") for k, v in T58_PICKS.items()}              # per-leg causal regime filter; eq N: the leg's last N closed signals average > 0R
T58_ENTRY_FILTERS = {k: v.get("fspec") for k, v in T58_PICKS.items()}       # (input, side, threshold) per leg: skip_low = skip when input <= threshold

# leg key -> (strategy file, label, symbol, warm-up days, note)
LEG_FILES = {
    "CDL_NQ": ["python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long", "NQ", 500, "Drive aligned with higher-timeframe context, long side only."],
    "CDL_ES": ["python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long ES", "ES", 500, "The same strategy on the S&P 500 future."],
    "IR_NQ": ["python/IndRule_NQ_15m_v1.py", "Ind Rule", "NQ", 15, "Trend rule on 15m; also trades Globex."],
    "OD_NQ": ["python/OpenDrive_NQ_5m_v1.py", "Open Drive", "NQ", 45, "Opening-drive continuation, one shot a day."],
    "OD_ES": ["python/OpenDrive_NQ_5m_v1.py", "Open Drive ES", "ES", 45, "Opening-drive continuation on the S&P 500 future."],
    "CORB_ES": ["python/CompressionORB_ES_5m_v1.py", "Compression ORB", "ES", 30, "S&P 500 opening-range breakout after a quiet day."],
    "ORB15C_NQ": ["python/ORB15Compression_NQ_1m_v1.py", "ORB15 compression NQ", "NQ", 30, "15m ORB after a compressed day, 3R."],
    "ORB15C_ES": ["python/ORB15Compression_ES_1m_v1.py", "ORB15 compression ES", "ES", 30, "15m ORB after a compressed day, 2R."],
    "ORB30T_NQ": ["python/ORB30Trend_NQ_1m_v1.py", "ORB30 with trend NQ", "NQ", 45, "30m ORB with the 20-day trend, 3R."],
    "VWPB_NQ": ["python/VWAPPullback_NQ_1m_v1.py", "VWAP pullback NQ", "NQ", 45, "VWAP pullback in the daily trend, 2R."],
    "GAP_GC": ["python/GapTrend_GC_1m_v1.py", "Gap with trend GC", "GC", 45, "Opening gap with the 20-day trend, 3R."],
    "PDLB_GC": ["python/PriorDayBreak_GC_1m_v1.py", "Prior-day break GC", "GC", 200, "Prior-day break in a quiet regime, 3R."],
}


def _legs(obj: str) -> list:
    out = []
    for prio, (k, w) in enumerate(T58_PICKS[obj]["legs"].items()):
        if w <= 0:
            continue
        path, label, sym, look, note = LEG_FILES[k]
        out.append(BotLeg(path, label, sym, float(w), prio, int(look), note))
    return out


# ---------------------------------------------------------------------------------------------------- objective C (BOT_C)
GATE27_TUNED = {"sma_window": 150, "vol_window": 40, "daily_vol_target_pct": 1.0, "leverage_cap": 5.0, "phase_in_days": 3}


def _on(path: str, label: str, sym: str, w: float, prio: int, lookback: int, note: str) -> BotLeg:
    return BotLeg(path, label, sym, w, prio, lookback, note)


def _orbc(sym: str, w: float, prio: int) -> BotLeg:
    return BotLeg("python/ORBCompression_ESNQ_15m_v1.py", f"Compression ORB 15m {sym}", sym, w, prio, 30,
                  "Opening-range breakout on days after a compressed session (prior range < 0.7 x its 14-day mean), 2R target, flat by 16:00 ET.")


def _gate27(w: float, prio: int, params: dict | None = None) -> list:
    note = "Monthly trend gate on US500 and Gold, volatility-sized, held overnight (rule-free accounts only)."
    return [BotLeg("builtin/Gate 27 swing basket (US500 + Gold)", "Gate 27 US500", "ES", w, prio, 400, note, kind="gate27", params=dict(params or {})),
            BotLeg("builtin/Gate 27 swing basket (US500 + Gold)", "Gate 27 Gold", "GC", w, prio, 400, note, kind="gate27", params=dict(params or {}))]


def _net_legs() -> list:
    """Objective C intraday book in selection order (earlier legs keep a contested slot), re-weighted by shrunk inverse covariance (half-Kelly shape)
    and scaled to about 20% annual volatility: a leg's weight is the % of equity risked per trade; a Gate 27 weight is a multiple of its 1% daily volatility target."""
    return [
        _on("python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long ES", "ES", 0.35, 0, 500, "Context Drive long-only on the S&P 500 future."),
        _on("python/IndRule_NQ_15m_v1.py", "Ind Rule", "NQ", 1.18, 1, 15, "Trend rule on 15m; also trades Globex."),
        _on("python/OpenDrive_NQ_5m_v1.py", "Open Drive", "NQ", 0.31, 2, 45, "Opening-drive continuation, one shot a day."),
        _on("python/LiquiditySweepReclaim_NQ_5m_v1.py", "Liquidity Sweep Reclaim", "NQ", 0.20, 3, 30, "Failed-breakout reversal at the prior-session and overnight levels."),
        _on("python/ContextDriveLong_NQ_1m_v2.py", "Context Drive Long", "NQ", 0.20, 4, 500, "Context Drive long-only on Nasdaq-100."),
        _on("python/IndRuleA_NQ_30m_v1.py", "Ind Rule 30m ES", "ES", 0.14, 5, 30, "Second timeframe of the Ind Rule on the S&P 500 future."),
    ]


def _acct_live() -> AccountLink:
    """A sandbox account with no prop-firm rules: the net-profit bot has nothing to pass, so Gate 27's overnight holds are allowed."""
    return AccountLink(venue="paper", account_id="t58-paper", size=50_000.0, broker_symbol="MNQ", preset_key="")


def preset_configs() -> list[BotConfig]:
    pa, pb = T58_POLICY["A"], T58_POLICY["B"]
    gov_a = GovernorConfig(objective="A", base_risk_pct=100.0 * pa["r_eval"] / 50_000, cushion_risk_frac=pa["f_cush"], need_risk_mult=pa.get("k_need"),
                           early_mult=1.0, mid_mult=1.0, late_mult=1.0, low_cushion_mult=1.0, crit_cushion_mult=1.0)
    gov_b = GovernorConfig(objective="B", base_risk_pct=100.0 * pb["r_eval"] / 50_000, cushion_risk_frac=pb["f_cush"], funded_mult=pb["r_fund"] / pb["r_eval"],
                           early_mult=1.0, mid_mult=1.0, late_mult=1.0, low_cushion_mult=1.0, win_day_lock_mult=(pb.get("fund_day_cap") or 0) / 150.0 or None)
    gov_n = GovernorConfig(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0,
                           streak_mult=0.7, streak_after=3, pace_max_mult=1.25)
    g27 = _gate27(1.0, 8, GATE27_TUNED)
    g27[0].weight, g27[1].weight = 0.16, 0.28
    return [
        BotConfig(id="bot-pass", name="Evaluation Passer", objective="A", preset_key="pass",
                  tagline="Objective A: pass the Lucid 50K Pro evaluation (T58 final bot A, round 6, 2026-11-25).",
                  description="Seven legs on Nasdaq-100, the S&P 500 and Gold (Context Drive Long, 15m opening-range breakouts after a compressed day, Ind Rule, "
                              "Open Drive, prior-day Gold break). Full size at $920 a trade, capped at 40% of the cushion above the drawdown floor. "
                              "See docs/T58_FINAL_BOTS_ROUND6_2026-11-25.md. The research sizing policy and the five prior-day entry filters live in "
                              "app/bots/presets.py (T58_POLICY, T58_ENTRY_FILTERS); this runtime applies neither, so its results will differ from the research numbers.",
                  legs=_legs("A"), governor=gov_a.to_dict(), max_open_positions=int(T58_PICKS["A"]["max_open"]), max_trades_per_day=6,
                  account=AccountLink(venue="demo", account_id="t58-demo", size=50_000.0, broker_symbol="MNQ", preset_key="lucid_50k"), preset_rev=PRESET_REV),
        BotConfig(id="bot-payout", name="Payout Hunter", objective="B", preset_key="payout",
                  tagline="Objective B: first and repeat payouts on a LucidFlex 50K account without a breach (T58 final bot B).",
                  description="Twelve legs on Nasdaq-100, the S&P 500 and Gold at small fixed risk ($300 in the evaluation, $250 funded), capped at 40% of the cushion. "
                              "Paid under LucidFlex's rule: five days of $150 or more since the last payout, with the cycle net positive. Link it to the "
                              "LucidFlex 50K rule set (lucid_flex_50k): on the Pro payout rule it rarely pays inside 30 days. "
                              "See docs/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md. The crash and regime filters live in app/bots/presets.py (T58_FILTERS, T58_REGIME) "
                              "and are not applied by this runtime.",
                  legs=_legs("B"), governor=gov_b.to_dict(), max_open_positions=int(T58_PICKS["B"]["max_open"]), max_trades_per_day=6,
                  account=AccountLink(venue="demo", account_id="t58-demo", size=50_000.0, broker_symbol="MNQ", preset_key="lucid_flex_50k"), preset_rev=PRESET_REV),
        BotConfig(id="bot-profit", name="Net Profit Compounder", objective="NET", preset_key="profit",
                  tagline="Objective C: grow capital and maximise net wealth.",
                  description="Six intraday sleeves on Nasdaq-100 and the S&P 500 weighted by shrunk inverse covariance (half-Kelly shape), plus the 15m Compression ORB on "
                              "both indices and the Gate 27 US500 + Gold swing basket (150-day trend, 40-day volatility, 1% a day), scaled to about 20% annual volatility. "
                              "Size follows equity and shrinks as drawdown deepens. Runs on a sandbox account with no prop-firm limits: Gate 27 holds overnight, "
                              "which a prop evaluation would not allow. See docs/T58_THREE_BOTS_2026-11-20.md.",
                  legs=_net_legs() + [_orbc("ES", 0.64, 6), _orbc("NQ", 0.32, 7)] + g27, governor=gov_n.to_dict(), account=_acct_live(),
                  max_open_positions=3, max_trades_per_day=20, preset_rev=PRESET_REV),
    ]
