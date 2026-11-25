# T58 final bots, round 6 (2026-11-25)

Research and code only: nothing here places, changes or cancels an order, and no account was touched.
Full tables: T58_FINAL_BOTS_ROUND6_2026-11-25_tables.md. Rules: research/PREREG_R6.md (+2 addenda), picks: research/FROZEN_PICKS_R6.md.

## Answer
- **BOT-A: new pick (round-6 config A59), for Lucid Pro 50K.** Same seven legs and sizing as the round-4 BOT-A, risk raised to $920,
  plus five entry filters built from the new inputs. It replaces the round-4 BOT-A under the pre-registered rule, but by a narrow margin.
- **BOT-B: round-4 BOT-B stays.** On Pro no config beats the baseline on every metric; the closest Pro design (B785) is documented only.
- **No crude oil or natural gas strategy passed**, so neither bot trades them. The 2026 crude/gas data is still sealed and unread.
- **Every ES/NQ/GC number in this round is in-sample**: all of that data was read in rounds 1-5. There is no clean holdout left for them.

## Inputs asked for, and what was possible
| input | status |
|---|---|
| VIX level, VIX/VIX3M term, VIX 5-day change | used (TradingView daily) |
| NYSE TICK | daily close only (TradingView keeps ~6 months of intraday TICK, too short; daily bars have no range) |
| Overnight gap size, overnight range | used (1m data) |
| Volume profile | prior-session value area from 1m volume; footprint / bid-ask volume not available (no tick or order-flow data) |
| News: FOMC, NFP | FOMC dates 2016 .. Jan 2026 (TradingView calendar ends there); NFP by the first-Friday rule. CPI not pulled (TradingView quota) |
| GEX | not available: no free history found |
Filter test: 252 (leg, input, side) trials, 26 kept (removed trades worse than the leg's average in every period). Chance alone would
keep about 31 of 252 at that rule, so the filter set as a whole is not evidence of an edge; only the bot-level tests below decide.
No FOMC or NFP filter was kept. The ones that recur: skip small overnight gaps, skip opens inside the prior value area.

## Crude oil and natural gas
1,198 strategy variants (the round-1 families plus a weekly inventory-report breakout) were screened on 2021-01 .. 2024-07 and
checked on 2024-07 .. 2026-01 at stress cost (MCL/MNG $2.14 a round trip [ASM], 1.5 ticks slippage a side). None passed; the best
research t-stat was 0.73 (bar 1.5). Lucid allowing energy products is also unverified [ASM].

## BOT-A
Filters (each skips that leg's entry; thresholds are research terciles): CDL_NQ when VIX 5-day change <= 0.958; CDL_ES when
VIX/VIX3M <= 0.835 (deep contango); ORB15C_NQ when the prior NYSE TICK close, signed by trade direction, <= -113; ORB15C_ES when
the open is outside the prior value area on the trade's own side; OD_NQ when |overnight gap| / ATR14 <= 0.194.

Stress cost, Pro 50K (2021-01 .. 2024-07 / 2024-07 .. 2026-01):
| | baseline | round-4 A | round-6 A |
|---|---|---|---|
| P(pass in 30 days) | 17.3% / 22.2% | 40.0% / 40.1% | 41.4% / 37.5% |
| 90-day EV after fees | -$139 / -$135 | $75 / $164 | $80 / $152 |
| Max drawdown | $3,502 / $3,657 | $2,503 / $2,544 | $1,921 / $1,930 |
| Profit factor | 1.47 / 1.57 | 1.57 / 1.45 | 1.79 / 1.30 |
Pro 100K (dollar knobs x1.75; fee $268 and reset $188 are [ASM]): EV $80 / $62 vs round-4 -$13 / -$103.

Shortfall vs the baseline bar (PREREG_R4), stress: round-6 A misses in one decision cell, Pro 50K 2024-07 .. 2026-01: profit factor
1.30 vs 1.57, expectancy, Sharpe 1.69 vs 2.45, Sortino; and Pro 100K 2021-24 median days to payout. Round-4 A misses in three cells.
Honest read: the gain is mostly on Pro 100K and in lower drawdown. On Pro 50K in 2024-07 .. 2026-01 it is slightly worse than the
round-4 A (P(pass) 37.5% vs 40.1%, EV $152 vs $164). Rotation and plateau checks passed (18 of 26 neighbours within one cell), but the
result leans on one filter: without the TICK filter on ORB15C_NQ it falls back to four shortfall cells.

2026 (read once after freezing; in-sample): every bot loses money. Pro 50K: round-6 A P(pass) 19.3%, EV -$228, max drawdown $2,460;
round-4 A 18.0%, -$214, $3,630; baseline 9.8%, -$239. Monte Carlo (70-session paths, stress): 90-day EV is about break-even on
2024-2026 days (+$6 / -$10) and negative on 2016-2026 days (-$56 / -$72), better than round-4 A (-$38 / -$32 and -$69 / -$94) and
the baseline. Treat the positive window EVs as optimistic.

Plan: Pro 50K (higher stress EV in both windows: $80 vs $80 and $152 vs $62 on 100K).

## BOT-B
The repo baseline_B barely trades on Pro (no consistency blocks, max drawdown ~$1,000-1,400, worst day ~-$250-325 on Pro 50K), so a
bot that actually trades for payouts cannot beat or tie it on every metric. Best of 800 Pro configs: 4 shortfall cells of 4.
Exact shortfall of the round-4 BOT-B on Pro 50K at stress: 2021-24 max drawdown $1,679 vs $1,408 and consistency blocks 0.14 vs 0 per
30 days; 2024-26 also profit factor, expectancy, Sharpe, Sortino, worst day -$300 vs -$246, max drawdown $3,114 vs $996.
B785 (documented Pro design, not validated): 90-day paid $1,434 / $1,003 vs round-4 B $351 / $485, but worse worst day, drawdown and
consistency blocks than the baseline, and it lost more than round-4 B in 2026.
On Pro, BOT-A also pays more than BOT-B (90-day paid $1,128 / $909 vs $351 / $485), so for Pro the A bot is the one to run.

## What changed in the package
final/BOT-A/params.json (round-6; round 4 kept as params_r4.json), app/bots/t58_final_bots.py (T58_PICKS["A"], T58_ENTRY_FILTERS),
pine/T58_BOT.pine (A: $920 risk and the five filters via CBOE:VIX, CBOE:VIX3M, USI:TICK daily and a prior-session value area; round 4
kept as T58_BOT_r4.pine). The Pine file has NOT been compile-checked: the TradingView daily quota was used up. run_bot.py takes pro100.
