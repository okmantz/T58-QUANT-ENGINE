# BOT-B (round 4): first and repeat payouts on a funded LucidFlex 50K

Research code only. Nothing here places, changes or cancels an order. Frozen 2026-11-24 before its holdout read
(research/FROZEN_PICKS_R4.md and FROZEN_PICKS_R4.sha256). Replaces round-3 B (params_r3.json, README_r3.md); earlier: params_r1/_r2.

**Bar (unchanged):** beat or tie the current BOT-B on every metric, in every split, at stress cost.

**Verdict: closest yet, not all the way.** At stress cost it beats or ties the current BOT-B on 49 of 54 cells (18 metrics x research,
validation, 2016-2019 holdout). Misses: trades a month in research (11.3 vs 18.1) and validation (11.5 vs 13.5); on the holdout,
90-day lifecycle EV (-$137 vs -$130), payouts in 90 funded days (0.56 vs 0.62) and P(2+ payouts) (10.9% vs 13.7%). Round-3 B,
scored the same way, misses 8 of 54.

BOT-B is a funded-account bot: its evaluation pass rate is near 0%. Pass with BOT-A (or your own way), then run BOT-B on Flex.

## What changed in round 4
- Regime filter (your point 3, pre-registered rule, code/regime.py): ORB15C_ES trades only while its own last 10 closed signals
  (taken or not) average above 0R. It was the only leg where a causal filter cleared the research rule. Filters on the NQ legs that
  lost in Mar-Nov 2026 did not survive research, so they were not added.
- Open Drive ES weight 0.5 (from 0.25).
- Everything else as round 3 (README_r3.md): twelve legs, up to 4 open, crash filter, $250 funded risk, $300 day stop, $200 day cap.

## Why this one and not the variant with fewer misses
None of 144 B variants clears the bar. Five miss one cell fewer (only research trades a month) but they get there by trading more
and pay about half as much (validation $468 vs $941 in 90 funded days, first payout 28% vs 45%). Trades a month measures activity,
not payouts, so this pick keeps the trade-count miss and the payouts. Logged in research/FROZEN_PICKS_R4.md before the holdout read.

## Results at stress cost (research / validation / 2016-2019 holdout; final/COMPARISON.md)
| | Current BOT-B | BOT-B round 4 | BOT-B round 3 |
|---|---|---|---|
| P(first payout in 30 funded days) | 19.0% / 11.1% / 23.7% | 52.5% / 44.9% / 25.1% | 49.4% / 42.7% / 21.1% |
| $ paid in 90 funded days | $365 / $297 / $196 | $728 / $941 / $202 | $721 / $872 / $204 |
| P(2+ payouts in 90 days) | 22.9% / 11.2% / 13.7% | 55.4% / 52.9% / 10.9% | 52.2% / 51.1% / 13.0% |
| Profit factor | 1.17 / 1.16 / 0.85 | 1.30 / 1.36 / 0.87 | 1.25 / 1.36 / 0.87 |
| Max drawdown | $2,011 / $1,801 / $6,487 | $1,758 / $1,331 / $6,318 | $1,825 / $1,384 / $6,593 |
| Trades a month | 18.1 / 13.5 / 23.1 | 11.3 / 11.5 / 43.1 | 12.7 / 12.8 / 46.5 |

2016-2019 note: every B variant, baseline included, lost money there (PF 0.85 to 0.91). Index prices were far lower then, so stops in
points cost fewer dollars and many more signals fit the $250 budget (43 trades a month vs 11). The holdout tests the bot in a
different sizing regime as well as a different market. Flex lock-on-payout sensitivity: final/COMPARISON.md. Monte Carlo: final/mc_r4.csv.

## How to run it
`python3 final/run_bot.py B 2024-01-01 2026-11-21 stress flex50` (add `--ports`). Pine: final/pine/T58_BOT.pine with Bot = B, one chart
each on MNQ1!, MES1!, MGC1! (no IR_NQ, no 4-position cross-instrument cap). The ORB15 equity filter is ported as virtual trades on
the MES chart. The round-4 Pine edits were not compiled on TradingView (daily tool quota used up); compile it once before use.

## Deploy (if you choose to)
1. Paper trade 20 sessions on MNQ, MES and MGC.
2. Only on a funded LucidFlex 50K. Request a payout as soon as the account shows 5 qualifying $150 days.

## Kill switch
- The funded balance falls $1,000 below its start.
- No qualifying $150 day in 15 sessions.
- Any day worse than -$320 (the $300 day stop plus slippage), or real slippage above 1.5 ticks a side.

## What would invalidate this
- No leg passed the Deflated Sharpe gate.
- The edge was negative in 2016-2019 for every B variant and the baseline; payouts there came from the Flex rules, not the entries.
- Research and validation trade counts stay below the baseline's.


## Round 5 alternative (not shipped)
params_r5_alt.json (search tag B2-26) has fewer shortfall cells than this pick on 2016-2026 (2 vs 5 at stress cost) but fails the rotation and plateau checks and pays out less often on 2020-2026. See ../T58_FINAL_BOTS_ROUND5_2026-11-24.md.
