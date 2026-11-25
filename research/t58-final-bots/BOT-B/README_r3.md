# BOT-B (round 3): first and repeat payouts on a funded LucidFlex 50K

Research code only. Nothing here places, changes or cancels an order. Frozen 2026-11-24 before its holdout read
(research/FROZEN_PICKS_R3.md, sha256 2f478200...). Replaces round-2 B (params_r2.json, README_r2.md); round 1: params_r1.json.

**Verdict: closest to the brief, but not all the way.** At stress cost it beats or ties the current BOT-B on 51 of 54 cells
(18 metrics x research, validation, holdout). It misses three: research trades a month (12.7 vs 18.1), and on the holdout max
drawdown ($2,954 vs $1,329) and worst day (-$299 vs -$162). On the fresh holdout it paid out 4.6x as much as the baseline.

BOT-B is a funded-account bot: its evaluation pass rate is near 0%. Pass with BOT-A (or your own way), then run BOT-B on Flex.

## What it trades
Micro futures (MNQ, MES, MGC), regular session, flat by 15:55 ET. Twelve legs, at most 4 positions open across instruments
(two legs may hold the same instrument), ES/NQ hedge guard, at most 6 trades a day:
- CDL_NQ 1, CDL_ES 1, ORB15C_NQ 1, ORB15C_ES 1, IR_NQ 1: as in BOT-A/README.md.
- VWPB_NQ 0.5: VWAP pullback with the daily trend, 10:00-15:00; stop 0.35 ATR, 2R.
- ORB30T_NQ 0.5: first close beyond the 30-minute range with the 20-day trend, 10:00-12:00; stop at the far side, 3R.
- OD_ES 0.25 and OD_NQ 0.25 (new): repo Open Drive on ES and NQ.
- CORB_ES 0.5 (new): repo Compression ORB (CompressionORB_ES_5m_v1), unchanged.
- PDLB_GC 1.0: prior-day break on gold in a quiet regime, 3R.
- GAP_GC 0.5 (new): RTH open more than 0.4 ATR from the prior close in the 20-day trend direction; signal at 09:34, stop 0.5 ATR, 3R.
- Crash filter: a leg's risk is halved when its instrument's 2-year return is negative and its 6-month volatility is above its median.

## Risk
- Funded: $250 x leg weight per trade, 30% of the cushion, $300 day stop (round 2: $220), no new trade once the day is up $200.
- Drawdown throttle: $400 below peak cuts risk to 25%. One-micro minimum only while one micro risks <= 3x the budget.

## Results at stress cost (final/COMPARISON.md)
| | Baseline B | BOT-B (round 3) |
|---|---|---|
| P(first payout in 30 funded days): research / validation / holdout | 19.0% / 12.0% / 9.7% | 49.4% / 47.3% / 24.0% |
| $ paid in 90 funded days | $365 / $367 / $161 | $721 / $964 / $742 |
| P(2+ payouts in 90 days) | 22.9% / 15.3% / 0% | 52.2% / 56.1% / 41.5% |
| Profit factor | 1.17 / 1.24 / 0.76 | 1.25 / 1.36 / 0.99 |
| Max drawdown | $2,011 / $1,628 / $1,329 | $1,825 / $1,384 / $2,954 |
| Trades a month | 18.1 / 15.2 / 9.3 | 12.7 / 17.0 / 15.5 |

Monte Carlo: final/mc_r3.csv.

## How to run it
`python3 final/run_bot.py B 2024-01-01 2026-03-02 stress flex50` (add `--ports` for the repo-format leg files). Pine:
final/pine/T58_BOT.pine with Bot = B, one chart each on MNQ1!, MES1!, MGC1! (no IR_NQ, no 4-position cross-instrument cap).

## Deploy (if you choose to)
1. Paper trade 20 sessions on MNQ, MES and MGC.
2. Only on a funded LucidFlex 50K. Request a payout as soon as the account shows 5 qualifying $150 days.

## Kill switch
- The funded balance falls $1,000 below its start (engine worst holdout drawdown was $2,954 from peak, so size the account cushion for that).
- No qualifying $150 day in 15 sessions.
- Any day worse than -$320 (the $300 day stop plus slippage), or real slippage above 1.5 ticks a side.

## What would invalidate this
- No leg passed the Deflated Sharpe gate.
- Its drawdown on the holdout was more than twice the baseline's. The higher $300 day stop and four open positions are why; that
  is the price of the extra payouts.
- Round-2 B (params_r2.json) did better than this pick on the Mar-Nov 2026 holdout (first payout 26.3% vs 24.0%, PF 1.28 vs 0.99,
  max drawdown $1,531 vs $2,954) but has more shortfalls overall (5 vs 3 of 54). The pick was frozen before the read and is not
  switched on holdout results; R2 is the lower-drawdown alternative.
- Research-split trade count stays below the baseline's (12.7 vs 18.1 a month).
- The research factory's mild whole-day filter lookahead (see BOT-A); with the causal repo-format legs the holdout P(first payout) is
  26.8% (vs 24.0%), but PF falls to 1.00.
- Lucid changing Flex payout rules (5 days of $150, 50% split, $2,000 cap) changes every number here.
