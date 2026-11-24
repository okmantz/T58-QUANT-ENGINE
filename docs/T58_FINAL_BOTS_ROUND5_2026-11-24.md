# T58 final bots, round 5 (2026-11-24)

**Bottom line.** Round 5 found nothing that should replace the round-4 bots. Ship round-4 BOT-A and round-4 BOT-B unchanged.

**Every window here was already read.** Round 5 searched and scored on 2016-11-24 .. 2026-11-20. No unread data is left:
- 2016-11-24 .. 2019-12-31 (H3) was round 4's holdout, read once on 2026-11-24 at 18:56 UTC. In round 5 it is dev data.
- 2020-2023 (research) has been the tuning window since round 1.
- 2024-01-01 .. 2026-11-20 (validation) includes the round-2 and round-3 holdout windows, read in those rounds.

So every number below is in-sample. Owen confirmed no pre-2016 data is available, so there is no holdout. The rotation, plateau and
Monte Carlo checks stand in for one, and none of them is a holdout.

Cost model, lookahead protection, firm rules and the bars are unchanged from round 4 (research/PREREG_R4.md). Each bar had to hold in
all three periods (research/PREREG_R5.md, written before any round-5 score).

## What was searched
3,720 configs, stride 2, at stress cost (research/bot_trials_r5.csv):
- A1: 1,500 bot A leg mixes (each leg 0/0.5/1, plus one optional new leg, regime rule on or off).
- A2: 480 funded-side settings on the A1 top 10.
- B1: 1,500 bot B leg mixes.
- B2: 240 funded-side settings on the B1 top 10.

Trials across all rounds (bot-level configs scored):
- R1: 3,912
- R2: 416
- R3: 1,776
- R4: 1,620
- R5: 3,720, plus 29 plateau neighbours

That is 11,473 in total, plus 1,825 single-strategy screens in round 1. With that many tries on the same ten years, a small edge over
round 4 is expected by chance alone.

