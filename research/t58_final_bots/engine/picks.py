"""The two frozen picks (written before the holdout was opened; see research/FROZEN_PICKS.md)."""
BOT_A = dict(plan="pro50", max_open=2,
             legs={"CDL_NQ": 1, "CDL_ES": 1, "ORB15C_NQ": 1, "ORB15C_ES": 1, "IR_NQ": 1, "OD_NQ": 0.5},
             policy=dict(r_eval=800, f_cush=0.4, k_need=1.0, day_stop=650, fund_day_stop=550, r_fund=300, fund_day_cap=None,
                         fund_f_cush=0.3, cons_k=0.55, cons_min=300, cons_g=0.2, cons_R=2.5, dd_lvl=1600, dd_k=0.25))
BOT_B = dict(plan="flex50", max_open=2,
             legs={"CDL_NQ": 1, "CDL_ES": 1, "ORB15C_NQ": 1, "ORB15C_ES": 1, "IR_NQ": 1, "VWPB_NQ": 0.5, "ORB30T_NQ": 0.5},
             policy=dict(r_eval=500, f_cush=0.4, k_need=1.0, day_stop=220, fund_day_stop=220, r_fund=150, fund_day_cap=200,
                         fund_f_cush=0.3, eval_day_cap=1100, dd_lvl=300, dd_k=0.25))
