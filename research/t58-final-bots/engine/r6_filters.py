"""PREREG_R6 section 5: filter admission per leg. Writes research/filter_trials_r6.csv (every tried leg x input x side)."""
import os, sys, json
os.environ["T58_R6"] = "1"; sys.path.insert(0, "research/t58_final_bots/engine")
import numpy as np, pandas as pd
import search as S, regime, r6feat as X, picks_r4
LEGS = sorted(set(picks_r4.BOT_A["legs"]) | set(picks_r4.BOT_B["legs"]))
CONT = ["vix_pct", "vix_term", "vix_chg5", "tick", "tick_dir", "gap_abs", "gap_dir", "onr"]
def period(day):
    d = np.asarray(day).astype("datetime64[D]")
    return np.where(d < np.datetime64("2020-01-02"), "h3", np.where(d < np.datetime64("2024-01-01"), "res", "val"))
rows = []
for k in LEGS:
    b = S.leg(k); R = regime.net_R(b); P = period(b["day"]); tf = X.trade_feats(b)
    mu = {p: R[P == p].mean() for p in ("h3", "res", "val")}
    def test(name, side, rm, thr=None):
        r = dict(leg=k, input=name, side=side, thr=thr, n=len(R), n_rm=int(rm.sum()))
        ok = True
        for p in ("h3", "res", "val"):
            m = P == p; x = R[m & rm]
            r[f"mu_{p}"] = round(mu[p], 4); r[f"rm_{p}"] = round(x.mean(), 4) if len(x) else np.nan; r[f"nrm_{p}"] = int(len(x))
            r[f"keep_{p}"] = round(R[m & ~rm].mean(), 4) if (m & ~rm).any() else np.nan
            ok &= len(x) >= 5 and x.mean() < mu[p]
        r["admit"] = bool(ok); rows.append(r)
    for name in CONT:
        v = tf[name]; rv = v[(P == "res") & np.isfinite(v)]
        if len(rv) < 30: continue
        q1, q2 = np.quantile(rv, [1 / 3, 2 / 3])
        test(name, "skip_low", np.isfinite(v) & (v <= q1), round(float(q1), 4)); test(name, "skip_high", np.isfinite(v) & (v >= q2), round(float(q2), 4))
    va = tf["va_dir"]
    for side, val in (("skip_against", -1.0), ("skip_inside", 0.0), ("skip_with", 1.0)): test("va_dir", side, va == val, val)
    test("nfp", "skip_day", tf["nfp"] == 1); test("fomc_pm", "skip_after_1330", tf["fomc_pm"] == 1)
d = pd.DataFrame(rows); d.to_csv("research/t58_final_bots/research/filter_trials_r6.csv", index=False)
print("trials", len(d), "admitted", int(d.admit.sum()))
pd.set_option("display.width", 250)
print(d[d.admit][["leg", "input", "side", "thr", "n_rm", "mu_h3", "rm_h3", "mu_res", "rm_res", "mu_val", "rm_val", "keep_h3", "keep_res", "keep_val"]].to_string())
