# Round 5 pre-registration (written 2026-11-24 ~20:45 UTC, before any round-5 search score)

## Why round 5 has no holdout
Owen asked to continue the search (20:37 UTC) and, asked for pre-2016 data, answered "I cant. Continue the search with all the data
I already sent you" (20:42 UTC). Every window of ES/NQ/GC data available has therefore already been read at least once:
- 2016-11-24 .. 2019-12-31 (H3): read once at 18:56 UTC 11-24 as the round-4 holdout (final_hold_r4.csv).
- 2020-01-01 .. 2023-12-31 (research): used for tuning in rounds 1-4.
- 2024-01-01 .. 2026-11-20 (validation): used for selection in rounds 1-4; contains the round-1/2 holdout (Sep 2025 .. Feb 2026)
  and H2 (Mar .. Nov 2026), read as the round-3 holdout.
Round-5 results are therefore in-sample on every split. No claim from round 5 is an out-of-sample claim.
Only check before this file: r5.py plumbing test reproducing the already-published H3 baseline_A / baseline_B numbers exactly.

## Mode
env T58_R5=1 (implies T58_R4). Dev = h3 + research + validation (code/r5.py, data.load(sealed=False) -> mat_*_full4).
Same engine, cost model (stress = 1.5x slippage + stress commissions), lookahead protection, firm model, scoring code as round 4. None relaxed.

## Bars (unchanged)
- BOT-A: PREREG_R4.md bar (primary: p_pass >= base, med_days_pass <= base and < 30, bust <= base, ev >= base; limits 10% on pf, exp_R,
  sharpe, sortino, p_payout, trades_pm, med_days_payout, fund_bust, cons_blocks_per30, cons_block_rate; 25% on max_dd and worst_day;
  worst_day >= -1200), vs baseline_A, at stress cost, now required in EACH of h3, research and validation.
- BOT-B: beat or tie baseline_B on every metric including the sustained block, at stress cost, in EACH of the three splits.

## Search menu (stride 2, stress cost, every config logged to research/bot_trials_r5.csv)
- A1: round-4 A policy fixed; leg weights: each of the 7 A legs in {0, .5, 1} plus at most one add from
  {VWPB_NQ, ORB30T_NQ, ORB15N_NQ, OD_ES, CORB_ES, GAP_GC, TOD10_NQ} at .5; regime rspec none / rule; random sample, seed 5, capped at 1500.
- A2: top A1 configs x sizing (cush_a, prog_b, r_eval, cons_k) neighbourhood of round 4.
- B1: round-4 B; each of the 12 B legs in {0, .5x, 1x of current weight} + at most one add, random sample seed 5, capped at 1500.
- B2: top B1 configs x policy (r_fund, day_stop, fund_day_cap, max_open).

## Pick rule
- A: 0 primary fails in all three splits; then fewest limit fails; then highest minimum-over-splits p_pass; ties -> fewer changes from R4.
- B: fewest shortfall cells over the three splits; then highest minimum-over-splits f90_paid; ties -> fewer changes from R4.
- If nothing meets a bar, the pick is the fewest-shortfall config and the report says it does not meet the bar.
- Keep R4 if no round-5 config is strictly better under the rule.

## Overfitting checks (replace the missing holdout; none is a holdout)
1. Confirm finalists at stride 1, stress and base cost, all three splits.
2. Rotation check: for each split S, rank the A1/B1 configs on the other two splits only and report where the pick lands on S.
3. Plateau: neighbours of the pick (one leg weight or one policy knob one step away) must stay within the bar or within one cell.
4. Monte Carlo (mc.py) on the full 2016-11-24 .. 2026-11-20 pool, reshuffle + block resampling.
5. Trial count reported (rounds 1-5).

## Addendum 21:12 UTC (after A1, before A2 is scored)
A1 result: the round-4 A config ranks first; its only shortfall in any split is the H3 p_payout limit (funded side). Eval-side knobs
cannot move a funded metric, so A2 is changed to funded-side knobs on the A1 top 10: r_fund {300,400,500} x fund_day_cap {500,None}
x fund_day_stop {400,550} x cons_k {.55,.4} x fund_f_cush {.3,.4} (480 configs). Pick rule unchanged.
