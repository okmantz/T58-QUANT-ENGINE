> **Round 5 update (2026-11-24, late):** a wider search on 2016-2026 found nothing that should replace these bots, so the round-4 picks below still stand. Every window in round 5 had already been read, so its results aren't a clean holdout. See T58_FINAL_BOTS_ROUND5_2026-11-24.md.

# T58 final bots: comparison report, round 4 (2026-11-24)

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

Baselines are your current bots in the repo (PRESET_REV 5): baseline_A on LucidPro 50K, baseline_B on LucidFlex 50K.

## BOT-A against the round-4 bar

Primary (beat or tie the current BOT-A): P(pass), median days to pass (and under 30), eval bust, 90-day EV after fees and resets. Limits: no other metric more than 10% worse (25% for max drawdown and worst day), worst day never below -$1,200. Stress cost decides (research/PREREG_R4.md).

| Bot | Cost | Split | Primary tests missed | Limits broken | Meets the bar |
|---|---|---|---|---|---|
| BOT-A-R4 | stress | research | none | none | yes |
| BOT-A-R4 | stress | validation | none | none | yes |
| BOT-A-R4 | stress | holdout | p_pass | p_payout | no |
| BOT-A-R4 | base | research | none | none | yes |
| BOT-A-R4 | base | validation | none | pf;exp_R;sharpe;sortino | no |
| BOT-A-R4 | base | holdout | none | exp_R;sharpe;sortino;p_payout | no |
| BOT-A-R4-port | stress | research | none | sortino | no |
| BOT-A-R4-port | stress | validation | none | exp_R;sharpe;sortino | no |
| BOT-A-R4-port | stress | holdout | p_pass | exp_R;sharpe;sortino;p_payout | no |
| BOT-A-R4-port | base | research | none | sharpe;sortino;max_dd | no |
| BOT-A-R4-port | base | validation | none | pf;exp_R;sharpe;sortino | no |
| BOT-A-R4-port | base | holdout | none | pf;exp_R;sharpe;sortino;p_payout;max_dd | no |
| BOT-A-R3 | stress | research | none | cons_blocks_per30 | no |
| BOT-A-R3 | stress | validation | none | exp_R | no |
| BOT-A-R3 | stress | holdout | none | pf;exp_R;sharpe;sortino;p_payout | no |
| BOT-A-R3 | base | research | none | cons_blocks_per30 | no |
| BOT-A-R3 | base | validation | none | exp_R;sharpe;sortino | no |
| BOT-A-R3 | base | holdout | bust | exp_R;p_payout | no |

## Every-metric count (cells worse than the baseline; BOT-B's bar, shown for A too)

| Bot | Plan | Research | Validation | 2016-2019 holdout | Total (stress) | Total (base) |
|---|---|---|---|---|---|---|
| BOT-A-R4 | pro50 | 4 | 1 | 3 | 8 of 42 | 16 of 42 |
| BOT-A-R4-port | pro50 | 4 | 5 | 6 | 15 of 42 | 17 of 42 |
| BOT-A-R3 | pro50 | 3 | 4 | 6 | 13 of 42 | 12 of 42 |
| BOT-B-R4 | flex50 | 1 | 1 | 3 | 5 of 54 | 14 of 54 |
| BOT-B-R4-port | flex50 | 2 | 1 | 4 | 7 of 54 | 12 of 54 |
| BOT-B-R3 | flex50 | 1 | 1 | 6 | 8 of 54 | 13 of 54 |

R3 = round-3 pick rescored on the round-4 splits. -port = R4 pick on the repo-format leg files.

## Why these picks

- BOT-A-R4: one of three of 1,476 A variants that meet the whole bar on both dev splits at stress cost; they differ only in the funded day cap and the pick is the middle one. Round-3 A passes a little more often in research but breaks two limits.
- BOT-B-R4: no B variant of 144 clears the every-metric bar. The pick fails only trades a month (as round 3) with higher payouts in both dev splits. Five variants fail one cell fewer but pay about half as much; rejected, reason logged before the holdout read.
- Both picks were frozen and hashed before the 2016-2019 read (research/FROZEN_PICKS_R4.md); nothing was changed after it.

## Full tables

### BOT-A-R4 vs baseline_A (pro50, stress cost)

