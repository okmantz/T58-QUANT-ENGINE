# Objective A / B books after the scorer's lookahead fix (2026-11-19)

## The bug

`app/prop/objective_scorecard.simulate_starts` booked each trade into the governor's account state the moment the trade was **sized**. When two
positions overlapped (an NQ leg and an ES leg open at the same time) the second one was sized, and allowed or blocked by the day stop, already
knowing how the first one ended. `score_net` had the same flaw from the other side (it sized every trade at its **exit**), and the research
bundler `scripts/run_objective_scores.bundle` counted a trade toward the combined daily loss cap the moment it was **entered**.

Fixed:

* `simulate_starts`: trades are sized at entry from closed trades only; open trades are booked when they close, in exit order, and the dollars
  they still have at risk are passed to `decide_risk(open_risk=...)`, the same argument the bot engine passes.
* `score_net`: sized at entry, booked at exit, same open-risk rule.
* `bundle`: the daily cap reads realised P&L only. New `as_weight=True` keeps each trade's 1x P&L and passes the leg multiplier as the `w` column,
  so the scorer hands it to the governor as the leg weight **before** the caps, exactly as the bot does since the 2026-11-18 governor change.

Tests: `tests/prop/test_objective_scorecard_no_lookahead.py` (five of its six tests fail on the old code).

## What the bug was worth

Same trades, same governors (the shipped ones, `PRESET_REV` 3), same splits; P(pass in 30 days) for A, P(first payout) for B. "Before" is the
code at 368355c, "after" is this change with `as_weight=True`. Every leg's trades come from the repo's own backtest engine
(`scripts/bundle_research.run_trades`), every book is cut at 2026-02-27 21:00 (the end of the NQ history) so no window sees only one instrument.

| Book | split | before | after |
|---|---|---|---|
| Evaluation Passer (shipped) | train / val / test | 54.9 / 67.6 / 38.9 | 51.2 / 63.9 / 36.1 |
| A combo tested (+ ES Open Drive bracket x1, + ES Context Drive Long bracket 2R x2) | train / val / test | 57.8 / 60.3 / 63.2 | 45.0 / 46.6 / 36.8 |
| Payout Hunter (shipped) | train / val / test | 76.0 / 64.1 / 0.0 | 80.5 / 61.5 / 7.1 |
| B combo (+ NQ Context Drive Long bracket 3R x0.5) | train / val / test | 88.5 / 88.6 / 64.3 | 83.1 / 73.4 / 42.9 |

The lookahead mostly flattered books that hold NQ and ES at the same time, which is why the A combo's apparent gain disappears once it is fixed.

## Objective A: the Evaluation Passer stays as it is

After the fix no book tested beats the shipped one on min(train, validation) of the selection score
(`p_pass_30_lo + 0.35 p_pass_60_lo - 0.35 breach_60`):

| A book (shipped governor) | sel train | sel val | p30 train / val / test |
|---|---|---|---|
| shipped: OD x1, IR x3, CDL x1 | **38.6** | **38.6** | 51.2 / 63.9 / 36.1 |
| + ES OD bracket x1 + ES CDL bracket 2R x2 | 32.4 | 21.0 | 45.0 / 46.6 / 36.8 |
| best other book of 80 weight combinations (IR 2-3, OD 0.5-1, ES OD bracket 0-1, ES CDL bracket 0-2): + ES CDL bracket x0.25 | 36.5 | 34.9 | 50.1 / 61.5 / n.a. |
| + NQ CDL bracket 3R x0.5 / x1 / x2 | 38.8 / 38.6 / 38.2 | 38.6 | unchanged |
| + Compression ORB ES x0.5 | 35.5 | 28.9 | 49.2 / 55.9 / 37.2 |
| the same ES legs under the pre-2026-11-18 A governor | 27.5 | 19.2 | 40.6 / 47.4 / 34.2 |

Every addition that helps on train costs validation, so none was shipped.

## Objective B: Payout Hunter gains a half-size Context Drive Long bracket

`strategies/python/ContextDriveLongBracket_NQ_1m_v1.py`: the entries of `ContextDriveLong_NQ_1m_v2` with a fixed bracket, stop 0.2 x ATR14,
target 3x the stop, no trailing stop. 254 trades 2020-2026 on NQ, profit factor 1.74 in the engine.

| B book (shipped governor) | paid train / val / test | bust | median days to pay | avg paid |
|---|---|---|---|---|
| shipped: IR x1, COB ES x0.25, OD x0.25 | 80.5 / 61.5 / 7.1 | 0 | 237 / 127 / 361 | $1,556 / $1,992 / $61 |
| **+ CDL bracket 3R x0.5** | **83.1 / 73.4 / 42.9** | 0 | 217 / 114 / 268 | $1,966 / $3,201 / $292 |

It wins on all three splits. The test split has only 14 start dates (the payout horizon is long and the NQ history ends in February 2026), so
read its number as a direction, not a rate. In the earlier 2026-11-19 study (before the fix) a coin-flip-direction control with the same entries and bracket paid out less than the
real leg on train and validation.

In the bot engine (6-month simulation, `runner.start_simulation("bot-payout", months=6)`) the new leg took 33 of the 94 trades; 7 of its
signals were skipped because half size was below one micro at the stop, which the research scorer (fractional sizing) does not model.

## Reproduce

1. `python scripts/run_objective_study.py trades --only ContextDriveLongBracket_NQ_1m_v1` (or `bundle_research.run_trades` per file).
2. Score with `run_objective_scores.bundle(..., as_weight=True)` and `objective_scorecard.score_pass` / `score_payout` on `ros.W("train" | "val" | "test")`.
