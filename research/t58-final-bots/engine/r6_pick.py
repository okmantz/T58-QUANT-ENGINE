"""Round 6 pick table (PREREG_R6 section 7). Usage: python3 r6_pick.py A|B  -> research/runs/r6_<obj>_rank.csv"""
import sys, json
sys.path.insert(0, "research/t58_final_bots/engine")
import numpy as np, pandas as pd
import r6
OBJ = sys.argv[1]
base = json.load(open(f"{r6.OUT}/runs/r6_base_stride3.json"))
bl = "baseline_A" if OBJ == "A" else "baseline_B"
PRIM = ["p_pass", "ev"] if OBJ == "A" else ["f90_paid", "p_payout", "ev"]
def fails(r, plan, sp):
    b = base[f"{bl}|{plan}|{sp}"]
    if OBJ == "A":
        pf, lf = r6.a_bar(r, b); return pf + lf
    return r6.b_bar(r, b)
rows = []
for line in open(f"{r6.OUT}/runs/r6_{OBJ}.jsonl"):
    o = json.loads(line); res = o["res"]
    for k in (1.5, 1.75, 2.0):
        cells = {"p50W1": res["pro50|W1|None"], "p50W2": res["pro50|W2|None"], "p100W1": res[f"pro100|W1|{k}"], "p100W2": res[f"pro100|W2|{k}"]}
        f = {c: fails(r, "pro50" if c.startswith("p50") else "pro100", c[-2:]) for c, r in cells.items()}
        row = dict(cid=o["cid"], k100=k, ncell=sum(bool(v) for v in f.values()), nfail=sum(len(v) for v in f.values()),
                   fails=json.dumps(f), fspec=json.dumps(o["pk"].get("fspec", {})))
        for c, r in cells.items():
            for m in PRIM + ["max_dd", "trades_pm", "p_payout", "f90_paid", "med_days_pass", "bust"]: row[f"{c}_{m}"] = r.get(m, np.nan)
        rows.append(row)
d = pd.DataFrame(rows)
ref_id = "A0" if OBJ == "A" else "B-B4ref"
ref = d[(d.cid == ref_id) & (d.k100 == 1.5)].iloc[0]
def prim_ok(r):
    n = 0
    for c in ("p50W1", "p50W2", "p100W1", "p100W2"):
        n += all(r[f"{c}_{m}"] >= ref[f"{c}_{m}"] for m in PRIM)
    return n
d["prim_cells_vs_r4"] = d.apply(prim_ok, axis=1)
d["ok_ab"] = (d.ncell < ref.ncell) & (d.prim_cells_vs_r4 >= 3)
d = d.sort_values(["ok_ab", "ncell", "nfail"], ascending=[False, True, True])
d.to_csv(f"{r6.OUT}/runs/r6_{OBJ}_rank.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 200)
print("ref", ref_id, "ncell", ref.ncell, "nfail", ref.nfail, ref.fails)
show = ["cid", "k100", "ncell", "nfail", "prim_cells_vs_r4", "ok_ab"] + [f"{c}_{m}" for c in ("p50W1", "p50W2", "p100W1", "p100W2") for m in PRIM[:2]]
print(d[show].head(25).round(3).to_string())
print(d.head(8)[["cid", "k100", "fails", "fspec"]].to_string())
