# Round 4 frozen picks, 2026-11-24 (written before the 2016-2019 holdout read)

Bar and data: research/PREREG_R4.md (written before any round-4 score). Research 2020-01-01 .. 2023-12-31, validation 2024-01-01 ..
2026-11-20 (includes Mar-Nov 2026, read once as the round-3 holdout, now ordinary validation). Holdout H3 = Owen's 2016-11-24 ..
2019-12-31 pack, sealed by hash (data_holdout3/SEAL.sha256) before any price was read; only integrity facts were computed on it
(research/data_h3_info.json). No round-4 choice used any bar before 2020-01-02. Stress cost (1.5x) decides; base cost shown too.

BOT-A round 4 (LucidPro 50K): round-3 A legs and arbiter unchanged (CDL_NQ 1, CDL_ES 1, ORB15C_NQ 1, ORB15C_ES 1, IR_NQ 1,
OD_NQ 0.5, PDLB_GC 0.5; max 2 open). Policy changes: barrier-aware eval sizing cush_a 0.5 (risk x (cushion over floor / MLL)^0.5)
and prog_b -0.3 (risk eases up to 30% as profit nears the target); r_eval 800 (from 1000), cons_k 0.55, r_fund 300,
fund_day_stop 400 (from 550), fund_day_cap 500 (from none). No regime filter. Code: code/picks_r4.py.
Why: of 1,476 A variants (r4_search A1 + A2, research/bot_trials_r4.csv) it is one of three that meet the whole new bar in both dev
splits at stress cost: primary tests all met (P(pass) 36.6% / 35.1% vs baseline 17.1% / 21.8%; median 16.5 / 15 days; bust 0% /
0.9% vs 0.8% / 4.1%; 90-day EV $25 / $121 vs -$160 / $26) and no limit broken. The three differ only in the funded day cap; 500
is the middle one. Neighbours on every sizing axis also meet the primary bar on research (plateau check).
Honest cost: the round-3 A passes slightly more often in research (38.9%) with higher research EV ($107), but breaks two limits
(research consistency blocks 0.57 vs 0.38 a month; validation expectancy 0.147R vs 0.196R). Barrier sizing did not raise the pass
rate; it bought the limits back. At base cost, validation PF, expectancy, Sharpe and Sortino fall outside the 10% tolerance.

BOT-B round 4 (LucidFlex 50K): round-3 B plus (1) the pre-registered regime rule's only pick: Compression ORB ES trades only while
its own last 10 closed signals average above 0R; (2) Open Drive ES at 0.5 (from 0.25). Everything else as round 3.
Why: no B variant of 144 clears the unchanged bar. This one fails only trades a month, in both splits, the same as the round-3 B,
and pays more in both: P(first payout) 52.5% / 44.9% vs 49.4% / 42.7% (baseline 19.0% / 11.1%), $728 / $941 paid in 90 funded days
vs $721 / $872 (baseline $365 / $297), validation max drawdown $1,331 vs $1,384.
Logged reason for not taking the fewest-fails variant: five variants fail one cell fewer (research trades a month only) but only
by trading more, and they pay about half as much (validation $468 vs $941, P(payout) 28%). Trades a month is an activity measure;
buying it with payouts would defeat the bot's purpose. Base cost: research PF, expectancy, Sharpe, Sortino, drawdown and worst day
fall short (round-3 B: PF, drawdown, worst day).

Pre-registered holdout read: one run of `T58_R4=1 python3 code/final_score_r4.py hold` -> research/final_hold_r4.csv. Roster:
baseline_A, baseline_B, BOT-A-R3, BOT-B-R3, BOT-A-R4, BOT-B-R4, BOT-A-R4-port, BOT-B-R4-port, base and stress, plus Flex
lock-on-payout rows for baseline_B, BOT-B-R3, BOT-B-R4. Reported against the same bars; nothing is chosen on it.
