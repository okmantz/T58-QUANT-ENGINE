# T58 final bots: comparison report (2026-11-24)

Research code only. Nothing in this work placed, changed or cancelled an order, signed in to a prop firm, broker or exchange, or created
an alert. Every number comes from one engine (research/t58_final_bots/engine): the repo's own strategy files for the existing legs,
next-bar-open fills, stops filled at the stop price plus slippage, Lucid 50K rules simulated by firm.py. Costs: base = $3.50 a side on
ES/NQ ($4.60 GC; micros $1.00 / $1.60) plus 1 tick a side; stress = 1.5x both (the cost every pick was chosen on).
Splits: research 2020-01-01 .. 2023-12-31, validation 2024-01-01 .. 2026-03-01, holdout 2026-03-02 .. 2026-11-20 (Owen's Mar-Nov 2026
files, sealed until the picks were frozen and read exactly once). Pass and payout metrics are averaged over rolling account starts
in the split; trade metrics (PF, expectancy, Sharpe, drawdown, worst day, trades a month) cover the whole split.

Baselines are the current bots in the repo (PRESET_REV 5): baseline_A on LucidPro 50K, baseline_B on LucidFlex 50K. A pick passes only if it beats or ties its baseline on every metric in every split. ✗ marks a shortfall.

## Shortfall count per pick (cells where the pick is worse than its baseline)

| Bot | Plan | Research | Validation | Holdout | Total short (stress) | Total short (base) |
|---|---|---|---|---|---|---|
| BOT-A-R3 | pro50 | 3 | 1 | 7 | 11 of 42 | 17 of 42 |
| BOT-A-R3-port | pro50 | 5 | 4 | 8 | 17 of 42 | 16 of 42 |
| BOT-A-R1 | pro50 | 6 | 4 | 8 | 18 of 42 | 13 of 42 |
| BOT-B-R3 | flex50 | 1 | 0 | 2 | 3 of 54 | 6 of 54 |
| BOT-B-R3-port | flex50 | 2 | 0 | 2 | 4 of 54 | 8 of 54 |
| BOT-B-R2 | flex50 | 1 | 1 | 3 | 5 of 54 | 5 of 54 |
| BOT-B-R1 | flex50 | 1 | 4 | 5 | 10 of 54 | 14 of 54 |

R1 = round 1, R2 = round 2, R3 = round 3 (the final picks). -port = R3 pick on the repo-format leg files.

## Why these picks

- BOT-A-R3 has the fewest stress-cost shortfalls of 784 A variants (research/bot_trials_r3.csv) and keeps A's own objective, P(pass), well above baseline. Round-1 A had 18 stress shortfalls over the three splits; R3 has 11.
- BOT-B-R3 was the B variant clean on both validation cells at full detail, with the fewest shortfalls overall (3 of 54 at stress).
- Honest caveat: on the Mar-Nov 2026 holdout, round-2 B did better than round-3 B on its own objective too (first payout 26.3% vs 24.0%, $858 vs $742 paid in 90 funded days, PF 1.28 vs 0.99, max drawdown $1,531 vs $2,954). It has more shortfalls overall (5 of 54: validation trade count and holdout days to payout, drawdown and worst day). Switching to it now would be choosing on the holdout, so R3 stays the pick; R2 (BOT-B/params_r2.json) is the lower-drawdown alternative if drawdown matters more to you.
- Top 5 per objective: research/top5_per_objective_r3.csv.

## Full tables

### BOT-A-R3 vs baseline_A (pro50, stress cost)

| Metric | Research base | Research BOT-A-R3 | Validation base | Validation BOT-A-R3 | Holdout base | Holdout BOT-A-R3 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.1% | 38.9% | 25.3% | 39.3% | 12.6% | 17.9% |
| Median days to pass | 23.00 | 15.00 | 20.00 | 14.00 | 13.00 | 12.50 |
| Eval bust | 0.8% | 0.0% | 1.7% | 0.0% | 12.6% | 7.7% |
| P(first payout in 30d, funded) | 5.4% | 10.7% | 10.4% | 15.9% | 0.0% | 0.0% |
| Median days to first payout | 22.00 | 24.00 ✗ | 23.00 | 22.00 | n/a | n/a |
| 90-day EV net of fees and resets ($) | -160 | 107 | 119 | 246 | -260 | -273 ✗ |
| Profit factor | 1.53 | 1.50 ✗ | 1.51 | 1.52 | 0.97 | 0.88 ✗ |
| Expectancy (R) | 0.18 | 0.21 | 0.24 | 0.20 ✗ | 0.08 | -0.01 ✗ |
| Sharpe | 2.50 | 2.57 | 2.27 | 2.34 | -0.15 | -0.52 ✗ |
| Sortino | 5.44 | 5.52 | 4.75 | 5.51 | -0.26 | -0.88 ✗ |
| Max drawdown ($) | 3,502 | 2,775 | 6,041 | 3,016 | 3,141 | 3,341 ✗ |
| Worst day ($) | -691 | -627 | -977 | -637 | -790 | -642 |
| Consistency blocks per 30d | 0.38 | 0.57 ✗ | 1.14 | 0.66 | 0.70 | 0.89 ✗ |
| Trades a month | 17.63 | 30.27 | 17.51 | 28.09 | 10.15 | 10.95 |

