import json, itertools, searchB
rows = [json.loads(l) for l in open(searchB.LOG)]
rows = [r for r in rows if r["stage"].startswith("joint")]; rows.sort(key=lambda r: -r["sel"])
sets, seen = [[["IR_NQ", 1.0], ["COB_ES", 0.25], ["OD_NQ", 0.25], ["CDLB_NQ", 0.5]]], set()
for r in rows:
    k = json.dumps(r["legs"])
    if k not in seen: seen.add(k); sets.append(r["legs"])
    if len(sets) >= 12: break
cfgs = []
for legs in sets:
    for crf, wl, ds, base in itertools.product([0.08, 0.1, 0.12, 0.15, 0.2], [None, 1.0, 2.0], [0.3, 0.6, 1.0], [0.75, 1.0, 1.5]):
        cfgs.append(dict(legs=legs, gov=dict(cushion_risk_frac=crf, win_day_lock_mult=wl, day_stop_frac=ds, base_risk_pct=base, funded_mult=1.0,
                                             early_mult=1.0, mid_mult=1.0, late_mult=1.0, streak_mult=None, low_cushion_mult=1.0), plan="flex", max_open=2))
out = searchB.run(cfgs, "localB"); out.sort(key=lambda o: -o["sel"])
for o in out[:20]:
    print(o["sel"], o["t1_pay30"], o["t2_pay30"], o["val_pay30"], max(o["t1_breach_before"], o["t2_breach_before"], o["val_breach_before"]), o["val_first_amt"], o["legs"], o["gov"], flush=True)
