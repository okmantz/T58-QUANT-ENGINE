# Frozen picks, round 5 (2026-11-24, ~23:15 UTC)

Frozen after the round-5 search and checks 1 and 3 (confirm, plateau) and before the round-5 Monte Carlo was read.
There is no holdout: every window used (2016-11-24 .. 2026-11-20) was read in rounds 1-4. Freezing only fixes the picks so later
runs can't move them.

- BOT-A: round-4 A, unchanged (code/picks_r5.py BOT_A == picks_r4.BOT_A).
- BOT-B: round-4 B, unchanged (BOT_B == picks_r4.BOT_B).
- BOT-B alternative: BOT_B_ALT (search tag B2-26), documented, not shipped.

Why B stays round 4: under the PREREG_R5 pick rule B2-26 has fewer shortfall cells (2 vs 5 at stress cost, 8 vs 13 at base cost),
but it fails the two overfitting checks that stand in for the missing holdout:
- Rotation: a pick made on any two periods misses 1 to 3 cells on the third.
- Plateau: 16 of its 29 one-step neighbours fall more than one cell behind it.
It also pays out less often than round-4 B in 2020-2026 (first-30-day payout rate .485 vs .565 research, .373 vs .449 validation);
most of its gain is in 2016-2019, the window round 5 tuned on that round 4 had not. This is a judgment call beyond the
pre-registered rule, made before the Monte Carlo was read, and disclosed in the round-5 report.

Trials: bot-level configs scored, all rounds: R1 3,912, R2 416, R3 1,776, R4 1,620, R5 3,720 (+29 plateau neighbours) = 11,473;
plus 1,825 single-strategy screens in round 1.