Shortfalls (11): research Median days to first payout 22.00 -> 24.00; holdout 90-day EV net of fees and resets ($) -260 -> -273; research Profit factor 1.53 -> 1.50; holdout Profit factor 0.97 -> 0.88; validation Expectancy (R) 0.24 -> 0.20; holdout Expectancy (R) 0.08 -> -0.01; holdout Sharpe -0.15 -> -0.52; holdout Sortino -0.26 -> -0.88; holdout Max drawdown ($) 3,141 -> 3,341; research Consistency blocks per 30d 0.38 -> 0.57; holdout Consistency blocks per 30d 0.70 -> 0.89

### BOT-A-R3 vs baseline_A (pro50, base cost)

| Metric | Research base | Research BOT-A-R3 | Validation base | Validation BOT-A-R3 | Holdout base | Holdout BOT-A-R3 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.8% | 40.5% | 27.6% | 38.7% | 11.9% | 20.5% |
| Median days to pass | 23.00 | 15.00 | 20.00 | 13.00 | 12.00 | 11.50 |
| Eval bust | 0.8% | 0.0% | 3.0% | 0.0% | 11.9% | 7.7% |
| P(first payout in 30d, funded) | 5.8% | 13.3% | 11.0% | 16.9% | 2.2% | 0.0% ✗ |
| Median days to first payout | 22.00 | 23.00 ✗ | 22.00 | 22.00 | 27.00 | n/a ✗ |
| 90-day EV net of fees and resets ($) | -137 | 158 | 137 | 297 | -255 | -257 ✗ |
| Profit factor | 1.53 | 1.49 ✗ | 1.51 | 1.45 ✗ | 1.09 | 0.80 ✗ |
| Expectancy (R) | 0.19 | 0.22 | 0.23 | 0.22 ✗ | 0.12 | -0.10 ✗ |
| Sharpe | 2.56 | 2.49 ✗ | 2.27 | 2.14 ✗ | 0.36 | -0.85 ✗ |
| Sortino | 5.40 | 5.37 ✗ | 4.73 | 4.65 ✗ | 0.68 | -1.44 ✗ |
| Max drawdown ($) | 2,935 | 2,581 | 6,010 | 3,043 | 2,402 | 4,739 ✗ |
| Worst day ($) | -722 | -640 | -974 | -640 | -733 | -648 |
| Consistency blocks per 30d | 0.42 | 0.61 ✗ | 1.17 | 0.71 | 0.90 | 0.87 |
| Trades a month | 17.23 | 30.04 | 17.51 | 27.71 | 9.57 | 10.03 |

Shortfalls (17): holdout P(first payout in 30d, funded) 2.2% -> 0.0%; research Median days to first payout 22.00 -> 23.00; holdout Median days to first payout 27.00 -> n/a; holdout 90-day EV net of fees and resets ($) -255 -> -257; research Profit factor 1.53 -> 1.49; validation Profit factor 1.51 -> 1.45; holdout Profit factor 1.09 -> 0.80; validation Expectancy (R) 0.23 -> 0.22; holdout Expectancy (R) 0.12 -> -0.10; research Sharpe 2.56 -> 2.49; validation Sharpe 2.27 -> 2.14; holdout Sharpe 0.36 -> -0.85; research Sortino 5.40 -> 5.37; validation Sortino 4.73 -> 4.65; holdout Sortino 0.68 -> -1.44; holdout Max drawdown ($) 2,402 -> 4,739; research Consistency blocks per 30d 0.42 -> 0.61

### BOT-A-R3-port vs baseline_A (pro50, stress cost)

