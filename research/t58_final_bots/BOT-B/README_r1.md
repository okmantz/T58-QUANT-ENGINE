# BOT-B: first and repeated payouts on a funded LucidFlex 50K

Research code only. Nothing here places, changes or cancels an order. Frozen 2026-11-23 (research/FROZEN_PICKS.md, sha256 d7bb0165...).

BOT-B is a funded-account bot. Its evaluation pass rate is near 0% (it sizes too small to make $3,000 in 30 days), so the intended use is:
pass with BOT-A (or your own method), then run BOT-B on the funded Flex account.

## What it trades
Micro futures, regular session, flat by 16:00 ET. Seven legs, same arbiter as BOT-A (max 2 open, one per instrument, ES/NQ hedge guard):
CDL_NQ 1, CDL_ES 1, ORB15C_NQ 1, ORB15C_ES 1, IR_NQ 1 (rules as in BOT-A/README.md), plus
- VWPB_NQ (0.5): with the daily trend (yesterday's close vs its 20-day average, price on the same side of VWAP at 09:59), the first
  touch of VWAP that closes back on the trend side between 10:00 and 15:00; stop 0.35 ATR, target 2R.
- ORB30T_NQ (0.5): first close beyond the 30-minute range, 10:00 to 12:00, only in the daily trend direction; stop at the far side
  of the range, target 3R.
Open Drive is left out on purpose: one 2020-03-10 Open Drive trade in the engine exits far beyond its stop and would set the worst day.

## Risk
- Funded: $150 x leg weight per trade, at most 30% of the cushion, $220 day stop, and no new trade after the day is up $200
  (keeps every day small, which is what Flex payouts reward: 5 days of $150+, and no day may dominate).
- Drawdown throttle: once equity is $300 below its peak, risk is cut to 25%.
- Evaluation settings exist (r_eval 500, $220 day stop, $1,100 day cap) but are not recommended.
- At current NQ prices one MNQ micro often risks more than the $220 day stop allows, so on MNQ many signals are skipped; MES carries more of the load.

## How to run it (engine)
`python3 final/run_bot.py B 2024-01-01 2025-09-01 stress flex50`. Pine: final/pine/T58_BOT.pine with Bot = B (no IR_NQ, no arbiter).

## Deploy
1. Paper trade 20 sessions on MNQ and MES.
2. Only on a funded LucidFlex 50K. Request a payout as soon as the account shows 5 qualifying days.

## Kill switch
- The funded balance falls $600 below its starting level (a third of the way to the floor).
- No qualifying $150 day in 15 sessions.
- Any day worse than -$250 (the engine's worst was -$220), or real slippage above 1.5 ticks a side.

## What would invalidate this
- Same evidence limits as BOT-A (no DSR pass; validation partly used for diagnosis).
- In the holdout BOT-B made a first payout more often than the baseline (7.5 to 8.8% vs 0%) but paid less over 90 funded days
  ($120 vs $384) and drew down more ($2,136 vs $883). The payout edge did not carry into Sep 2025 to Feb 2026.
