import numpy as np, pandas as pd, sim, lib
pd.set_option("display.width", 250)
days = {}
for k in lib.LIB:
    d = sim.leg(k)
    ct = pd.DatetimeIndex(d.entry).tz_localize("UTC").tz_convert("America/Chicago").tz_localize(None)
    days[k] = pd.Series(d.pnl.values / 500, index=(ct + pd.Timedelta(hours=7)).normalize()).groupby(level=0).sum()
cal = pd.bdate_range("2020-01-02", "2024-12-31")
D = pd.DataFrame(days).reindex(cal).fillna(0)
for sp, (a, z) in [("train", ("2020", "2023")), ("val", ("2024", "2024"))]:
    x = D.loc[a:z]
    s = pd.DataFrame({"mean": x.mean(), "sd": x.std(), "sh_ann": x.mean() / x.std() * np.sqrt(252)})
    print(sp); print(s.round(3).T.to_string())
print(D.loc["2020":"2023"].corr().round(2).to_string())
D.to_parquet("/home/user/work/daily_legs_dev.parquet")