| Metric | Research base | Research BOT-A-R4 | Validation base | Validation BOT-A-R4 | Holdout base | Holdout BOT-A-R4 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.1% | 36.6% | 21.8% | 35.1% | 15.0% | 14.9% ✗ |
| Median days to pass | 23.00 | 16.50 | 19.50 | 15.00 | 19.00 | 14.00 |
| Eval bust | 0.8% | 0.0% | 4.1% | 0.9% | 1.3% | 0.1% |
| P(first payout in 30d, funded) | 5.4% | 8.9% | 7.8% | 9.6% | 4.5% | 1.7% ✗ |
| Median days to first payout | 22.00 | 23.50 ✗ | 23.00 | 23.00 | 23.00 | 21.50 |
| 90-day EV net of fees and resets ($) | -160 | 25 | 26 | 121 | -226 | -198 |
| Profit factor | 1.53 | 1.46 ✗ | 1.36 | 1.43 | 1.06 | 1.09 |
| Expectancy (R) | 0.18 | 0.21 | 0.20 | 0.18 ✗ | 0.03 | 0.02 ✗ |
| Sharpe | 2.50 | 2.40 ✗ | 1.65 | 1.68 | 0.25 | 0.40 |
| Sortino | 5.44 | 5.16 ✗ | 3.44 | 4.03 | 0.43 | 0.77 |
| Max drawdown ($) | 3,502 | 3,040 | 6,041 | 2,932 | 5,943 | 2,699 |
| Worst day ($) | -691 | -627 | -977 | -637 | -1,055 | -647 |
| Consistency blocks per 30d | 0.38 | 0.31 | 1.01 | 0.78 | 0.53 | 0.07 |
| Trades a month | 17.63 | 29.04 | 17.31 | 21.84 | 12.08 | 25.23 |

Cells worse than the baseline (8): holdout P(pass in 30d) 15.0% -> 14.9%; holdout P(first payout in 30d, funded) 4.5% -> 1.7%; research Median days to first payout 22.00 -> 23.50; research Profit factor 1.53 -> 1.46; validation Expectancy (R) 0.20 -> 0.18; holdout Expectancy (R) 0.03 -> 0.02; research Sharpe 2.50 -> 2.40; research Sortino 5.44 -> 5.16

### BOT-A-R4 vs baseline_A (pro50, base cost)

| Metric | Research base | Research BOT-A-R4 | Validation base | Validation BOT-A-R4 | Holdout base | Holdout BOT-A-R4 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.8% | 39.0% | 23.4% | 35.4% | 16.3% | 19.3% |
| Median days to pass | 23.00 | 17.00 | 20.00 | 15.00 | 18.00 | 15.00 |
| Eval bust | 0.8% | 0.0% | 4.9% | 0.9% | 1.1% | 0.1% |
| P(first payout in 30d, funded) | 5.8% | 10.4% | 8.8% | 10.9% | 4.7% | 2.4% ✗ |
| Median days to first payout | 22.00 | 24.00 ✗ | 22.50 | 23.00 ✗ | 23.00 | 23.00 |
| 90-day EV net of fees and resets ($) | -137 | 88 | 41 | 97 | -217 | -185 |
| Profit factor | 1.53 | 1.46 ✗ | 1.45 | 1.26 ✗ | 1.03 | 0.93 ✗ |
| Expectancy (R) | 0.19 | 0.22 | 0.21 | 0.15 ✗ | 0.05 | 0.02 ✗ |
| Sharpe | 2.56 | 2.42 ✗ | 1.98 | 1.44 ✗ | 0.12 | -0.32 ✗ |
| Sortino | 5.40 | 5.17 ✗ | 4.11 | 3.02 ✗ | 0.20 | -0.55 ✗ |
| Max drawdown ($) | 2,935 | 2,979 ✗ | 6,010 | 4,444 | 6,142 | 6,748 ✗ |
| Worst day ($) | -722 | -640 | -974 | -599 | -1,063 | -648 |
| Consistency blocks per 30d | 0.42 | 0.41 | 1.07 | 0.75 | 0.64 | 0.11 |
| Trades a month | 17.23 | 29.27 | 16.13 | 32.72 | 11.73 | 23.25 |

Cells worse than the baseline (16): holdout P(first payout in 30d, funded) 4.7% -> 2.4%; research Median days to first payout 22.00 -> 24.00; validation Median days to first payout 22.50 -> 23.00; research Profit factor 1.53 -> 1.46; validation Profit factor 1.45 -> 1.26; holdout Profit factor 1.03 -> 0.93; validation Expectancy (R) 0.21 -> 0.15; holdout Expectancy (R) 0.05 -> 0.02; research Sharpe 2.56 -> 2.42; validation Sharpe 1.98 -> 1.44; holdout Sharpe 0.12 -> -0.32; research Sortino 5.40 -> 5.17; validation Sortino 4.11 -> 3.02; holdout Sortino 0.20 -> -0.55; research Max drawdown ($) 2,935 -> 2,979; holdout Max drawdown ($) 6,142 -> 6,748

