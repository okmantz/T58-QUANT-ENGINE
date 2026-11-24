> **Round 5 update (2026-11-24, late):** a wider search on 2016-2026 found nothing that should replace these bots, so the round-4 picks below still stand. Every window in round 5 had already been read, so its results aren't a clean holdout. See T58_FINAL_BOTS_ROUND5_2026-11-24.md.

# T58 final bots: performance report, round 4 (2026-11-24)

Research code only. Nothing in this work placed, changed or cancelled an order, signed in to a prop firm, broker or exchange, or created
an alert. Every number comes from one engine (research/t58_final_bots/engine): the repo's own strategy files for the existing legs,
next-bar-open fills, stops filled at the stop price plus slippage, Lucid 50K rules simulated by firm.py. Costs: base = $3.50 a side on
ES/NQ ($4.60 GC; micros $1.00 / $1.60) plus 1 tick a side; stress = 1.5x both (the cost every pick was chosen on).

**What was and was not touched (round 4).**
- Research 2020-01-01 .. 2023-12-31: used to fit every filter, weight and sizing setting.
- Validation 2024-01-01 .. 2026-11-20: used to confirm. It is NOT untouched: Sep 2025 .. Feb 2026 was the round-1/2 holdout and
  Mar 2 .. Nov 20 2026 was the round-3 holdout, each read before; in round 4 they are ordinary validation data.
