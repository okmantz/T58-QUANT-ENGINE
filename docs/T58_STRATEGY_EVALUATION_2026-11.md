# T58 strategy evaluation, 2026-11

Every number below is produced by `scripts/make_objective_report.py` from the saved study files (`run_objective_scores.py`, `run_gate27_study.py`, `run_objective_c_final.py`). Nothing is estimated by hand.

## Method

- Splits: train 2019-10..2023-12, validation 2024, test 2025-01..2026-11 (locked: read once, never used to choose).
- Selection: choose on train, confirm on validation (rank by the lower of the two), then read test.
- A and B are scored with the Lucid 50K evaluation / funded simulator (`app/prop/simulator.py`) over rolling start dates; Wilson 95% bounds use n_eff = window days / horizon (overlapping starts are not independent).
- C is scored on a compounding equity curve; sizing equity is capped at $250K (`SIZE_CAP_DEFAULT`), because unbounded compounding on futures is not realisable.

## Honesty notes

- Objective B's horizon is 365 days, so the 2025-2026 test window holds only 2-13 valid starts: **the B test is uninformative**. B is chosen on train+validation evidence and its test row is reported, not trusted.
- Objective C train/validation CAGRs (130%+ and 600%+) are regime-driven compounding at 2x sleeve leverage in 2021 and 2024; read the test column.
- Crude oil data is unadjusted (roll gaps) and USDX data is missing; the oil and USDX legs of Gate27 are therefore not evaluated on clean data.
- The deleted MQL5 EAs (Ninja Turtle Scalper, Fisherman, Turnaround Tuesday, ATR Candle Breakout) cannot be run by the repo's MQL5 interpreter (`SetTypeFillingBySymbol` is unsupported). They have **no numbers here by design**; to evaluate them they need a Python twin (`// T58_TWIN=`) first.

## Directives

Each objective must have its own independent strategy discovery, optimization, portfolio construction, position-sizing logic, risk governor, scoring system, and selection criteria. Never optimize a strategy for one objective using another objective's priorities. A strategy that is excellent at passing an evaluation may be unsuitable for payouts or live compounding. Strategies must be judged exclusively by how effectively they accomplish their assigned mission.

- **A EVALUATION PASSER**: primary Probability of passing within 30/60 days.; secondary Median days to pass, breach probability, profit-target efficiency, risk of ruin.
- **B PAYOUT HUNTER**: primary Probability of reaching a payout without breaching account rules.; secondary Time to first payout, payout expectancy, account survival, drawdown, consistency compliance, repeat payout probability.
- **C NET PROFIT COMPOUNDER**: primary Long-term net profit and compounded growth.; secondary Risk-adjusted return, Calmar ratio, expectancy, maximum drawdown, return on capital, robustness across market regimes.

## Individual strategies (per instrument sleeve)

Screen: profit factor ≥ 1.1 and ≥ 60 trades on train+validation. 19 sleeves passed.

