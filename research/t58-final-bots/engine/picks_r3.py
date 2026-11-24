"""Round 3 picks (2026-11-24), chosen on research 2020-2023 + extended validation 2024-01..2026-03 at 1.5x stress cost (run_r3.py,
research/bot_trials_r3.csv), before Owen's Mar..Nov 2026 holdout (H2) was opened. Plateau: the neighbouring settings score the same.
BOT_A: round-1 A + PDLB_GC at half weight, eval risk $1,000 a trade (from $800), drawdown throttle from $1,600 to $1,200.
BOT_B: round-2 B + Open Drive NQ x0.25, Compression ORB ES x0.5, GC gap-with-trend x0.5; up to 4 open positions, two legs may share an
instrument; day stop $300 (from $220)."""
import picks, picks_r2
BOT_A = dict(plan="pro50", max_open=2, spec=None, legs=dict(picks.BOT_A["legs"], PDLB_GC=0.5),
             policy=dict(picks.BOT_A["policy"], r_eval=1000, dd_lvl=1200))
BOT_B = dict(plan="flex50", max_open=4, spec=dict(picks_r2.BOT_B["spec"], one_per_inst=False),
             legs=dict(picks_r2.BOT_B["legs"], OD_NQ=0.25, CORB_ES=0.5, GAP_GC=0.5),
             policy=dict(picks_r2.BOT_B["policy"], fund_day_cap=200, floor_x=3.0, day_stop=300, fund_day_stop=300))
