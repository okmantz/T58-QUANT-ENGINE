# BOT-A: pass the LucidPro 50K evaluation

Research code only. Nothing here places, changes or cancels an order. Frozen 2026-11-23 (research/FROZEN_PICKS.md, sha256 d7bb0165...).

## What it trades
Micro futures, regular session (09:30 to 16:00 ET), flat by 16:00. Six signal legs, at most 2 positions open, one per instrument,
never long one index and short the other at the same time, at most 6 trades a day:

| Leg | Instrument | Rule (decided on a closed bar, filled at the next bar open) | Weight |
|---|---|---|---|
| CDL_NQ | MNQ | Context Drive Long (repo ContextDriveLong_NQ_1m_v2): long when the open is above yesterday's close, 50 EMA above 200 EMA on daily bars, price above VWAP and in the top 30% of the day's range after a 0.15 to 0.6 ATR move; trailing stop | 1 |
| CDL_ES | MES | Same rule on ES | 1 |
| ORB15C_NQ | MNQ | After a compressed day (range < 0.7 ATR): first close beyond the 15-minute opening range, 09:45 to 12:00; stop 0.25 ATR inside the range, target 3R | 1 |
| ORB15C_ES | MES | Same, target 2R | 1 |
| IR_NQ | MNQ | Repo Ind Rule (IndRule_NQ_15m_v1, Discovery Lab indicator rule) | 1 |
| OD_NQ | MNQ | Open Drive (repo OpenDrive_NQ_5m_v1): 10:30 entry in the direction of the first hour's move if it is at least 0.10 ATR; stop 0.35 ATR; hold to 15:55 | 0.5 |

## Risk (per trade, in dollars of risk to the stop)
- Evaluation: $800 x leg weight, but never more than what is still needed to reach the $3,000 target (minimum $150),
  never more than 40% of the cushion above the trailing floor, never more than what is left of a $650 day stop.
- Funded: $300 x weight, 30% of cushion, $550 day stop; on Pro funded a consistency guard caps a day so it cannot exceed
  the larger of $300, 55% of the cycle's profit, or 20% of what the cycle still has to make (uses 2.5R of room per trade).
- Drawdown throttle: once equity (balance plus payouts) is $1,600 below its peak, risk is cut to 25%.
- One micro is allowed when the budget is smaller than one micro, only if that micro risks at most 35% of the cushion and fits the day stop.

## How to run it (engine)
`python3 final/run_bot.py A 2024-01-01 2025-09-01 stress` prints the full metric set from the same code used for every number in
final/COMPARISON.md. The Pine port is final/pine/T58_BOT.pine (set Bot = A); it leaves out IR_NQ and the cross-instrument arbiter.

## Deploy
1. Paper trade it first on both MNQ and MES for at least 20 sessions and compare fills with the engine's (entries at the next bar
   open, stops filled at the stop plus 1 tick).
2. Buy one LucidPro 50K evaluation. Run the eval sizing until the pass. Switch to the funded sizing the next session.
3. Keep 2 micros of margin per instrument free; the bot never holds more than 2 positions.

## Kill switch (stop the bot and reassess)
- Two failed evaluations in a row, or a 30-day stretch with profit factor below 1.0 at real fills.
- A single day worse than -$700 (the engine never had one worse than -$647).
- Real slippage averaging more than 1.5 ticks a side (the stress cost) over 20 trades.
- The holdout (Sep 2025 to Feb 2026) already shows the edge can switch off for months: if the last 60 sessions are net negative, stop.

## What would invalidate this
- The edge was accepted on research-to-validation replication and PBO, not on the Deflated Sharpe gate, which no leg passed.
- In the holdout every bot lost money, baseline included; BOT-A's pass rate there (12.6%) is below the baseline's (16.8 to 18.9%).
- Validation was looked at to diagnose earlier searches, so it is not fully untouched for the policy shape.
- NQ is now far higher priced and more volatile than in most of the data; per-trade stops in points are larger, so fewer trades can be sized.