- Holdout 2016-11-24 .. 2019-12-31 (Owen's new pack): untouched. Sealed by hash before any price was read; only row counts, session
  counts, roll checks and the splice offset were computed on it before the picks were frozen (research/FROZEN_PICKS_R4.sha256), then
  read exactly once per finalist. The pack's 2020 part overlaps research and was not used; MES and MNQ start in 2019-05 and were not used.
- Pre-2020 bars get the same session, cost and roll handling: the repo engine runs on the combined file and prices are shifted onto
  the repo's back-adjusted basis (offset spread 0). No roll splice was detected before 2020; the detector is partial, so a small
  unadjusted roll gap cannot be ruled out.
Pass and payout metrics average rolling account starts in each split; trade metrics cover the whole split.

## Bottom line

- **BOT-A (pass LucidPro 50K) meets your new bar on 2020-2026 at stress cost, and nearly meets it on the untouched 2016-2019 data.** P(pass in 30 days) 36.6% / 35.1% / 14.9% vs 17.1% / 21.8% / 15.0% for your current BOT-A (research / validation / 2016-2019); median days to pass 16.50 / 15.00 / 14.00 vs 23.00 / 19.50 / 19.00; eval bust 0.0% / 0.9% / 0.1% vs 0.8% / 4.1% / 1.3%; 90-day EV 25 / 121 / -198 vs -160 / 26 / -226. On 2016-2019 it misses P(pass) by 0.1 point and breaks one limit (funded first payout).
- **Monte Carlo agrees on 2020-2026 and not on 2016-2019.** On 70-session resamples BOT-A round 4 passes 30-33% vs 19-23% for your current BOT-A (FULL and OOS pools), but on 2016-2019 resamples it passes 15.5-19.4% vs 17.2-21.4%, with fewer busts. Round-3 A is a little ahead of round-4 A in every Monte Carlo pool; round 4 is the pick because it keeps the limits.
- **The sizing you suggested did not raise the pass rate.** It kept the round-3 pass rate within about 2 points and brought every limit back inside tolerance; round-3 A broke two limits on 2020-2026 and five on 2016-2019.
- **BOT-B (Flex payouts) beats or ties your current BOT-B on 49 of 54 cells at stress cost** (round-3 B: 46). Misses: trades a month in research and validation; 90-day EV, payouts in 90 days and P(2+ payouts) on 2016-2019.
- **The regime filter found little.** Of the causal filters tested, only the 10-signal equity filter on the ES ORB15 leg cleared the pre-registered research rule. None fixed the NQ legs that lost in Mar-Nov 2026, so the Mar-Nov problem is not solved; it is disclosed.
- 2016-2019 was a weak stretch for every bot, current bots included (current A PF 1.06, current B PF 0.85 at stress).

## BOT-A round 4 on LucidPro 50K

| Metric | Research base | Research stress | Validation base | Validation stress | Holdout base | Holdout stress |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 39.0% | 36.6% | 35.4% | 35.1% | 19.3% | 14.9% |
| Median days to pass | 17.00 | 16.50 | 15.00 | 15.00 | 15.00 | 14.00 |
| Eval bust | 0.0% | 0.0% | 0.9% | 0.9% | 0.1% | 0.1% |
| P(first payout in 30d, funded) | 10.4% | 8.9% | 10.9% | 9.6% | 2.4% | 1.7% |
| Median days to first payout | 24.00 | 23.50 | 23.00 | 23.00 | 23.00 | 21.50 |
| 90-day EV net of fees and resets ($) | 88 | 25 | 97 | 121 | -185 | -198 |
| Profit factor | 1.46 | 1.46 | 1.26 | 1.43 | 0.93 | 1.09 |
| Expectancy (R) | 0.22 | 0.21 | 0.15 | 0.18 | 0.02 | 0.02 |
| Sharpe | 2.42 | 2.40 | 1.44 | 1.68 | -0.32 | 0.40 |
| Sortino | 5.17 | 5.16 | 3.02 | 4.03 | -0.55 | 0.77 |
| Max drawdown ($) | 2,979 | 3,040 | 4,444 | 2,932 | 6,748 | 2,699 |
| Worst day ($) | -640 | -627 | -599 | -637 | -648 | -647 |
| Consistency blocks per 30d | 0.41 | 0.31 | 0.75 | 0.78 | 0.11 | 0.07 |
| Trades a month | 29.27 | 29.04 | 32.72 | 21.84 | 23.25 | 25.23 |

Repo-format legs (strategies/python/*_t58.py, causal bar-count filter; what the zip ships):

| Metric | Research base | Research stress | Validation base | Validation stress | Holdout base | Holdout stress |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 37.3% | 34.0% | 33.3% | 31.7% | 18.8% | 14.5% |
| Median days to pass | 18.00 | 17.00 | 14.00 | 15.00 | 15.00 | 14.00 |
| Eval bust | 0.0% | 0.0% | 1.0% | 0.9% | 0.1% | 0.1% |
| P(first payout in 30d, funded) | 10.1% | 8.9% | 11.4% | 9.9% | 2.4% | 1.4% |
| Median days to first payout | 23.00 | 24.00 | 23.00 | 23.50 | 23.00 | 22.00 |
| 90-day EV net of fees and resets ($) | 41 | 5 | 110 | 50 | -182 | -195 |
| Profit factor | 1.43 | 1.43 | 1.27 | 1.24 | 0.92 | 0.97 |
| Expectancy (R) | 0.20 | 0.19 | 0.15 | 0.14 | -0.01 | 0.01 |
| Sharpe | 2.14 | 2.29 | 1.22 | 1.35 | -0.34 | -0.14 |
| Sortino | 4.57 | 4.85 | 2.56 | 2.74 | -0.57 | -0.25 |
| Max drawdown ($) | 4,279 | 3,085 | 6,612 | 4,067 | 7,920 | 4,747 |
| Worst day ($) | -649 | -635 | -629 | -621 | -650 | -648 |
| Consistency blocks per 30d | 0.39 | 0.32 | 0.65 | 0.73 | 0.08 | 0.07 |
| Trades a month | 27.71 | 30.11 | 22.45 | 31.68 | 19.54 | 25.53 |

## BOT-B round 4 on LucidFlex 50K

| Metric | Research base | Research stress | Validation base | Validation stress | Holdout base | Holdout stress |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 2.3% | 1.9% | 6.5% | 6.0% | 1.2% | 0.3% |
| Median days to pass | 20.00 | 22.00 | 25.00 | 26.00 | 28.00 | 25.50 |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 57.1% | 52.5% | 45.1% | 44.9% | 29.5% | 25.1% |
| Median days to first payout | 19.00 | 19.00 | 20.00 | 20.00 | 22.00 | 22.00 |
| 90-day EV net of fees and resets ($) | -78 | -101 | -9 | -32 | -130 | -137 |
| Profit factor | 1.15 | 1.29 | 1.44 | 1.36 | 0.86 | 0.87 |
| Expectancy (R) | 0.11 | 0.13 | 0.25 | 0.21 | -0.05 | -0.05 |
| Sharpe | 0.90 | 1.78 | 2.41 | 2.09 | -0.98 | -0.85 |
| Sortino | 1.62 | 3.29 | 5.18 | 4.21 | -1.48 | -1.34 |
| Max drawdown ($) | 3,766 | 1,758 | 1,227 | 1,331 | 6,946 | 6,318 |
| Worst day ($) | -299 | -300 | -293 | -297 | -300 | -299 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 15.17 | 11.29 | 10.73 | 11.51 | 42.92 | 43.11 |
| Payouts in 90 funded days | 2.00 | 1.82 | 1.69 | 1.65 | 0.72 | 0.56 |
| $ paid in 90 funded days | 839 | 728 | 984 | 941 | 274 | 202 |
| P(2+ payouts in 90d) | 65.6% | 55.4% | 54.7% | 52.9% | 18.4% | 10.9% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Repo-format legs:

| Metric | Research base | Research stress | Validation base | Validation stress | Holdout base | Holdout stress |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 1.5% | 1.4% | 7.1% | 5.5% | 0.9% | 0.3% |
| Median days to pass | 20.00 | 21.50 | 27.00 | 27.00 | 25.00 | 25.50 |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 57.2% | 53.8% | 44.2% | 43.5% | 26.4% | 22.7% |
| Median days to first payout | 20.00 | 19.00 | 19.00 | 19.00 | 21.00 | 22.00 |
| 90-day EV net of fees and resets ($) | -99 | -110 | -8 | -35 | -130 | -133 |
| Profit factor | 1.30 | 1.20 | 1.40 | 1.38 | 0.91 | 0.91 |
| Expectancy (R) | 0.12 | 0.12 | 0.22 | 0.20 | -0.03 | -0.05 |
| Sharpe | 1.77 | 1.22 | 2.33 | 2.24 | -0.62 | -0.66 |
| Sortino | 3.33 | 2.23 | 4.71 | 4.51 | -1.00 | -1.06 |
| Max drawdown ($) | 1,682 | 2,738 | 1,257 | 1,313 | 5,530 | 5,832 |
| Worst day ($) | -299 | -299 | -298 | -299 | -299 | -298 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 11.52 | 15.58 | 12.26 | 12.06 | 50.63 | 48.00 |
| Payouts in 90 funded days | 1.93 | 1.77 | 1.64 | 1.57 | 0.76 | 0.54 |
| $ paid in 90 funded days | 806 | 706 | 940 | 874 | 287 | 196 |
| P(2+ payouts in 90d) | 64.8% | 58.1% | 54.9% | 51.8% | 18.0% | 10.9% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

## Monte Carlo (10,000 paths per row, stress cost)

Each path is 70 sessions resampled from the bot's own booked trade days (whole days kept together). FULL = 2020-01-01 .. 2026-11-20, OOS = 2024-01-01 .. 2026-11-20, H3 = 2016-11-24 .. 2019-12-31 (run after its single read; it chooses nothing). 'block' keeps 10-session runs; 'reshuffle' draws days independently. BOT-B's 90-day EV pays for an evaluation it rarely passes, so it is negative by design.

| Bot | Pool | Resampler | P(pass in 30d) | Median days to pass | Eval bust | P(first payout in 30d) | Median days to payout | 90-day EV (5th to 95th pct) |
|---|---|---|---|---|---|---|---|---|
| baseline_A | FULL | reshuffle | 20.6% | 19 | 1.7% | 8.2% | 23 | -103 (-292 to 769) |
| baseline_A | FULL | block | 19.4% | 22 | 1.8% | 6.9% | 24 | -122 (-292 to 565) |
| baseline_A | OOS | reshuffle | 22.7% | 18 | 2.7% | 7.0% | 23 | -110 (-292 to 816) |
| baseline_A | OOS | block | 22.4% | 18 | 3.1% | 6.9% | 23 | -95 (-292 to 852) |
| baseline_A | H3 | reshuffle | 21.4% | 18 | 0.5% | 6.0% | 22 | -182 (-292 to 294) |
| baseline_A | H3 | block | 17.2% | 19 | 0.6% | 3.6% | 23 | -212 (-292 to -172) |
| BOT-A-R3 | FULL | reshuffle | 35.1% | 12 | 0.6% | 13.3% | 22 | 50 (-292 to 1,628) |
| BOT-A-R3 | FULL | block | 36.1% | 15 | 0.8% | 11.3% | 23 | 29 (-292 to 1,628) |
| BOT-A-R3 | OOS | reshuffle | 32.5% | 11 | 1.1% | 11.4% | 19 | -20 (-292 to 1,421) |
| BOT-A-R3 | OOS | block | 32.7% | 12 | 1.7% | 10.5% | 22 | -36 (-292 to 1,393) |
| BOT-A-R3 | H3 | reshuffle | 21.8% | 11 | 0.6% | 3.9% | 22 | -189 (-292 to -172) |
| BOT-A-R3 | H3 | block | 18.8% | 12 | 0.4% | 2.5% | 24 | -207 (-292 to -172) |
| BOT-A-R4 | FULL | reshuffle | 31.6% | 15 | 0.4% | 12.1% | 22 | 19 (-292 to 1,409) |
| BOT-A-R4 | FULL | block | 32.6% | 15 | 0.4% | 10.0% | 23 | 1 (-292 to 1,193) |
| BOT-A-R4 | OOS | reshuffle | 30.0% | 12 | 0.8% | 10.3% | 22 | -35 (-292 to 1,126) |
| BOT-A-R4 | OOS | block | 31.5% | 12 | 0.7% | 10.2% | 22 | -35 (-292 to 1,183) |
| BOT-A-R4 | H3 | reshuffle | 19.4% | 11 | 0.3% | 3.6% | 22 | -170 (-292 to -172) |
| BOT-A-R4 | H3 | block | 15.5% | 15 | 0.2% | 2.0% | 23 | -188 (-292 to -172) |
| baseline_B | FULL | reshuffle | 0.2% | 30 | 0.0% | 13.4% | 24 | -118 (-126 to -126) |
| baseline_B | FULL | block | 0.1% | 30 | 0.0% | 14.5% | 24 | -125 (-126 to -126) |
| baseline_B | OOS | reshuffle | 0.1% | 26 | 0.0% | 7.2% | 25 | -124 (-126 to -126) |
| baseline_B | OOS | block | 0.0% | 30 | 0.0% | 9.6% | 24 | -128 (-126 to -126) |
| baseline_B | H3 | reshuffle | 0.4% | 26 | 0.0% | 20.7% | 23 | -125 (-126 to -126) |
| baseline_B | H3 | block | 0.1% | 29 | 0.0% | 20.3% | 23 | -130 (-126 to -126) |
| BOT-B-R3 | FULL | reshuffle | 4.1% | 23 | 0.0% | 46.8% | 18 | -52 (-126 to 496) |
| BOT-B-R3 | FULL | block | 3.7% | 23 | 0.0% | 48.3% | 18 | -67 (-126 to 379) |
| BOT-B-R3 | OOS | reshuffle | 3.6% | 23 | 0.0% | 40.9% | 19 | -76 (-126 to 303) |
| BOT-B-R3 | OOS | block | 3.7% | 24 | 0.0% | 40.8% | 19 | -66 (-126 to 413) |
| BOT-B-R3 | H3 | reshuffle | 0.8% | 23 | 0.0% | 23.8% | 19 | -129 (-252 to -126) |
| BOT-B-R3 | H3 | block | 0.4% | 24 | 0.0% | 22.7% | 19 | -130 (-126 to -126) |
| BOT-B-R4 | FULL | reshuffle | 4.7% | 23 | 0.0% | 48.6% | 18 | -44 (-126 to 551) |
| BOT-B-R4 | FULL | block | 3.2% | 24 | 0.0% | 48.0% | 18 | -67 (-126 to 397) |
| BOT-B-R4 | OOS | reshuffle | 4.0% | 23 | 0.0% | 43.4% | 19 | -65 (-126 to 412) |
| BOT-B-R4 | OOS | block | 3.6% | 24 | 0.0% | 42.3% | 19 | -62 (-126 to 452) |
| BOT-B-R4 | H3 | reshuffle | 1.0% | 22 | 0.0% | 26.5% | 19 | -126 (-252 to -126) |
| BOT-B-R4 | H3 | block | 0.4% | 23 | 0.0% | 25.2% | 19 | -130 (-126 to -126) |
| BOT-A-R4-port | FULL | reshuffle | 30.6% | 15 | 0.3% | 11.7% | 22 | -1 (-292 to 1,070) |
| BOT-A-R4-port | FULL | block | 31.1% | 15 | 0.4% | 9.9% | 23 | -26 (-292 to 969) |
| BOT-A-R4-port | OOS | reshuffle | 28.2% | 12 | 0.8% | 10.1% | 22 | -54 (-292 to 795) |
| BOT-A-R4-port | OOS | block | 30.7% | 12 | 0.8% | 9.9% | 22 | -59 (-292 to 812) |
| BOT-A-R4-port | H3 | reshuffle | 18.6% | 11 | 0.4% | 3.4% | 23 | -178 (-292 to -172) |
| BOT-A-R4-port | H3 | block | 16.0% | 15 | 0.2% | 2.4% | 22 | -191 (-292 to -172) |
| BOT-B-R4-port | FULL | reshuffle | 4.1% | 23 | 0.0% | 48.8% | 18 | -51 (-126 to 507) |
| BOT-B-R4-port | FULL | block | 2.5% | 24 | 0.0% | 46.8% | 19 | -80 (-126 to 286) |
| BOT-B-R4-port | OOS | reshuffle | 3.6% | 23 | 0.0% | 42.6% | 19 | -72 (-126 to 353) |
| BOT-B-R4-port | OOS | block | 3.2% | 24 | 0.0% | 42.9% | 19 | -78 (-126 to 328) |
| BOT-B-R4-port | H3 | reshuffle | 1.0% | 22 | 0.0% | 25.6% | 19 | -128 (-252 to -126) |
| BOT-B-R4-port | H3 | block | 0.6% | 25 | 0.0% | 22.7% | 19 | -130 (-126 to -126) |

## Disclosures

- No single leg passed the Deflated Sharpe gate (research/gate_ladder_log.md). Acceptance rests on research-to-validation replication at stress cost and the 2016-2019 holdout.
- Validation includes two windows read before as holdouts (see above).
- In 2016-2019 index prices were much lower, so stops in points cost fewer dollars and many more signals fit a fixed dollar budget (BOT-B traded 43 a month there vs 11 in 2020-2023). The holdout tests a different sizing regime as well as a different market.
- The research leg factory's whole-day bar-count filter is a mild lookahead; the repo-format legs are causal and score lower (rows above).
- The round-4 Pine edits were not compiled on TradingView: the daily tool quota was used up. Compile final/pine/T58_BOT.pine once before use.
- The Pine port leaves out IR_NQ and the cross-instrument cap; the Flex lock-on-payout rule is reported as a sensitivity only.
