"""T58 final bots (research, round 4, 2026-11-24): BOT-A for passing a LucidPro 50K evaluation, BOT-B for LucidFlex 50K payouts.

Not seeded as presets: load with ``next(c for c in t58_final_configs() if c.id == 'bot-t58-final-a')``.
Every number in docs/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md comes from the research engine in research/t58_final_bots/engine
(firm simulator + the sizing policy in T58_POLICY below). The GovernorConfig here is the closest setting of the repo's own
governor; it has NOT been validated and will not reproduce those numbers exactly. Use the research engine's policy for that.
"""
from __future__ import annotations

from app.bots.models import AccountLink, BotConfig, BotLeg
from app.bots.risk_governor import GovernorConfig

T58_PICKS = {
 "A": {
  "plan": "pro50",
  "max_open": 2,
  "spec": None,
  "legs": {
   "CDL_NQ": 1,
   "CDL_ES": 1,
   "ORB15C_NQ": 1,
   "ORB15C_ES": 1,
   "IR_NQ": 1,
   "OD_NQ": 0.5,
   "PDLB_GC": 0.5
  },
  "policy": {
   "r_eval": 800,
   "f_cush": 0.4,
   "k_need": 1.0,
   "day_stop": 650,
   "fund_day_stop": 400,
   "r_fund": 300,
   "fund_day_cap": 500,
   "fund_f_cush": 0.3,
   "cons_k": 0.55,
   "cons_min": 300,
   "cons_g": 0.2,
   "cons_R": 2.5,
   "dd_lvl": 1200,
   "dd_k": 0.25,
   "cush_a": 0.5,
   "prog_b": -0.3,
   "pace_c": 0
  }
 },
 "B": {
  "plan": "flex50",
  "max_open": 4,
  "spec": {
   "crash": 0.5,
   "one_per_inst": False
  },
  "legs": {
   "CDL_NQ": 1,
   "CDL_ES": 1,
   "ORB15C_NQ": 1,
   "ORB15C_ES": 1,
   "IR_NQ": 1,
   "VWPB_NQ": 0.5,
   "ORB30T_NQ": 0.5,
   "OD_ES": 0.5,
   "PDLB_GC": 1.0,
   "OD_NQ": 0.25,
   "CORB_ES": 0.5,
   "GAP_GC": 0.5
  },
  "policy": {
   "r_eval": 300,
   "f_cush": 0.4,
   "k_need": 1.0,
   "day_stop": 300,
   "fund_day_stop": 300,
   "r_fund": 250,
   "fund_day_cap": 200,
   "fund_f_cush": 0.3,
   "eval_day_cap": 1100,
   "dd_lvl": 400,
   "dd_k": 0.25,
   "floor_x": 3.0
  },
  "rspec": {
   "ORB15C_ES": {
    "eq": 10
   }
  }
 }
}
T58_POLICY = {k: v['policy'] for k, v in T58_PICKS.items()}   # exact sizing used in research (research/t58_final_bots/engine/policy.py)
T58_FILTERS = {k: v.get('spec') for k, v in T58_PICKS.items()}   # crash: size x0.5 when the 504-day return < 0 and 126-day vol > its median
T58_REGIME = {k: v.get('rspec') for k, v in T58_PICKS.items()}   # per-leg causal regime filter (engine/regime.py); eq N: the leg's last N closed signals average > 0R
LEG_FILES = {
 "CDL_NQ": [
  "python/ContextDriveLong_NQ_1m_v2.py",
  "Context Drive Long",
  "NQ",
  500,
  "Repo strategy, unchanged."
 ],
 "CDL_ES": [
  "python/ContextDriveLong_NQ_1m_v2.py",
  "Context Drive Long ES",
  "ES",
  500,
  "Repo strategy, unchanged, on ES."
 ],
 "IR_NQ": [
  "python/IndRule_NQ_15m_v1.py",
  "Ind Rule",
  "NQ",
  15,
  "Repo strategy, unchanged."
 ],
 "OD_NQ": [
  "python/OpenDrive_NQ_5m_v1.py",
  "Open Drive",
  "NQ",
  45,
  "Repo strategy, unchanged."
 ],
 "OD_ES": [
  "python/OpenDrive_NQ_5m_v1.py",
  "Open Drive ES",
  "ES",
  45,
  "Repo strategy, unchanged, on ES."
 ],
 "CORB_ES": [
  "python/CompressionORB_ES_5m_v1.py",
  "Compression ORB",
  "ES",
  30,
  "Repo strategy, unchanged."
 ],
 "CDLB_NQ": [
  "python/ContextDriveLongBracket_NQ_1m_v1.py",
  "Context Drive Long Bracket",
  "NQ",
  500,
  "Repo strategy, unchanged."
 ],
 "ORB15C_NQ": [
  "python/ORB15Compression_NQ_1m_t58.py",
  "ORB15 compression NQ",
  "NQ",
  30,
  "New (T58 final bots): 15m ORB after a compressed day, 3R."
 ],
 "ORB15C_ES": [
  "python/ORB15Compression_ES_1m_t58.py",
  "ORB15 compression ES",
  "ES",
  30,
  "New (T58 final bots): 15m ORB after a compressed day, 2R."
 ],
 "ORB30T_NQ": [
  "python/ORB30Trend_NQ_1m_t58.py",
  "ORB30 with trend NQ",
  "NQ",
  45,
  "New (T58 final bots): 30m ORB with the 20-day trend, 3R."
 ],
 "VWPB_NQ": [
  "python/VWAPPullback_NQ_1m_t58.py",
  "VWAP pullback NQ",
  "NQ",
  45,
  "New (T58 final bots): VWAP pullback in the daily trend, 2R."
 ],
 "GAP_GC": [
  "python/GapTrend_GC_1m_t58.py",
  "Gap with trend GC",
  "GC",
  45,
  "New (T58 final bots): opening gap with the 20-day trend, 3R."
 ],
 "PDLB_GC": [
  "python/PriorDayBreak_GC_1m_t58.py",
  "Prior-day break GC",
  "GC",
  200,
  "New (T58 final bots): prior-day break in a quiet regime, 3R."
 ]
}


