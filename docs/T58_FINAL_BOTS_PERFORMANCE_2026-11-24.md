# T58 final bots: performance report (2026-11-24)

Research code only. Nothing in this work placed, changed or cancelled an order, signed in to a prop firm, broker or exchange, or created
an alert. Every number comes from one engine (research/t58_final_bots/engine): the repo's own strategy files for the existing legs,
next-bar-open fills, stops filled at the stop price plus slippage, Lucid 50K rules simulated by firm.py. Costs: base = $3.50 a side on
ES/NQ ($4.60 GC; micros $1.00 / $1.60) plus 1 tick a side; stress = 1.5x both (the cost every pick was chosen on).
Splits: research 2020-01-01 .. 2023-12-31, validation 2024-01-01 .. 2026-03-01, holdout 2026-03-02 .. 2026-11-20 (Owen's Mar-Nov 2026
files, sealed until the picks were frozen and read exactly once). Pass and payout metrics are averaged over rolling account starts
in the split; trade metrics (PF, expectancy, Sharpe, drawdown, worst day, trades a month) cover the whole split.

## Bottom line

- **BOT-B (payouts on LucidFlex 50K) is the better bot and the closer miss.** At stress cost it beats or ties the current BOT-B on 51 of 54 cells. On the fresh holdout it reached a first payout 24.0% of the time vs 9.7%, paid $742 vs $161 over 90 funded days, and made 2+ payouts 41.5% of the time vs 0%. It falls short on max drawdown and worst day on the holdout and on trade count in research.
- **BOT-A (passing LucidPro 50K) passes more often and faster, and busts less, in every split**, holdout included (17.9% vs 12.6% pass, 7.7% vs 12.6% bust). It beats or ties the current BOT-A on 31 of 42 cells at stress cost; the misses are trade-quality metrics (PF, expectancy, Sharpe, Sortino) and drawdown, mostly on the holdout.
- **Neither meets the brief of beating the current bots on every metric.** The search is exhausted under the rules: with the fresh holdout read, any more tuning would have no untouched test left.
- Mar-Nov 2026 was a losing stretch for every bot, baseline included (baseline A PF 0.97, baseline B PF 0.76 at stress).

## BOT-A (round 3) on LucidPro 50K

| Metric | Research base | Research stress | Validation base | Validation stress | Holdout base | Holdout stress |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 40.5% | 38.9% | 38.7% | 39.3% | 20.5% | 17.9% |
| Median days to pass | 15.00 | 15.00 | 13.00 | 14.00 | 11.50 | 12.50 |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 7.7% | 7.7% |
| P(first payout in 30d, funded) | 13.3% | 10.7% | 16.9% | 15.9% | 0.0% | 0.0% |
| Median days to first payout | 23.00 | 24.00 | 22.00 | 22.00 | n/a | n/a |
| 90-day EV net of fees and resets ($) | 158 | 107 | 297 | 246 | -257 | -273 |
| Profit factor | 1.49 | 1.50 | 1.45 | 1.52 | 0.80 | 0.88 |
| Expectancy (R) | 0.22 | 0.21 | 0.22 | 0.20 | -0.10 | -0.01 |
| Sharpe | 2.49 | 2.57 | 2.14 | 2.34 | -0.85 | -0.52 |
| Sortino | 5.37 | 5.52 | 4.65 | 5.51 | -1.44 | -0.88 |
| Max drawdown ($) | 2,581 | 2,775 | 3,043 | 3,016 | 4,739 | 3,341 |
| Worst day ($) | -640 | -627 | -640 | -637 | -648 | -642 |
| Consistency blocks per 30d | 0.61 | 0.57 | 0.71 | 0.66 | 0.87 | 0.89 |
| Trades a month | 30.04 | 30.27 | 27.71 | 28.09 | 10.03 | 10.95 |

