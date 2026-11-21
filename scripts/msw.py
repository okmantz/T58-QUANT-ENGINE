import numpy as np, pandas as pd
D = pd.read_parquet("/home/user/work/daily_legs_dev.parquet")
keys = ["OD_NQ","IR_NQ","CDL_NQ","IRA_NQ","IRB_NQ","LSR_NQ","TM_NQ","ONB_NQ","OD_ES","CDL_ES","COB_ES","ONB_ES","ORBC_ES","IR_ES","IRA_ES"]
tr, va = D.loc["2020":"2023", keys], D.loc["2024", keys]
def msw(x, shrink=0.5, mshrink=0.5):
    S = x.cov().values; S = (1 - shrink) * S + shrink * np.diag(np.diag(S))
    m = x.mean().values; m = (1 - mshrink) * m + mshrink * m.mean()
    w = np.linalg.solve(S, m); w = np.clip(w, 0, None); return pd.Series(w / w.max() * 3, index=x.columns)
for sh, ms in [(0.5, 0.5), (0.8, 0.5), (0.5, 0.0)]:
    w = msw(tr, sh, ms)
    def shp(x): r = x @ w; return r.mean() / r.std() * np.sqrt(252), r.mean(), r.std()
    print(sh, ms, w.round(2).to_dict()); print("  train", np.round(shp(tr), 3), "val", np.round(shp(va), 3))
w0 = pd.Series(0.0, index=keys); w0[["OD_NQ","IR_NQ","CDL_NQ"]] = [1, 3, 1]
r = tr @ w0; rv = va @ w0
print("shipped A weights train sh", r.mean()/r.std()*np.sqrt(252), "val", rv.mean()/rv.std()*np.sqrt(252))