| Metric | Research base | Research BOT-A-R3-port | Validation base | Validation BOT-A-R3-port | Holdout base | Holdout BOT-A-R3-port |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.1% | 35.7% | 25.3% | 37.6% | 12.6% | 17.6% |
| Median days to pass | 23.00 | 16.00 | 20.00 | 14.00 | 13.00 | 13.00 |
| Eval bust | 0.8% | 0.0% | 1.7% | 0.0% | 12.6% | 8.8% |
| P(first payout in 30d, funded) | 5.4% | 10.8% | 10.4% | 16.1% | 0.0% | 0.0% |
| Median days to first payout | 22.00 | 23.00 ✗ | 23.00 | 22.00 | n/a | n/a |
| 90-day EV net of fees and resets ($) | -160 | 81 | 119 | 300 | -260 | -268 ✗ |
| Profit factor | 1.53 | 1.42 ✗ | 1.51 | 1.44 ✗ | 0.97 | 0.83 ✗ |
| Expectancy (R) | 0.18 | 0.20 | 0.24 | 0.18 ✗ | 0.08 | -0.02 ✗ |
| Sharpe | 2.50 | 2.23 ✗ | 2.27 | 2.13 ✗ | -0.15 | -0.66 ✗ |
| Sortino | 5.44 | 4.62 ✗ | 4.75 | 4.71 ✗ | -0.26 | -1.11 ✗ |
| Max drawdown ($) | 3,502 | 3,398 | 6,041 | 2,563 | 3,141 | 6,574 ✗ |
| Worst day ($) | -691 | -633 | -977 | -637 | -790 | -646 |
| Consistency blocks per 30d | 0.38 | 0.54 ✗ | 1.14 | 0.56 | 0.70 | 0.94 ✗ |
| Trades a month | 17.63 | 30.88 | 17.51 | 29.13 | 10.15 | 9.57 ✗ |

Shortfalls (17): research Median days to first payout 22.00 -> 23.00; holdout 90-day EV net of fees and resets ($) -260 -> -268; research Profit factor 1.53 -> 1.42; validation Profit factor 1.51 -> 1.44; holdout Profit factor 0.97 -> 0.83; validation Expectancy (R) 0.24 -> 0.18; holdout Expectancy (R) 0.08 -> -0.02; research Sharpe 2.50 -> 2.23; validation Sharpe 2.27 -> 2.13; holdout Sharpe -0.15 -> -0.66; research Sortino 5.44 -> 4.62; validation Sortino 4.75 -> 4.71; holdout Sortino -0.26 -> -1.11; holdout Max drawdown ($) 3,141 -> 6,574; research Consistency blocks per 30d 0.38 -> 0.54; holdout Consistency blocks per 30d 0.70 -> 0.94; holdout Trades a month 10.15 -> 9.57

### BOT-A-R3-port vs baseline_A (pro50, base cost)

| Metric | Research base | Research BOT-A-R3-port | Validation base | Validation BOT-A-R3-port | Holdout base | Holdout BOT-A-R3-port |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.8% | 37.7% | 27.6% | 37.5% | 11.9% | 20.8% |
| Median days to pass | 23.00 | 16.00 | 20.00 | 14.00 | 12.00 | 13.00 ✗ |
| Eval bust | 0.8% | 0.0% | 3.0% | 0.0% | 11.9% | 7.5% |
| P(first payout in 30d, funded) | 5.8% | 13.0% | 11.0% | 18.2% | 2.2% | 0.0% ✗ |
| Median days to first payout | 22.00 | 23.00 ✗ | 22.00 | 22.00 | 27.00 | n/a ✗ |
| 90-day EV net of fees and resets ($) | -137 | 140 | 137 | 310 | -255 | -245 |
| Profit factor | 1.53 | 1.42 ✗ | 1.51 | 1.45 ✗ | 1.09 | 1.35 |
| Expectancy (R) | 0.19 | 0.20 | 0.23 | 0.20 ✗ | 0.12 | 0.11 ✗ |
| Sharpe | 2.56 | 2.06 ✗ | 2.27 | 2.17 ✗ | 0.36 | 0.91 |
| Sortino | 5.40 | 4.41 ✗ | 4.73 | 4.73 ✗ | 0.68 | 2.45 |
| Max drawdown ($) | 2,935 | 7,399 ✗ | 6,010 | 2,644 | 2,402 | 2,438 ✗ |
| Worst day ($) | -722 | -649 | -974 | -640 | -733 | -624 |
| Consistency blocks per 30d | 0.42 | 0.56 ✗ | 1.17 | 0.61 | 0.90 | 1.02 ✗ |
| Trades a month | 17.23 | 28.61 | 17.51 | 29.21 | 9.57 | 12.34 |

Shortfalls (16): holdout Median days to pass 12.00 -> 13.00; holdout P(first payout in 30d, funded) 2.2% -> 0.0%; research Median days to first payout 22.00 -> 23.00; holdout Median days to first payout 27.00 -> n/a; research Profit factor 1.53 -> 1.42; validation Profit factor 1.51 -> 1.45; validation Expectancy (R) 0.23 -> 0.20; holdout Expectancy (R) 0.12 -> 0.11; research Sharpe 2.56 -> 2.06; validation Sharpe 2.27 -> 2.17; research Sortino 5.40 -> 4.41; validation Sortino 4.73 -> 4.73; research Max drawdown ($) 2,935 -> 7,399; holdout Max drawdown ($) 2,402 -> 2,438; research Consistency blocks per 30d 0.42 -> 0.56; holdout Consistency blocks per 30d 0.90 -> 1.02

