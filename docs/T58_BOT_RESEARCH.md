# T58 Bot Research: strategy bundles and risk governor

Method: the pipeline's own sizing (rr_planned, micro substitution, 1% cap) produced one trade list per strategy and instrument. Bundles are merged into one account (one position at a time per instrument, combined daily loss cap $480). Each bundle is replayed from a fresh Lucid 50K account at every 3rd start date through the real `simulate_account`. Harness: `scripts/bundle_research.py` (reproduces the Game Plan numbers). 162 bundles of 1-4 legs were tried across 8 strategies.

## Honest caveats
- Effective sample is about 3 independent start windows (overlapping 730-day horizons), so Wilson lower bounds are wide (about 17% for the best Objective A bundle). Treat gaps of a few points as noise.
- Selecting the best of 162 bundles inflates results (selection bias). The H1/H2 columns split the starts at 2022-07-01; H2 is consistently weaker, so expect the lower number.
- Backtests are not promises. Slippage, fills and prop-firm rule changes will differ live.

## Findings
1. **Objective A.** Adding Context Aligned Drive (CAD) to Open Drive + Ind Rule lifts pass-within-60d from 48.2% to 58.9% (60.8% with Gap Aligned Drive); bust rises with it (about 35-39%). Ungoverned, OD+IR+CAD+GAD is the top bundle. The report's OD+IR core is not wrong, but it is not the maximum.
2. **Governor effect.** With the bot risk governor (progress ladder, need taper, cushion cap, day stop) the same bundle passes within 60d in about 49% of starts with 0% bust (H1 63% / H2 28%). That trade of about 12 points of pass rate for removing the bust tail is the A bot's calibration.
3. **Objective B.** Payout rate saturates, so ranking uses payout timing and bust. OD+IR+CAD with risk capped at 25% of the cushion and a 30% day stop: 0% bust, about 21% reach a payout within 180 days, median 141 days (H1/H2 bust both 0). Faster settings (no cushion cap) reach payout in about 93 days but accept bust risk.
4. **Net profit.** On an unconstrained equity simulation, compounding OD+IR+CAD+GAD+LSR with a 10% drawdown throttle gives about +$236k on $50k with $16k max drawdown (net/DD 14.6, H1 8.4 / H2 11.2). Non-compounding is smoother (net/DD 23.7, +$104k). The bot uses compounding plus a cushion cap so it cannot breach a prop floor.
5. **Open Drive variants (228 tested).** Entry time, target, volatility and bias filters were swept with a dev/holdout split. The current Open Drive stays best on holdout; rank correlation dev vs holdout was only 0.26, so no variant is adopted.
6. **Not supported by the bots.** The ES Compression ORB filler (single-instrument bots) and Range Breakout (entry parity with the backtest not verified) are excluded.

## Top 10 bundles per objective (ungoverned research harness, NQ/ES trade lists)

### A

| Bundle | Trades | Net $ | Net/DD | Pass≤60d % (Wilson lo) | Bust % | Pass60 H1/H2 | Payout≤180d % | Median days to payout |
|---|---|---|---|---|---|---|---|---|
| OD+IR+CAD+GAD | 1834 | 122,856 | 16.7 | 60.8 (17.9) | 35.0 | 67.4/51.2 | 22.5 | 83.0 |
| OD+CAD+GAD | 1598 | 108,400 | 15.2 | 59.6 (17.2) | 35.1 | 64.8/52.0 | 25.5 | 94.0 |
| OD+CAD+GAD+ORB | 1945 | 111,312 | 15.6 | 59.3 (17.9) | 35.7 | 63.2/55.0 | 27.4 | 91.5 |
| OD+IR+CAD+ORB | 1955 | 137,861 | 19.9 | 59.2 (17.9) | 38.6 | 64.0/53.8 | 27.6 | 71.0 |
| OD+IR+CAD+LSR | 2051 | 128,690 | 19.8 | 59.1 (17.0) | 35.7 | 64.6/51.1 | 31.7 | 83.0 |
| OD+IR+CAD | 1607 | 134,043 | 19.4 | 58.9 (16.9) | 38.7 | 65.3/49.6 | 22.9 | 81.0 |
| OD+CAD+GAD+TMC | 1659 | 105,667 | 14.2 | 58.9 (16.9) | 34.6 | 65.9/48.8 | 25.6 | 98.0 |
| OD+IR+CAD+TMC | 1664 | 131,872 | 17.8 | 58.0 (16.5) | 40.0 | 65.0/48.0 | 24.3 | 89.0 |
| OD+CAD+TMC+ORB | 1793 | 119,039 | 16.9 | 57.3 (16.9) | 39.0 | 61.1/53.3 | 25.7 | 92.0 |
| OD+IR+ORB | 1798 | 99,457 | 14.4 | 56.4 (16.4) | 30.3 | 57.9/54.6 | 29.2 | 73.0 |