### BOT-A-R4-port vs baseline_A (pro50, stress cost)

| Metric | Research base | Research BOT-A-R4-port | Validation base | Validation BOT-A-R4-port | Holdout base | Holdout BOT-A-R4-port |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.1% | 34.0% | 21.8% | 31.7% | 15.0% | 14.5% ✗ |
| Median days to pass | 23.00 | 17.00 | 19.50 | 15.00 | 19.00 | 14.00 |
| Eval bust | 0.8% | 0.0% | 4.1% | 0.9% | 1.3% | 0.1% |
| P(first payout in 30d, funded) | 5.4% | 8.9% | 7.8% | 9.9% | 4.5% | 1.4% ✗ |
| Median days to first payout | 22.00 | 24.00 ✗ | 23.00 | 23.50 ✗ | 23.00 | 22.00 |
| 90-day EV net of fees and resets ($) | -160 | 5 | 26 | 50 | -226 | -195 |
| Profit factor | 1.53 | 1.43 ✗ | 1.36 | 1.24 ✗ | 1.06 | 0.97 ✗ |
| Expectancy (R) | 0.18 | 0.19 | 0.20 | 0.14 ✗ | 0.03 | 0.01 ✗ |
| Sharpe | 2.50 | 2.29 ✗ | 1.65 | 1.35 ✗ | 0.25 | -0.14 ✗ |
| Sortino | 5.44 | 4.85 ✗ | 3.44 | 2.74 ✗ | 0.43 | -0.25 ✗ |
| Max drawdown ($) | 3,502 | 3,085 | 6,041 | 4,067 | 5,943 | 4,747 |
| Worst day ($) | -691 | -635 | -977 | -621 | -1,055 | -648 |
| Consistency blocks per 30d | 0.38 | 0.32 | 1.01 | 0.73 | 0.53 | 0.07 |
| Trades a month | 17.63 | 30.11 | 17.31 | 31.68 | 12.08 | 25.53 |

Cells worse than the baseline (15): holdout P(pass in 30d) 15.0% -> 14.5%; holdout P(first payout in 30d, funded) 4.5% -> 1.4%; research Median days to first payout 22.00 -> 24.00; validation Median days to first payout 23.00 -> 23.50; research Profit factor 1.53 -> 1.43; validation Profit factor 1.36 -> 1.24; holdout Profit factor 1.06 -> 0.97; validation Expectancy (R) 0.20 -> 0.14; holdout Expectancy (R) 0.03 -> 0.01; research Sharpe 2.50 -> 2.29; validation Sharpe 1.65 -> 1.35; holdout Sharpe 0.25 -> -0.14; research Sortino 5.44 -> 4.85; validation Sortino 3.44 -> 2.74; holdout Sortino 0.43 -> -0.25

### BOT-A-R4-port vs baseline_A (pro50, base cost)

| Metric | Research base | Research BOT-A-R4-port | Validation base | Validation BOT-A-R4-port | Holdout base | Holdout BOT-A-R4-port |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.8% | 37.3% | 23.4% | 33.3% | 16.3% | 18.8% |
| Median days to pass | 23.00 | 18.00 | 20.00 | 14.00 | 18.00 | 15.00 |
| Eval bust | 0.8% | 0.0% | 4.9% | 1.0% | 1.1% | 0.1% |
| P(first payout in 30d, funded) | 5.8% | 10.1% | 8.8% | 11.4% | 4.7% | 2.4% ✗ |
| Median days to first payout | 22.00 | 23.00 ✗ | 22.50 | 23.00 ✗ | 23.00 | 23.00 |
| 90-day EV net of fees and resets ($) | -137 | 41 | 41 | 110 | -217 | -182 |
| Profit factor | 1.53 | 1.43 ✗ | 1.45 | 1.27 ✗ | 1.03 | 0.92 ✗ |
| Expectancy (R) | 0.19 | 0.20 | 0.21 | 0.15 ✗ | 0.05 | -0.01 ✗ |
| Sharpe | 2.56 | 2.14 ✗ | 1.98 | 1.22 ✗ | 0.12 | -0.34 ✗ |
| Sortino | 5.40 | 4.57 ✗ | 4.11 | 2.56 ✗ | 0.20 | -0.57 ✗ |
| Max drawdown ($) | 2,935 | 4,279 ✗ | 6,010 | 6,612 ✗ | 6,142 | 7,920 ✗ |
| Worst day ($) | -722 | -649 | -974 | -629 | -1,063 | -650 |
| Consistency blocks per 30d | 0.42 | 0.39 | 1.07 | 0.65 | 0.64 | 0.08 |
| Trades a month | 17.23 | 27.71 | 16.13 | 22.45 | 11.73 | 19.54 |

