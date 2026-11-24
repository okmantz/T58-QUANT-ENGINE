# Gate ladder log (Phase 3)

Fixed gates, never relaxed: cost model (base and 1.5x stress, charged once in firm.py), lookahead protection (prior-session features
only, entry at the next bar open, holdout sealed in code), sealed holdout (2025-09-01 on), beat-the-baseline rule (every metric).

## Leg level (1,825 trials, research/strategy_ledger.csv)
| Rung | Gate | Result |
|---|---|---|
| 1 | DSR >= 0.95 (N_eff 78) | 0 legs pass. Best Open Drive NQ 0.027. |
| 2 | DSR >= 0.90 | 0 legs. |
| 3 | DSR >= 0.80 | 0 legs. The DSR gate cannot be met by any intraday leg here at any rung on the ladder. |
| 4 | Relax PF / Sharpe minimums: replace DSR with "HAC t >= 1.8 at stress cost in research AND validation, PBO of the family <= 0.45" | 9 legs: OD_NQ, CDL_NQ, CDLB_NQ, CDL_ES, IR_NQ (research only strong), ORB15C_NQ, ORB15C_ES, ORB30T_NQ, VWPB_NQ. |
| 5 | Horizon 30 -> 45 -> 60 days | Not needed for A (30-day pass rate already above baseline). |
| 6 | Lower frequency | Used: the high-PF leg set (H5) trades ~25 a month vs 17 for the baseline, so not binding. |
| 7 | Untested families | All 10 families screened; gold, mean reversion, sweeps and ORB fades found nothing at rung 4. |

Consequence: the edge is accepted on out-of-sample replication (research -> validation, base and stress) plus PBO, not on DSR.
That is weaker evidence than the spec asks for and is stated in each README.

## Bot level (research/bot_trials.csv, research/runs/*)
- Search a1 (L6/L7/L8 leg sets, 1,152 configs): best 43% pass but every config lost on worst day, max DD and both consistency metrics.
- Policy changes (each a general rule, not a fitted constant): open risk capped by what is left of the day stop; equity drawdown throttle;
  Pro funded consistency guard sized so a winner cannot make one day too large a share of the cycle.
- Search a2 (H5/H5o/H6/P5, 1,536 configs): 8 configs beat the baseline on every metric in research at base cost; on validation they
  lose on EV ($127 vs $293) and days to payout (the guard made payouts slow).
- Search a3: guard also allows a day up to a share of what the cycle must reach to be payable. Validation was looked at to diagnose a2,
  so validation is no longer fully untouched for the policy shape; the holdout is still sealed.
- Searches b_flex, b_flex2 (Flex, B objective, sustained metrics) and b_pro (Pro, B): best Flex configs roughly double P(first payout)
  and $ paid in 90 funded days vs the current Payout Hunter in research and validation, but every one trades less (the baseline's
  trade count cannot be matched without the small-day discipline that produces the payouts) and none matches validation EV.
  B on Pro fails consistency metrics because the baseline never becomes payout-eligible (0 blocks) on Pro.
- Rung 5 (horizon 45/60 days) was not run at bot level: the metrics are defined on 30-day windows in Phase 0 and a longer horizon
  would not change the chain metrics (PF, Sharpe, max DD, trades a month) where the failures sit. Rung 6 (lower frequency) is the
  direction B already moved in and is exactly what costs it the trade-count metric.
