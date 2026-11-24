"""Round 4 step 1: per-leg regime menu on RESEARCH only (2020-2023), stress net R. Selection rule from PREREG_R4.md.
Also prints the same filters' effect on validation (2024-01 .. 2026-11-20) for information; selection uses research only."""
import sys, os, json; os.environ["T58_R4"] = "1"; sys.path.insert(0, "research/t58_final_bots/engine")
import numpy as np, pandas as pd
import r4, regime as RG, search as S, legs as LG
from stats import nw_t
MENU = {"none": None}
for lo in (0, .2):
    for hi in (.8, 1.0):
        if (lo, hi) != (0, 1.0): MENU[f"vol{lo}-{hi}"] = {"vol": (lo, hi)}
MENU["er30"] = {"er": .3}
for N in (10, 20): MENU[f"eq{N}"] = {"eq": N}
rows = []
for k in LG.CAND:
    b = S.leg(k)
    if b is None: continue
    for name, rs in MENU.items():
        bb = RG.apply(b, rs) if rs else b
        R = RG.net_R(bb); d = bb["day"]
        for sp, (x, y) in (("research", r4.SPL["research"]), ("validation", r4.SPL["validation"]), ("H2", ("2026-03-02", "2026-11-21"))):
            m = (d >= np.datetime64(x)) & (d < np.datetime64(y)); n0 = ((b["day"] >= np.datetime64(x)) & (b["day"] < np.datetime64(y))).sum()
            rows.append(dict(leg=k, filt=name, split=sp, n=int(m.sum()), keep=m.sum() / max(n0, 1), mR=float(R[m].mean()) if m.any() else np.nan,
                             t=float(nw_t(R[m])) if m.sum() > 10 else np.nan))
df = pd.DataFrame(rows); df.to_csv(f"{r4.OUT}/r4_leg_regime.csv", index=False)
pick = {}
for k, g in df[df.split == "research"].groupby("leg"):
    t0 = g[g.filt == "none"].t.iloc[0]; c = g[(g.keep >= .5) & (g.filt != "none")].sort_values("t", ascending=False)
    pick[k] = c.filt.iloc[0] if len(c) and c.t.iloc[0] >= t0 + 0.5 else "none"
json.dump({k: [v, MENU[v]] for k, v in pick.items()}, open(f"{r4.OUT}/r4_leg_regime_pick.json", "w"), indent=1)
pd.set_option("display.width", 250)
for k in pick:
    g = df[df.leg == k].pivot_table(index="filt", columns="split", values=["mR", "t", "keep"]).round(3)
    print(k, "-> pick", pick[k]); print(g[[("t", "research"), ("keep", "research"), ("mR", "research"), ("t", "validation"), ("mR", "validation"), ("mR", "H2"), ("keep", "H2")]].to_string())
