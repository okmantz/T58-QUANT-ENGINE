# Research and audit

One document for the prop-30 research and its audit. Part 1 is the audit of the 30-day evaluation engine; part 2 is the research report built on it.

---

## Part 1 - Audit


Target: pass a $50,000 evaluation (+6%, 4% max drawdown, 2.4% daily loss, Lucid-style floating/EOD rules) within 30 CALENDAR days
of purchase, with the 95% lower bound on P(pass) at or above 65%.

**Bottom line: the data in this repository does not establish that any strategy achieves this, and the existing NQ Gap-Aligned
Opening Drive does not come close (0.0% within 30 and 60 calendar days, 95% upper bound 5.0%). No success is claimed.**

## 1. Why 99.8% (Monte Carlo) vs 12.5% (actual-date replay)

They answer different questions, and the report mixed them under one "pass" label.

| Number | What it really measures |
|---|---|
| 99.8% MC "eventual" / chain pass | Probability that repeated attempts eventually pass at some time; no calendar limit |
| `per_attempt_pass_probability` | One attempt, MC-resampled trades, horizon counted in TRADES/trading days |
| 12.5% replay | Fresh account purchased on real dates, run through the real engine, fixed horizon |
| 30.8% historical evaluation | Unlimited-time evaluation from one start |
| **0.0% (this audit)** | Purchase on every weekday, clock from PURCHASE in calendar days, floating DD/daily loss |

Concrete unit/clock mismatches found:

1. `days_to_pass` counts days that contained a trade; `calendar_days_to_pass` starts at the attempt's FIRST TRADE day. A sparse strategy
   (about 9 trades per 30 days) is reported as passing in far fewer "days" than elapsed. `orchestration/full_pipeline.py` converts
   median trading days with x7/5, which is only valid for a daily-trading strategy.
2. `run_attempt_replay` allowed starts up to `horizon/4` before the data ends, so up to a quarter of the windows were truncated and
   their unresolved outcomes counted as failures (downward bias), and it started accounts "mid-signal" on level signals.
3. The skip metric divided signal EPISODES by BARS: `sizing_summary.skip_rate` printed 0.6% where 4.0% of signals (28 of 696) were
   skipped. The warning text and the report disagreed. (Fixed; the new field `signals_seen` is the denominator.)
4. 2,236 "skipped" vs 0%: the 2,236 was bar-level retries of the same unaffordable signals (`skipped_for_sizing_bars` 3,717 here), the 0% was
   the per-signal rate computed on the wrong base. Both are now labelled and reconciled.
5. MC used the 300 development trades; the report's total is 373 including the 73 holdout trades, so the holdout was both reported and
   already used for sizing/selection: it is not independent.

## 2. Adaptive risk and sizing

On the bundled NQ data (668 trades): adaptive risk reports an average multiplier of 0.41 and is active on 85% of trades (intended
risk $126.45, actual stop risk $69.97 vs $90.96 without adaptive). Net P&L is $11,644 with adaptive vs $11,833 without (1.6% apart) and
the set of traded signals is identical: in this run the throttle is almost inert in P&L terms, which is consistent with whole-micro-contract
rounding absorbing it (not isolated further). Reporting "0.48x" as a risk reduction overstates what the account experienced.

## 3. Exit engine

Verified by regression tests (`tests/backtest/test_exit_engine_audit_2026_11_10.py`): stop wins when stop and target share a bar; a gap
through the stop fills near the open, worse than the stop; the target fills at the target; entries pay spread/slippage. No bug found.

## 4. Research/validation independence

The bundled data has a sealed window (from 2025-09-01) that earlier experiments already read; the GAD run's 73-trade holdout lies inside the
same file. Nothing in the bundle can be certified as never observed. The new gate (`app/validation/prop30_validation.py`) therefore
refuses to call any holdout independent unless it starts after the selection cut-off plus embargo and overlaps no declared observed range,
and it never reports CONFIRMED without forward results.

## 5. What was built

| Phase | Module |
|---|---|
| Evaluator (calendar days from purchase, floating DD, dependence-aware CI) | `app/prop/thirty_day.py` |
| Frequency/edge feasibility | `app/prop/feasibility.py` |
| Replay fixes (opt-in, defaults unchanged) | `app/prop/attempt_replay.py`: `calendar_days_to_pass`, `n_truncated`, `pass_within_days`, `min_horizon_coverage`, `arm_signals_after_start` |
| Skip-rate unit fix | `app/backtest/execution.py`, `portfolio_engine.py` |
| Opportunity scanner (NQ/ES/GC; CL has no data in the bundle) | `app/discovery/opportunity_scanner.py` |
| Exit lab on frozen entries | `app/research/exit_lab.py` |
| Portfolio: correlation, shared risk, regime gate, allocation | `app/portfolio/prop_portfolio.py` |
| Validation gate and forward registry | `app/validation/prop30_validation.py` |
| Pipeline / CLIs | `app/research/prop30_pipeline.py`, `scripts/run_prop30_research.py`, `scripts/audit_gad_engine.py` |

