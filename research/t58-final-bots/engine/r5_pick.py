"""Round 5 pick rule (PREREG_R5.md) + rotation check. Usage: python3 r5_pick.py A1|B1|A2|B2 [ntop]"""
import sys, json
sys.path.insert(0, "research/t58_final_bots/engine")
import numpy as np, pandas as pd
OUT = "research/t58_final_bots/research"; DEV = ("h3", "research", "validation")
def nf(row, sps, obj):
    if obj == "A":
        p, l = json.loads(row.prim), json.loads(row.lim)
        return sum(len(p[s]) for s in sps), sum(len(l[s]) for s in sps)
    b = json.loads(row.bad); return sum(len(b[s]) for s in sps), 0
def rank(df, sps, obj):
    k = np.array([nf(r, sps, obj) for r in df.itertuples()])
    key = "p_pass" if obj == "A" else "f90_paid"
    mn = df[[f"{s}_{key}" for s in sps]].min(1).to_numpy()
    nchg = df.pick.map(lambda s: len(json.dumps(s))).to_numpy() * 0     # tie-break placeholder (R4 row is vid R4)
    o = np.lexsort((-mn, k[:, 1], k[:, 0]))
    return df.iloc[o].assign(f1=k[o, 0], f2=k[o, 1], minkey=mn[o])
if __name__ == "__main__":
    tag = sys.argv[1]; ntop = int(sys.argv[2]) if len(sys.argv) > 2 else 10; obj = tag[0]
    df = pd.read_pickle(f"{OUT}/runs/r5_{tag}_table.pkl")
    r = rank(df, DEV, obj); pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 80)
    cols = ["vid", "f1", "f2", "minkey"] + ([f"{s}_p_pass" for s in DEV] if obj == "A" else [f"{s}_trades_pm" for s in DEV] + [f"{s}_f90_paid" for s in DEV])
    print(r[cols].head(25).round(3).to_string())
    print("R4 row:"); print(r[r.vid == "R4"][cols].round(3).to_string())
    print("distribution of f1:", np.bincount(r.f1.astype(int))[:10])
    for s in DEV:
        oth = [x for x in DEV if x != s]; t = rank(df, oth, obj).iloc[0]
        print(f"rotation: pick on {oth} -> {t.vid}; on {s}:", nf(t, [s], obj), (json.loads(t.prim)[s], json.loads(t.lim)[s]) if obj == "A" else json.loads(t.bad)[s])
    top = [json.loads(p) for p in r.pick.head(ntop)]
    json.dump(top, open(f"{OUT}/runs/r5_{tag}_top.json", "w"))
    print("first bad/lim of top:", r.iloc[0].lim if obj == "A" else r.iloc[0].bad)
