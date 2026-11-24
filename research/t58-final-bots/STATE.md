# STATE (resume point), T58 final bots A and B

Last checkpoint: 2026-11-23, cycle 5 (picks frozen, holdout read, Monte Carlo, deliverables).

## Done
- Phase 0: research/00_recon.md; baselines research/baseline_dev.csv (Pro, base+stress, + sustained), research/baseline_dev_flex.csv.
- Phase 1: code/data.py (splits res 2020-23 / val 2024-Aug25 / holdout Sep25+ SEALED), code/firm.py (Lucid Pro + Flex, 12 tests pass).
- Phase 2: code/factory.py, screen.py, lib_screen.py -> research/strategy_ledger.csv (1,825 trials). gates.py: DSR (N_eff 78) + PBO.
  No single leg reaches DSR >= 0.95 even at 80% confidence (best 0.03). Robust at stress cost in res AND val: OD_NQ, CDL_NQ, CDL_ES,
  ORB15C_NQ/ES (ORB after compressed day), VWPB_NQ, ORB30T_NQ. Gold, mean reversion, sweeps, fades: none.
- Phase 3/4 so far: code/policy.py Pol now has day_room (open risk <= what is left of the day stop), one-micro minimum, equity drawdown
  throttle (dd_lvl/dd_k, uses St.peak_eq), consistency guard for Pro funded (cons_k/cons_min/cons_R).
  Search 1 (L6/L7/L8 leg sets, 1,152 configs): P(pass) 43% vs 18% but every config lost on worst day, max DD, consistency.
  Probe with high-PF leg set H5 + guards: fails only med_days_payout and max_dd (or pf/sharpe) by small margins.

## Cycle 5
- Picks frozen (research/FROZEN_PICKS.md, code/picks.py, final/BOT-*/params.json). Holdout read once -> research/final_hold.csv.
- Pine: final/pine/T58_BOT.pine saved to TradingView as "T58 BOT (A/B) research" (no alerts); backtested on MNQ1!/MES1! 1m,
  window 2026-11-08..11-23 only (plan limit, no overlap with engine data).
- Monte Carlo: code/mc.py -> research/mc.csv (10k paths per bot x pool x method, stress cost).
- Deliverables: final/run_bot.py, final/BOT-A/README.md, final/BOT-B/README.md, final/COMPARISON.md, code/compare.py.

## Round 2 (cycle 6), coordinator asked to keep going
- Data-hole stop repair added (book.py, factory.py); baseline and round-1 picks rescored (research/round1 keeps the originals).
- code/screen2.py: round-1 bots + one new leg each (ORB15N_NQ, TOD10_NQ, CDLB_NQ, OD_ES, CORB_ES, PDLB_GC, GAP_GC, ...), research
  stride 2 -> research/runs/screen2.pkl. Next: pick legs that fix shortfall cells, focused grid, confirm on validation, freeze round-2
  picks (new FROZEN_PICKS_R2), single holdout read per new finalist (disclose second use of the holdout window), MC, update final/.
- RESEARCH PAPERS.zip blocked (34 MB > 10 MB connector limit); asked Owen to unzip it in Drive.

## Older notes (cycle 4)
- code/run_grid.py a2 (1,536 configs, Pro, A) -> research/runs/a2.pkl; queued after it: b_flex, b_pro (sustained metrics).
- Next: filter research winners by search.beats (tol 0), confirm on validation (base AND stress), pick A and B, write gate ladder log,
  FROZEN_PICKS.md + sha256, open holdout once, Monte Carlo 10k, Pine ports (prefer P5 leg set: no IR), deliverables in final/.

## Rules (never relax)
Costs, lookahead protection, sealed holdout, beat-baseline rule. No trades, no broker/prop sign-in, no TradingView alerts/watchlists.

## Round 2, cycle 7 (Nov 24)
- Read all 32 papers in the RESEARCH PAPERS folder (four batches, read-only). Notes and pre-registered hypotheses: research/papers_notes.md.
  None shows a cost-adjusted intraday ES/NQ/GC edge stronger than our legs; both MNQ papers report nearly all OHLCV families fail after costs.
  What they add: regime filters (long-horizon trend, crash state, VVG day, first-hour range expansion), vol-scaled sizing, an eval daily-sigma
  target of about $400-600, OTR exit calibration, and three low-prior entry families (CMF, pre-RTH range, prior-day reversal).
- screen2 (one new leg added to the round-1 bots, research stride 2): no add fixes the shortfalls. A still fails med_days_payout and
  consistency blocks on research; B still fails trades_pm and max_dd (adding OD_ES lifts trades but costs PF).
- New code/filters.py: causal regime filters applied per leg before the arbiter. Verified: no filter reproduces search.bot exactly.
  NQ rates: VVG 6.6% of days, crash state 10.3%, above 7-month SMA 67%, first-hour range > 2x 4.0%.
- Running code/screen3.py: 10 filter specs x 16 policies x leg adds (A 320 configs, B 640), research stride 2, base cost.
- Next: pick configs with zero research fails, confirm on validation at base and stress, freeze R2 picks, one holdout read each, MC.
- Round 2 picks frozen 2026-11-24: research/FROZEN_PICKS_R2.md (sha256 3092f259...), code/picks_r2.py. A = round-1 A; B = c10b cfg 3.
- Holdout read once for BOT-B-R2 (second read of the window, disclosed) -> research/final_hold_r2.csv. MC -> research/mc_r2.csv.
- Pine: final/pine/T58_BOT.pine now ports BOT-B-R2 (OD_ES, PDLB_GC, crash, floor_x); round-1 port kept as T58_BOT_r1.pine.
  Saved to TradingView as version 2.0 of "T58 BOT (A/B) research". On the 2-week 1m window: MES B 2 trades +$330, MNQ B 0, MGC B 0
  (PDLB needs 134 sessions of history to arm).
- Next: params.json, run_bot.py, COMPARISON.md, BOT-B README, zip, report.

## Round 3 (Nov 24): fresh holdout, final picks, repo zip
- Data: Owen's Mar-Nov 2026 pack = round-3 holdout (sealed, read once). Validation = 2024-01-01 .. 2026-03-01. Mode: env T58_R3=1.
- Picks: code/picks_r3.py, research/FROZEN_PICKS_R3.md (sha256 2f478200...). Holdout: research/final_hold_r3.csv (read once; never again).
- Comparison: code/compare_r3.py -> research/comparison_r3.md, comparison_long_r3.csv, shortfalls_r3.csv. Top 5: research/top5_per_objective_r3.csv.
- MC: code/mc.py 10000 r3 -> research/mc_r3.csv (pools stop at 2026-03-01).
- Repo zip: code/build_repo_zip.py -> final/T58-QUANT-ENGINE_t58_final_bots.zip (layout of the T58-QUANT-ENGINE repo at 66280ba).
- Pine: final/pine/T58_BOT.pine = round 3, saved to TradingView as version 3.0 (compiles; TradingView daily tool quota hit, so only
  one 2-week MGC smoke run, 0 trades because the GC legs need 120+ sessions of history to arm).
- Outcome: neither bot beats baseline on every metric. B short on 3 of 54 stress cells, A on 11 of 42. Search exhausted under the rules.
