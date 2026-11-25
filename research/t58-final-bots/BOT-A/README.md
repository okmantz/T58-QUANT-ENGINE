# BOT-A (round 6, 2026-11-25): pass the Lucid Pro 50K evaluation

Research code only. Nothing here places, changes or cancels an order. Frozen before its 2026 read (research/FROZEN_PICKS_R6.md, .sha256).
Replaces round-4 A (params_r4.json, README_r4.md). Report: final/T58_FINAL_BOTS_ROUND6_2026-11-25.md.

- Legs, max open and sizing as round 4 (README_r4.md), except evaluation risk $920 (was $800).
- Five entry filters (params.json "fspec"; reference code: code/r6feat.py and r6.fapply):
  CDL_NQ skip if VIX 5-day change <= 0.9581; CDL_ES skip if VIX/VIX3M <= 0.8354; ORB15C_NQ skip if prior TICK close x direction <= -113;
  ORB15C_ES skip if the 09:30 open is outside the prior RTH value area on the trade's side; OD_NQ skip if |gap| / ATR14 <= 0.1944.
- Pro 100K: every dollar knob x1.75 ("k100").
- All its numbers are in-sample (ES/NQ/GC 2016-2026 were read in earlier rounds). Remaining shortfall vs the baseline bar at stress:
  Pro 50K 2024-07 .. 2026-01 profit factor, expectancy, Sharpe and Sortino; Pro 100K 2021-24 median days to payout.
Run: `python3 final/run_bot.py A 2024-07-16 2026-01-05 stress pro50`