### B

| Bundle | Trades | Net $ | Net/DD | Pass≤60d % (Wilson lo) | Bust % | Pass60 H1/H2 | Payout≤180d % | Median days to payout |
|---|---|---|---|---|---|---|---|---|
| IR+RB+CAD+ORB | 1757 | 70,378 | 15.5 | 38.5 (8.5) | 16.9 | 31.8/45.6 | 24.9 | 206.5 |
| IR+RB+CAD | 1409 | 66,244 | 14.5 | 35.4 (7.0) | 16.2 | 30.2/42.3 | 21.5 | 218.0 |
| IR+RB+LSR+ORB | 1996 | 41,792 | 20.3 | 4.3 (0.1) | 5.8 | 2.4/6.4 | 14.8 | 279.5 |
| IR+RB+GAD+ORB | 1914 | 38,408 | 20.6 | 3.1 (0.1) | 0.0 | 3.0/3.2 | 12.8 | 328.0 |
| IR+GAD+LSR+ORB | 1975 | 41,459 | 24.8 | 4.6 (0.2) | 0.0 | 4.9/4.3 | 12.0 | 272.0 |
| RB+CAD | 1139 | 50,865 | 10.8 | 27.8 (4.5) | 18.4 | 23.9/33.0 | 11.0 | 268.0 |
| IR+RB+TMC+ORB | 1824 | 37,903 | 18.4 | 2.5 (0.1) | 5.9 | 1.8/3.3 | 9.6 | 282.0 |
| IR+RB+TMC+LSR | 1887 | 39,435 | 20.0 | 1.6 (0.0) | 0.0 | 0.5/3.1 | 9.2 | 321.0 |
| IR+RB+ORB | 1530 | 35,929 | 22.3 | 2.6 (0.1) | 0.0 | 2.9/2.3 | 8.8 | 321.0 |
| IR+TMC+LSR+ORB | 1823 | 38,741 | 20.6 | 0.3 (0.0) | 0.0 | 0.0/0.6 | 6.8 | 297.5 |

### NET

| Bundle | Trades | Net $ | Net/DD | Pass≤60d % (Wilson lo) | Bust % | Pass60 H1/H2 | Payout≤180d % | Median days to payout |
|---|---|---|---|---|---|---|---|---|
| OD+IR+CAD+ORB | 1955 | 137,861 | 19.9 | 59.2 (17.9) | 38.6 | 64.0/53.8 | 27.6 | 71.0 |
| OD+IR+CAD | 1607 | 134,043 | 19.4 | 58.9 (16.9) | 38.7 | 65.3/49.6 | 22.9 | 81.0 |
| OD+IR+CAD+TMC | 1664 | 131,872 | 17.8 | 58.0 (16.5) | 40.0 | 65.0/48.0 | 24.3 | 89.0 |
| OD+IR+CAD+LSR | 2051 | 128,690 | 19.8 | 59.1 (17.0) | 35.7 | 64.6/51.1 | 31.7 | 83.0 |
| OD+IR+CAD+GAD | 1834 | 122,856 | 16.7 | 60.8 (17.9) | 35.0 | 67.4/51.2 | 22.5 | 83.0 |
| OD+CAD+ORB | 1726 | 122,123 | 18.2 | 55.4 (15.9) | 42.9 | 57.5/53.0 | 23.2 | 76.5 |
| OD+CAD+TMC+ORB | 1793 | 119,039 | 16.9 | 57.3 (16.9) | 39.0 | 61.1/53.3 | 25.7 | 92.0 |
| OD+CAD | 1380 | 118,578 | 15.9 | 54.8 (14.9) | 43.4 | 60.8/46.1 | 21.0 | 91.0 |
| OD+CAD+LSR+ORB | 2161 | 115,737 | 16.8 | 54.6 (15.5) | 41.1 | 58.2/50.6 | 26.6 | 76.0 |
| OD+CAD+TMC | 1447 | 115,494 | 15.7 | 55.2 (15.0) | 42.1 | 61.0/46.6 | 22.1 | 101.0 |

NET ranking above is ungoverned net dollars; see finding 4 for the governed equity result. T58 scores were not recomputed for these bundles; run them through Full Pipeline for the official score.

## Bot parity
The bot engine replays the same signals as the backtest. Open Drive: 86/86 entries match; Context Drive: 32/33. Ind Rule differs in a few entries because the bot skips entries the governor sizes to zero at a different bar. Context Drive needs about 500 days of history, so it runs in simulation but not on a short live feed.
