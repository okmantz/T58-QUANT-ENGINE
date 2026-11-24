# Round 2 frozen pick, 2026-11-24 (written before its holdout read)

BOT-A: unchanged from round 1 (research/FROZEN_PICKS.md). Round 2 tried the paper filters (trend, crash, VVG, ATR expansion,
vol sizing), a capped one-micro minimum (floor_x), a tighter drawdown throttle (dd_lvl 1200), extra legs (VWPB_NQ, OD_ES, PDLB_GC),
rebuilt leg sets and funded-only leg sets. The best variant (c11a cfg 4, dd_lvl 1200) cuts dev shortfall cells from 13 to 12 but
lowers P(pass) in all four dev cells, which is A's own objective, so it is not a better pick. No new holdout read for A.

BOT-B round 2 (Objective B, LucidFlex 50K): legs CDL_NQ 1, CDL_ES 1, ORB15C_NQ 1, ORB15C_ES 1, IR_NQ 1, VWPB_NQ 0.5, ORB30T_NQ 0.5,
OD_ES 0.25, PDLB_GC 1.0; max 3 open, one per instrument, ES/NQ hedge guard, 6 trades a day. Crash filter: every leg's weight x 0.5
when the instrument's 504-session return < 0 and 126-session vol > its expanding median. Policy: round-1 B with r_eval 300,
r_fund 250, day_stop 220, fund_day_stop 220, fund_day_cap 200, dd_lvl 400, dd_k 0.25, floor_x 3.0 (the one-micro minimum only
applies while one micro risks <= 3x the budget). Code: code/picks_r2.py, built by code/filters.bot.

Dev result (research/final_dev_r2.csv): beats or ties baseline B on every metric in research and validation, base and stress,
except trades per month (6.3-13.2 vs 8.7-18.1). Known shortfall before the holdout: trade count.

Holdout disclosure: the holdout window 2025-09-01 .. 2026-03-01 was already read once in round 1 (for the round-1 picks). This is
its second read, for a new finalist. Round 2 never tuned on it, but the round-1 holdout numbers were seen before round 2 started,
so it is no longer a perfectly untouched sample. Scored once by code/final_score_r2.py hold; the pick is not changed afterwards.
The sha256 below covers this file's text above this line plus code/picks.py, picks_r2.py, policy.py, filters.py, firm.py, legs.py,
factory.py, book.py, score.py, search.py, final_score.py, final_score_r2.py.
sha256 3092f259a4e00a7fbdffa175b372e59c31bad380b22bf51605abfef5d0f3b1bc