Thresholds were not changed. Run: `python scripts/run_prop30_research.py` (writes `reports/prop30/`).

## 6. Results (discovery 2020-2022, development 2023-H1 2024)

See Part 2 below. 150 scanner cells on NQ/ES/GC: the best has P(pass<=30d) 8.4% (95% lower 3.3%) on discovery
and 4.9% on development. The best exit policy on the best entries reached 19.0% (lower 8.2%) in-sample; the best 3-leg portfolio 27.7%
(lower 16.4%) in-sample with 60% bust. All fail the 65% lower-bound target by a wide margin.

## 7. Why, and what would change it (i.i.d. upper bound)

At a 0.3 R net edge per trade a strategy needs about 40 trades per 30 days for ~72% (0.5 R: ~10-20 trades). The scanned families give
17 trades per 30 days at 0.03-0.06 R net edge. The binding constraints are the 4% trailing drawdown against a 6% target and the
net-of-cost edge, not the number of ideas tried. Recommended: new genuine edge sources with higher net R per trade or much higher frequency
(more liquid intraday instruments, true multi-instrument concurrency), a CL dataset, and a forward test of any survivor before any claim.

## 8. Limits of this work

- Scanner families are simple, costs are fixed estimates (`INSTRUMENTS` table), and all scans are in-sample on discovery; survivors are hypotheses.
- Portfolio weights are chosen and scored on the same data (flagged in the report).
- Block robustness is contiguous-block dispersion, not a full CPCV purge/embargo.
- `tests/suite/test_journal_suite.py` is skipped because `app/journal/{behavior,capture,statistics}.py` are absent from the checkout supplied.

---

## Part 2 - Research report


**Verdict:** `NOT_ESTABLISHED`

The top discovery candidate does NOT establish a 30-day pass: Development P(pass<=30d) is 4.9%: below half the 65% target, so there is nothing worth validating.; The holdout overlaps a range already observed (bundled data after development: read by earlier experiments / sealed window (cannot be proven unread): 2024-07-01..2026-03-01). A window that was looked at before cannot be reused as independent validation.; No independent holdout: the 30-day claim cannot be established from this data. A forward test (or newer, unseen data) is required.

## Rules simulated

```
{
 "account": 50000,
 "target_pct": 6.0,
 "max_dd_pct": 4.0,
 "daily_loss_pct": 2.4
}
```

## Feasibility frontier (i.i.d. upper bound, best risk size)

| Net edge R/trade | Trades/30d | Best risk % | P(pass<=30d) |
|---|---|---|---|
| 0.1 | 5 | 2.0 | 22% |
| 0.1 | 10 | 2.0 | 33% |
| 0.1 | 20 | 1.25 | 41% |
| 0.1 | 40 | 1.25 | 41% |
| 0.1 | 80 | 0.6 | 46% |
| 0.2 | 5 | 2.0 | 27% |
| 0.2 | 10 | 2.0 | 39% |
| 0.2 | 20 | 1.25 | 52% |
| 0.2 | 40 | 0.75 | 56% |
| 0.2 | 80 | 0.5 | 67% |
| 0.3 | 5 | 2.0 | 32% |
| 0.3 | 10 | 2.0 | 47% |
| 0.3 | 20 | 1.25 | 63% |
| 0.3 | 40 | 0.75 | 72% |
| 0.3 | 80 | 0.5 | 84% |
| 0.5 | 5 | 2.0 | 44% |
| 0.5 | 10 | 1.5 | 63% |
| 0.5 | 20 | 1.25 | 82% |
| 0.5 | 40 | 0.75 | 92% |
| 0.5 | 80 | 0.4 | 99% |

## Opportunity scan (discovery data only, 150 cells tried)

- 150 cells tried on DISCOVERY data only (< 2023-01-01). Survivors are hypotheses: they have not touched development, walk-forward or sealed data and the trial count above is the multiple-testing burden.
- CL: skipped (no data supplied)