Cells worse than the baseline (17): holdout P(first payout in 30d, funded) 4.7% -> 2.4%; research Median days to first payout 22.00 -> 23.00; validation Median days to first payout 22.50 -> 23.00; research Profit factor 1.53 -> 1.43; validation Profit factor 1.45 -> 1.27; holdout Profit factor 1.03 -> 0.92; validation Expectancy (R) 0.21 -> 0.15; holdout Expectancy (R) 0.05 -> -0.01; research Sharpe 2.56 -> 2.14; validation Sharpe 1.98 -> 1.22; holdout Sharpe 0.12 -> -0.34; research Sortino 5.40 -> 4.57; validation Sortino 4.11 -> 2.56; holdout Sortino 0.20 -> -0.57; research Max drawdown ($) 2,935 -> 4,279; validation Max drawdown ($) 6,010 -> 6,612; holdout Max drawdown ($) 6,142 -> 7,920

### BOT-A-R3 vs baseline_A (pro50, stress cost)

| Metric | Research base | Research BOT-A-R3 | Validation base | Validation BOT-A-R3 | Holdout base | Holdout BOT-A-R3 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.1% | 38.9% | 21.8% | 35.3% | 15.0% | 18.5% |
| Median days to pass | 23.00 | 15.00 | 19.50 | 14.00 | 19.00 | 14.00 |
| Eval bust | 0.8% | 0.0% | 4.1% | 1.8% | 1.3% | 1.1% |
| P(first payout in 30d, funded) | 5.4% | 10.7% | 7.8% | 12.8% | 4.5% | 2.6% ✗ |
| Median days to first payout | 22.00 | 24.00 ✗ | 23.00 | 22.00 | 23.00 | 22.50 |
| 90-day EV net of fees and resets ($) | -160 | 107 | 26 | 115 | -226 | -201 |
| Profit factor | 1.53 | 1.50 ✗ | 1.36 | 1.30 ✗ | 1.06 | 0.91 ✗ |
| Expectancy (R) | 0.18 | 0.21 | 0.20 | 0.15 ✗ | 0.03 | -0.05 ✗ |
| Sharpe | 2.50 | 2.57 | 1.65 | 1.54 ✗ | 0.25 | -0.36 ✗ |
| Sortino | 5.44 | 5.52 | 3.44 | 3.23 ✗ | 0.43 | -0.63 ✗ |
| Max drawdown ($) | 3,502 | 2,775 | 6,041 | 4,209 | 5,943 | 7,154 ✗ |
| Worst day ($) | -691 | -627 | -977 | -637 | -1,055 | -648 |
| Consistency blocks per 30d | 0.38 | 0.57 ✗ | 1.01 | 0.69 | 0.53 | 0.10 |
| Trades a month | 17.63 | 30.27 | 17.31 | 28.36 | 12.08 | 17.88 |

Cells worse than the baseline (13): holdout P(first payout in 30d, funded) 4.5% -> 2.6%; research Median days to first payout 22.00 -> 24.00; research Profit factor 1.53 -> 1.50; validation Profit factor 1.36 -> 1.30; holdout Profit factor 1.06 -> 0.91; validation Expectancy (R) 0.20 -> 0.15; holdout Expectancy (R) 0.03 -> -0.05; validation Sharpe 1.65 -> 1.54; holdout Sharpe 0.25 -> -0.36; validation Sortino 3.44 -> 3.23; holdout Sortino 0.43 -> -0.63; holdout Max drawdown ($) 5,943 -> 7,154; research Consistency blocks per 30d 0.38 -> 0.57

### BOT-A-R3 vs baseline_A (pro50, base cost)

| Metric | Research base | Research BOT-A-R3 | Validation base | Validation BOT-A-R3 | Holdout base | Holdout BOT-A-R3 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 17.8% | 40.5% | 23.4% | 35.4% | 16.3% | 21.3% |
| Median days to pass | 23.00 | 15.00 | 20.00 | 13.00 | 18.00 | 14.50 |
| Eval bust | 0.8% | 0.0% | 4.9% | 1.8% | 1.1% | 1.1% ✗ |
| P(first payout in 30d, funded) | 5.8% | 13.3% | 8.8% | 13.7% | 4.7% | 2.7% ✗ |
| Median days to first payout | 22.00 | 23.00 ✗ | 22.50 | 22.00 | 23.00 | 23.00 |
| 90-day EV net of fees and resets ($) | -137 | 158 | 41 | 155 | -217 | -185 |
| Profit factor | 1.53 | 1.49 ✗ | 1.45 | 1.31 ✗ | 1.03 | 1.22 |
| Expectancy (R) | 0.19 | 0.22 | 0.21 | 0.16 ✗ | 0.05 | -0.00 ✗ |
| Sharpe | 2.56 | 2.49 ✗ | 1.98 | 1.59 ✗ | 0.12 | 0.91 |
| Sortino | 5.40 | 5.37 ✗ | 4.11 | 3.27 ✗ | 0.20 | 1.86 |
| Max drawdown ($) | 2,935 | 2,581 | 6,010 | 3,860 | 6,142 | 4,134 |
| Worst day ($) | -722 | -640 | -974 | -640 | -1,063 | -650 |
| Consistency blocks per 30d | 0.42 | 0.61 ✗ | 1.07 | 0.73 | 0.64 | 0.14 |
| Trades a month | 17.23 | 30.04 | 16.13 | 27.61 | 11.73 | 23.14 |