### BOT-A-R1 vs baseline_A (pro50, stress cost)

| Metric | Research base | Research BOT-A-R1 | Validation base | Validation BOT-A-R1 | Holdout base | Holdout BOT-A-R1 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.1% | 39.1% | 25.3% | 35.1% | 12.6% | 19.6% |
| Median days to pass | 23.00 | 18.00 | 20.00 | 13.00 | 13.00 | 9.00 |
| Eval bust | 0.8% | 0.0% | 1.7% | 0.0% | 12.6% | 8.1% |
| P(first payout in 30d, funded) | 5.4% | 9.0% | 10.4% | 13.5% | 0.0% | 0.0% |
| Median days to first payout | 22.00 | 24.00 ✗ | 23.00 | 22.00 | n/a | n/a |
| 90-day EV net of fees and resets ($) | -160 | 123 | 119 | 125 | -260 | -279 ✗ |
| Profit factor | 1.53 | 1.50 ✗ | 1.51 | 1.43 ✗ | 0.97 | 0.80 ✗ |
| Expectancy (R) | 0.18 | 0.22 | 0.24 | 0.19 ✗ | 0.08 | -0.02 ✗ |
| Sharpe | 2.50 | 2.32 ✗ | 2.27 | 1.79 ✗ | -0.15 | -0.92 ✗ |
| Sortino | 5.44 | 5.05 ✗ | 4.75 | 4.00 ✗ | -0.26 | -1.42 ✗ |
| Max drawdown ($) | 3,502 | 3,911 ✗ | 6,041 | 4,789 | 3,141 | 3,977 ✗ |
| Worst day ($) | -691 | -627 | -977 | -646 | -790 | -615 |
| Consistency blocks per 30d | 0.38 | 0.59 ✗ | 1.14 | 0.48 | 0.70 | 1.11 ✗ |
| Trades a month | 17.63 | 24.42 | 17.51 | 20.67 | 10.15 | 9.92 ✗ |

Shortfalls (18): research Median days to first payout 22.00 -> 24.00; holdout 90-day EV net of fees and resets ($) -260 -> -279; research Profit factor 1.53 -> 1.50; validation Profit factor 1.51 -> 1.43; holdout Profit factor 0.97 -> 0.80; validation Expectancy (R) 0.24 -> 0.19; holdout Expectancy (R) 0.08 -> -0.02; research Sharpe 2.50 -> 2.32; validation Sharpe 2.27 -> 1.79; holdout Sharpe -0.15 -> -0.92; research Sortino 5.44 -> 5.05; validation Sortino 4.75 -> 4.00; holdout Sortino -0.26 -> -1.42; research Max drawdown ($) 3,502 -> 3,911; holdout Max drawdown ($) 3,141 -> 3,977; research Consistency blocks per 30d 0.38 -> 0.59; holdout Consistency blocks per 30d 0.70 -> 1.11; holdout Trades a month 10.15 -> 9.92

### BOT-A-R1 vs baseline_A (pro50, base cost)

| Metric | Research base | Research BOT-A-R1 | Validation base | Validation BOT-A-R1 | Holdout base | Holdout BOT-A-R1 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.8% | 41.0% | 27.6% | 35.5% | 11.9% | 18.2% |
| Median days to pass | 23.00 | 17.00 | 20.00 | 13.00 | 12.00 | 9.00 |
| Eval bust | 0.8% | 0.0% | 3.0% | 0.0% | 11.9% | 8.1% |
| P(first payout in 30d, funded) | 5.8% | 11.8% | 11.0% | 15.1% | 2.2% | 0.0% ✗ |
| Median days to first payout | 22.00 | 23.00 ✗ | 22.00 | 22.00 | 27.00 | n/a ✗ |
| 90-day EV net of fees and resets ($) | -137 | 207 | 137 | 152 | -255 | -288 ✗ |
| Profit factor | 1.53 | 1.59 | 1.51 | 1.54 | 1.09 | 0.58 ✗ |
| Expectancy (R) | 0.19 | 0.24 | 0.23 | 0.23 | 0.12 | -0.07 ✗ |
| Sharpe | 2.56 | 2.73 | 2.27 | 1.97 ✗ | 0.36 | -2.05 ✗ |
| Sortino | 5.40 | 6.19 | 4.73 | 4.77 | 0.68 | -2.73 ✗ |
| Max drawdown ($) | 2,935 | 2,857 | 6,010 | 3,216 | 2,402 | 5,152 ✗ |
| Worst day ($) | -722 | -640 | -974 | -634 | -733 | -609 |
| Consistency blocks per 30d | 0.42 | 0.63 ✗ | 1.17 | 0.56 | 0.90 | 1.14 ✗ |
| Trades a month | 17.23 | 25.86 | 17.51 | 19.20 | 9.57 | 8.30 ✗ |

