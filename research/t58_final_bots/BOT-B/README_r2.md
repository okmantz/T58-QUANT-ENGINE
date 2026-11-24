# BOT-B (round 2): first and repeated payouts on a funded LucidFlex 50K

Research code only. Nothing here places, changes or cancels an order. Frozen 2026-11-24 (research/FROZEN_PICKS_R2.md, sha256 3092f259...).
Replaces round-1 B (BOT-B/params_r1.json, README_r1.md).

BOT-B is a funded-account bot. Its evaluation pass rate is near 0% (it sizes too small to make $3,000 in 30 days), so the intended
use is: pass with BOT-A (or your own method), then run BOT-B on the funded Flex account.

## What it trades
Micro futures (MNQ, MES, MGC), regular session, flat by 16:00 ET. Nine legs, at most 3 positions open, one per instrument, never
long one index and short the other at the same time, at most 6 trades a day:
- CDL_NQ 1, CDL_ES 1, ORB15C_NQ 1, ORB15C_ES 1, IR_NQ 1: rules as in BOT-A/README.md.
- VWPB_NQ 0.5: with the daily trend, the first VWAP touch that closes back on the trend side, 10:00-15:00; stop 0.35 ATR, target 2R.
- ORB30T_NQ 0.5: first close beyond the 30-minute range, 10:00-12:00, trend direction only; stop at the far side, target 3R.
- OD_ES 0.25 (new): repo Open Drive on ES: 10:29 close at least 0.10 ATR from the 09:30 open, enter 10:30 that way, stop 0.35 ATR,
  hold to 15:55.
- PDLB_GC 1.0 (new): first close beyond the prior RTH high or low between 10:00 and 14:00 on gold, only when the 14-day RTH range
  is below its 120-day median; stop 0.5 ATR from the signal close, target 3R. Gold barely correlates with the index legs.
- Crash filter (new, Daniel and Moskowitz): risk on a leg is halved when its instrument's 2-year return is negative and its 6-month
  volatility is above its long-run median. Every input is from prior sessions only.

## Risk
- Funded: $250 x leg weight per trade, at most 30% of the cushion, $220 day stop, and no new trade after the day is up $200.
- Drawdown throttle: once equity is $400 below its peak, risk is cut to 25%.
- One-micro minimum, capped (new): when the budget is smaller than one micro at the trade's stop, take one micro only if that micro
  risks at most 3x the budget (and under 35% of the cushion). Round 1 had no cap, which let one-micro trades in high-ATR stretches
  (2020-03) override both the small budget and the drawdown throttle; that is where its drawdown came from.
- Evaluation settings exist (r_eval 300) but are not recommended.

## Results (stress cost, final/COMPARISON.md)
Research and validation: beats or ties the baseline on every metric except trades a month (6.5 and 13.2 vs 18.1 and 15.6).
First payout in 30 funded days 49% / 55% vs 19% / 16%; $795 / $929 paid in 90 funded days vs $365 / $401; max drawdown
$1,213 / $1,182 vs $2,011 / $1,628. Monte Carlo (40,000 paths): first payout 44-46% vs baseline 10-16%, median 19-22 days.
Holdout (Sep 2025 to Feb 2026, a losing period for every bot): first payout 9.8% vs 0%, but PF 0.89 vs 0.92, max drawdown $2,051
vs $883, $53 vs $384 paid in 90 funded days.

## How to run it (engine)
`python3 final/run_bot.py B 2024-01-01 2025-09-01 stress flex50`. Pine: final/pine/T58_BOT.pine with Bot = B, one chart each on
MNQ1!, MES1! and MGC1! (no IR_NQ, no cross-instrument cap of 3).

## Deploy
1. Paper trade 20 sessions on MNQ, MES and MGC.
2. Only on a funded LucidFlex 50K. Request a payout as soon as the account shows 5 qualifying days.

## Kill switch
- The funded balance falls $600 below its starting level.
- No qualifying $150 day in 15 sessions.
- Any day worse than -$250 (the engine's worst was -$220), or real slippage above 1.5 ticks a side.

## What would invalidate this
- No leg passed the Deflated Sharpe gate; the edge rests on research to validation replication at stress cost.
- The holdout window was read twice (round 1 and round 2). Round 2 did not tune on it, but it is no longer a fully clean test.
- The holdout already shows the edge switching off for six months. If 60 live sessions look like it, stop.
- The trade count is lower than the baseline's; fewer trades means more months where no 5 qualifying days arrive.
- Lucid changing the Flex payout rules (5 days of $150, 50% cap, $2,000 max) changes every number here.