Cells worse than the baseline (12): holdout Eval bust 1.1% -> 1.1%; holdout P(first payout in 30d, funded) 4.7% -> 2.7%; research Median days to first payout 22.00 -> 23.00; research Profit factor 1.53 -> 1.49; validation Profit factor 1.45 -> 1.31; validation Expectancy (R) 0.21 -> 0.16; holdout Expectancy (R) 0.05 -> -0.00; research Sharpe 2.56 -> 2.49; validation Sharpe 1.98 -> 1.59; research Sortino 5.40 -> 5.37; validation Sortino 4.11 -> 3.27; research Consistency blocks per 30d 0.42 -> 0.61

### BOT-B-R4 vs baseline_B (flex50, stress cost)

| Metric | Research base | Research BOT-B-R4 | Validation base | Validation BOT-B-R4 | Holdout base | Holdout BOT-B-R4 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 1.9% | 0.0% | 6.0% | 0.0% | 0.3% |
| Median days to pass | 30.00 | 22.00 | n/a | 26.00 | n/a | 25.50 |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 19.0% | 52.5% | 11.1% | 44.9% | 23.7% | 25.1% |
| Median days to first payout | 25.00 | 19.00 | 22.50 | 20.00 | 23.00 | 22.00 |
| 90-day EV net of fees and resets ($) | -133 | -101 | -137 | -32 | -130 | -137 ✗ |
| Profit factor | 1.17 | 1.29 | 1.16 | 1.36 | 0.85 | 0.87 |
| Expectancy (R) | 0.09 | 0.13 | 0.08 | 0.21 | -0.09 | -0.05 |
| Sharpe | 0.85 | 1.78 | 0.70 | 2.09 | -0.87 | -0.85 |
| Sortino | 1.56 | 3.29 | 1.30 | 4.21 | -1.41 | -1.34 |
| Max drawdown ($) | 2,011 | 1,758 | 1,801 | 1,331 | 6,487 | 6,318 |
| Worst day ($) | -324 | -300 | -311 | -297 | -305 | -299 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 18.06 | 11.29 ✗ | 13.50 | 11.51 ✗ | 23.06 | 43.11 |
| Payouts in 90 funded days | 1.01 | 1.82 | 0.77 | 1.65 | 0.62 | 0.56 ✗ |
| $ paid in 90 funded days | 365 | 728 | 297 | 941 | 196 | 202 |
| P(2+ payouts in 90d) | 22.9% | 55.4% | 11.2% | 52.9% | 13.7% | 10.9% ✗ |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Cells worse than the baseline (5): holdout 90-day EV net of fees and resets ($) -130 -> -137; research Trades a month 18.06 -> 11.29; validation Trades a month 13.50 -> 11.51; holdout Payouts in 90 funded days 0.62 -> 0.56; holdout P(2+ payouts in 90d) 13.7% -> 10.9%

### BOT-B-R4 vs baseline_B (flex50, base cost)

