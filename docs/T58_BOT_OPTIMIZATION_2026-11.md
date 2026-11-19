# Bot optimisation study, 2026-11-18

Question: can a profit-lock ladder, an adaptive loser cut, the "5 winning days" payout rule or an FOMC overlay make the three bots satisfy their objectives
materially better? Method, every number and the decisions taken are below. Reproduce with `scripts/run_bot_optimization.py` (`trades`, `books`, `paired`).

## Method (so a good number cannot be an accident)

* Data: bundled NQ and ES 1-minute history, 2020-01-01 to 2026-03-01. Splits: **train** 2020-01..2023-12, **validation** 2024, **hold-out** 2025-01..2026-03.
* Every strategy x instrument x risk variant ran through the real bar engine (`bundle_research.run_trades`, costs and slippage included), then through the
  same scorecards the earlier study used (`app/prop/objective_scorecard.py`): A = P(pass in 30 days), B = P(first payout within a year), C = compounded net profit.
* Selection used train and validation only; a candidate is adopted only if it wins on **both**. The hold-out was read once and never used to choose.
* Variants: `base`, profit-lock ladder at 3x and 6x the dollar rungs (trail 72% past the last rung), adaptive loser cut at 80%, ladder + cut, and
  "no entries on an FOMC decision day". Each overlay was one paired comparison on a finished book (30 looks in all), so only train-and-validation agreement counts.

## 1. The profit-lock ladder and the loser cut do not add edge to these strategies

Net profit of one strategy alone on NQ, whole history (OpenDrive etc. at the engine's prop sizing):

| Strategy | base | lock x2 | lock x4 | lock x8 | cut 60% | cut 80% |
|---|---:|---:|---:|---:|---:|---:|
| Open Drive 5m | $78,974 | $20,321 | $51,331 | $79,479 | $67,293 | $76,199 |
| Ind Rule 15m | $24,094 | $22,463 | $24,094 | $24,094 | $21,539 | $23,199 |
| Context Drive Long 1m | $55,406 | $45,207 | $52,266 | $55,143 | $53,018 | $54,824 |
| Liquidity Sweep Reclaim 5m | $9,159 | $8,769 | $9,159 | $9,159 | $9,217 | $9,233 |

At the rungs as typed ($100 / $200 / $300 / $400) the ladder moves the stop to break-even after a 0.2R gain on a trade whose stop is about $500: Open Drive keeps
6% of its profit. These are trend legs with no target; they pay for the few big runs and the ladder clips those. At 6x the rungs it costs almost nothing, and it
still adds almost nothing. The loser cut gives up winners that dip before they run.

Book level, shipped books, p(pass in 30 days) for A and first-payout odds for B (train / validation / hold-out):

| Book | base | lock x3 | lock x6 | cut | lock x6 + cut | no FOMC day |
|---|---|---|---|---|---|---|
| A, P(pass 30d) % | 50.5 / 59.3 / 35.2 | 43.2 / 58.3 / 33.6 | 49.8 / 62.0 / 38.0 | 48.0 / 59.3 / 35.2 | 48.8 / 62.0 / 38.9 | 50.6 / 58.1 / 41.0 |
| C, net $K (train / val / hold-out) | 1,336 / 298 / 39 | 1,158 / 290 / 20 | 1,362 / 285 / 41 | 1,334 / 289 / 44 | 1,352 / 245 / 47 | 1,324 / 358 / 48 |

(C's train and validation dollars are compounding artefacts of 1% a trade on a growing account, capped at $250K of sizing equity; read them only against each
other. The hold-out, 14 months, is the realistic column.) No overlay improves train **and** validation, so none is switched on in a shipped bot. They remain options
(Trading Bots > New bot > Advanced: profit lock, ladder size, loser cut) and the Optimize page tests them on your own data.

## 2. FOMC

* Two pre-registered event strategies (trade the 14:00 ET decision-day bar with or against it, one trade a day, hold to 15:50, no parameter search):
  with-the-move 46 trades, **-$4,245**, 30% wins; against-the-move 43 trades, +$1,021, 47% wins, but -$1,828 in 2025. About eight events a year cannot carry a book
  and neither shows an edge, so neither was added to the library.
* "No entries on FOMC day" as an overlay: see the last column above. It helps C's validation and hold-out and costs C's train; it does not help A or B. Not adopted.
* Conclusion: there is no quick-pass edge in FOMC with these strategies. The Optimize page still tests it.

## 3. Objective B and the "5 winning days" payout rule

Rule built into the simulators (`PropRules.payout_rule_mode = "winning_days_net_positive"`, `app/prop/payout_rule.py`, the bot `AccountState`): a payout is due once
five days since the last payout each made at least $250 (any order), and the cycle's net P&L is positive. The owner's example (+250, -50, +300, -100, +127, +260,
-200, +250, -98, +271) first qualifies on **day 10** with a **$1,010** payout, in both simulators (`tests/prop/test_payout_rule_winning_days.py`).

Under that rule, first payout within 365 days (train / validation / hold-out; hold-out has only 5 to 48 overlapping starts, so it is indicative only):

| Book | train | validation | hold-out | median days to payout (train / val) |
|---|---:|---:|---:|---|
| Shipped before (Ind Rule x1 + Context Drive Long x1) | 22.9% | 60.0% | 0.0% (5 starts) | 221 / 140 |
| **New: Ind Rule x1 + Compression ORB (ES) x0.25 + Open Drive x0.25** | **86.3%** | **69.2%** | 14.6% (48 starts) | 207 / 131 |

The rule needs many ordinary winning days, not a few big ones, so the bot now trades more days at small size. Breach before payout was 0.0% in every split for both
books. Forward selection on train picked the legs; validation confirmed; four- and five-leg versions scored higher on train and lower on validation, so were not used.
The shipped Payout Hunter is the three-leg book (`preset_rev` 2: stopped, untouched copies in the bots database are refreshed once).

## 4. Objectives A and C

* **A (Evaluation Passer)**: selecting by min(train, validation), the shipped book (Open Drive x1 + Ind Rule x3 + Context Drive Long x1) beat every searched book
  (shipped 50.5 / 59.3 / 35.2% pass in 30 days; the best searched two-leg book 60.9 / 53.3 / 51.4%, better on train and hold-out, worse on validation). It stays.
  Honest read: P(pass in 30 days) is **35-59%**, not 65%+. The earlier PDF's conclusion stands: the edge in these seven strategies is too thin for a 65% 30-day pass
  rate; nothing tried here changes that, and I would not trust a configuration that claimed otherwise.
* **C (Net Profit Compounder)**: the shipped six sleeves scored $39,068 over the hold-out (41.9% CAGR, 13.2% max drawdown); the best searched six-sleeve book scored
  $40,343 (42.8%, 15.5%). Statistically the same book. It stays.

## What changed in the app because of this

* Bots are strategies: `app/strategy/bot_strategy.py`. Test (Full Pipeline), Optimize, Validate and Replay list them; per-leg weights reach the sizer
  (`StrategyResult.size_multiplier`), the bot's profit lock and loser cut reach the engine. Gate 27 and legs on another instrument are named as "left out" in a
  one-instrument test; Trading Bots > Simulation runs the whole bot.
* Optimize on a bot runs `app/optimize/bot_optimizer.py` (leg weights + overlays, train / validation / hold-out, adopts only on agreement, saves "(optimized)" copy).
* Profit lock and adaptive loser cut in the backtester (`app/backtest/profit_lock.py`, off by default, same numbers in the bot engine).
* Objective B payout rule in the prop simulator, lifecycle (default for Objective B) and bot governor.
