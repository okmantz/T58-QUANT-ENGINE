import sys, json
sys.path.insert(0, "research/t58_final_bots/engine")
import r6, pandas as pd
OBJ, CID = sys.argv[1], sys.argv[2]
base = json.load(open(f"{r6.OUT}/runs/r6_base_stride3.json")); bl = "baseline_A" if OBJ == "A" else "baseline_B"
def fails(r, plan, sp):
    b = base[f"{bl}|{plan}|{sp}"]
    if OBJ == "A": pf, lf = r6.a_bar(r, b); return pf + lf
    return r6.b_bar(r, b)
rows = []
for l in open(f"{r6.OUT}/runs/r6_{OBJ}_plateau_{CID}.jsonl"):
    o = json.loads(l); res = o["res"]; f = {}
    for key, r in res.items():
        plan, sp, k = key.split("|"); f[f"{plan}{sp}"] = fails(r, plan, sp)
    rows.append(dict(step=o["cid"].split("~")[1], ncell=sum(bool(v) for v in f.values()), nfail=sum(len(v) for v in f.values()),
                     p50W1_pp=res["pro50|W1|None"]["p_pass"], p50W2_pp=res["pro50|W2|None"]["p_pass"], p50W1_ev=res["pro50|W1|None"]["ev"], p50W2_ev=res["pro50|W2|None"]["ev"], fails=json.dumps(f)))
d = pd.DataFrame(rows).sort_values(["ncell", "nfail"]); pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 140)
print(d.round(3).to_string()); print("within one cell (ncell<=2):", int((d.ncell <= 2).sum()), "of", len(d))
d.to_csv(f"{r6.OUT}/plateau_r6_{OBJ}_{CID}.csv", index=False)