| Metric | Research base | Research BOT-B-R4 | Validation base | Validation BOT-B-R4 | Holdout base | Holdout BOT-B-R4 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 2.3% | 0.0% | 6.5% | 0.0% | 1.2% |
| Median days to pass | 29.00 | 20.00 | n/a | 25.00 | n/a | 28.00 |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 21.6% | 57.1% | 12.7% | 45.1% | 26.9% | 29.5% |
| Median days to first payout | 25.00 | 19.00 | 22.00 | 20.00 | 23.00 | 22.00 |
| 90-day EV net of fees and resets ($) | -132 | -78 | -137 | -9 | -128 | -130 ✗ |
| Profit factor | 1.28 | 1.15 ✗ | 1.42 | 1.44 | 0.95 | 0.86 ✗ |
| Expectancy (R) | 0.16 | 0.11 ✗ | 0.18 | 0.25 | -0.04 | -0.05 ✗ |
| Sharpe | 1.37 | 0.90 ✗ | 1.72 | 2.41 | -0.27 | -0.98 ✗ |
| Sortino | 2.82 | 1.62 ✗ | 3.50 | 5.18 | -0.47 | -1.48 ✗ |
| Max drawdown ($) | 1,245 | 3,766 ✗ | 1,620 | 1,227 | 3,670 | 6,946 ✗ |
| Worst day ($) | -298 | -299 ✗ | -304 | -293 | -314 | -300 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 8.67 | 15.17 | 8.68 | 10.73 | 22.82 | 42.92 |
| Payouts in 90 funded days | 1.11 | 2.00 | 0.84 | 1.69 | 0.76 | 0.72 ✗ |
| $ paid in 90 funded days | 406 | 839 | 339 | 984 | 256 | 274 |
| P(2+ payouts in 90d) | 31.6% | 65.6% | 12.1% | 54.7% | 19.4% | 18.4% ✗ |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Cells worse than the baseline (14): holdout 90-day EV net of fees and resets ($) -128 -> -130; research Profit factor 1.28 -> 1.15; holdout Profit factor 0.95 -> 0.86; research Expectancy (R) 0.16 -> 0.11; holdout Expectancy (R) -0.04 -> -0.05; research Sharpe 1.37 -> 0.90; holdout Sharpe -0.27 -> -0.98; research Sortino 2.82 -> 1.62; holdout Sortino -0.47 -> -1.48; research Max drawdown ($) 1,245 -> 3,766; holdout Max drawdown ($) 3,670 -> 6,946; research Worst day ($) -298 -> -299; holdout Payouts in 90 funded days 0.76 -> 0.72; holdout P(2+ payouts in 90d) 19.4% -> 18.4%

### BOT-B-R4-port vs baseline_B (flex50, stress cost)

| Metric | Research base | Research BOT-B-R4-port | Validation base | Validation BOT-B-R4-port | Holdout base | Holdout BOT-B-R4-port |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 1.4% | 0.0% | 5.5% | 0.0% | 0.3% |
| Median days to pass | 30.00 | 21.50 | n/a | 27.00 | n/a | 25.50 |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 19.0% | 53.8% | 11.1% | 43.5% | 23.7% | 22.7% ✗ |
| Median days to first payout | 25.00 | 19.00 | 22.50 | 19.00 | 23.00 | 22.00 |
| 90-day EV net of fees and resets ($) | -133 | -110 | -137 | -35 | -130 | -133 ✗ |
| Profit factor | 1.17 | 1.20 | 1.16 | 1.38 | 0.85 | 0.91 |
| Expectancy (R) | 0.09 | 0.12 | 0.08 | 0.20 | -0.09 | -0.05 |
| Sharpe | 0.85 | 1.22 | 0.70 | 2.24 | -0.87 | -0.66 |
| Sortino | 1.56 | 2.23 | 1.30 | 4.51 | -1.41 | -1.06 |
| Max drawdown ($) | 2,011 | 2,738 ✗ | 1,801 | 1,313 | 6,487 | 5,832 |
| Worst day ($) | -324 | -299 | -311 | -299 | -305 | -298 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 18.06 | 15.58 ✗ | 13.50 | 12.06 ✗ | 23.06 | 48.00 |
| Payouts in 90 funded days | 1.01 | 1.77 | 0.77 | 1.57 | 0.62 | 0.54 ✗ |
| $ paid in 90 funded days | 365 | 706 | 297 | 874 | 196 | 196 |
| P(2+ payouts in 90d) | 22.9% | 58.1% | 11.2% | 51.8% | 13.7% | 10.9% ✗ |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Cells worse than the baseline (7): holdout P(first payout in 30d, funded) 23.7% -> 22.7%; holdout 90-day EV net of fees and resets ($) -130 -> -133; research Max drawdown ($) 2,011 -> 2,738; research Trades a month 18.06 -> 15.58; validation Trades a month 13.50 -> 12.06; holdout Payouts in 90 funded days 0.62 -> 0.54; holdout P(2+ payouts in 90d) 13.7% -> 10.9%

### BOT-B-R4-port vs baseline_B (flex50, base cost)

