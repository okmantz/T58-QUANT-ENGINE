"""Round 4 search (PREREG_R4.md). Stride 2, stress cost, research + validation; every config logged to research/bot_trials_r4.csv.
A1: round-3 A x barrier sizing (cush_a, prog_b, pace_c, r_eval) x regime options (rspec, bot_eq).
A2: funded-side tweaks (cons_k, fund_day_cap, r_fund) on the best A1 sizing/regime combos.
B1: round-3 B x regime options x r_fund / day stop.
Usage: T58_R4=1 python3 r4_search.py A1|A2|B1"""
import sys, os, json, itertools, pickle, time, copy
os.environ["T58_R4"] = "1"; sys.path.insert(0, "research/t58_final_bots/engine")
import numpy as np, pandas as pd
from multiprocessing import Pool
import r4, picks_r3, search as S
PRE = json.load(open(f"{r4.OUT}/r4_leg_regime_pick.json"))
RULE = {k: v[1] for k, v in PRE.items() if v[1]}
def rsopts(legs):
    return {"none": None, "rule": {k: v for k, v in RULE.items() if k in legs} or None, "er30": {"*": {"er": .3}}, "eq20": {"*": {"eq": 20}}}
def variants(tag):
    if tag == "A1":
        a = picks_r3.BOT_A
        for (rn, rs), be, ca, pb, pc, re_ in itertools.product(rsopts(a["legs"]).items(), (None, (20, .5)), (0, .5, 1, 1.5), (-.3, 0, .3, .6), (0, .5, 1), (800, 1000, 1200)):
            pk = copy.deepcopy(a); pk.update(rspec=rs, bot_eq=be, rname=rn); pk["policy"].update(cush_a=ca, prog_b=pb, pace_c=pc, r_eval=re_)
            yield pk
    if tag == "A2":
        top = json.load(open(f"{r4.OUT}/runs/r4_A1_top.json"))
        for pk0, ck, fdc, rf, fds in itertools.product(top, (0.55, 0.4, 0.3), (None, 500, 350), (300, 200), (550, 400)):
            pk = copy.deepcopy(pk0); pk["policy"].update(cons_k=ck, fund_day_cap=fdc, r_fund=rf, fund_day_stop=fds); yield pk
    if tag == "B1":
        b = picks_r3.BOT_B
        extras = [{}, {"ORB15N_NQ": .25, "TOD10_NQ": .25}, {"OD_ES": .5}]
        for (rn, rs), be, ex, ds, fdc in itertools.product(rsopts(b["legs"]).items(), (None, (20, .5)), extras, (300, 220), (200, 260, None)):
            pk = copy.deepcopy(b); pk["legs"] = dict(pk["legs"], **ex); pk.update(rspec=rs, bot_eq=be, rname=rn)
            pk["policy"].update(day_stop=ds, fund_day_stop=ds, fund_day_cap=fdc)
            yield pk
def job(pk):
    plan = pk["plan"]; sus = plan == "flex50"
    return pk, {sp: r4.run(pk, plan, sp, "stress", stride=2, sustained=sus) for sp in ("research", "validation")}
if __name__ == "__main__":
    tag = sys.argv[1]; V = list(variants(tag)); print(len(V), flush=True)
    base = pd.read_csv(f"{r4.OUT}/dev_r4_prior.csv"); base = base[base.cost == "stress"]
    t0 = time.time()
    with Pool(4) as pool: res = pool.map(job, V, chunksize=4)
    pickle.dump(res, open(f"{r4.OUT}/runs/r4_{tag}.pkl", "wb")); print("secs", round(time.time() - t0))
    rows = []
    for pk, o in res:
        if tag.startswith("A"):
            bA = {sp: base[(base.bot == "baseline_A") & (base.split == sp)].iloc[0].to_dict() for sp in o}
            fails = {sp: r4.a_bar(o[sp], bA[sp]) for sp in o}
            row = dict(nprim=sum(len(f[0]) for f in fails.values()), nlim=sum(len(f[1]) for f in fails.values()),
                       prim=json.dumps({sp: f[0] for sp, f in fails.items()}), lim=json.dumps({sp: f[1] for sp, f in fails.items()}))
        else:
            bB = {sp: base[(base.bot == "baseline_B") & (base.split == sp)].iloc[0].to_dict() for sp in o}
            bad = {sp: S.beats(o[sp], bB[sp], sustained=True) for sp in o}
            row = dict(nbad=sum(len(v) for v in bad.values()), bad=json.dumps(bad))
        row.update(pick=json.dumps(pk), **{f"{sp}_{k}": o[sp].get(k) for sp in o for k in ("p_pass", "med_days_pass", "bust", "ev", "p_payout", "f90_paid", "pf", "exp_R", "sharpe", "max_dd", "worst_day", "trades_pm", "cons_blocks_per30")})
        rows.append(row)
    df = pd.DataFrame(rows).assign(ts=time.strftime("%Y-%m-%d %H:%M"), tag=tag, cost="stress", stride=2)
    f = f"{r4.OUT}/bot_trials_r4.csv"; df.to_csv(f, mode="a", header=not os.path.exists(f), index=False)
    df.to_pickle(f"{r4.OUT}/runs/r4_{tag}_table.pkl"); print("done")