## BOT-A
- No config clears every BOT-A bar in all three periods.
- The best one ties round-4 A exactly.
- Raising the 2016-2019 payout rate (round-4 A's one standing miss) broke 12 to 14 other limits.

Round-4 A stays. Stride 1 confirms the round-4 picture:
- 2020-2026: round-4 A clears the bar at stress cost.
- 2016-2019: P(pass) is .149 vs .150 (within noise, but a fail by the letter), and the first-30-day payout rate is .017 vs .045.

## BOT-B
The best B is search tag B2-26, a slimmer round-4 B. It drops Context Drive Long ES, ORB15 compression ES (and with it the regime
rule), ORB30 with trend NQ and Gap with trend GC. It halves Ind Rule NQ, VWAP pullback NQ and Prior-day break GC, adds the 10:00
time-of-day NQ leg at 0.5, and removes the $200 funded day cap. Every other setting is the same.

At stress cost it has 2 shortfall cells against the current B across the three periods, vs 5 for round-4 B (8 vs 13 at base cost).
By the pre-registered count it wins.

I am not shipping it. It is kept as BOT_B_ALT in code/picks_r5.py and final/BOT-B/params_r5_alt.json. Reasons:
- **Rotation check fails.** A B picked on any two periods misses 1 to 3 cells on the third, so the gains don't carry across periods.
- **Plateau check fails.** Only 13 of its 29 one-step neighbours stay within one cell of it (research/plateau_r5_B.csv). It sits on
  a narrow peak.
- **It pays out less often in recent years.** Its first-30-day payout rate is .485 vs .565 on 2020-2023 and .373 vs .449 on
  2024-2026. That is the number a payout bot exists for. Most of its gain is on 2016-2019, the one window round 5 tuned on that
  round 4 had not.
- **Monte Carlo puts it about level.** On the full 2016-2026 pool, round-5 alt and round-4 B pay out about equally often (.40-.43),
  and the alt's 90-day EV is $8 to $20 less negative.

This decision goes beyond the pre-registered rule. It was made and frozen (research/FROZEN_PICKS_R5.md) after the confirm and plateau
checks and before the Monte Carlo was read. If you'd rather follow the count, swap in BOT_B_ALT. Every number for it is below.

## Shortfall cells by period (stride 1)
| cost | period | A_primary_fails | A_limit_fails | B_round4_shortfalls | B_alt_shortfalls |
|---|---|---|---|---|---|
| stress | 2016-11-24..2019-12-31 | p_pass | p_payout | ev, f90_payouts, f90_p2 | none |
| stress | 2020-2023 | none | none | trades_pm | none |
| stress | 2024-01-01..2026-11-20 | none | none | trades_pm | trades_pm, max_dd |
| base | 2016-11-24..2019-12-31 | none | exp_R, sharpe, sortino, p_payout | ev, pf, exp_R, sharpe, sortino, f90_payouts, f90_p2, max_dd | none |
| base | 2020-2023 | none | none | pf, exp_R, sortino, worst_day, max_dd | pf, exp_R, sharpe, sortino, worst_day, max_dd |
| base | 2024-01-01..2026-11-20 | none | pf, exp_R, sharpe, sortino | none | pf, max_dd |

## Metrics (stride 1)

### stress cost
| period | bot | p_pass | med_days_pass | bust | ev | p_payout | med_days_payout | f90_paid | f90_payouts | pf | sharpe | max_dd | worst_day | trades_pm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2016-11-24..2019-12-31 | baseline_A | 0.150 | 19.000 | 0.013 | -225.624 | 0.045 | 23.000 |  |  | 1.056 | 0.249 | 5943.085 | -1055.231 | 12.079 |
| 2020-2023 | baseline_A | 0.171 | 23.000 | 0.008 | -159.717 | 0.054 | 22.000 |  |  | 1.530 | 2.497 | 3501.770 | -690.549 | 17.626 |
| 2024-01-01..2026-11-20 | baseline_A | 0.218 | 19.500 | 0.041 | 25.796 | 0.078 | 23.000 |  |  | 1.358 | 1.652 | 6040.982 | -977.037 | 17.312 |
| 2016-11-24..2019-12-31 | BOT-A-R4 | 0.149 | 14.000 | 0.001 | -197.704 | 0.017 | 21.500 |  |  | 1.088 | 0.403 | 2698.734 | -646.754 | 25.232 |
| 2020-2023 | BOT-A-R4 | 0.372 | 16.000 | 0.000 | 36.121 | 0.089 | 23.500 |  |  | 1.506 | 2.599 | 2950.274 | -649.066 | 29.169 |
| 2024-01-01..2026-11-20 | BOT-A-R4 | 0.351 | 15.000 | 0.009 | 121.031 | 0.096 | 23.000 |  |  | 1.429 | 1.676 | 2932.364 | -637.200 | 21.842 |
| 2016-11-24..2019-12-31 | baseline_B | 0.000 |  | 0.000 | -129.706 | 0.237 | 23.000 | 196.240 | 0.621 | 0.847 | -0.868 | 6487.007 | -305.450 | 23.058 |
| 2020-2023 | baseline_B | 0.001 | 30.000 | 0.000 | -132.654 | 0.190 | 25.000 | 364.641 | 1.013 | 1.169 | 0.849 | 2010.526 | -323.818 | 18.064 |
| 2024-01-01..2026-11-20 | baseline_B | 0.000 |  | 0.000 | -136.991 | 0.111 | 22.500 | 297.186 | 0.766 | 1.156 | 0.695 | 1800.877 | -311.105 | 13.503 |
| 2016-11-24..2019-12-31 | BOT-B-R4 | 0.003 | 25.500 | 0.000 | -137.263 | 0.251 | 22.000 | 201.516 | 0.556 | 0.873 | -0.845 | 6318.051 | -299.387 | 43.110 |
| 2020-2023 | BOT-B-R4 | 0.020 | 21.500 | 0.000 | -101.070 | 0.565 | 19.000 | 766.720 | 1.927 | 1.278 | 1.754 | 1758.094 | -299.540 | 12.230 |
| 2024-01-01..2026-11-20 | BOT-B-R4 | 0.060 | 26.000 | 0.000 | -31.960 | 0.449 | 20.000 | 943.865 | 1.658 | 1.357 | 2.093 | 1307.953 | -296.743 | 11.455 |
| 2016-11-24..2019-12-31 | BOT-B-R5 | 0.007 | 17.000 | 0.000 | -128.676 | 0.307 | 21.000 | 307.668 | 0.938 | 0.984 | -0.097 | 3909.630 | -299.760 | 50.653 |
| 2020-2023 | BOT-B-R5 | 0.027 | 22.000 | 0.000 | -92.723 | 0.485 | 20.000 | 741.541 | 1.717 | 1.195 | 1.066 | 1996.882 | -299.997 | 31.086 |
| 2024-01-01..2026-11-20 | BOT-B-R5 | 0.082 | 25.000 | 0.000 | 31.459 | 0.373 | 19.000 | 926.106 | 1.549 | 1.474 | 2.543 | 1801.650 | -294.140 | 10.964 |

### base cost
| period | bot | p_pass | med_days_pass | bust | ev | p_payout | med_days_payout | f90_paid | f90_payouts | pf | sharpe | max_dd | worst_day | trades_pm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2016-11-24..2019-12-31 | baseline_A | 0.163 | 18.000 | 0.011 | -217.095 | 0.047 | 23.000 |  |  | 1.025 | 0.119 | 6142.231 | -1063.030 | 11.730 |
| 2020-2023 | baseline_A | 0.178 | 23.000 | 0.008 | -137.199 | 0.058 | 22.000 |  |  | 1.532 | 2.564 | 2934.975 | -721.987 | 17.231 |
| 2024-01-01..2026-11-20 | baseline_A | 0.234 | 20.000 | 0.049 | 41.319 | 0.088 | 22.500 |  |  | 1.455 | 1.978 | 6009.772 | -973.757 | 16.129 |
| 2016-11-24..2019-12-31 | BOT-A-R4 | 0.193 | 15.000 | 0.001 | -184.943 | 0.024 | 23.000 |  |  | 0.931 | -0.320 | 6747.735 | -647.500 | 23.246 |
| 2020-2023 | BOT-A-R4 | 0.396 | 17.000 | 0.000 | 95.706 | 0.103 | 24.000 |  |  | 1.486 | 2.495 | 2911.232 | -643.857 | 29.169 |
| 2024-01-01..2026-11-20 | BOT-A-R4 | 0.354 | 15.000 | 0.009 | 97.387 | 0.109 | 23.000 |  |  | 1.256 | 1.437 | 4444.067 | -599.157 | 32.719 |
| 2016-11-24..2019-12-31 | baseline_B | 0.000 |  | 0.000 | -128.224 | 0.269 | 23.000 | 255.527 | 0.758 | 0.948 | -0.272 | 3670.224 | -313.700 | 22.817 |
| 2020-2023 | baseline_B | 0.001 | 29.000 | 0.000 | -132.250 | 0.216 | 25.000 | 406.399 | 1.113 | 1.284 | 1.366 | 1245.381 | -298.275 | 8.667 |
| 2024-01-01..2026-11-20 | baseline_B | 0.000 |  | 0.000 | -137.487 | 0.127 | 22.000 | 339.175 | 0.836 | 1.420 | 1.717 | 1620.150 | -303.938 | 8.685 |
| 2016-11-24..2019-12-31 | BOT-B-R4 | 0.012 | 28.000 | 0.000 | -129.665 | 0.295 | 22.000 | 273.546 | 0.720 | 0.859 | -0.984 | 6946.284 | -300.000 | 42.922 |
| 2020-2023 | BOT-B-R4 | 0.024 | 20.000 | 0.000 | -78.766 | 0.603 | 20.000 | 851.967 | 2.038 | 1.233 | 1.391 | 3244.665 | -299.829 | 13.355 |
| 2024-01-01..2026-11-20 | BOT-B-R4 | 0.065 | 25.000 | 0.000 | -9.097 | 0.451 | 20.000 | 985.533 | 1.693 | 1.442 | 2.430 | 1215.946 | -293.005 | 10.791 |
| 2016-11-24..2019-12-31 | BOT-B-R5 | 0.014 | 22.000 | 0.000 | -127.638 | 0.324 | 21.000 | 365.474 | 0.988 | 0.993 | -0.044 | 3372.086 | -297.148 | 56.209 |
| 2020-2023 | BOT-B-R5 | 0.036 | 24.500 | 0.000 | -77.150 | 0.492 | 20.000 | 775.847 | 1.769 | 1.139 | 0.856 | 1859.291 | -298.775 | 16.543 |
| 2024-01-01..2026-11-20 | BOT-B-R5 | 0.094 | 25.000 | 0.000 | 25.723 | 0.388 | 19.000 | 988.398 | 1.633 | 1.403 | 2.281 | 1765.590 | -299.075 | 10.474 |

## Plateau, BOT_B_ALT one-step neighbours (stride 2, stress)
| step | nbad |
|---|---|
| leg CDL_NQ 1->0.5 | 8 |
| leg ORB15C_NQ 1->0.5 | 3 |
| leg IR_NQ 0.5->0.25 | 6 |
| leg IR_NQ 0.5->1 | 4 |
| leg VWPB_NQ 0.25->0 | 3 |
| leg VWPB_NQ 0.25->0.5 | 8 |
| leg OD_ES 0.5->0.25 | 6 |
| leg OD_ES 0.5->1 | 2 |
| leg PDLB_GC 0.5->0.25 | 3 |
| leg PDLB_GC 0.5->1 | 3 |
| leg OD_NQ 0.25->0 | 1 |
| leg OD_NQ 0.25->0.5 | 3 |
| leg CORB_ES 0.5->0.25 | 7 |
| leg CORB_ES 0.5->1 | 6 |
| leg TOD10_NQ 0.5->0.25 | 2 |
| leg TOD10_NQ 0.5->1 | 4 |
| r_fund 250->200 | 7 |
| r_fund 250->300 | 5 |
| day_stop 300->220 | 5 |
| day_stop 300->380 | 8 |
| fund_day_cap None->200 | 2 |
| f_cush 0.4->0.3 | 2 |
| f_cush 0.4->0.5 | 2 |
| fund_f_cush 0.3->0.2 | 2 |
| fund_f_cush 0.3->0.4 | 2 |
| r_eval 300->250 | 6 |
| r_eval 300->350 | 5 |
| max_open 4->3 | 9 |
| max_open 4->5 | 6 |

## Monte Carlo (10,000 70-session paths per row, stress cost; FULL = 2016-11-24..2026-11-20, OOS = 2024-01-01..2026-11-20, both already read)
| bot | pool | method | p_pass | med_days_pass | bust | p_payout | med_days_payout | ev90 |
|---|---|---|---|---|---|---|---|---|
| baseline_A | FULL | reshuffle | 0.211 | 19.000 | 0.012 | 0.072 | 22.000 | -120.946 |
| baseline_A | FULL | block | 0.189 | 19.000 | 0.013 | 0.060 | 23.000 | -153.772 |
| baseline_A | OOS | reshuffle | 0.227 | 18.000 | 0.027 | 0.070 | 23.000 | -109.766 |
| baseline_A | OOS | block | 0.224 | 18.000 | 0.031 | 0.069 | 23.000 | -94.850 |
| BOT-A-R4 | FULL | reshuffle | 0.281 | 12.000 | 0.003 | 0.083 | 23.000 | -63.205 |
| BOT-A-R4 | FULL | block | 0.277 | 15.000 | 0.002 | 0.069 | 23.000 | -90.239 |
| BOT-A-R4 | OOS | reshuffle | 0.289 | 11.000 | 0.006 | 0.101 | 22.000 | -36.889 |
| BOT-A-R4 | OOS | block | 0.310 | 12.000 | 0.009 | 0.099 | 22.000 | -35.986 |
| baseline_B | FULL | reshuffle | 0.002 | 26.000 | 0.000 | 0.158 | 24.000 | -119.651 |
| baseline_B | FULL | block | 0.000 | 27.500 | 0.000 | 0.164 | 24.000 | -130.946 |
| baseline_B | OOS | reshuffle | 0.001 | 29.000 | 0.000 | 0.069 | 25.000 | -123.357 |
| baseline_B | OOS | block | 0.000 | 30.000 | 0.000 | 0.096 | 24.000 | -128.148 |
| BOT-B-R4 | FULL | reshuffle | 0.031 | 23.000 | 0.000 | 0.410 | 19.000 | -86.967 |
| BOT-B-R4 | FULL | block | 0.022 | 24.000 | 0.000 | 0.410 | 19.000 | -97.788 |
| BOT-B-R4 | OOS | reshuffle | 0.037 | 23.000 | 0.000 | 0.424 | 19.000 | -64.930 |
| BOT-B-R4 | OOS | block | 0.038 | 24.000 | 0.000 | 0.423 | 19.000 | -60.728 |
| BOT-B-R5 | FULL | reshuffle | 0.044 | 22.000 | 0.000 | 0.415 | 19.000 | -69.338 |
| BOT-B-R5 | FULL | block | 0.029 | 24.000 | 0.000 | 0.397 | 19.000 | -90.276 |
| BOT-B-R5 | OOS | reshuffle | 0.051 | 23.000 | 0.000 | 0.431 | 19.000 | -45.398 |
| BOT-B-R5 | OOS | block | 0.046 | 24.000 | 0.000 | 0.415 | 19.000 | -47.736 |

## Files
- code/r5.py, r5_search.py, r5_pick.py, r5_confirm.py, reports_r5.py, picks_r5.py; mc.py gains an r5 mode; data.py gains T58_R5
  (pre-edit copies in research/round1_code/).
- research/PREREG_R5.md, FROZEN_PICKS_R5.md (+ .sha256), bot_trials_r5.csv, final_dev_r5.csv, plateau_r5_B.csv, mc_r5.csv.
