import sys, json, random, itertools, multiprocessing as mp, time
import numpy as np, pandas as pd, sim
from app.bots.risk_governor import GovernorConfig
from app.bots.presets import preset_configs
cf = {c.preset_key: c for c in preset_configs()}
GA = cf["pass"].governor
CANDS = ["OD_NQ", "IR_NQ", "CDL_NQ", "CDLB_NQ", "IRA_NQ", "TM_NQ", "LSR_NQ", "ONB_NQ", "CDL_ES", "CDLB_ES", "OD_ES", "COB_ES", "ONB_ES", "ORBC_ES", "IRB_NQ"]
LOG = "/mnt/project-files/t58-new-bots/results/searchA_log.jsonl"

def ev(cfg):
    legs, gov, plan, mo = cfg["legs"], cfg["gov"], cfg.get("plan", "pro"), cfg.get("max_open", 2)
    g = GovernorConfig.from_dict({**GA, **gov})
    s = sim.score_dev([tuple(x) for x in legs], g, plan, "A", max_open=mo)
    s["sel"] = min(s["t1_p30"], s["t2_p30"], s["val_p30"])
    return {**cfg, **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()}}

def run(cfgs, tag):
    with mp.Pool(4) as p:
        out = p.map(ev, cfgs, chunksize=4)
    with open(LOG, "a") as f:
        for o in out: f.write(json.dumps({"stage": tag, **o}, default=float) + "\n")
    return out

FLAT = dict(base_risk_pct=0.75, early_mult=1.0, mid_mult=1.0, late_mult=1.0, need_risk_mult=1.0, day_stop_frac=0.6, cushion_risk_frac=0.75, pace_max_mult=1.5)
if __name__ == "__main__":
    stage = sys.argv[1]
    if stage == "greedy":
        govs = {"shipped": {}, "flat": FLAT}
        for gname, gov in govs.items():
            cur = []; best = None
            for step in range(6):
                cfgs = []
                for c in CANDS:
                    if c in [x[0] for x in cur]: continue
                    for w in (0.5, 1.0, 2.0, 3.0):
                        cfgs.append(dict(legs=cur + [[c, w]], gov=gov))
                out = run(cfgs, f"greedy_{gname}_{step}")
                top = max(out, key=lambda o: o["sel"])
                print(gname, step, top["legs"], top["train_p30"], top["val_p30"], top["sel"], flush=True)
                if best is not None and top["sel"] <= best["sel"] + 0.5: break
                best = top; cur = top["legs"]
            print("BEST", gname, best["legs"], best["sel"], flush=True)

def rand_gov(rng):
    return dict(base_risk_pct=rng.choice([0.5, 0.6, 0.75, 0.9, 1.0, 1.25, 1.5]), early_mult=rng.choice([0.8, 1.0, 1.3, 1.6]),
                mid_mult=rng.choice([0.7, 1.0, 1.3]), late_mult=rng.choice([0.5, 0.7, 1.0]), need_risk_mult=rng.choice([None, 0.5, 0.75, 1.0, 1.5]),
                day_stop_frac=rng.choice([0.3, 0.4, 0.6, 0.8, 1.0, 1.5]), cushion_risk_frac=rng.choice([0.4, 0.5, 0.6, 0.75, 0.9]),
                pace_max_mult=rng.choice([None, 1.25, 1.5, 2.0]), pace_gain=rng.choice([1.0, 2.0, 3.0]),
                low_cushion_mult=rng.choice([0.5, 0.75, 1.0]), crit_cushion_mult=rng.choice([0.25, 0.5, 1.0]),
                streak_mult=rng.choice([None, 0.5, 0.7]), day_profit_lock_frac=rng.choice([None, 0.3, 0.5]))

if __name__ == "__main__" and sys.argv[1] == "gov":
    rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    legs = json.loads(sys.argv[3]) if len(sys.argv) > 3 else [["OD_NQ", 1.0], ["IR_NQ", 3.0], ["CDL_NQ", 1.0]]
    plans = ["pro", "pro_nodll"]
    cfgs = [dict(legs=legs, gov={k: (float(v) if isinstance(v, (int, float, np.floating)) and v is not None else v) for k, v in rand_gov(rng).items()},
                 plan=rng.choice(plans), max_open=rng.choice([1, 2])) for _ in range(int(sys.argv[4]) if len(sys.argv) > 4 else 400)]
    out = run(cfgs, "gov_" + sys.argv[2])
    out.sort(key=lambda o: -o["sel"])
    for o in out[:12]:
        print(o["sel"], o["train_p30"], o["val_p30"], o["train_breach"], o["plan"], o["max_open"], o["gov"], flush=True)

if __name__ == "__main__" and sys.argv[1] == "joint":
    rng = random.Random(int(sys.argv[2])); N = int(sys.argv[3])
    cfgs = []
    for _ in range(N):
        k = rng.randint(3, 7)
        legs = rng.sample(CANDS, k)
        if "CDL_NQ" in legs and "CDLB_NQ" in legs: legs.remove("CDLB_NQ")
        if "CDL_ES" in legs and "CDLB_ES" in legs: legs.remove("CDLB_ES")
        legs = [[x, float(rng.choice([0.5, 1.0, 1.5, 2.0, 3.0]))] for x in legs]
        g = {k2: (float(v) if isinstance(v, (int, float)) and v is not None else v) for k2, v in rand_gov(rng).items()}
        cfgs.append(dict(legs=legs, gov=g, plan=rng.choice(["pro", "pro_nodll"]), max_open=rng.choice([1, 2, 2, 3])))
    out = run(cfgs, "joint_" + sys.argv[2]); out.sort(key=lambda o: -o["sel"])
    for o in out[:15]:
        print(o["sel"], o["t1_p30"], o["t2_p30"], o["val_p30"], o["train_breach"], o["plan"], o["max_open"], o["legs"], o["gov"], flush=True)
