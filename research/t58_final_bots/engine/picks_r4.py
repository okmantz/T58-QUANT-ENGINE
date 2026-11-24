"""Round 4 picks (2026-11-24), chosen on research 2020-2023 and confirmed on validation 2024-01-01 .. 2026-11-20 at 1.5x stress
cost (r4_search.py tags A1, A2, B1; research/bot_trials_r4.csv), before Owen's 2016-11-24 .. 2019-12-31 pack (H3) was opened.
BOT_A: round-3 A with barrier-aware sizing (cush_a 0.5: ease risk as the cushion over the drawdown floor shrinks; prog_b -0.3:
ease risk as profit nears the target), eval risk back to $800 a trade, consistency throttle 0.55, funded risk $300, funded day
stop $400 and funded day cap $500. No regime filter (none helped on research).
BOT_B: round-3 B with the pre-registered regime rule (Compression ORB ES trades only while its own last 10 signals average > 0R)
and Open Drive ES at 0.5 (from 0.25)."""
import copy, picks_r3
BOT_A = copy.deepcopy(picks_r3.BOT_A)
BOT_A["policy"].update(r_eval=800, cons_k=0.55, r_fund=300, fund_day_stop=400, fund_day_cap=500, cush_a=0.5, prog_b=-0.3, pace_c=0)
BOT_B = copy.deepcopy(picks_r3.BOT_B)
BOT_B["legs"]["OD_ES"] = 0.5
BOT_B["rspec"] = {"ORB15C_ES": {"eq": 10}}