| Metric | Research base | Research BOT-B-R4-port | Validation base | Validation BOT-B-R4-port | Holdout base | Holdout BOT-B-R4-port |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 1.5% | 0.0% | 7.1% | 0.0% | 0.9% |
| Median days to pass | 29.00 | 20.00 | n/a | 27.00 | n/a | 25.00 |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 21.6% | 57.2% | 12.7% | 44.2% | 26.9% | 26.4% ✗ |
| Median days to first payout | 25.00 | 20.00 | 22.00 | 19.00 | 23.00 | 21.00 |
| 90-day EV net of fees and resets ($) | -132 | -99 | -137 | -8 | -128 | -130 ✗ |
| Profit factor | 1.28 | 1.30 | 1.42 | 1.40 ✗ | 0.95 | 0.91 ✗ |
| Expectancy (R) | 0.16 | 0.12 ✗ | 0.18 | 0.22 | -0.04 | -0.03 |
| Sharpe | 1.37 | 1.77 | 1.72 | 2.33 | -0.27 | -0.62 ✗ |
| Sortino | 2.82 | 3.33 | 3.50 | 4.71 | -0.47 | -1.00 ✗ |
| Max drawdown ($) | 1,245 | 1,682 ✗ | 1,620 | 1,257 | 3,670 | 5,530 ✗ |
| Worst day ($) | -298 | -299 ✗ | -304 | -298 | -314 | -299 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 8.67 | 11.52 | 8.68 | 12.26 | 22.82 | 50.63 |
| Payouts in 90 funded days | 1.11 | 1.93 | 0.84 | 1.64 | 0.76 | 0.76 ✗ |
| $ paid in 90 funded days | 406 | 806 | 339 | 940 | 256 | 287 |
| P(2+ payouts in 90d) | 31.6% | 64.8% | 12.1% | 54.9% | 19.4% | 18.0% ✗ |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Cells worse than the baseline (12): holdout P(first payout in 30d, funded) 26.9% -> 26.4%; holdout 90-day EV net of fees and resets ($) -128 -> -130; validation Profit factor 1.42 -> 1.40; holdout Profit factor 0.95 -> 0.91; research Expectancy (R) 0.16 -> 0.12; holdout Sharpe -0.27 -> -0.62; holdout Sortino -0.47 -> -1.00; research Max drawdown ($) 1,245 -> 1,682; holdout Max drawdown ($) 3,670 -> 5,530; research Worst day ($) -298 -> -299; holdout Payouts in 90 funded days 0.76 -> 0.76; holdout P(2+ payouts in 90d) 19.4% -> 18.0%

### BOT-B-R3 vs baseline_B (flex50, stress cost)

| Metric | Research base | Research BOT-B-R3 | Validation base | Validation BOT-B-R3 | Holdout base | Holdout BOT-B-R3 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 2.3% | 0.0% | 6.0% | 0.0% | 0.0% |
| Median days to pass | 30.00 | 21.00 | n/a | 26.00 | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 19.0% | 49.4% | 11.1% | 42.7% | 23.7% | 21.1% ✗ |
| Median days to first payout | 25.00 | 19.00 | 22.50 | 19.00 | 23.00 | 20.00 |
| 90-day EV net of fees and resets ($) | -133 | -83 | -137 | -35 | -130 | -135 ✗ |
| Profit factor | 1.17 | 1.25 | 1.16 | 1.36 | 0.85 | 0.87 |
| Expectancy (R) | 0.09 | 0.17 | 0.08 | 0.20 | -0.09 | -0.05 |
| Sharpe | 0.85 | 1.48 | 0.70 | 2.06 | -0.87 | -0.87 ✗ |
| Sortino | 1.56 | 2.79 | 1.30 | 3.94 | -1.41 | -1.36 |
| Max drawdown ($) | 2,011 | 1,825 | 1,801 | 1,384 | 6,487 | 6,593 ✗ |
| Worst day ($) | -324 | -299 | -311 | -297 | -305 | -299 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 18.06 | 12.73 ✗ | 13.50 | 12.78 ✗ | 23.06 | 46.49 |
| Payouts in 90 funded days | 1.01 | 1.66 | 0.77 | 1.58 | 0.62 | 0.60 ✗ |
| $ paid in 90 funded days | 365 | 721 | 297 | 872 | 196 | 204 |
| P(2+ payouts in 90d) | 22.9% | 52.2% | 11.2% | 51.1% | 13.7% | 13.0% ✗ |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Cells worse than the baseline (8): holdout P(first payout in 30d, funded) 23.7% -> 21.1%; holdout 90-day EV net of fees and resets ($) -130 -> -135; holdout Sharpe -0.87 -> -0.87; holdout Max drawdown ($) 6,487 -> 6,593; research Trades a month 18.06 -> 12.73; validation Trades a month 13.50 -> 12.78; holdout Payouts in 90 funded days 0.62 -> 0.60; holdout P(2+ payouts in 90d) 13.7% -> 13.0%

