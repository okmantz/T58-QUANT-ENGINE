# Frozen picks, 2026-11-23 (written before the holdout was opened)

BOT-A (Objective A, LucidPro 50K): legs CDL_NQ 1, CDL_ES 1, ORB15C_NQ 1, ORB15C_ES 1, IR_NQ 1, OD_NQ 0.5; max 2 open, one per instrument,
ES/NQ hedge guard, 6 trades a day. Policy: r_eval 800, f_cush 0.4, k_need 1.0, day_stop 650, fund_day_stop 550, r_fund 300,
fund_f_cush 0.3, cons_k 0.55, cons_min 300, cons_g 0.2, cons_R 2.5, dd_lvl 1600, dd_k 0.25.

BOT-B (Objective B, LucidFlex 50K primary): legs CDL_NQ 1, CDL_ES 1, ORB15C_NQ 1, ORB15C_ES 1, IR_NQ 1, VWPB_NQ 0.5, ORB30T_NQ 0.5;
same arbiter. Policy: r_eval 500, f_cush 0.4, k_need 1.0, day_stop 220, fund_day_stop 220, r_fund 150, fund_day_cap 200,
fund_f_cush 0.3, eval_day_cap 1100, dd_lvl 300, dd_k 0.25.

Known shortfalls vs the baseline before the holdout (research/final_dev.csv): see final/COMPARISON.md. The picks are not changed after
the holdout read whatever it shows. Holdout window: 2025-09-01 .. 2026-03-01 (NQ data end). Scored once by code/final_score.py hold.
The sha256 below covers this file's text above this line plus code/picks.py, policy.py, firm.py, legs.py, factory.py, book.py, score.py,
search.py, final_score.py.
sha256 d7bb01651f9ccbc3e3ac9da9ef19652080e15de5ca25ffaeb07f33eb83b97eed
