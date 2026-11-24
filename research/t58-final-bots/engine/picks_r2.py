"""Round 2 frozen pick (written before its holdout read; see research/FROZEN_PICKS_R2.md).
BOT-A is unchanged from round 1 (picks.BOT_A): no round-2 variant beat it on validation without losing P(pass)."""
import picks
BOT_A = picks.BOT_A
BOT_B = dict(plan="flex50", max_open=3, spec={"crash": 0.5},
             legs=dict(picks.BOT_B["legs"], OD_ES=0.25, PDLB_GC=1.0),
             policy=dict(picks.BOT_B["policy"], day_stop=220, fund_day_stop=220, fund_day_cap=200,
                         r_eval=300, r_fund=250, dd_lvl=400, dd_k=0.25, floor_x=3.0))