Shortfalls (13): holdout P(first payout in 30d, funded) 2.2% -> 0.0%; research Median days to first payout 22.00 -> 23.00; holdout Median days to first payout 27.00 -> n/a; holdout 90-day EV net of fees and resets ($) -255 -> -288; holdout Profit factor 1.09 -> 0.58; holdout Expectancy (R) 0.12 -> -0.07; validation Sharpe 2.27 -> 1.97; holdout Sharpe 0.36 -> -2.05; holdout Sortino 0.68 -> -2.73; holdout Max drawdown ($) 2,402 -> 5,152; research Consistency blocks per 30d 0.42 -> 0.63; holdout Consistency blocks per 30d 0.90 -> 1.14; holdout Trades a month 9.57 -> 8.30

### BOT-B-R3 vs baseline_B (flex50, stress cost)

| Metric | Research base | Research BOT-B-R3 | Validation base | Validation BOT-B-R3 | Holdout base | Holdout BOT-B-R3 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 2.3% | 0.0% | 8.1% | 0.0% | 0.0% |
| Median days to pass | 30.00 | 21.00 | n/a | 26.00 | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 19.0% | 49.4% | 12.0% | 47.3% | 9.7% | 24.0% |
| Median days to first payout | 25.00 | 19.00 | 23.00 | 19.00 | 22.00 | 22.00 |
| 90-day EV net of fees and resets ($) | -133 | -83 | -136 | -1 | -130 | -126 |
| Profit factor | 1.17 | 1.25 | 1.24 | 1.36 | 0.76 | 0.99 |
| Expectancy (R) | 0.09 | 0.17 | 0.11 | 0.20 | -0.08 | -0.01 |
| Sharpe | 0.85 | 1.48 | 1.06 | 2.06 | -1.21 | -0.03 |
| Sortino | 1.56 | 2.79 | 2.03 | 3.94 | -1.91 | -0.06 |
| Max drawdown ($) | 2,011 | 1,825 | 1,628 | 1,384 | 1,329 | 2,954 ✗ |
| Worst day ($) | -324 | -299 | -311 | -297 | -162 | -299 ✗ |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 18.06 | 12.73 ✗ | 15.16 | 17.05 | 9.34 | 15.45 |
| Payouts in 90 funded days | 1.01 | 1.66 | 0.94 | 1.71 | 0.45 | 1.20 |
| $ paid in 90 funded days | 365 | 721 | 367 | 964 | 161 | 742 |
| P(2+ payouts in 90d) | 22.9% | 52.2% | 15.3% | 56.1% | 0.0% | 41.5% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Shortfalls (3): holdout Max drawdown ($) 1,329 -> 2,954; holdout Worst day ($) -162 -> -299; research Trades a month 18.06 -> 12.73

### BOT-B-R3 vs baseline_B (flex50, base cost)

| Metric | Research base | Research BOT-B-R3 | Validation base | Validation BOT-B-R3 | Holdout base | Holdout BOT-B-R3 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 3.1% | 0.0% | 8.4% | 0.0% | 0.0% |
| Median days to pass | 29.00 | 19.50 | n/a | 26.00 | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 21.6% | 54.1% | 13.5% | 49.2% | 11.7% | 24.0% |
| Median days to first payout | 25.00 | 20.00 | 23.00 | 20.00 | 19.00 | 22.00 ✗ |
| 90-day EV net of fees and resets ($) | -132 | -88 | -136 | 50 | -133 | -126 |
| Profit factor | 1.28 | 1.26 ✗ | 1.42 | 1.43 | 0.69 | 0.99 |
| Expectancy (R) | 0.16 | 0.19 | 0.18 | 0.24 | -0.12 | -0.01 |
| Sharpe | 1.37 | 1.57 | 1.72 | 2.40 | -1.45 | -0.02 |
| Sortino | 2.82 | 2.92 | 3.50 | 4.85 | -2.19 | -0.05 |
| Max drawdown ($) | 1,245 | 1,768 ✗ | 1,620 | 1,280 | 1,300 | 2,927 ✗ |
| Worst day ($) | -298 | -299 ✗ | -304 | -294 | -160 | -296 ✗ |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 8.67 | 13.04 | 11.58 | 14.59 | 7.61 | 15.91 |
| Payouts in 90 funded days | 1.11 | 1.85 | 1.02 | 1.93 | 0.50 | 1.20 |
| $ paid in 90 funded days | 406 | 831 | 418 | 1,076 | 189 | 749 |
| P(2+ payouts in 90d) | 31.6% | 62.7% | 16.6% | 63.4% | 0.0% | 41.5% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Shortfalls (6): holdout Median days to first payout 19.00 -> 22.00; research Profit factor 1.28 -> 1.26; research Max drawdown ($) 1,245 -> 1,768; holdout Max drawdown ($) 1,300 -> 2,927; research Worst day ($) -298 -> -299; holdout Worst day ($) -160 -> -296

