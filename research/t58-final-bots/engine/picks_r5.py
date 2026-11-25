"""Round 5 picks (2026-11-24). Round 5 searched 3,720 configs on 2016-11-24 .. 2026-11-20 (h3 + research + validation, all already
read in earlier rounds; no holdout left). See research/PREREG_R5.md and final/T58_FINAL_BOTS_ROUND5_2026-11-24.md.
BOT_A: unchanged from round 4. No round-5 config clears every BOT-A bar in all three periods; the best one ties round-4 A.
BOT_B: unchanged from round 4. BOT_B_ALT (search tag B2-26) wins the pre-registered count (2 shortfall cells vs 5) but fails the
rotation and plateau checks and pays out less often than round-4 B on 2020-2026, so it is kept as a documented alternative only."""
import copy, json, picks_r4
BOT_A = copy.deepcopy(picks_r4.BOT_A)
BOT_B = copy.deepcopy(picks_r4.BOT_B)
BOT_B_ALT = json.loads('''{"plan": "flex50", "max_open": 4, "spec": {"crash": 0.5, "one_per_inst": false}, "legs": {"CDL_NQ": 1, "ORB15C_NQ": 1, "IR_NQ": 0.5, "VWPB_NQ": 0.25, "OD_ES": 0.5, "PDLB_GC": 0.5, "OD_NQ": 0.25, "CORB_ES": 0.5, "TOD10_NQ": 0.5}, "policy": {"r_eval": 300, "f_cush": 0.4, "k_need": 1.0, "day_stop": 300, "fund_day_stop": 300, "r_fund": 250, "fund_day_cap": null, "fund_f_cush": 0.3, "eval_day_cap": 1100, "dd_lvl": 400, "dd_k": 0.25, "floor_x": 3.0}, "rspec": null}''')