| Sleeve | n | PF all | PF train | PF val | PF test | scored |
|---|---|---|---|---|---|---|
| IndRule_NQ_15m on NQ | 391 | 2.01 | 2.2 | 1.75 | 1.77 | yes |
| ContextDriveLong_NQ_1m on NQ | 359 | 1.7 | 1.54 | 2.34 | 1.35 | yes |
| ContextDrive_NQ_1m on NQ | 456 | 1.53 | 1.36 | 2.34 | 1.26 | yes |
| IndRuleA_NQ_30m on NQ | 266 | 1.51 | 1.43 | 1.67 | 1.64 | yes |
| ContextDriveLong_NQ_1m on ES | 392 | 1.46 | 1.8 | 1.84 | 0.93 | yes |
| IndRuleB_NQ_30m on NQ | 155 | 1.44 | 1.85 | 1.17 | 0.53 | yes |
| OpenDrive_NQ_5m on NQ | 1204 | 1.36 | 1.34 | 1.66 | 1.18 | yes |
| GapAlignedDriveRWTight_NQ_1m on NQ | 609 | 1.35 | 1.24 | 1.89 | 1.25 | yes |
| ContextDrive_NQ_1m on ES | 461 | 1.32 | 1.41 | 1.84 | 0.93 | yes |
| RangeBreakout_NQ_5m on NQ | 870 | 1.29 | 1.25 | 1.31 | 1.57 | yes |
| CompressionORB_ES_5m on ES | 357 | 1.28 | 1.32 | 1.15 | 1.32 | yes |
| GapAlignedDriveRWTight_NQ_1m on ES | 688 | 1.25 | 1.36 | 1.27 | 0.97 | yes |
| LiquiditySweepReclaim_NQ_5m on NQ | 730 | 1.25 | 1.18 | 1.35 | 1.57 | yes |
| CompressionORB_ES_5m on NQ | 43 | 1.24 | 1.3 | 1.02 | None | no (screen) |
| IndRuleB_NQ_30m on ES | 240 | 1.24 | 1.27 | 0.84 | 1.49 | yes |
| TrendMomentum_NQ_5m on NQ | 557 | 1.21 | 1.3 | 1.19 | 1.0 | yes |
| IndRuleB_NQ_30m on GC | 132 | 1.2 | 1.18 | 1.15 | 1.37 | yes |
| IndRuleA_NQ_30m on ES | 342 | 1.16 | 1.22 | 1.1 | 1.09 | yes |
| IndRule_NQ_15m on ES | 410 | 1.15 | 1.19 | 1.09 | 1.13 | yes |
| OpenDrive_NQ_5m on ES | 1254 | 1.14 | 1.14 | 1.24 | 1.08 | yes |
| GoLong_ESNQ_5m on NQ | 1517 | 1.08 | 1.09 | 0.96 | 1.19 | yes |
| GoLong_ESNQ_5m on ES | 1750 | 1.04 | 1.05 | 0.88 | 1.05 | yes |
| CompressionORB_ES_5m on GC | 171 | 1.02 | 0.93 | 0.93 | 1.97 | no (screen) |
| IndRule_NQ_15m on GC | 419 | 1.02 | 0.93 | 1.21 | 1.17 | no (screen) |
| RangeBreakout_NQ_5m on ES | 1633 | 0.97 | 1.02 | 0.79 | 1.0 | no (screen) |
| IndRuleA_NQ_30m on GC | 285 | 0.96 | 0.86 | 1.23 | 1.3 | no (screen) |
| OpenDrive_NQ_5m on GC | 1151 | 0.94 | 0.89 | 1.06 | 1.01 | no (screen) |
| ContextDriveLong_NQ_1m on GC | 366 | 0.93 | 1.33 | 0.84 | 0.83 | yes |
| GoLong_ESNQ_5m on GC | 1542 | 0.93 | 0.89 | 0.91 | 1.02 | no (screen) |
| RangeBreakout_NQ_5m on GC | 1337 | 0.9 | 0.89 | 0.83 | 0.98 | no (screen) |
| ContextDrive_NQ_1m on GC | 437 | 0.86 | 0.92 | 0.84 | 0.83 | no (screen) |
| GapAlignedDriveRWTight_NQ_1m on GC | 616 | 0.85 | 0.8 | 0.98 | 0.88 | no (screen) |
| LiquiditySweepReclaim_NQ_5m on ES | 1071 | 0.83 | 0.81 | 0.75 | 0.97 | no (screen) |
| LiquiditySweepReclaim_NQ_5m on GC | 858 | 0.74 | 0.74 | 0.76 | 0.7 | no (screen) |

## Objective A: Evaluation Passer

| Book | Train P(pass≤30) | Train P(pass≤60) [lo95] | Median days | Breach≤60 | Val P(pass≤60) | Test P(pass≤30) [lo95] | Test P(pass≤60) | Test breach≤60 |
|---|---|---|---|---|---|---|---|---|
| shipped: OpenDrive_NQ_5m[NQ]×1 + IndRule_NQ_15m[NQ]×3 + ContextDriveLong_NQ_1m[NQ]×1 | 50.5% | 60.0% [41.1] | 14.0 | 30.4% | 66.7% | 35.2% [16.0] | 41.7% | 39.8% |

Candidates compared (selection score on train / validation; the shipped book is the first row, the rest are single-sleeve and greedy alternatives it was ranked against):
- shipped book: train 41.0, val 34.1
- single ContextDriveLong_NQ_1m_v2|ES x2: train 25.3, val 22.8
- single ContextDrive_NQ_1m_v2|NQ x3: train 22.7, val 28.0
- single ContextDriveLong_NQ_1m_v2|NQ x3: train 29.7, val 22.4
- single GapAlignedDriveRWTight_NQ_1m_v1|ES x3: train 34.2, val 21.9
- greedy-1: train 44.4, val 20.6
- greedy-2: train 59.4, val 15.3

## Objective B: Payout Hunter

| Split | starts | n_eff | P(paid, no breach) | lower95 | bust | survival | median days to pay | repeat payout | consistency ok |
|---|---|---|---|---|---|---|---|---|---|
| train | 83 | 4.3 | 31.3% | 7.0% | 0.0% | 100.0% | 224.5 | 15.4 | 50.0 |
| val | 35 | 1.0 | 85.7% | 15.3% | 0.0% | 100.0% | 165.0 | 66.7 | 70.0 |
| test | 5 | 1.2 | 0.0% | 0.0% | 0.0% | 100.0% | n/a | n/a | n/a |

