"""Round 5 search (research/PREREG_R5.md). Stride 2, stress cost, splits h3 + research + validation (all already read; no holdout).
Every config is logged to research/bot_trials_r5.csv.  Usage: python3 r5_search.py A1|B1|A2|B2"""
import sys, os, json, itertools, pickle, time, copy, random
sys.path.insert(0, "research/t58_final_bots/engine")
import r5
import numpy as np, pandas as pd
from multiprocessing import Pool
import r4, picks_r4, search as S
PRE = json.load(open(f"{r5.OUT}/r4_leg_regime_pick.json"))
RULE = {k: v[1] for k, v in PRE.items() if v[1]}
ADD_A = ["VWPB_NQ", "ORB30T_NQ", "ORB15N_NQ", "OD_ES", "CORB_ES", "GAP_GC", "TOD10_NQ"]
ADD_B = ["ORB15N_NQ", "TOD10_NQ", "CDLB_NQ", "ORB15_NQ"]
CAP = 1500
def _rs(legs, on): return ({k: v for k, v in RULE.items() if k in legs} or None) if on else None
def variants(tag):
    rnd = random.Random(5)
    if tag == "A1":
        a = picks_r4.BOT_A; L = list(a["legs"]); seen = set(); out = [copy.deepcopy(a)]
        out[0].update(rspec=None, vid="R4")
        allc = list(itertools.product(itertools.product((0, .5, 1), repeat=len(L)), [None] + ADD_A, (0, 1)))
        rnd.shuffle(allc)
        for ws, add, rs in allc:
            if sum(w > 0 for w in ws) < 2: continue
            legs = {k: w for k, w in zip(L, ws) if w > 0}
            if add: legs[add] = .5
            pk = copy.deepcopy(a); pk["legs"] = legs; pk["rspec"] = _rs(legs, rs); pk["vid"] = f"A1-{len(out)}"
            out.append(pk)
            if len(out) >= CAP: break
        return out
    if tag == "B1":
        b = picks_r4.BOT_B; L = list(b["legs"]); out = [copy.deepcopy(b)]; out[0]["vid"] = "R4"
        allc = list(itertools.product(itertools.product((0, .5, 1), repeat=len(L)), [None] + [(k, w) for k in ADD_B for w in (.25, .5)]))
        rnd.shuffle(allc); allc = allc[:CAP * 3]
        for ws, add in allc:
            if sum(w > 0 for w in ws) < 3: continue
            legs = {k: b["legs"][k] * w for k, w in zip(L, ws) if w > 0}
            if add: legs[add[0]] = add[1]
            pk = copy.deepcopy(b); pk["legs"] = legs; pk["rspec"] = _rs(legs, True); pk["vid"] = f"B1-{len(out)}"
            out.append(pk)
            if len(out) >= CAP: break
        return out
    if tag in ("A2", "B2"):
        top = json.load(open(f"{r5.OUT}/runs/r5_{tag[0]}1_top.json")); out = []
        if tag == "A2":
            grid = itertools.product((300, 400, 500), (500, None), (400, 550), (.55, .4), (.3, .4))
            keys = ("r_fund", "fund_day_cap", "fund_day_stop", "cons_k", "fund_f_cush")
        else:
            grid = itertools.product((250, 200, 300), (300, 220), (200, None), (4, 3))
            keys = ("r_fund", "day_stop", "fund_day_cap", "max_open")
        grid = list(grid)
        for t in top:
            for g in grid:
                pk = copy.deepcopy(t)
                for k, v in zip(keys, g):
                    if k == "max_open": pk["max_open"] = v
                    else:
                        pk["policy"][k] = v
                        if k == "day_stop" and tag == "B2": pk["policy"]["fund_day_stop"] = v
                pk["vid"] = f"{tag}-{len(out)}"; out.append(pk)
        return out
def job(pk):
    plan = pk["plan"]; sus = plan == "flex50"
    q = {k: v for k, v in pk.items() if k != "vid"}
    return pk, {sp: r5.run(q, plan, sp, "stress", stride=2, sustained=sus) for sp in r5.DEV}
def base_rows():
    d = pd.read_csv(f"{r5.OUT}/final_dev_r4.csv"); h = pd.read_csv(f"{r5.OUT}/final_hold_r4.csv").assign(split="h3")
    x = pd.concat([d, h]); return x[(x.cost == "stress") & (x.firm == "current")]
def score_rows(res, tag):
    base = base_rows(); rows = []
    for pk, o in res:
        if tag.startswith("A"):
            bA = {sp: base[(base.bot == "baseline_A") & (base.split == sp)].iloc[0].to_dict() for sp in o}
            f = {sp: r5.a_bar(o[sp], bA[sp]) for sp in o}
            row = dict(nprim=sum(len(v[0]) for v in f.values()), nlim=sum(len(v[1]) for v in f.values()),
                       prim=json.dumps({sp: v[0] for sp, v in f.items()}), lim=json.dumps({sp: v[1] for sp, v in f.items()}))
        else:
            bB = {sp: base[(base.bot == "baseline_B") & (base.split == sp)].iloc[0].to_dict() for sp in o}
            bad = {sp: S.beats(o[sp], bB[sp], sustained=True) for sp in o}
            row = dict(nbad=sum(len(v) for v in bad.values()), bad=json.dumps(bad))
        row.update(vid=pk["vid"], pick=json.dumps(pk), **{f"{sp}_{k}": o[sp].get(k) for sp in o for k in (
            "p_pass", "med_days_pass", "bust", "ev", "p_payout", "f90_paid", "f90_payouts", "f90_p2", "pf", "exp_R", "sharpe", "max_dd",
            "worst_day", "trades_pm", "cons_blocks_per30")})
        rows.append(row)
    return pd.DataFrame(rows)
if __name__ == "__main__":
    tag = sys.argv[1]; V = variants(tag); print(tag, len(V), flush=True)
    t0 = time.time()
    with Pool(4) as pool: res = pool.map(job, V, chunksize=4)
    pickle.dump(res, open(f"{r5.OUT}/runs/r5_{tag}.pkl", "wb")); print("secs", round(time.time() - t0), flush=True)
    df = score_rows(res, tag).assign(ts=time.strftime("%Y-%m-%d %H:%M"), tag=tag, cost="stress", stride=2)
    f = f"{r5.OUT}/bot_trials_r5.csv"; df.to_csv(f, mode="a", header=not os.path.exists(f), index=False)
    df.to_pickle(f"{r5.OUT}/runs/r5_{tag}_table.pkl"); print("done", flush=True)