Repo-format legs (strategies/python/*_t58.py, causal bar-count filter):

| Metric | Research base | Research stress | Validation base | Validation stress | Holdout base | Holdout stress |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 37.7% | 35.7% | 37.5% | 37.6% | 20.8% | 17.6% |
| Median days to pass | 16.00 | 16.00 | 14.00 | 14.00 | 13.00 | 13.00 |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 7.5% | 8.8% |
| P(first payout in 30d, funded) | 13.0% | 10.8% | 18.2% | 16.1% | 0.0% | 0.0% |
| Median days to first payout | 23.00 | 23.00 | 22.00 | 22.00 | n/a | n/a |
| 90-day EV net of fees and resets ($) | 140 | 81 | 310 | 300 | -245 | -268 |
| Profit factor | 1.42 | 1.42 | 1.45 | 1.44 | 1.35 | 0.83 |
| Expectancy (R) | 0.20 | 0.20 | 0.20 | 0.18 | 0.11 | -0.02 |
| Sharpe | 2.06 | 2.23 | 2.17 | 2.13 | 0.91 | -0.66 |
| Sortino | 4.41 | 4.62 | 4.73 | 4.71 | 2.45 | -1.11 |
| Max drawdown ($) | 7,399 | 3,398 | 2,644 | 2,563 | 2,438 | 6,574 |
| Worst day ($) | -649 | -633 | -640 | -637 | -624 | -646 |
| Consistency blocks per 30d | 0.56 | 0.54 | 0.61 | 0.56 | 1.02 | 0.94 |
| Trades a month | 28.61 | 30.88 | 29.21 | 29.13 | 12.34 | 9.57 |

## BOT-B (round 3) on LucidFlex 50K

| Metric | Research base | Research stress | Validation base | Validation stress | Holdout base | Holdout stress |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 3.1% | 2.3% | 8.4% | 8.1% | 0.0% | 0.0% |
| Median days to pass | 19.50 | 21.00 | 26.00 | 26.00 | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 54.1% | 49.4% | 49.2% | 47.3% | 24.0% | 24.0% |
| Median days to first payout | 20.00 | 19.00 | 20.00 | 19.00 | 22.00 | 22.00 |
| 90-day EV net of fees and resets ($) | -88 | -83 | 50 | -1 | -126 | -126 |
| Profit factor | 1.26 | 1.25 | 1.43 | 1.36 | 0.99 | 0.99 |
| Expectancy (R) | 0.19 | 0.17 | 0.24 | 0.20 | -0.01 | -0.01 |
| Sharpe | 1.57 | 1.48 | 2.40 | 2.06 | -0.02 | -0.03 |
| Sortino | 2.92 | 2.79 | 4.85 | 3.94 | -0.05 | -0.06 |
| Max drawdown ($) | 1,768 | 1,825 | 1,280 | 1,384 | 2,927 | 2,954 |
| Worst day ($) | -299 | -299 | -294 | -297 | -296 | -299 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 13.04 | 12.73 | 14.59 | 17.05 | 15.91 | 15.45 |
| Payouts in 90 funded days | 1.85 | 1.66 | 1.93 | 1.71 | 1.20 | 1.20 |
| $ paid in 90 funded days | 831 | 721 | 1,076 | 964 | 749 | 742 |
| P(2+ payouts in 90d) | 62.7% | 52.2% | 63.4% | 56.1% | 41.5% | 41.5% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Repo-format legs:

| Metric | Research base | Research stress | Validation base | Validation stress | Holdout base | Holdout stress |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 2.1% | 1.3% | 8.6% | 7.7% | 0.0% | 0.0% |
| Median days to pass | 19.00 | 19.00 | 27.00 | 27.00 | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 53.4% | 50.3% | 48.2% | 45.6% | 26.8% | 26.8% |
| Median days to first payout | 20.00 | 20.00 | 19.00 | 19.00 | 20.00 | 20.00 |
| 90-day EV net of fees and resets ($) | -48 | -84 | 23 | -8 | -126 | -126 |
| Profit factor | 1.28 | 1.22 | 1.40 | 1.46 | 1.13 | 1.00 |
| Expectancy (R) | 0.15 | 0.17 | 0.21 | 0.23 | 0.08 | -0.00 |
| Sharpe | 1.65 | 1.36 | 2.21 | 2.53 | 0.60 | 0.01 |
| Sortino | 3.09 | 2.50 | 4.37 | 5.18 | 1.17 | 0.03 |
| Max drawdown ($) | 2,196 | 2,258 | 1,322 | 1,362 | 1,655 | 2,550 |
| Worst day ($) | -299 | -295 | -298 | -296 | -295 | -300 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 10.48 | 13.81 | 14.39 | 15.74 | 20.29 | 16.03 |
| Payouts in 90 funded days | 1.83 | 1.66 | 1.81 | 1.72 | 1.26 | 1.24 |
| $ paid in 90 funded days | 837 | 712 | 1,026 | 931 | 765 | 789 |
| P(2+ payouts in 90d) | 60.0% | 54.0% | 58.8% | 55.8% | 40.5% | 40.5% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

## Monte Carlo (10,000 paths per row, stress cost)

Each path is 70 sessions resampled from the bot's own booked trade days (whole days kept together). FULL pool = 2020-01-01 .. 2026-03-01, OOS pool = 2024-01-01 .. 2026-03-01. The pools stop before the holdout so it is not reused. 'block' keeps 10-session runs (volatility clustering); 'reshuffle' draws days independently. The 90-day EV pays for an evaluation and runs the bot through it, so it is negative for BOT-B by design (B is a funded-account bot).

| Bot | Pool | Resampler | P(pass in 30d) | Median days to pass | Eval bust | P(first payout in 30d) | Median days to payout | 90-day EV (5th to 95th pct) |
|---|---|---|---|---|---|---|---|---|
| baseline_A | FULL | reshuffle | 21.5% | 22 | 1.3% | 9.6% | 23 | -82 (-292 to 870) |
| baseline_A | FULL | block | 19.8% | 22 | 1.2% | 7.7% | 24 | -115 (-292 to 633) |
| baseline_A | OOS | reshuffle | 25.8% | 19 | 2.2% | 9.6% | 23 | -47 (-292 to 1,230) |
| baseline_A | OOS | block | 25.4% | 18 | 2.2% | 9.8% | 23 | -34 (-292 to 1,249) |
| BOT-A-R3 | FULL | reshuffle | 37.8% | 12 | 0.0% | 16.6% | 22 | 137 (-292 to 1,764) |
| BOT-A-R3 | FULL | block | 38.4% | 15 | 0.0% | 13.3% | 23 | 104 (-292 to 1,628) |
| BOT-A-R3 | OOS | reshuffle | 36.9% | 12 | 0.1% | 16.4% | 22 | 147 (-292 to 2,024) |
| BOT-A-R3 | OOS | block | 37.8% | 12 | 0.0% | 14.3% | 22 | 106 (-292 to 1,628) |
| BOT-A-R3-port | FULL | reshuffle | 35.2% | 12 | 0.0% | 14.9% | 22 | 97 (-292 to 1,628) |
| BOT-A-R3-port | FULL | block | 35.3% | 15 | 0.0% | 12.4% | 23 | 65 (-292 to 1,628) |
| BOT-A-R3-port | OOS | reshuffle | 36.9% | 12 | 0.0% | 17.1% | 22 | 118 (-292 to 1,743) |
| BOT-A-R3-port | OOS | block | 37.9% | 12 | 0.0% | 14.9% | 23 | 90 (-292 to 1,628) |
| baseline_B | FULL | reshuffle | 0.4% | 30 | 0.0% | 15.1% | 24 | -114 (-126 to -126) |
| baseline_B | FULL | block | 0.1% | 30 | 0.0% | 16.4% | 24 | -123 (-126 to -126) |
| baseline_B | OOS | reshuffle | 0.1% | 29 | 0.0% | 9.5% | 24 | -119 (-126 to -126) |
| baseline_B | OOS | block | 0.0% | 30 | 0.0% | 11.4% | 24 | -125 (-126 to -126) |
| BOT-B-R3 | FULL | reshuffle | 4.6% | 23 | 0.0% | 48.5% | 18 | -44 (-126 to 558) |
| BOT-B-R3 | FULL | block | 3.7% | 24 | 0.0% | 48.7% | 18 | -67 (-126 to 390) |
| BOT-B-R3 | OOS | reshuffle | 4.5% | 23 | 0.0% | 46.8% | 19 | -48 (-126 to 543) |
| BOT-B-R3 | OOS | block | 5.5% | 24 | 0.0% | 46.6% | 19 | -35 (-126 to 612) |
| BOT-B-R3-port | FULL | reshuffle | 4.3% | 23 | 0.0% | 48.3% | 18 | -51 (-126 to 503) |
| BOT-B-R3-port | FULL | block | 3.2% | 24 | 0.0% | 47.6% | 18 | -70 (-126 to 364) |
| BOT-B-R3-port | OOS | reshuffle | 4.1% | 23 | 0.0% | 46.3% | 19 | -53 (-126 to 501) |
| BOT-B-R3-port | OOS | block | 4.7% | 25 | 0.0% | 46.2% | 19 | -47 (-126 to 555) |

## Disclosures

- No single leg passed the Deflated Sharpe gate (research/gate_ladder_log.md). Acceptance rests on research-to-validation replication at stress cost, and the holdout.
- The research leg factory skipped days with fewer than 80% of RTH bars over the whole day, which a live bot cannot know at entry (a mild lookahead). The repo-format legs check only the bars up to the signal; their rows are shown above, and they are what the zip ships.
- The Sep 2025 .. Feb 2026 window was read as a holdout in rounds 1 and 2 before joining validation in round 3.
- The Python ports of IR_NQ, CDL and Open Drive are the repo's own files. The Pine port leaves out IR_NQ and the cross-instrument cap.
