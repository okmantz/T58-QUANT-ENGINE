# Round 4 pre-registration (written 2026-11-24 ~18:35 UTC, before any round-4 score was computed)

Source of the changes: Owen's message of 2026-11-24 18:17 UTC (four points: change BOT-A's bar, untouched data, regime filter,
sizing for BOT-A). Where they conflict with the original "beat on every metric" bar, they win, for BOT-A only.

## Data and splits (mode: env T58_R4=1)
- research   2020-01-01 .. 2023-12-31  (fit filters, sizing and weights here)
- validation 2024-01-01 .. 2026-11-20  (confirm). Includes H2 (2026-03-02 .. 2026-11-20), which was read once as the round-3
  holdout and is now ordinary validation data. Disclosed in every report.
- holdout H3 2016-11-24 .. 2020-01-01  (session days < 2020-01-02). Owen's new pack, sealed by hash before any price was read
  (data_holdout3/SEAL.sha256: ES/NQ/MES 18:19:06Z, GC/MNQ 18:21:49Z). Read once per finalist after FROZEN_PICKS_R4 is hashed.
  Only integrity facts (rows, sessions, rolls, splice offsets) were computed on it before the freeze (code/data_h3.py).
- The 2020 part of the new files overlaps research and is not used (repo data is kept for 2020, as in rounds 1-3).
- Costs: 1.5x stress is the deciding case (as round 3); base cost is reported alongside.
- Firm model: unchanged (code/firm.py). The Flex lock-on-payout rule found on Lucid's pages today is reported as a sensitivity
  for BOT-B only (code/firm_lockpay.py), applied identically to the baseline. Reason: keeps rounds 1-4 comparable; Owen's call
  whether to adopt it.

## BOT-A bar (LucidPro 50K, eval)
Primary (must beat or tie baseline_A, in research AND validation, at stress cost):
  p_pass (higher), med_days_pass (lower, and < 30), bust (lower), ev = 90-day lifecycle EV after fees and resets (higher).
Limits ("can't break" = no worse than baseline_A by more than the tolerance, same cells):
  10% relative: pf, exp_R, sharpe, sortino, p_payout, med_days_payout, fund_bust, cons_blocks_per30, cons_block_rate, trades_pm
  25% relative: max_dd, worst_day (dollar risk scales with the extra variance a faster pass needs)
  Absolute: worst_day never below -$1,200 (the Pro daily loss limit).
A pick that meets the primary set but breaks a limit is reported with the exact shortfall, not hidden.
Holdout H3 is reported against the same bar; it is not used to choose.

## BOT-B bar (LucidFlex 50K, funded payouts)
Unchanged: beat or tie baseline_B on every metric incl. the sustained (90-day funded) block, research and validation, stress.

## Regime filter (point 3), causal, per leg, applied before the arbiter (code/regime.py)
Menu, each known before the trade's entry minute (prior sessions only):
  R1 vol band: prior-session ATR20 percentile (expanding, >= 120 prior sessions) inside [lo, hi]; lo in {0, .2}, hi in {.8, 1}
  R2 trend efficiency: Kaufman efficiency ratio of the prior 20 RTH closes above its expanding 30th percentile
  R3 leg equity filter: the leg's own last N closed signals (all signals, taken or not), N in {10, 20}, mean R > 0
  R4 bot equity filter: the bot's last 20 closed signals mean R > 0, else size x 0.5
  plus the round-2 filters (crash, sma147 trend, VVG, first-hour range expansion)
Selection rule: per leg, the menu item with the best research HAC t-stat of mean R, keeping >= 50% of its trades and improving
t by >= 0.5 over no filter; otherwise none. Then bot-level choice on research, confirmed on validation (stress).

## Sizing for BOT-A (point 4), code/policy.py (new optional fields, defaults = round-3 behaviour)
  cush_a: risk x (cushion / MLL) ^ cush_a         (de-risk as the account nears the drawdown floor), cush_a in {0, .5, 1, 1.5}
  prog_b: risk x (1 + prog_b x progress), progress = profit so far / target clipped to [0, 1]  (press into the target), {-.3, 0, .3, .6}
  pace_c: risk x clip(need share / time share left, .7, 1.5) ^ pace_c  (behind pace: press; ahead: ease), {0, .5, 1}
  plus r_eval in {800, 1000, 1200}. k_need (finish exactly, don't overshoot) kept.
Plateau check: a pick's neighbours on each sizing axis must also meet the primary bar on research.
