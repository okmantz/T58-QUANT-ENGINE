"""AQR-style trend ensemble (1/3/12-month sign, equal weight) as a regime filter on intraday trades. Dev data only."""
import numpy as np, pandas as pd, sim, lib
def daily(sym):
    b = pd.read_parquet(f"/home/claude/t58-quant-engine/data/raw/{sym}1!/futures_{sym}.F_1m.parquet", columns=["ts", "close"])
    b = b[b.ts < pd.Timestamp("2025-01-01", tz="UTC")]
    ct = pd.DatetimeIndex(b.ts).tz_convert("America/Chicago")
    m = ct.hour * 60 + ct.minute
    x = pd.Series(b.close.values, index=ct.tz_localize(None))[(m <= 15 * 60) & (m >= 8 * 60 + 30)]
    d = x.groupby(x.index.normalize()).last(); return d[d.index.dayofweek < 5]
SIG = {}
for s in ("ES", "NQ"):
    c = daily(s)
    sg = sum(np.sign(c / c.shift(n) - 1) for n in (21, 63, 252)) / 3.0
    SIG[s] = sg.shift(1)            # known before today's session
def tag(d):
    inst = d.inst.iloc[0]
    ct = pd.DatetimeIndex(d.entry).tz_localize("UTC").tz_convert("America/Chicago").tz_localize(None)
    day = (ct + pd.Timedelta(hours=7)).normalize()
    s = SIG[inst].reindex(day).values
    return np.asarray(d["dir"]) * s
if __name__ == "__main__":
    rows = []
    for k in lib.LIB:
        d = sim.leg(k); a = tag(d)
        for sp, (lo, hi) in [("train", ("2021-01-01", "2024-01-01")), ("val", ("2024-01-01", "2025-01-01"))]:
            m = (d.entry >= lo) & (d.entry < hi) & np.isfinite(a)
            R = d.pnl.values / 500
            ag, dis = m & (a > 0), m & (a < 0)
            rows.append(dict(leg=k, sp=sp, n_ag=int(ag.sum()), R_ag=round(R[ag].mean(), 3), n_dis=int(dis.sum()), R_dis=round(R[dis].mean(), 3),
                             strong_ag=round(R[m & (a > 0.9)].mean(), 3), strong_dis=round(R[m & (a < -0.9)].mean(), 3)))
    df = pd.DataFrame(rows); pd.set_option("display.width", 200); print(df.to_string())
    df.to_csv("/mnt/project-files/t58-new-bots/results/tsmom_filter_dev.csv", index=False)