- Ladder exhausted. No configuration beats the baseline on every metric in research AND validation for either objective.
  Picks frozen as the best compromise (fewest and smallest failures, biggest wins on the objective's own headline metrics).

## Final
- Frozen 2026-11-23 before the holdout: research/FROZEN_PICKS.md (sha256 d7bb0165...).
- Holdout read once (research/final_hold.csv): every bot loses money Sep 2025 to Feb 2026, the baselines included.
- Full pass/fail table per metric: research/comparison_tables.md and final/COMPARISON.md.

## Round 2 (started 2026-11-23 23:52Z, after the round-1 report)
- RESEARCH PAPERS.zip: still unread. It is 34 MB; the Drive connector only downloads files up to 10 MB and cannot read a zip as text.
  Asked Owen to unzip it into the research folder. Rung 5 counts as not exhausted for the papers until then.
- 2020-03-10 stop overrun: not an engine bug. The NQ 1-minute pack has no bars 15:00-16:00 that day (and ES/NQ 14:00-14:10 on
  2022-09-21); data.py forward-fills holes, so the repo filled the stop at the first real bar. Rule added in book.points and
  factory.simulate for every bot, baseline included: a stop whose first touching bar comes straight after a data hole fills at the stop
  (costs still add slippage). Repaired: OD_NQ 2020-03-10, OD_ES 2022-09-21. Effect on round-1 numbers: EV moved by at most $0.30,
  baseline B worst day on Pro moved (-446 -> -324 at stress). Round-1 code is kept in research/round1_code (sha256 d7bb0165... verified).
- New candidate legs: ORB15N_NQ (ORB15 ATR stop, no filter, ~21 trades a month), TOD10_NQ, CDLB_NQ, OD_ES, CORB_ES (repo
  CompressionORB_ES), PDLB_GC and GAP_GC (gold; the only GC legs positive in validation; research t is weak, 1.1 and 0.1).
  Gold breakout family F8: 144 trials, none positive in both research and validation at stress cost.

### Round 2, cycle 7: papers folded in (Nov 24)
- All 32 papers read; hypotheses pre-registered in research/papers_notes.md before any run.
- New entry families from the papers, 120 leg trials appended to the ledger (research + validation, base + stress):
  - F11 Chaikin Money Flow (Huber): best research t at stress < 1.5 on every instrument. Rejected.
  - F12 pre-RTH 08:00 range with mid pullback (Levine): mean R near zero. Rejected.
  - F13 prior-day reversal after the first hour (Waldow et al.): research t up to 3.5 at stress on NQ and ES, but validation t is
    0.0 to 0.9 (one ES variant -2.0). Does not replicate. Rejected; logged as the clearest overfitting example of the round.
- Regime filters (code/filters.py, causal): trend (7-month SMA, 12-month return), crash state, VVG day block, first-hour range
  expansion block, vol-scaled size.
- screen3 (960 configs): best A short on 2 research cells (max_dd, consistency); best B short on 1 (max_dd).
- screen4 (1,232 configs): 16 A configs beat baseline on every research cell (crash filter or VVG+ATRX block, VWPB added,
  r_fund 250-300, consistency guard cons_g 0.1, DD throttle at $1,000-1,200). All 16 fail 15-18 validation cells: PF 1.30-1.37 vs
  baseline 1.58, p_payout .08 vs .14, EV negative vs +$293. Research-only wins did not survive; none carried forward.
  B: best still short on max_dd only (1,856 vs 1,245 on research).
- screen5 running: A rebuilt around the baseline's own high-PF NQ legs (Open Drive, Ind Rule, Context Drive) with round-2 sizing and
  filters; B with smaller uncorrelated legs and lower eval risk.
- screen5 (A on the baseline's NQ legs, B with smaller legs): no A config better than round-1 A on research; B unchanged.
- Diagnosis: B's research max drawdown (1,778 in the best screen4 config) all came from the 2020 COVID evaluation stretch. The
  one-micro minimum (take one micro when the budget is below one micro but one micro is under 35% of the cushion) overrode both the
  small eval budget and the drawdown throttle whenever ATR was high. New policy field floor_x: the minimum only applies while one
  micro risks at most floor_x times the budget. screen6 (floor_cush values) and screen7 (floor_x values) confirmed it.
- screen8: B with more frequent legs added (ORB15N_NQ, OD_ES 0.5, one_per_inst off) to recover trade count: every config that
  restores trades brings the max drawdown failure back. Trade count and drawdown are a Pareto pair for B at this cost model.
- Direct confirmation grids at stride 1, research and validation, base and stress (code/confirm3.py, rows in research/bot_trials_r2_confirm.csv):
  - c9b (16 B configs) and c10b (24): best B = c10b cfg 3 (= c9b cfg 7): round-1 B legs + OD_ES 0.25 + PDLB_GC 1.0, max 3 open,
    crash filter 0.5, r_eval 300, r_fund 250, dd_lvl 400, dd_k 0.25, floor_x 3.0. Beats or ties baseline B on every metric in all
    four dev cells except trades a month (6.3-13.2 vs 8.7-18.1). Round-1 B failed 4-6 dev cells.
  - c11a (24 A configs: filters x dd_lvl x floor_x on round-1 legs): best is 12 dev fails (dd_lvl 1200) vs 13 for round-1 A,
    but it lowers P(pass) in all four cells. c12a (funded-only leg sets): 26-31 fails. c9a (A7 legs): no better.
- Ladder, round 2: rungs 1-4 rerun with the papers' filters, sizing and three new families; rung 5 (horizon) and rung 6 (frequency)
  unchanged in effect; rung 7 (new families, gold) added PDLB_GC to B. Exhausted for A; B's one remaining dev shortfall is trade count.

### Round 2 final
- Frozen 2026-11-24 before its holdout read: research/FROZEN_PICKS_R2.md (sha256 3092f259...). A unchanged; B = round-2 config.
- Holdout read for BOT-B-R2 (research/final_hold_r2.csv). This is the second read of the same window: round 1 read it for the
  round-1 picks. Round 2 never tuned on it, but its round-1 results were known. Result: a losing period again for every bot; R2 makes
  a first payout more often than baseline (6.9-9.8% vs 0%) but pays less over 90 funded days and draws down more.
- Monte Carlo for BOT-B-R2, 40,000 paths (research/mc_r2.csv): P(first payout in 30d) 44-46% vs baseline 10-16% and round-1 B 31-36%.
- A third holdout read (rescoring the baseline and round-1 picks on the repaired books) was not done: it would read the window again.

## Round 3 (2026-11-24): fresh holdout from Owen's Mar-Nov 2026 data
- New data (ES, NQ, GC and micros, 2026-03-01 .. 2026-11-24) copied in, hashed (data_holdout2/SEAL.sha256) and logged in
  /mnt/project-files/.notes/inputs.md. Sessions 2026-03-02 .. 2026-11-20 became the round-3 holdout; nothing in the search could see
  them (book.points drops those days until research/FROZEN_PICKS_R3.sha256 exists).
- Old holdout (Sep 2025 .. Feb 2026) folded into validation: validation is now 2024-01-01 .. 2026-03-01. Baseline rescored on it
  (research/baseline_dev*_r3.csv). On the longer validation the round-1 A loses PF, expectancy, Sharpe and Sortino at stress; round-2
  B loses only trades a month.
- Search (code/run_r3.py, stress cost, research + validation, 1,776 bot variants: 784 A, 992 B; research/bot_trials_r3.csv):
  - B stage 1 (672) and stage 2 (320): extra legs (OD_NQ, CORB_ES, GAP_GC, CDLB_NQ, ...), 3-4 open positions, one_per_inst on/off,
    day stop, day cap, floor_x. Best: round-2 B + OD_NQ 0.25, CORB_ES 0.5, GAP_GC 0.5, 4 open, one_per_inst off, $300 day stop.
    Clean on both validation cells; one research shortfall (trades a month). No variant had zero shortfall cells.
  - A stage 1 and 2 (784): leg adds (PDLB_GC, GAP_GC, VWPB, CORB), r_eval 800-1200, dd_lvl, filters. Best: round-1 A + PDLB_GC 0.5,
    r_eval 1000, dd_lvl 1200: 4 stress shortfall cells (round-1 A: 10). Exhausted: no A variant below 4.
- Repo-format ports of the six new legs (repo_zip/strategies/python/*_t58.py) match the research legs on 98-100% of trades
  (research/port_check.csv). Found and disclosed: the factory's whole-day bar-count filter is a mild lookahead; the ports are causal.
- Frozen before the read: research/FROZEN_PICKS_R3.md (sha256 2f478200...), code/picks_r3.py.
- Holdout read once (code/final_score_r3.py hold -> research/final_hold_r3.csv): baseline A and B, A-R1, B-R1, B-R2, A-R3, B-R3 on
  both plans, plus A-R3 and B-R3 on the repo-format legs, base and stress.
  - Every bot lost money over the period, baseline included (baseline A PF 0.97, baseline B PF 0.76 at stress).
  - BOT-B-R3 at stress: first payout 24.0% vs 9.7%, $742 vs $161 paid in 90 funded days, PF 0.99 vs 0.76; misses max drawdown
    ($2,954 vs $1,329) and worst day (-$299 vs -$162). With research trade count, 3 of 54 cells short.
  - BOT-A-R3 at stress: P(pass) 17.9% vs 12.6%, bust 7.7% vs 12.6%, 12.5 vs 13 days; misses EV, PF, expectancy, Sharpe, Sortino,
    max drawdown, consistency blocks. 11 of 42 cells short overall.
  - Round-2 B did better than round-3 B on this holdout (first payout 26.3% vs 24.0%, $858 vs $742 paid, PF 1.28 vs 0.99, max
    drawdown $1,531 vs $2,954), though it has more shortfalls overall (5 vs 3 of 54). Per the pre-registration the pick is not changed
    after the read; R2 is documented as the lower-drawdown alternative.
- Monte Carlo on pre-holdout pools only (code/mc.py r3 -> research/mc_r3.csv), so the holdout is not reused.
- Ladder status: exhausted under the rules. With the fresh holdout now read, any further tuning would have no untouched test left.
