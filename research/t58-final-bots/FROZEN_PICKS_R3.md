# Round 3 frozen picks, 2026-11-24 (written before the new holdout read)

Data change: Owen's Mar 1 .. Nov 24 2026 files (ES, NQ, GC, MES/MNQ/MGC) are the fresh, never-read round-3 holdout (sessions
2026-03-02 .. 2026-11-20; logged in .notes/inputs.md and research/data_h2_info.json). The old holdout window 2025-09-01 ..
2026-03-01 is folded into validation, which now runs 2024-01-01 .. 2026-03-01. Research is unchanged. No round-3 choice looked
at any bar on or after 2026-03-02 (book.points drops those days unless the seal below exists).

BOT-A round 3 (Objective A, LucidPro 50K): round-1 legs (CDL_NQ 1, CDL_ES 1, ORB15C_NQ 1, ORB15C_ES 1, IR_NQ 1, OD_NQ 0.5) plus
PDLB_GC 0.5; max 2 open; round-1 policy with r_eval 1000 and dd_lvl 1200. Code: code/picks_r3.py.
Why: of 784 A variants scored on the extended validation, this is the one with the fewest stress-cost shortfall cells
(4 vs 10 for the round-1 pick), with P(pass) at validation stress 0.39 vs baseline 0.25 and median 13 days to pass. The spec
ranks stress cost first. Known dev shortfalls (13 cells over research/validation x base/stress): profit factor, sharpe, sortino,
expectancy R, median days to payout and consistency blocks in some cells; validation stress misses only expectancy R.

BOT-B round 3 (Objective B, LucidFlex 50K): round-2 legs plus OD_NQ 0.25, CORB_ES 0.5, GAP_GC 0.5; max 4 open; crash filter 0.5
kept but one_per_inst off; round-2 policy with fund_day_cap 200, floor_x 3.0, day_stop 300, fund_day_stop 300. Code: picks_r3.py.
Why: beats or ties baseline B on every metric in both validation cells (base and stress), including trades per month
(17.0 vs 15.2 at stress) and P(first payout) 0.47 vs 0.12 at stress. Known dev shortfalls: research base pf, worst day and
max drawdown; research stress trades per month (12.7 vs 18.1).

Repo-format ports (repo_zip/strategies/python/*_t58.py, code/port_legs.py, checked by code/verify_ports.py): the six new leg files
match their research legs on 98-100% of trades (research/port_check.csv). Disclosure: the research leg factory's day filter
("at least 80% of RTH bars over the whole day") uses the whole day, a mild lookahead; the ports use a causal version (80% of bars
from 09:30 to the signal bar), which keeps some extra trades the factory dropped (for PDLB_GC, 61 extra trades, mean -0.10R).
Bot scores with ports are slightly worse (research/port_bots_check.csv; B validation stress P(payout) 0.46).

Pre-registered holdout read: one run of `T58_R3=1 python3 code/final_score_r3.py hold`, written to research/final_hold_r3.csv.
Roster: baseline A and B (repo PRESET_REV 5), BOT-A-R1, BOT-B-R1, BOT-B-R2, BOT-A-R3, BOT-B-R3, each on pro50 and flex50, plus
BOT-A-R3-port on pro50 and BOT-B-R3-port on flex50; base and stress cost. Headline: R3 picks on factory legs at stress cost,
each on its own plan, against the baseline on the same plan; port rows shown alongside as the repo-deployable numbers.
The pass rule is unchanged: a finalist must beat (or tie) baseline on every Phase 0 metric. No pick, cost, filter or rule changes
after this read; whatever it shows is reported as is.
The sha256 below covers this file's text above this line plus code/picks.py, picks_r2.py, picks_r3.py, policy.py, filters.py,
firm.py, legs.py, factory.py, book.py, score.py, search.py, data.py, baseline.py, final_score.py, final_score_r2.py,
final_score_r3.py, port_legs.py and the six repo_zip/strategies/python/*_t58.py files.
sha256 2f47820098ed85bd75e98454e4795730bc1bb4a3cb1f6f7f7a0fbd0918c7ed09
