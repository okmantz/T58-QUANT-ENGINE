# Round 6 frozen picks (written 2026-11-25, after the stride-1 dev confirm, before any H6 read)

Pick rule: PREREG_R6.md section 7 (+ addenda). Decisions at stress cost on the 4 cells Pro 50K / Pro 100K x W1 / W2.

## BOT-A: round-6 config A59 REPLACES the round-4 BOT-A
Config: research/picks_r6_A.json (sha256 below). Round-4 BOT-A legs, max_open and policy, plus
- risk multiplier rm 1.15 (r_eval 920 on Pro 50K),
- Pro 100K dollar knobs x1.75 (searched in 1.5 / 1.75 / 2.0),
- five entry filters (prior-day inputs, thresholds = research terciles):
  CDL_NQ skip when VIX 5-day change < 0.9581; CDL_ES skip when VIX/VIX3M < 0.8354;
  ORB15C_NQ skip when prior NYSE TICK close < -113; ORB15C_ES skip when the open is outside the prior value area on the trade's side;
  OD_NQ skip when |overnight gap| / ATR14 < 0.1944.
Stride-1 stress shortfall cells vs baseline_A (PREREG_R4 bar):
| cell | BOT-A-R4 | BOT-A-R6 |
|---|---|---|
| pro50 W1 | 0 | 0 |
| pro50 W2 | 3 (exp_R, sharpe, sortino) | 4 (pf, exp_R, sharpe, sortino) |
| pro100 W1 | 1 (med_days_payout) | 1 (med_days_payout) |
| pro100 W2 | 2 (exp_R, p_payout) | 0 |
(a) cells 2 < 3 PASS. (b) p_pass and ev >= R4 in pro50 W1, pro100 W1, pro100 W2 (3 of 4) PASS; pro50 W2 is worse
(p_pass .375 vs .401, ev 152 vs 164). (c) rotation PASS (stride 3, r6_A_rank). (d) plateau 18 / 26 within one cell PASS.
Plan: Pro 50K (stress ev W1 80.5 vs 80.4 on 100K, W2 152 vs 62).

## BOT-B: round-4 BOT-B STAYS (Flex 50K design)
No round-6 B config reached fewer than 4 shortfall cells vs baseline_B on Pro. baseline_B on Pro barely trades (no consistency
blocks, tiny drawdown and worst day), so beat-or-tie on every metric is not reached by any config. Documented, not picked:
B785 (research/picks_r6_Balt.json), a Pro design with higher payouts.

## H6 read
One read of 2026-01-05 .. 2026-11-21 for the baselines, both round-4 bots, BOT-A-R6 and B785, stress and base (code/r6_confirm.py h6).
ES/NQ/GC H6 is in-sample (read in rounds 1-5). No energy leg was admitted, so the sealed CL/NG H6 data is not loaded and stays sealed.