| Cell | Trades/30d | Net R | Feasibility UB | P(30d) | 95% lower |
|---|---|---|---|---|---|
| NQ|orb|ny_open|{'or_minutes': 60}|t1.5R | 17.79 | 0.0363 | 0.305 | 8.4% | 3.3% |
| NQ|orb|ny_open|{'or_minutes': 60}|t2R_be | 17.79 | 0.0581 | 0.35 | 8.3% | 2.7% |
| NQ|compression|ny_open|{'lookback': 12, 'ratio': 0.7}|t2R_be | 14.08 | 0.0005 | 0.325 | 5.7% | 1.3% |
| NQ|orb|ny_open|{'or_minutes': 60}|t1R | 17.79 | 0.0466 | 0.315 | 5.6% | 1.3% |
| NQ|orb|ny_open|{'or_minutes': 30}|t2R_be | 19.87 | 0.0062 | 0.35 | 6.6% | 0.9% |
| NQ|gap_fade|london|{'k_atr': 2.0}|t1.5R | 11.64 | 0.0089 | 0.252 | 1.9% | 0.0% |
| NQ|gap_fade|london|{'k_atr': 2.0}|t2R_be | 11.64 | 0.0749 | 0.362 | 0.5% | 0.0% |
| NQ|drive_cont|ny_open|{'drive_minutes': 30, 'k_atr': 2.0}|t2R_be | 8.92 | 0.1607 | 0.36 | 0.4% | 0.0% |
| NQ|drive_cont|ny_open|{'drive_minutes': 30, 'k_atr': 1.0}|t2R_be | 14.27 | 0.0191 | 0.298 | 0.4% | 0.0% |
| NQ|gap_fade|london|{'k_atr': 2.0}|t1R | 11.64 | 0.0273 | 0.278 | 0.0% | 0.0% |

## Exit lab (frozen entries of NQ|orb|ny_open|{'or_minutes': 60}|t1.5R; 13 policies tried)

| Policy | Mean R | P(30d) | 95% lower |
|---|---|---|---|
| fixed_3R | 0.083 | 19.0% | 8.2% |
| be_1R_t3 | 0.057 | 13.4% | 6.0% |
| fixed_2R | 0.088 | 13.8% | 5.6% |
| time_60_t2 | 0.081 | 13.0% | 5.1% |
| dyn_target_3atr | 0.077 | 13.0% | 5.1% |
| regime_t1.5_hi2.5 | 0.045 | 9.9% | 4.3% |
| be_1R_t2 | 0.056 | 9.3% | 3.0% |
| partial_1R_run3 | 0.053 | 8.5% | 3.0% |

## Portfolio (in-sample, 26 weight vectors)

Diversification ratio 1.25

- weights {"NQ|orb|ny_open|{'or_minutes': 60}|t1.5R": 1.0, "NQ|orb|ny_open|{'or_minutes': 60}|t2R_be": 1.0, "NQ|compression|ny_open|{'lookback': 12, 'ratio': 0.7}|t2R_be": 1.0} -> P(30d) 27.7%, lower 16.4%, bust 59.9%
- weights {"NQ|orb|ny_open|{'or_minutes': 60}|t1.5R": 1.0, "NQ|orb|ny_open|{'or_minutes': 60}|t2R_be": 1.0, "NQ|compression|ny_open|{'lookback': 12, 'ratio': 0.7}|t2R_be": 0.5} -> P(30d) 24.3%, lower 14.3%, bust 59.1%
- weights {"NQ|orb|ny_open|{'or_minutes': 60}|t1.5R": 1.0, "NQ|orb|ny_open|{'or_minutes': 60}|t2R_be": 1.0, "NQ|compression|ny_open|{'lookback': 12, 'ratio': 0.7}|t2R_be": 0.0} -> P(30d) 23.5%, lower 13.6%, bust 59.4%

## Validation gate

Verdict: **NOT_ESTABLISHED**

- Development P(pass<=30d) is 4.9%: below half the 65% target, so there is nothing worth validating.
- The holdout overlaps a range already observed (bundled data after development: read by earlier experiments / sealed window (cannot be proven unread): 2024-07-01..2026-03-01). A window that was looked at before cannot be reused as independent validation.
- No independent holdout: the 30-day claim cannot be established from this data. A forward test (or newer, unseen data) is required.
- Walk-forward: only 0% of test spans reach half the target pass rate (need >= 60%).
- Block robustness: the pass rate is concentrated in a minority of blocks, i.e. one regime carries the result.
- discovery: P(30d) 8.4% (95% lower 3.0%, 741 windows, ~35 independent)
- development: P(30d) 4.9% (95% lower 0.0%, 349 windows, ~16 independent)

## Honesty notes

- Pass probability is measured on real calendar time from purchase, using the existing prop rule engine's floating drawdown / daily loss.
- Eventual (chain) Monte Carlo pass is never used as a 30-day number.
- No holdout inside the bundled data can be certified untouched; a forward test is required before any success claim.