def _legs(obj: str) -> list:
    out = []
    for prio, (k, w) in enumerate(T58_PICKS[obj]['legs'].items()):
        if w <= 0:
            continue
        path, label, sym, look, note = LEG_FILES[k]
        out.append(BotLeg(path, label, sym, float(w), prio, int(look), note))
    return out


def t58_final_configs() -> list[BotConfig]:
    pa, pb = T58_POLICY['A'], T58_POLICY['B']
    gov_a = GovernorConfig(objective='A', base_risk_pct=100.0 * pa['r_eval'] / 50_000, cushion_risk_frac=pa['f_cush'],
                           need_risk_mult=pa.get('k_need'), early_mult=1.0, mid_mult=1.0, late_mult=1.0, low_cushion_mult=1.0, crit_cushion_mult=1.0)
    gov_b = GovernorConfig(objective='B', base_risk_pct=100.0 * pb['r_eval'] / 50_000, cushion_risk_frac=pb['f_cush'], funded_mult=pb['r_fund'] / pb['r_eval'],
                           early_mult=1.0, mid_mult=1.0, late_mult=1.0, low_cushion_mult=1.0, win_day_lock_mult=(pb.get('fund_day_cap') or 0) / 150.0 or None)
    return [
        BotConfig(id='bot-t58-final-a', name='T58_FINAL_BOT_A', objective='A', preset_key='t58-final-a',
                  tagline='Research: pass the Lucid 50K Pro evaluation (T58 final bots, 2026-11-24).',
                  description='See docs/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md. Sizing: T58_POLICY["A"] (research engine); governor here is an unvalidated approximation.',
                  legs=_legs('A'), governor=gov_a.to_dict(), max_open_positions=int(T58_PICKS['A']['max_open']), max_trades_per_day=6,
                  account=AccountLink(venue='demo', account_id='t58-demo', size=50_000.0, broker_symbol='MNQ', preset_key='lucid_50k')),
        BotConfig(id='bot-t58-final-b', name='T58_FINAL_BOT_B', objective='B', preset_key='t58-final-b',
                  tagline='Research: first and repeat payouts on a LucidFlex 50K account (T58 final bots, 2026-11-24).',
                  description='See docs/T58_FINAL_BOTS_PERFORMANCE_2026-11-24.md. Sizing: T58_POLICY["B"] and T58_FILTERS["B"] (research engine); governor here is an unvalidated approximation.',
                  legs=_legs('B'), governor=gov_b.to_dict(), max_open_positions=int(T58_PICKS['B']['max_open']), max_trades_per_day=6,
                  account=AccountLink(venue='demo', account_id='t58-demo', size=50_000.0, broker_symbol='MNQ', preset_key='lucid_flex_50k')),
    ]
