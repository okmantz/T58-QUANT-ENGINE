import sys, json, random, multiprocessing as mp
import numpy as np, sim
from app.bots.risk_governor import GovernorConfig
from app.bots.presets import preset_configs
cf = {c.preset_key: c for c in preset_configs()}
GB = cf["payout"].governor
CANDS = ["OD_NQ", "IR_NQ", "CDL_NQ", "CDLB_NQ", "IRA_NQ", "TM_NQ", "LSR_NQ", "ONB_NQ", "CDL_ES", "CDLB_ES", "OD_ES", "COB_ES", "ONB_ES", "ORBC_ES", "IRB_NQ", "IRA_ES"]
LOG = "/mnt/project-files/t58-new-bots/results/searchB_log.jsonl"
def ev(cfg):
    g = GovernorConfig.from_dict({**GB, **cfg["gov"]})
    s = sim.score_dev([tuple(x) for x in cfg["legs"]], g, cfg.get("plan", "flex"), "B", max_open=cfg.get("max_open", 2))
    s["sel"] = min(s["t1_pay30"], s["t2_pay30"], s["val_pay30"]) - 2 * max(s["t1_breach_before"], s["t2_breach_before"], s["val_breach_before"])
    return {**cfg, **{k: (round(float(v), 2) if isinstance(v, (float, np.floating)) else v) for k, v in s.items()}}
def run(cfgs, tag):
    with mp.Pool(4) as p: out = p.map(ev, cfgs, chunksize=4)
    with open(LOG, "a") as f:
        for o in out: f.write(json.dumps({"stage": tag, **o}, default=float) + "\n")
    return out
def rand_gov(rng):
    return dict(base_risk_pct=rng.choice([0.3, 0.5, 0.75, 1.0, 1.25]), cushion_risk_frac=rng.choice([0.1, 0.15, 0.25, 0.35, 0.5]),
                day_stop_frac=rng.choice([0.2, 0.3, 0.4, 0.6]), funded_mult=rng.choice([0.6, 0.8, 1.0, 1.3]),
                win_day_lock_mult=rng.choice([None, 1.0, 1.5, 2.0, 3.0]), early_mult=rng.choice([0.8, 1.0, 1.3]), mid_mult=rng.choice([0.7, 1.0, 1.3]),
                late_mult=rng.choice([0.5, 0.7, 1.0]), streak_mult=rng.choice([None, 0.5, 0.7]), low_cushion_mult=rng.choice([0.5, 0.75, 1.0]))
def fl(d): return {k: (float(v) if isinstance(v, (int, float)) and v is not None else v) for k, v in d.items()}
if __name__ == "__main__":
    mode, seed, N = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    rng = random.Random(seed); cfgs = []
    shipped = [["IR_NQ", 1.0], ["COB_ES", 0.25], ["OD_NQ", 0.25], ["CDLB_NQ", 0.5]]
    for _ in range(N):
        if mode == "gov": legs = shipped
        else:
            legs = rng.sample(CANDS, rng.randint(3, 8))
            if "CDL_NQ" in legs and "CDLB_NQ" in legs: legs.remove("CDLB_NQ")
            if "CDL_ES" in legs and "CDLB_ES" in legs: legs.remove("CDLB_ES")
            legs = [[x, float(rng.choice([0.25, 0.5, 1.0, 1.5, 2.0]))] for x in legs]
        cfgs.append(dict(legs=legs, gov=fl(rand_gov(rng)), plan="flex", max_open=rng.choice([1, 2, 2, 3])))
    out = run(cfgs, f"{mode}_{seed}"); out.sort(key=lambda o: -o["sel"])
    for o in out[:12]:
        print(o["sel"], o["t1_pay30"], o["t2_pay30"], o["val_pay30"], o["val_breach_before"], o["val_first_amt"], o["max_open"], o["legs"], o["gov"], flush=True)
