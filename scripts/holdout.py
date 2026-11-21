"""Opens holdout H1 ONCE (after FROZEN_PICKS.sha256). Same scorer as dev; scaling from dev."""
import json, numpy as np, pandas as pd, multiprocessing as mp, sim, acct, cands, evalL, dev, lib
A0, Z0, LAST = "2025-01-01", "2026-03-01", "2026-02-28"
OUT = "/mnt/project-files/t58-new-bots/results/"
def perstart(name, plan, mode):
    c = getattr(cands, name); b = sim.book(c["legs"], holdout=True); tr = acct.arrays(b); r = sim.PLANS[plan](); g = cands.gov(c)
    st = sim.starts_in(tr, A0, Z0, 60, LAST); rows = []
    for s in st:
        o = acct.run(tr, s, 60, r, sim.policy(g, plan, tr["w"]), phase="eval" if mode == "A" else "funded")
        if mode == "A": rows.append((o["pass_day"] is not None and o["pass_day"] <= 30, o["breach_day"] is not None))
        else:
            fp = o["payouts"][0][0] if o["payouts"] else None; br = o["breach_day"]
            rows.append((fp is not None and fp <= 30, br is not None and (fp is None or br < fp), o["payouts"][0][1] if o["payouts"] else 0.0))
    return [str(s) for s in st], rows
def job(x): return x, perstart(*x)
def boot(a, b=None, B=4000, blk=21, rng=np.random.default_rng(1)):
    a = np.asarray(a, float); d = a if b is None else a - np.asarray(b, float); n = len(d); nb = int(np.ceil(n / blk)); bs = []
    for _ in range(B):
        s = rng.integers(0, n - blk + 1, nb); bs.append(d[(s[:, None] + np.arange(blk)).ravel()[:n]].mean())
    return d.mean(), np.percentile(bs, 5), np.percentile(bs, 95)
if __name__ == "__main__":
    jobs = [("A_SHIP", "pro", "A"), ("A_NEW", "pro", "A"), ("A_SHIP", "flex", "A"), ("A_NEW", "flex", "A"),
            ("B_SHIP", "flex", "B"), ("B_NEW", "flex", "B"), ("B_NEW2", "flex", "B"), ("B_SHIP", "pro", "B"), ("B_NEW", "pro", "B")]
    with mp.Pool(4) as p: R = dict(p.map(job, jobs))
    res = {}
    for (nm, plan, mode), (st, rows) in R.items():
        k = f"{nm}|{plan}|{mode}"
        if mode == "A":
            p = [x[0] for x in rows]; br = [x[1] for x in rows]; res[k] = dict(n=len(rows), pass30=[100 * v for v in boot(p)], breach=100 * np.mean(br))
        else:
            p = [x[0] for x in rows]; bb = [x[1] for x in rows]
            res[k] = dict(n=len(rows), pay30=[100 * v for v in boot(p)], breach_before=100 * np.mean(bb),
                          score=100 * np.mean(p) - 200 * np.mean(bb), first_amt=float(np.mean([x[2] for x in rows if x[0]] or [0])))
        print(k, res[k], flush=True)
    def gap(a, b, i=0, mult=100):
        ra, rb = R[a][1], R[b][1]; return [mult * v for v in boot([x[i] for x in ra], [x[i] for x in rb])]
    res["gap_A_pro"] = gap(("A_NEW", "pro", "A"), ("A_SHIP", "pro", "A"))
    res["gap_A_flex"] = gap(("A_NEW", "flex", "A"), ("A_SHIP", "flex", "A"))
    res["gap_B_flex"] = gap(("B_NEW", "flex", "B"), ("B_SHIP", "flex", "B"))
    res["gap_B_pro"] = gap(("B_NEW", "pro", "B"), ("B_SHIP", "pro", "B"))
    print({k: [round(x, 1) for x in v] for k, v in res.items() if k.startswith("gap")})
    # per-leg H1 stats
    legs = {}
    for key in sorted(set(k for c in ["A_SHIP", "A_NEW", "B_SHIP", "B_NEW", "B_NEW2"] for k, _ in getattr(cands, c)["legs"])):
        d = sim.leg(key, holdout=True); e = pd.to_datetime(d["entry"]); h = d[(e >= A0) & (e < Z0)]
        R_ = h["pnl"] / 500.0 if "pnl" in h else h["R"]
        dd = pd.to_datetime(h["entry"]).dt.date; g = R_.groupby(dd.values).sum()
        legs[key] = dict(n=int(len(h)), mR=float(R_.mean()) if len(h) else None, t=float(g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))) if len(g) > 2 else None)
        print("leg", key, legs[key], flush=True)
    res["legs_H1"] = legs
    json.dump(res, open(OUT + "holdout_H1.json", "w"), indent=1, default=float)