### BOT-B-R3 vs baseline_B (flex50, base cost)

| Metric | Research base | Research BOT-B-R3 | Validation base | Validation BOT-B-R3 | Holdout base | Holdout BOT-B-R3 |
|---|---|---|---|---|---|---|
| P(pass in 30d) | 0.1% | 3.1% | 0.0% | 6.3% | 0.0% | 0.0% |
| Median days to pass | 29.00 | 19.50 | n/a | 26.00 | n/a | n/a |
| Eval bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| P(first payout in 30d, funded) | 21.6% | 54.1% | 12.7% | 44.1% | 26.9% | 25.9% ✗ |
| Median days to first payout | 25.00 | 20.00 | 22.00 | 20.00 | 23.00 | 21.00 |
| 90-day EV net of fees and resets ($) | -132 | -88 | -137 | 2 | -128 | -131 ✗ |
| Profit factor | 1.28 | 1.26 ✗ | 1.42 | 1.43 | 0.95 | 0.89 ✗ |
| Expectancy (R) | 0.16 | 0.19 | 0.18 | 0.24 | -0.04 | -0.07 ✗ |
| Sharpe | 1.37 | 1.57 | 1.72 | 2.40 | -0.27 | -0.70 ✗ |
| Sortino | 2.82 | 2.92 | 3.50 | 4.85 | -0.47 | -1.13 ✗ |
| Max drawdown ($) | 1,245 | 1,768 ✗ | 1,620 | 1,280 | 3,670 | 5,678 ✗ |
| Worst day ($) | -298 | -299 ✗ | -304 | -294 | -314 | -299 |
| Consistency blocks per 30d | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Trades a month | 8.67 | 13.04 | 8.68 | 10.94 | 22.82 | 45.71 |
| Payouts in 90 funded days | 1.11 | 1.85 | 0.84 | 1.74 | 0.76 | 0.72 ✗ |
| $ paid in 90 funded days | 406 | 831 | 339 | 954 | 256 | 250 ✗ |
| P(2+ payouts in 90d) | 31.6% | 62.7% | 12.1% | 56.4% | 19.4% | 15.9% ✗ |
| 90d funded bust | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Cells worse than the baseline (13): holdout P(first payout in 30d, funded) 26.9% -> 25.9%; holdout 90-day EV net of fees and resets ($) -128 -> -131; research Profit factor 1.28 -> 1.26; holdout Profit factor 0.95 -> 0.89; holdout Expectancy (R) -0.04 -> -0.07; holdout Sharpe -0.27 -> -0.70; holdout Sortino -0.47 -> -1.13; research Max drawdown ($) 1,245 -> 1,768; holdout Max drawdown ($) 3,670 -> 5,678; research Worst day ($) -298 -> -299; holdout Payouts in 90 funded days 0.76 -> 0.72; holdout $ paid in 90 funded days 256 -> 250; holdout P(2+ payouts in 90d) 19.4% -> 15.9%

### Flex lock-on-payout sensitivity (stress cost, the floor locks at the start balance after the first payout)

| Bot | Split | P(first payout in 30d) | $ paid in 90 funded days | P(2+ payouts in 90d) | 90d funded bust |
|---|---|---|---|---|---|
| BOT-B-R3 | holdout | 21.1% | 174 | 2.5% | 0.0% |
| BOT-B-R4 | holdout | 25.1% | 169 | 3.3% | 0.0% |
| baseline_B | holdout | 23.7% | 151 | 0.0% | 0.0% |
| BOT-B-R3 | research | 49.4% | 509 | 20.7% | 0.0% |
| BOT-B-R4 | research | 52.5% | 492 | 18.2% | 0.0% |
| baseline_B | research | 19.0% | 275 | 0.0% | 0.0% |
| BOT-B-R3 | validation | 42.7% | 627 | 23.1% | 1.8% |
| BOT-B-R4 | validation | 44.9% | 658 | 24.9% | 0.9% |
| baseline_B | validation | 11.1% | 240 | 0.0% | 0.0% |


## Monte Carlo (10,000 paths per row, stress cost)

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

## What would invalidate this

- 60 live sessions with PF below 1.0 at real fills (2016-2019 and Mar-Nov 2026 both showed such stretches for every bot).
- Real slippage above 1.5 ticks a side.
- A change to Lucid's rules: Pro $3,000 target with a $2,000 EOD trailing floor locking at $50,100; Flex five $150 days, 50% split, $2,000 cap. Flex's lock-on-payout floor is shown above as a sensitivity.
- NQ volatility or price level far outside the tested range (stops in points change how many signals fit the dollar budget).
- Both untouched windows are now spent; any further tuning needs new data to test on.
