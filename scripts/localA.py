import json, random, searchA
rows = [json.loads(l) for l in open(searchA.LOG)]
rows = [r for r in rows if r["stage"].startswith("joint")]; rows.sort(key=lambda r: -r["sel"])
sets, seen = [[["OD_NQ", 1.0], ["IR_NQ", 3.0], ["CDL_NQ", 1.0]], [["OD_NQ", 1.0], ["IR_NQ", 3.0], ["CDL_NQ", 1.0], ["CDL_ES", 1.0], ["OD_ES", 0.5]],
               [["IR_NQ", 3.0], ["OD_NQ", 1.0], ["CDL_NQ", 1.0], ["CDL_ES", 1.0], ["ONB_NQ", 1.0], ["ONB_ES", 1.0]]], set()
for r in rows:
    k = json.dumps(r["legs"])
    if k not in seen: seen.add(k); sets.append(r["legs"])
    if len(sets) >= 12: break
rng = random.Random(7); cfgs = []
for legs in sets:
    for _ in range(130):
        g = dict(base_risk_pct=rng.choice([0.6, 0.75, 0.9, 1.0, 1.25]), cushion_risk_frac=rng.choice([0.6, 0.75, 0.9]), need_risk_mult=rng.choice([0.75, 1.0, 1.5]),
                 day_stop_frac=rng.choice([0.4, 0.8, 1.5]), pace_max_mult=rng.choice([None, 1.5, 2.0]), pace_gain=rng.choice([1.0, 2.0, 3.0]),
                 early_mult=rng.choice([1.0, 1.3]), mid_mult=rng.choice([0.7, 1.0]), late_mult=rng.choice([0.7, 1.0]),
                 day_profit_lock_frac=rng.choice([None, 0.3]), low_cushion_mult=rng.choice([0.5, 1.0]), crit_cushion_mult=rng.choice([0.25, 0.5, 1.0]), streak_mult=None)
        cfgs.append(dict(legs=legs, gov=g, plan=rng.choice(["pro", "pro_nodll"]), max_open=2))
out = searchA.run(cfgs, "localA"); out.sort(key=lambda o: -o["sel"])
for o in out[:20]:
    print(o["sel"], round((o["t1_p30"] + o["t2_p30"] + o["val_p30"]) / 3, 1), o["t1_p30"], o["t2_p30"], o["val_p30"], o["train_breach"], o["plan"], o["legs"], o["gov"], flush=True)