Alternatives tried:
- shipped book: train 31.3, val 85.7
- single OpenDrive_NQ_5m_v1|NQ x0.5: train 27.6, val 56.1
- single ContextDriveLong_NQ_1m_v2|NQ x1: train 26.0, val 88.9
- single ContextDrive_NQ_1m_v2|NQ x0.5: train 24.7, val 66.7
- single ContextDriveLong_NQ_1m_v2|NQ x0.5: train 24.0, val 66.7
- greedy-2: train 73.7, val 14.3
- greedy-1: train 43.1, val 0.0

## Objective C: Net Profit Compounder

| Book | Train CAGR/DD/Calmar | Val CAGR/DD/Calmar | Test CAGR / maxDD / Calmar |
|---|---|---|---|
| intraday book (chosen) | 131.4% / 14.1% / 9.3 | 599.9% / 12.3% / 48.8 | 41.9% / 13.2% / 3.2 |
| previous preset (IR + CAD) | 28.4% / 8.6% / 3.3 | 106.2% / 5.6% / 19.1 | 22.6% / 6.2% / 3.7 |
| Gate 27 alone (original) | -1.3% / 15.9% / -0.1 | 20.5% / 6.3% / 3.2 | 11.4% / 9.4% / 1.2 |
| Gate 27 alone (tuned) | 8.6% / 20.4% / 0.4 | 43.8% / 13.8% / 3.2 | 25.4% / 17.5% / 1.4 |
| intraday + Gate 27 original | 127.9% / 14.1% / 9.1 | 798.8% / 10.5% / 76.0 | 53.8% / 12.2% / 4.4 |
| intraday + Gate 27 tuned | 136.7% / 15.1% / 9.1 | 941.2% / 13.7% / 68.5 | 72.9% / 19.9% / 3.7 |
| previous preset + Gate 27 original | 22.2% / 16.5% / 1.4 | 143.3% / 9.3% / 15.4 | 31.4% / 9.6% / 3.3 |

## Gate27 against its original EA

| Variant | Train CAGR/DD | Val CAGR/DD | Test CAGR/DD/Calmar |
|---|---|---|---|
| no guards (original v1) | -1.7% / 15.9% | 20.5% / 6.3% | 11.4% / 9.4% / 1.2 |
| v1.10 guards, manual resume (never resumes) | -2.8% / 12.1% | no data | no data / n/a |
| v1.10 guards, resume next month | -3.3% / 13.4% | -0.6% / 0.8% | 0.4% / 0.7% / 0.7 |
| v1.10 daily guard only, resume next month | -1.7% / 15.9% | 20.5% / 6.3% | 11.4% / 9.4% / 1.2 |

Grid: 720 configurations, 600 usable. Top by min(train, val) CAGR:

| SMA | vol window | vol target % | lev cap | phase-in | Train CAGR/DD | Val CAGR/DD | Test CAGR/DD/Calmar |
|---|---|---|---|---|---|---|---|
| 150 | 40 | 1.0 | 3.0 | 5 | 10.8% / 20.4% | 43.5% / 13.8% | 25.7% / 17.5% / 1.47 |
| 150 | 40 | 1.0 | 5.0 | 5 | 10.8% / 20.4% | 43.5% / 13.8% | 25.7% / 17.5% / 1.47 |
| 150 | 40 | 1.0 | 8.0 | 5 | 10.8% / 20.4% | 43.5% / 13.8% | 25.7% / 17.5% / 1.47 |
| 150 | 40 | 1.0 | 3.0 | 3 | 10.2% / 21.0% | 44.8% / 13.5% | 26.8% / 17.7% / 1.51 |
| 150 | 40 | 1.0 | 5.0 | 3 | 10.2% / 21.0% | 44.8% / 13.5% | 26.8% / 17.7% / 1.51 |
| 150 | 40 | 1.0 | 8.0 | 3 | 10.2% / 21.0% | 44.8% / 13.5% | 26.8% / 17.7% / 1.51 |

## Individual vs combined

The combined books beat every single sleeve on the selection score for A and B (tables above: the chosen book vs the `single ...` rows). For C the combination adds Gate27 (a daily-bar, overnight, multi-asset sleeve with low correlation to the intraday NQ/ES books): see the `intraday` rows against `intraday + Gate 27` rows.

## Keep / drop

KEEP (in a shipped bot): OpenDrive_NQ_5m_v1, IndRule_NQ_15m_v1, ContextDriveLong_NQ_1m_v2 (A, B, C); LiquiditySweepReclaim_NQ_5m_v1, IndRuleA_NQ_30m_v1 (C sleeves); Gate27_Basket_Daily_v2 (C; v1 kept as the owner's armored original).

FLAG, DO NOT DELETE (did not pass the screen or are not used by a bot): see `docs/OBSOLETE_FILES.md`.

