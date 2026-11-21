"""Book builder (the bot arbiter's rules) + Lucid account replays scored per objective. Dev only unless holdout=True is passed by holdout scripts."""
import warnings; warnings.filterwarnings("ignore")
import math, numpy as np, pandas as pd
import dev, lib, acct, policies
from app.bots.risk_governor import GovernorConfig, AccountRulesLite

_CACHE = {}
def leg(key, holdout=False):
    k = (key, holdout)
    if k not in _CACHE: _CACHE[k] = lib.get(key, holdout)
    return _CACHE[k]

def book(legs, max_open=2, max_tpd=6, holdout=False):
    """legs = [(key, weight)] in priority order. One position per instrument, max_open at once, max_tpd entries a day (bot arbiter)."""
    rows = []
    for p, (k, w) in enumerate(legs):
        d = leg(k, holdout)
        for r in d[["entry", "exit", "pnl", "inst"]].itertuples(index=False):
            rows.append((r.entry, p, r.exit, r.pnl, r.inst, w, k))
    rows.sort(key=lambda x: (x[0], x[1]))
    out, busy, live, cnt = [], {}, [], {}
    for e, p, x, pnl, inst, w, k in rows:
        live = [t for t in live if t > e]
        if e < busy.get(inst, pd.Timestamp.min) or len(live) >= max_open: continue
        day = (e + pd.Timedelta(hours=7 - 0)).normalize()   # placeholder, recomputed below in CT
        out.append((e, x, pnl, inst, w, k)); busy[inst] = x; live.append(x)
    b = pd.DataFrame(out, columns=["entry", "exit", "pnl", "inst", "w", "leg"])
    ct = pd.DatetimeIndex(b["entry"]).tz_localize("UTC").tz_convert("America/Chicago").tz_localize(None)
    b["day"] = (ct + pd.Timedelta(hours=7)).normalize()
    if max_tpd:
        b = b[b.groupby("day").cumcount() < max_tpd].reset_index(drop=True)
    b["R"] = b["pnl"] / 500.0; b["kind"] = 1; b["pts"] = 0.0; b["risk_pts"] = 1.0
    return b

PLANS = {
    "pro": lambda: acct.Rules.pro(),
    "pro_nodll": lambda: acct.Rules(dll=1e9),
    "flex": lambda: acct.Rules.flex(),
}
FEE = {"pro": 126.0, "pro_nodll": 156.0, "flex": 88.0, "flex_nodll": 123.0}

def lite_for(plan):
    l = AccountRulesLite.lucid_50k()
    if plan.startswith("flex"): l = l.with_winning_days_payout(5, 150.0)
    return l

def policy(gov, plan, w):
    p = policies.repo_policy(gov, lite_for(plan)); p.w = w; return p

def starts_in(tr, a, b, horizon, last):
    cal = pd.bdate_range(a, b, inclusive="left").values.astype("datetime64[D]")
    lim = np.datetime64(last) - np.timedelta64(horizon, "D")
    return [x for x in cal if x <= lim]

def wilson(k, n, z=1.645):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)

def score(b, gov, plan, a, z, last, mode="A", stride=1, n_eff_days=30):
    """mode A: eval from each start, pass within 30 / 60 days.  mode B: funded from each start, first payout within 30 funded days.
    mode L: lifecycle from eval start: payouts (x0.9) collected within 90 days of purchase minus the fee (per-attempt EV)."""
    tr = acct.arrays(b); w = tr["w"]; r = PLANS[plan]()
    hz = {"A": 60, "B": 60, "L": 90}[mode]
    st = starts_in(tr, a, z, hz, last)[::stride]
    res = []
    for s in st:
        pol = policy(gov, plan, w)
        if mode == "A":
            o = acct.run(tr, s, 60, r, pol, phase="eval")
            res.append((o["pass_day"], o["breach_day"]))
        elif mode == "B":
            o = acct.run(tr, s, 60, r, pol, phase="funded")
            fp = o["payouts"][0][0] if o["payouts"] else None
            res.append((fp, o["breach_day"], o["payouts"][0][1] if o["payouts"] else 0.0))
        else:
            o = acct.run(tr, s, 90, r, pol, phase="eval", stop_at_pass=False)
            # payouts days are relative to the funded start; convert to purchase-relative
            fd = o.get("funded_day")
            pays = [(fd + d, amt) for d, amt in o["payouts"]] if (fd is not None and o["pass_day"] is not None) else []
            res.append((o["pass_day"], o["breach_day"], sum(0.9 * a_ for d, a_ in pays if d <= 90), pays[0][0] if pays else None))
    n = len(res)
    if mode == "A":
        k30 = sum(1 for p, br in res if p is not None and p <= 30); k60 = sum(1 for p, br in res if p is not None)
        brc = sum(1 for p, br in res if br is not None)
        return dict(n=n, p30=100 * k30 / n, p60=100 * k60 / n, breach=100 * brc / n, lo30=100 * wilson(k30, max(n * 21 // 250 // 1, 1) if False else n)[0])
    if mode == "B":
        k30 = sum(1 for fp, br, amt in res if fp is not None and fp <= 30)
        bb = sum(1 for fp, br, amt in res if br is not None and (fp is None or br < fp))
        amt = np.mean([amt for fp, br, amt in res if fp is not None and fp <= 30] or [0])
        return dict(n=n, pay30=100 * k30 / n, breach_before=100 * bb / n, first_amt=amt)
    ev = np.array([x[2] for x in res]) - FEE[plan]
    k = sum(1 for x in res if x[3] is not None and x[3] <= 60)
    return dict(n=n, ev90=ev.mean(), pass_pay60=100 * k / n, pass30=100 * sum(1 for x in res if x[0] is not None and x[0] <= 30) / n)

SPL = {"train": ("2020-01-01", "2024-01-01"), "val": ("2024-01-01", "2025-01-01"), "t1": ("2020-01-01", "2022-01-01"), "t2": ("2022-01-01", "2024-01-01")}
LAST_DEV = "2024-12-31"
def score_dev(legs, gov, plan, mode, stride=1, max_open=2):
    b = book(legs, max_open=max_open)
    out = {}
    for sp, (a, z) in SPL.items():
        last = z if sp == "train" else LAST_DEV
        # train windows may run into val data (no holdout); val windows end inside dev
        s = score(b, gov, plan, a, z, "2024-12-31", mode, stride)
        for kk, v in s.items(): out[f"{sp}_{kk}"] = v
    return out
