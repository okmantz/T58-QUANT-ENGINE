"""Lifecycle per attempt: evaluation with bot E (book, governor, plan) -> funded with bot F from the next trading day.
Counts payouts (x0.9 split) collected within H days of purchase; EV = mean(payouts) - fee. One attempt = one fee (no resets)."""
import numpy as np, pandas as pd, acct, sim
def lifecycle(bE, gE, bF, gF, plan, a, z, last, H=60, fee=None, stride=1, split=0.9):
    trE, trF = acct.arrays(bE), acct.arrays(bF); r = sim.PLANS[plan]()
    st = sim.starts_in(trE, a, z, H, last)[::stride]
    res = []
    for s in st:
        o = acct.run(trE, s, min(H, 60), r, sim.policy(gE, plan, trE["w"]), phase="eval")
        if o["pass_day"] is None:
            res.append((None, None, 0.0, o["breach_day"] is not None)); continue
        pdays = o["pass_day"]; fs = np.datetime64(s) + np.timedelta64(pdays + 1, "D")
        rem = H - pdays - 1
        if rem <= 0: res.append((pdays, None, 0.0, False)); continue
        f = acct.run(trF, fs, rem, r, sim.policy(gF, plan, trF["w"]), phase="funded")
        pays = f["payouts"]
        first = pdays + 1 + pays[0][0] if pays else None
        res.append((pdays, first, split * sum(x[1] for x in pays), f["breach_day"] is not None))
    n = len(res); fee = sim.FEE[plan] if fee is None else fee
    pay = np.array([x[2] for x in res])
    k30 = sum(1 for x in res if x[1] is not None and x[1] <= 30)
    kH = sum(1 for x in res if x[1] is not None)
    return dict(n=n, pass30=100 * sum(1 for x in res if x[0] is not None and x[0] <= 30) / n, paid30=100 * k30 / n, paidH=100 * kH / n,
                mean_paid=pay.mean(), ev=pay.mean() - fee, ev_per_fee=(pay.mean() - fee) / fee, pay_if_paid=pay[pay > 0].mean() if (pay > 0).any() else 0.0)
