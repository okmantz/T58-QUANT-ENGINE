"""Lifecycle per attempt on DEV starts (2020-01..2024-10, windows end by 2024-12-31): buy -> eval with bot E -> funded with bot F, 60 days.
Block-bootstrap 90% CIs (blocks of 21 consecutive start days)."""
import sys, json, numpy as np, multiprocessing as mp, sim, acct, cands
FEES = {"pro": (126, 180), "pro_nodll": (156, 223), "flex": (88, 126)}
PATHS = {
  "pro: shipped A -> shipped B": ("pro", "A_SHIP", "B_SHIP"),
  "pro: shipped A -> shipped A": ("pro", "A_SHIP", "A_SHIP"),
  "pro: new A -> new A": ("pro", "A_NEW", "A_NEW"),
  "pro: new A -> new B": ("pro", "A_NEW", "B_NEW"),
  "flex: shipped A -> shipped B": ("flex", "A_SHIP", "B_SHIP"),
  "flex: new A -> new B": ("flex", "A_NEW", "B_NEW"),
  "flex: new B -> new B": ("flex", "B_NEW", "B_NEW"),
  "flex: new B2 -> new B2": ("flex", "B_NEW2", "B_NEW2"),
  "flex: new A -> new B2": ("flex", "A_NEW", "B_NEW2"),
  "pro: new A -> shipped A": ("pro", "A_NEW", "A_SHIP"),
  "flex: new A -> shipped A": ("flex", "A_NEW", "A_SHIP"),
  "pro_nodll: new A -> new A": ("pro_nodll", "A_NEW", "A_NEW"),
  "flex: shipped A -> new B [post-H1 combo]": ("flex", "A_SHIP", "B_NEW"),
  "pro: shipped A -> new B [post-H1 combo]": ("pro", "A_SHIP", "B_NEW"),
}
H = 60
import policies
_orig = sim.policy
def _pc(gov, plan, w):
    if plan.startswith("flex"):
        p = policies.repo_policy_cons(gov, sim.lite_for(plan)); p.w = w; return p
    return _orig(gov, plan, w)
sim.policy = _pc
def one(name, holdout=False, a="2020-01-01", z="2025-01-01", last="2024-12-31"):
    plan, e, f = PATHS[name]; E, F = getattr(cands, e), getattr(cands, f)
    bE = sim.book(E["legs"], holdout=holdout); bF = sim.book(F["legs"], holdout=holdout)
    trE, trF = acct.arrays(bE), acct.arrays(bF); r = sim.PLANS[plan]()
    gE, gF = cands.gov(E), cands.gov(F)
    st = sim.starts_in(trE, a, z, H, last); rows = []
    for s in st:
        o = acct.run(trE, s, H, r, sim.policy(gE, plan, trE["w"]), phase="eval")
        if o["pass_day"] is None: rows.append((-1, -1, 0.0)); continue
        pdays = o["pass_day"]; rem = H - pdays - 1
        if rem <= 0: rows.append((pdays, -1, 0.0)); continue
        fs = np.datetime64(s) + np.timedelta64(pdays + 1, "D")
        fo = acct.run(trF, fs, rem, r, sim.policy(gF, plan, trF["w"]), phase="funded")
        pays = fo["payouts"]
        rows.append((pdays, pdays + 1 + pays[0][0] if pays else -1, 0.9 * sum(x[1] for x in pays)))
    return name, plan, rows
def summ(plan, rows, rng=np.random.default_rng(0), B=2000, blk=21):
    P = np.array([x[0] for x in rows]); F = np.array([x[1] for x in rows]); Y = np.array([x[2] for x in rows]); n = len(rows)
    def m(idx):
        p30 = ((P[idx] >= 0) & (P[idx] <= 30)).mean(); pd30 = ((F[idx] >= 0) & (F[idx] <= 30)).mean()
        pd60 = (F[idx] >= 0).mean(); y = Y[idx].mean(); return np.array([p30, pd30, pd60, y])
    pt = m(np.arange(n)); nb = int(np.ceil(n / blk)); bs = []
    for _ in range(B):
        st = rng.integers(0, n - blk + 1, nb); idx = (st[:, None] + np.arange(blk)).ravel()[:n]; bs.append(m(idx))
    lo, hi = np.percentile(bs, [5, 95], axis=0)
    out = dict(n=n, pass30=100 * pt[0], paid30=100 * pt[1], paid60=100 * pt[2], mean_paid=pt[3], mean_paid_lo=lo[3], mean_paid_hi=hi[3],
               pass30_ci=(100 * lo[0], 100 * hi[0]), paid30_ci=(100 * lo[1], 100 * hi[1]), paid60_ci=(100 * lo[2], 100 * hi[2]))
    fc, fl = FEES[plan]
    out.update(ev_coupon=pt[3] - fc, ev_coupon_ci=(lo[3] - fc, hi[3] - fc), ev_list=pt[3] - fl, fee_coupon=fc, fee_list=fl)
    return out
def job(name):
    global H
    H = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    n, plan, rows = one(name, holdout=HOLD, a=A, z=Z, last=LAST); return n, plan, rows
import os
HOLD, A, Z, LAST = (True, "2025-01-01", "2026-03-01", "2026-02-28") if os.environ.get("H1") else (False, "2020-01-01", "2025-01-01", "2024-12-31")
if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if len(sys.argv) > 2: H = int(sys.argv[2])
    names = [n for n in PATHS if len(sys.argv) <= 3 or sys.argv[3] in n]
    with mp.Pool(4) as p: res = p.map(job, names)
    out = {}
    for n, plan, rows in res:
        s = summ(plan, rows); out[n] = s
        print(f"{n:32s} n={s['n']} pass30 {s['pass30']:.1f} paid30 {s['paid30']:.1f} {tuple(round(x,1) for x in s['paid30_ci'])} paid60 {s['paid60']:.1f} "
              f"mean ${s['mean_paid']:.0f} EV coupon ${s['ev_coupon']:.0f} {tuple(round(x) for x in s['ev_coupon_ci'])} EV list ${s['ev_list']:.0f}", flush=True)
    json.dump(out, open(f"/mnt/project-files/t58-new-bots/results/lifecycle_{tag}.json", "w"), indent=1, default=float)