### BOT-B-R3-port vs baseline_B (flex50, stress cost)

| Metric | Research base | Research BOT-B-R3-port | Validation base | Validation BOT-B-R3-port | Holdout base | Holdout BOT-B-R3-port |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 1.3% | 0.0% | 7.7% | 0.0% | 0.0% |
| Median days to pass | 30.00 | 19.00 | n/a | 27.00 | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 19.0% | 50.3% | 12.0% | 45.6% | 9.7% | 26.8% |
| Median days to first payout | 25.00 | 20.00 | 23.00 | 19.00 | 22.00 | 20.00 |
| 90-day EV net of fees and resets ($) | -133 | -84 | -136 | -8 | -130 | -126 |
| Profit factor | 1.17 | 1.22 | 1.24 | 1.46 | 0.76 | 1.00 |
| Expectancy (R) | 0.09 | 0.17 | 0.11 | 0.23 | -0.08 | -0.00 |
| Sharpe | 0.85 | 1.36 | 1.06 | 2.53 | -1.21 | 0.01 |
| Sortino | 1.56 | 2.50 | 2.03 | 5.18 | -1.91 | 0.03 |
| Max drawdown ($) | 2,011 | 2,258 ✗ | 1,628 | 1,362 | 1,329 | 2,550 ✗ |
| Worst day ($) | -324 | -295 | -311 | -296 | -162 | -300 ✗ |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 18.06 | 13.81 ✗ | 15.16 | 15.74 | 9.34 | 16.03 |
| Payouts in 90 funded days | 1.01 | 1.66 | 0.94 | 1.72 | 0.45 | 1.24 |
| $ paid in 90 funded days | 365 | 712 | 367 | 931 | 161 | 789 |
| P(2+ payouts in 90d) | 22.9% | 54.0% | 15.3% | 55.8% | 0.0% | 40.5% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Shortfalls (4): research Max drawdown ($) 2,011 -> 2,258; holdout Max drawdown ($) 1,329 -> 2,550; holdout Worst day ($) -162 -> -300; research Trades a month 18.06 -> 13.81

### BOT-B-R3-port vs baseline_B (flex50, base cost)

| Metric | Research base | Research BOT-B-R3-port | Validation base | Validation BOT-B-R3-port | Holdout base | Holdout BOT-B-R3-port |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 2.1% | 0.0% | 8.6% | 0.0% | 0.0% |
| Median days to pass | 29.00 | 19.00 | n/a | 27.00 | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 21.6% | 53.4% | 13.5% | 48.2% | 11.7% | 26.8% |
| Median days to first payout | 25.00 | 20.00 | 23.00 | 19.00 | 19.00 | 20.00 ✗ |
| 90-day EV net of fees and resets ($) | -132 | -48 | -136 | 23 | -133 | -126 |
| Profit factor | 1.28 | 1.28 ✗ | 1.42 | 1.40 ✗ | 0.69 | 1.13 |
| Expectancy (R) | 0.16 | 0.15 ✗ | 0.18 | 0.21 | -0.12 | 0.08 |
| Sharpe | 1.37 | 1.65 | 1.72 | 2.21 | -1.45 | 0.60 |
| Sortino | 2.82 | 3.09 | 3.50 | 4.37 | -2.19 | 1.17 |
| Max drawdown ($) | 1,245 | 2,196 ✗ | 1,620 | 1,322 | 1,300 | 1,655 ✗ |
| Worst day ($) | -298 | -299 ✗ | -304 | -298 | -160 | -295 ✗ |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 8.67 | 10.48 | 11.58 | 14.39 | 7.61 | 20.29 |
| Payouts in 90 funded days | 1.11 | 1.83 | 1.02 | 1.81 | 0.50 | 1.26 |
| $ paid in 90 funded days | 406 | 837 | 418 | 1,026 | 189 | 765 |
| P(2+ payouts in 90d) | 31.6% | 60.0% | 16.6% | 58.8% | 0.0% | 40.5% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Shortfalls (8): holdout Median days to first payout 19.00 -> 20.00; research Profit factor 1.28 -> 1.28; validation Profit factor 1.42 -> 1.40; research Expectancy (R) 0.16 -> 0.15; research Max drawdown ($) 1,245 -> 2,196; holdout Max drawdown ($) 1,300 -> 1,655; research Worst day ($) -298 -> -299; holdout Worst day ($) -160 -> -295

### BOT-B-R2 vs baseline_B (flex50, stress cost)

