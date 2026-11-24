"""Rank a research grid against the baseline, then re-score the best configs at stride 1 on research AND validation, base AND stress cost.
Usage: python3 confirm.py <run> <obj A|B> <plan pro50|flex50> [top]. Writes research/runs/<run>_confirm.csv and appends every grid row to
research/bot_trials.csv."""
import sys, json, pickle, csv, time
from multiprocessing import Pool
import numpy as np, pandas as pd
sys.path.insert(0, "research/t58_final_bots/engine")
import search as S, score, firm
from policy import Pol
RUNS = "research/t58_final_bots/research/runs"
TRIALS = "research/t58_final_bots/research/bot_trials.csv"
def plan_of(name, cost="base"):
    return (firm.Plan(cost=cost) if name == "pro50" else firm.Plan.flex50(cost=cost))
def base_all(plan, obj):
    import data as D; sfx = "_r3" if D.R3 else ""
    d = pd.read_csv(f"research/t58_final_bots/research/{'baseline_dev' if plan == 'pro50' else 'baseline_dev_flex'}{sfx}.csv")
    d = d[d.bot == "baseline_" + obj]
    return {(r.split, r.cost): r.to_dict() for _, r in d.iterrows()}
def rescore(a):
    legs, g, plan, sus = a
    b = S.bot(legs, max_open=2); out = {}
    for sp, (x, y) in (("research", S.RES), ("validation", S.VAL)):
        for c in ("base", "stress"):
            p = plan_of(plan, c); pol = Pol(**g)
            r = score.full(b, pol, p, x, y, stride=1)
            if sus: r.update(score.sustained_block(b, pol, p, x, y))
            out[(sp, c)] = r
    return out
if __name__ == "__main__":
    run, obj, plan = sys.argv[1:4]; top = int(sys.argv[4]) if len(sys.argv) > 4 else 12
    sus = obj == "B"
    R = pickle.load(open(f"{RUNS}/{run}.pkl", "rb")); LS = R["legsets"]
    base = base_all(plan, obj); br = base[("research", "base")]
    rows = []
    for ln, mo, g, r in R["res"]:
        bad = S.beats(r, br, sustained=sus)
        rows.append(dict(run=run, legset=ln, mo=mo, params=json.dumps(g), nbad=len(bad), bad=",".join(bad), **{k: r.get(k) for k in S.HIGHER + S.LOWER + (S.HIGHER_B + S.LOWER_B if sus else [])}))
    df = pd.DataFrame(rows)
    new = not __import__("os").path.exists(TRIALS)
    df.assign(ts=time.strftime("%Y-%m-%d %H:%M"), plan=plan, obj=obj, split="research", cost="base", stride=2).to_csv(TRIALS, mode="a", header=new, index=False)
    key = "p_pass" if obj == "A" else ("f90_paid" if plan == "flex50" else "p_payout")
    df = df.sort_values(["nbad", key], ascending=[True, False])
    print(df.nbad.value_counts().sort_index().to_dict()); print(df.bad.str.split(",").explode().value_counts().head(12).to_dict())
    print(df.head(top)[["legset", "params", "nbad", "bad", key]].to_string())
    pick = df.head(top)
    jobs = [(LS[r.legset], json.loads(r.params), plan, sus) for r in pick.itertuples()]
    with Pool(4) as pool:
        outs = pool.map(rescore, jobs)
    crow = []
    for r, o in zip(pick.itertuples(), outs):
        for (sp, c), m in o.items():
            bad = S.beats(m, base[(sp, c)], sustained=sus)
            crow.append(dict(legset=r.legset, params=r.params, split=sp, cost=c, nbad=len(bad), bad=",".join(bad), **{k: m.get(k) for k in m}))
    cd = pd.DataFrame(crow); cd.to_csv(f"{RUNS}/{run}_confirm.csv", index=False)
    s = cd.groupby(["legset", "params"]).agg(tot=("nbad", "sum"), worst=("nbad", "max"), bads=("bad", lambda x: " | ".join(x))).sort_values("tot")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 140)
    print(s.to_string())
