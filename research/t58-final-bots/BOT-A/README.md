# BOT-A (round 3): pass the LucidPro 50K evaluation

Research code only. Nothing here places, changes or cancels an order. Frozen 2026-11-24 before its holdout read
(research/FROZEN_PICKS_R3.md, sha256 2f478200...). Replaces round-1 A (params_r1.json, README_r1.md).

**Verdict: does not meet the brief.** It passes more often, faster and busts less than the current BOT-A in every split, including
the fresh Mar-Nov 2026 holdout, but it does not beat it on every metric. At stress cost it misses 11 of 42 cells (14 metrics x
research, validation, holdout); 7 of those are on the holdout, where every bot, baseline included, lost money.

## What it trades
Micro futures (MNQ, MES, MGC), regular session, flat by 15:55 ET. Seven legs, at most 2 positions open, one per instrument, never
long one index and short the other at once, at most 6 trades a day. Each rule decides on a closed bar and fills at the next bar open.

| Leg | Instrument | Rule | Weight |
|---|---|---|---|
| CDL_NQ | MNQ | Context Drive Long (repo ContextDriveLong_NQ_1m_v2) | 1 |
| CDL_ES | MES | Same rule on ES | 1 |
| ORB15C_NQ | MNQ | After a compressed day (prior range < 0.7 ATR): first close beyond the 15-minute range, 09:45-12:00; stop 0.25 ATR inside, 3R | 1 |
| ORB15C_ES | MES | Same, 2R | 1 |
| IR_NQ | MNQ | Repo Ind Rule (IndRule_NQ_15m_v1) | 1 |
| OD_NQ | MNQ | Open Drive (repo OpenDrive_NQ_5m_v1): 10:30 entry with the first hour's move if >= 0.10 ATR; stop 0.35 ATR; hold to 15:55 | 0.5 |
| PDLB_GC (new) | MGC | First close beyond the prior RTH high or low, 10:00-14:00, only when ATR is below its 120-day median; stop 0.5 ATR, 3R | 0.5 |

## Risk (dollars at risk to the stop)
- Evaluation: $1,000 x leg weight (round 1: $800), never more than what is still needed to reach $3,000 (min $150), 40% of the
  cushion, or what is left of a $650 day stop.
- Funded: $300 x weight, 30% of cushion, $550 day stop; Pro consistency guard as round 1.
- Drawdown throttle: once equity is $1,200 below its peak (round 1: $1,600), risk is cut to 25%.

## Results at stress cost (1.5x commission and slippage; final/COMPARISON.md)
| | Baseline A | BOT-A (round 3) |
|---|---|---|
| P(pass in 30d): research / validation / holdout | 17.1% / 25.3% / 12.6% | 38.9% / 39.3% / 17.9% |
| Median days to pass | 23 / 20 / 13 | 15 / 14 / 12.5 |
| Eval bust | 0.8% / 1.7% / 12.6% | 0% / 0% / 7.7% |
| Profit factor | 1.53 / 1.51 / 0.97 | 1.50 / 1.52 / 0.88 |
| Max drawdown | $3,502 / $6,041 / $3,141 | $2,775 / $3,016 / $3,341 |

Shortfalls: research PF, median days to first payout and consistency blocks; validation expectancy (0.20R vs 0.24R); holdout EV,
PF, expectancy, Sharpe, Sortino, max drawdown and consistency blocks. Monte Carlo: final/mc_r3.csv.

## How to run it
`python3 final/run_bot.py A 2024-01-01 2026-03-02 stress` (add `--ports` for the repo-format leg files). Pine: final/pine/T58_BOT.pine,
Bot = A, on MNQ1!, MES1! and MGC1! 1-minute charts (no IR_NQ, no cross-instrument arbiter).

## Deploy (if you choose to)
1. Paper trade 20 sessions on MNQ, MES and MGC; compare fills with the engine (next-bar-open entries, stop + 1 tick).
2. One LucidPro 50K evaluation at a time; switch to the funded sizing the session after the pass, or hand the funded account to BOT-B.

## Kill switch
- Two failed evaluations in a row, or 30 sessions with profit factor below 1.0 at real fills.
- A day worse than -$700 (engine worst: -$642 on the holdout).
- Real slippage above 1.5 ticks a side over 20 trades.

## What would invalidate this
- No leg passed the Deflated Sharpe gate; acceptance rests on research-to-validation replication at stress cost.
- On the Mar-Nov 2026 holdout the trade-level edge was gone (PF 0.88, expectancy -0.01R) for this bot and the baseline (PF 0.97).
  Its pass-rate lead held only because of the sizing. If 60 live sessions look like that, stop.
- The research leg factory used a whole-day "enough bars" filter (mild lookahead). The repo-format ports use a causal filter; with
  them the holdout P(pass) is 17.6% vs 17.9% and PF 0.83 vs 0.88 (research/final_hold_r3.csv, rows BOT-A-R3-port).