| Metric | Research base | Research BOT-B-R2 | Validation base | Validation BOT-B-R2 | Holdout base | Holdout BOT-B-R2 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 1.2% | 0.0% | 0.0% | 0.0% | 0.0% |
| Median days to pass | 30.00 | 28.00 | n/a | n/a | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 19.0% | 49.0% | 12.0% | 44.2% | 9.7% | 26.2% |
| Median days to first payout | 25.00 | 21.00 | 23.00 | 20.00 | 22.00 | 23.00 ✗ |
| 90-day EV net of fees and resets ($) | -133 | -106 | -136 | -90 | -130 | -126 |
| Profit factor | 1.17 | 1.31 | 1.24 | 1.62 | 0.76 | 1.28 |
| Expectancy (R) | 0.09 | 0.19 | 0.11 | 0.28 | -0.08 | 0.07 |
| Sharpe | 0.85 | 1.61 | 1.06 | 2.83 | -1.21 | 0.94 |
| Sortino | 1.56 | 3.02 | 2.03 | 6.37 | -1.91 | 2.53 |
| Max drawdown ($) | 2,011 | 1,213 | 1,628 | 1,182 | 1,329 | 1,531 ✗ |
| Worst day ($) | -324 | -219 | -311 | -220 | -162 | -217 ✗ |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 18.06 | 6.50 ✗ | 15.16 | 10.16 ✗ | 9.34 | 15.80 |
| Payouts in 90 funded days | 1.01 | 1.77 | 0.94 | 1.81 | 0.45 | 0.88 |
| $ paid in 90 funded days | 365 | 795 | 367 | 756 | 161 | 858 |
| P(2+ payouts in 90d) | 22.9% | 59.8% | 15.3% | 61.6% | 0.0% | 7.5% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Shortfalls (5): holdout Median days to first payout 22.00 -> 23.00; holdout Max drawdown ($) 1,329 -> 1,531; holdout Worst day ($) -162 -> -217; research Trades a month 18.06 -> 6.50; validation Trades a month 15.16 -> 10.16

### BOT-B-R2 vs baseline_B (flex50, base cost)

| Metric | Research base | Research BOT-B-R2 | Validation base | Validation BOT-B-R2 | Holdout base | Holdout BOT-B-R2 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 1.2% | 0.0% | 0.0% | 0.0% | 0.0% |
| Median days to pass | 29.00 | 25.00 | n/a | n/a | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 21.6% | 51.6% | 13.5% | 43.8% | 11.7% | 26.9% |
| Median days to first payout | 25.00 | 21.00 | 23.00 | 20.00 | 19.00 | 23.00 ✗ |
| 90-day EV net of fees and resets ($) | -132 | -62 | -136 | -80 | -133 | -126 |
| Profit factor | 1.28 | 1.35 | 1.42 | 1.54 | 0.69 | 1.30 |
| Expectancy (R) | 0.16 | 0.20 | 0.18 | 0.29 | -0.12 | 0.09 |
| Sharpe | 1.37 | 1.76 | 1.72 | 2.55 | -1.45 | 1.02 |
| Sortino | 2.82 | 3.34 | 3.50 | 5.52 | -2.19 | 2.75 |
| Max drawdown ($) | 1,245 | 1,189 | 1,620 | 1,173 | 1,300 | 1,515 ✗ |
| Worst day ($) | -298 | -220 | -304 | -219 | -160 | -217 ✗ |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 8.67 | 6.27 ✗ | 11.58 | 9.81 ✗ | 7.61 | 16.14 |
| Payouts in 90 funded days | 1.11 | 1.92 | 1.02 | 1.91 | 0.50 | 0.88 |
| $ paid in 90 funded days | 406 | 935 | 418 | 849 | 189 | 889 |
| P(2+ payouts in 90d) | 31.6% | 62.1% | 16.6% | 65.4% | 0.0% | 10.0% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Shortfalls (5): holdout Median days to first payout 19.00 -> 23.00; holdout Max drawdown ($) 1,300 -> 1,515; holdout Worst day ($) -160 -> -217; research Trades a month 8.67 -> 6.27; validation Trades a month 11.58 -> 9.81

### BOT-B-R1 vs baseline_B (flex50, stress cost)

