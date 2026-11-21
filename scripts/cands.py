import sim  # sets up the repo import path
from app.bots.risk_governor import GovernorConfig
from app.bots.presets import preset_configs
cf = {c.preset_key: c for c in preset_configs()}
GA = cf["pass"].governor
# rev-4 (shipped before 2026-11-21) Payout Hunter governor, pinned so the comparison survives the preset change
GB = dict(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.25, day_stop_frac=0.30, funded_mult=0.6, pace_max_mult=1.3, pace_min_mult=0.85, win_day_lock_mult=0.5)
def _b(g): return dict(g) if isinstance(g, dict) else (g.to_dict() if hasattr(g, 'to_dict') else dict(g.__dict__))
def gA(d): return GovernorConfig.from_dict({**_b(GA), **d})
def gB(d): return GovernorConfig.from_dict({**_b(GB), **d})
A_SHIP = dict(legs=[("OD_NQ", 1.0), ("IR_NQ", 3.0), ("CDL_NQ", 1.0)], gov={}, kind="A")
A_NEW = dict(legs=[("IR_NQ", 2.0), ("CDL_ES", 0.5), ("IRB_NQ", 1.0), ("OD_ES", 0.5)], kind="A",
             gov={'base_risk_pct': 0.9, 'cushion_risk_frac': 0.75, 'need_risk_mult': 0.75, 'day_stop_frac': 0.8, 'pace_max_mult': 1.5, 'pace_gain': 3.0,
                  'early_mult': 1.3, 'mid_mult': 1.0, 'late_mult': 1.0, 'day_profit_lock_frac': 0.3, 'low_cushion_mult': 0.5, 'crit_cushion_mult': 0.25, 'streak_mult': None})
B_SHIP = dict(legs=[("IR_NQ", 1.0), ("COB_ES", 0.25), ("OD_NQ", 0.25), ("CDLB_NQ", 0.5)], gov={}, kind="B")
B_NEW = dict(legs=[("OD_NQ", 0.25), ("IR_NQ", 2.0), ("OD_ES", 0.25), ("COB_ES", 0.5)], kind="B",
             gov={'cushion_risk_frac': 0.1, 'win_day_lock_mult': 1.0, 'day_stop_frac': 0.3, 'base_risk_pct': 1.0, 'funded_mult': 1.0,
                  'early_mult': 1.0, 'mid_mult': 1.0, 'late_mult': 1.0, 'streak_mult': None, 'low_cushion_mult': 1.0})
B_NEW2 = dict(legs=[("OD_ES", 0.25), ("COB_ES", 2.0), ("CDL_ES", 1.0), ("CDLB_NQ", 1.0), ("OD_NQ", 2.0), ("TM_NQ", 0.5), ("IRB_NQ", 0.5)], kind="B",
              gov={'cushion_risk_frac': 0.1, 'win_day_lock_mult': 1.0, 'day_stop_frac': 0.6, 'base_risk_pct': 0.75, 'funded_mult': 1.0,
                   'early_mult': 1.0, 'mid_mult': 1.0, 'late_mult': 1.0, 'streak_mult': None, 'low_cushion_mult': 1.0})
def gov(c): return (gA if c["kind"] == "A" else gB)(c["gov"])
