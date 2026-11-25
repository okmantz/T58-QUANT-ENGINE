# BOT-A (round 4): pass the LucidPro 50K evaluation

Research code only. Nothing here places, changes or cancels an order. Frozen 2026-11-24 before its holdout read
(research/FROZEN_PICKS_R4.md and FROZEN_PICKS_R4.sha256). Replaces round-3 A (params_r3.json, README_r3.md); earlier: params_r1.json.

**Bar (round 4, your 2026-11-24 message; research/PREREG_R4.md).** Primary: P(pass), median days to pass (and under 30), eval bust
and 90-day EV after fees and resets must beat or tie the current BOT-A. Limits ("can't break"): no other metric more than 10% worse
than the current BOT-A (25% for max drawdown and worst day), and worst day never below -$1,200. Stress cost decides.

**Verdict.** It meets the whole bar in research (2020-2023) and validation (2024-01 .. 2026-11-20) at stress cost. On the sealed
2016-2019 holdout, read once, it meets three of four primary tests and misses P(pass) by 0.1 point (14.9% vs 15.0%), and it misses
one limit (P(first payout in 30 funded days) 1.7% vs 4.5%). At base cost it meets every primary test in all three splits but breaks
the trade-quality limits in validation and the holdout.

## What it trades
Same seven legs as round 3, at most 2 positions open, one per instrument, ES/NQ hedge guard, at most 6 trades a day:
CDL_NQ 1, CDL_ES 1, ORB15C_NQ 1, ORB15C_ES 1, IR_NQ 1, OD_NQ 0.5, PDLB_GC 0.5 (rules in README_r3.md). No regime filter: none of the
causal filters tested (volatility band, trend efficiency, leg and bot equity) helped A on research.

## Risk (what changed in round 4)
- Evaluation: $800 x leg weight (round 3: $1,000), then two barrier terms you asked for:
  - cushion term: x (cushion over the drawdown floor / $2,000) ^ 0.5, so risk shrinks as the account nears the floor;
  - target term: x (1 - 0.3 x share of the $3,000 target already made), so it eases off as it nears the target.
  Still capped by what is left to the target (min $150), 40% of the cushion and what is left of the $650 day stop.
- Funded: $300 x weight, 30% of cushion, $400 day stop (round 3: $550), stop adding once the day is up $500 (new), Pro consistency
  guard with k 0.55. Drawdown throttle unchanged: $1,200 below peak cuts risk to 25%.
- Honest finding: the sizing did not raise the pass rate (round 3: 38.9% / 35.3%; round 4: 36.6% / 35.1%). What it bought is the
  limits: round 3 broke consistency blocks (research) and expectancy (validation); round 4 breaks none.

## Results at stress cost (research / validation / 2016-2019 holdout; final/COMPARISON.md)
| | Current BOT-A | BOT-A round 4 | BOT-A round 3 |
|---|---|---|---|
| P(pass in 30d) | 17.1% / 21.8% / 15.0% | 36.6% / 35.1% / 14.9% | 38.9% / 35.3% / 18.5% |
| Median days to pass | 23 / 19.5 / 19 | 16.5 / 15 / 14 | 15 / 14 / 14 |
| Eval bust | 0.8% / 4.1% / 1.3% | 0% / 0.9% / 0.1% | 0% / 1.8% / 1.1% |
| 90-day EV after fees and resets | -$160 / $26 / -$226 | $25 / $121 / -$198 | $107 / $115 / -$201 |
| Profit factor | 1.53 / 1.36 / 1.06 | 1.46 / 1.43 / 1.09 | 1.50 / 1.30 / 0.91 |
| Max drawdown | $3,502 / $6,041 / $5,943 | $3,040 / $2,932 / $2,699 | $2,775 / $4,209 / $7,154 |
| Worst day | -$691 / -$977 / -$1,055 | -$627 / -$637 / -$647 | -$627 / -$637 / -$648 |

Repo-format legs (what the zip ships, causal bar-count filter): P(pass) 34.0% / 31.7% / 14.5%; they break the Sortino limit in
research and expectancy, Sharpe and Sortino in validation (research/a_bar_r4.csv). Monte Carlo: final/mc_r4.csv.

## How to run it
`python3 final/run_bot.py A 2024-01-01 2026-11-21 stress` (add `--ports` for the repo-format leg files). Pine: final/pine/T58_BOT.pine,
Bot = A, on MNQ1!, MES1! and MGC1! 1-minute charts (no IR_NQ, no cross-instrument arbiter). The round-4 Pine edits were not compiled
on TradingView: the daily tool quota was used up. Compile it once before use.

## Deploy (if you choose to)
1. Paper trade 20 sessions on MNQ, MES and MGC; compare fills with the engine (next-bar-open entries, stop + 1 tick).
2. One LucidPro 50K evaluation at a time; hand the funded account to BOT-B or switch to the funded sizing the session after the pass.

## Kill switch
- Two failed evaluations in a row, or 30 sessions with profit factor below 1.0 at real fills.
- A day worse than -$700 (engine worst in all three splits: -$647).
- Real slippage above 1.5 ticks a side over 20 trades.

## What would invalidate this
- No leg passed the Deflated Sharpe gate; acceptance rests on research-to-validation replication at stress cost and the holdout.
- Every bot's edge was thin in 2016-2019 (current BOT-A PF 1.06, this one 1.09) and in Mar-Nov 2026. A's lead there comes from
  sizing (fewer busts, smaller drawdowns), not from better entries. If 60 live sessions show PF below 1.0, stop.
- Mar-Nov 2026 is part of validation in round 4 after being the round-3 holdout, so validation is not untouched data.