| Metric | Research base | Research BOT-B-R1 | Validation base | Validation BOT-B-R1 | Holdout base | Holdout BOT-B-R1 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 0.1% | 0.0% | 0.0% | 0.0% | 0.0% |
| Median days to pass | 30.00 | 30.00 | n/a | n/a | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 19.0% | 47.9% | 12.0% | 34.1% | 9.7% | 7.5% ✗ |
| Median days to first payout | 25.00 | 24.00 | 23.00 | 24.50 ✗ | 22.00 | 26.50 ✗ |
| 90-day EV net of fees and resets ($) | -133 | -115 | -136 | -140 ✗ | -130 | -139 ✗ |
| Profit factor | 1.17 | 1.37 | 1.24 | 1.33 | 0.76 | 1.18 |
| Expectancy (R) | 0.09 | 0.24 | 0.11 | 0.23 | -0.08 | 0.08 |
| Sharpe | 0.85 | 2.06 | 1.06 | 1.70 | -1.21 | 0.71 |
| Sortino | 1.56 | 4.01 | 2.03 | 3.48 | -1.91 | 1.84 |
| Max drawdown ($) | 2,011 | 1,411 | 1,628 | 2,118 ✗ | 1,329 | 1,758 ✗ |
| Worst day ($) | -324 | -219 | -311 | -219 | -162 | -220 ✗ |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 18.06 | 6.81 ✗ | 15.16 | 10.12 ✗ | 9.34 | 15.45 |
| Payouts in 90 funded days | 1.01 | 1.84 | 0.94 | 1.37 | 0.45 | 0.76 |
| $ paid in 90 funded days | 365 | 875 | 367 | 473 | 161 | 516 |
| P(2+ payouts in 90d) | 22.9% | 61.6% | 15.3% | 44.3% | 0.0% | 0.0% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Shortfalls (10): holdout P(first payout in 30d, funded) 9.7% -> 7.5%; validation Median days to first payout 23.00 -> 24.50; holdout Median days to first payout 22.00 -> 26.50; validation 90-day EV net of fees and resets ($) -136 -> -140; holdout 90-day EV net of fees and resets ($) -130 -> -139; validation Max drawdown ($) 1,628 -> 2,118; holdout Max drawdown ($) 1,329 -> 1,758; holdout Worst day ($) -162 -> -220; research Trades a month 18.06 -> 6.81; validation Trades a month 15.16 -> 10.12

### BOT-B-R1 vs baseline_B (flex50, base cost)

| Metric | Research base | Research BOT-B-R1 | Validation base | Validation BOT-B-R1 | Holdout base | Holdout BOT-B-R1 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 0.8% | 0.0% | 0.0% | 0.0% | 0.0% |
| Median days to pass | 29.00 | 29.00 | n/a | n/a | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 21.6% | 47.8% | 13.5% | 38.4% | 11.7% | 7.5% ✗ |
| Median days to first payout | 25.00 | 23.00 | 23.00 | 23.50 ✗ | 19.00 | 26.50 ✗ |
| 90-day EV net of fees and resets ($) | -132 | -96 | -136 | -138 ✗ | -133 | -139 ✗ |
| Profit factor | 1.28 | 1.41 | 1.42 | 1.32 ✗ | 0.69 | 1.21 |
| Expectancy (R) | 0.16 | 0.25 | 0.18 | 0.25 | -0.12 | 0.11 |
| Sharpe | 1.37 | 2.24 | 1.72 | 1.69 ✗ | -1.45 | 0.82 |
| Sortino | 2.82 | 4.47 | 3.50 | 3.45 ✗ | -2.19 | 2.15 |
| Max drawdown ($) | 1,245 | 1,437 ✗ | 1,620 | 2,093 ✗ | 1,300 | 1,702 ✗ |
| Worst day ($) | -298 | -218 | -304 | -219 | -160 | -219 ✗ |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 8.67 | 6.60 ✗ | 11.58 | 9.35 ✗ | 7.61 | 15.34 |
| Payouts in 90 funded days | 1.11 | 1.91 | 1.02 | 1.47 | 0.50 | 0.76 |
| $ paid in 90 funded days | 406 | 900 | 418 | 524 | 189 | 534 |
| P(2+ payouts in 90d) | 31.6% | 65.3% | 16.6% | 48.1% | 0.0% | 0.0% |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Shortfalls (14): holdout P(first payout in 30d, funded) 11.7% -> 7.5%; validation Median days to first payout 23.00 -> 23.50; holdout Median days to first payout 19.00 -> 26.50; validation 90-day EV net of fees and resets ($) -136 -> -138; holdout 90-day EV net of fees and resets ($) -133 -> -139; validation Profit factor 1.42 -> 1.32; validation Sharpe 1.72 -> 1.69; validation Sortino 3.50 -> 3.45; research Max drawdown ($) 1,245 -> 1,437; validation Max drawdown ($) 1,620 -> 2,093; holdout Max drawdown ($) 1,300 -> 1,702; holdout Worst day ($) -160 -> -219; research Trades a month 8.67 -> 6.60; validation Trades a month 11.58 -> 9.35


## Monte Carlo (10,000 paths per row, stress cost, pools stop at 2026-03-01)

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

## What would invalidate this

- 60 live sessions with PF below 1.0 at real fills (the holdout already showed one such stretch for every bot).
- Real slippage above 1.5 ticks a side.
- A change to Lucid's rules: Pro $3,000 target with a $2,000 EOD trailing floor locking at $50,100; Flex five $150 days, 50% split, $2,000 cap.
- NQ volatility far outside 2020-2026 (stops in points get wider, fewer trades can be sized at one micro).
