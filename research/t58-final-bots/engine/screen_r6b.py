"""PREREG_R6 addendum 1: energy inventory-report breakout (CL Wed, NG Thu, range from 10:30 ET = energy mat column 1020)."""
import os, sys, csv, json, time
os.environ["T58_R6"] = "1"; sys.path.insert(0, "research/t58_final_bots/engine")
import numpy as np, pandas as pd
import data as D, factory as F, screen
from screen_r6 import LEDGER
WD = {"CL": 2, "NG": 3}
def fam_report(inst, k=15, stop="opp", R=2.0, cut=60, sealed=False):
    b = F.fam_orb(inst, k=k, stop=stop, R=R, cut=cut, start=1020, sealed=sealed)
    if b is None: return None
    m = pd.DatetimeIndex(b["day"]).dayofweek == WD[inst]
    b = {kk: v[m] for kk, v in b.items()}; b["leg"] = np.array([f"RPT{k}_{stop}_R{R}_c{cut}@{inst}"] * m.sum()); return b
if __name__ == "__main__":
    fh = LEDGER.open("a", newline=""); w = csv.DictWriter(fh, screen.COLS, extrasaction="ignore")
    for inst in D.ENERGY:
        f = F.feats(inst); days = f["M"]["days"]; spl = f["split"]; wd = pd.DatetimeIndex(days).dayofweek == WD[inst]
        dres, dval = days[(spl == "res") & f["ok"] & wd], days[(spl == "val") & f["ok"] & wd]
        for k in (5, 15):
            for st in ("opp", "mid"):
                for R in (1.5, 2.0, 3.0, np.nan):
                    for cut in (60, 180):
                        p = dict(k=k, stop=st, R=R, cut=cut); b = fam_report(inst, **p); i = screen.tid("F14_report", inst, p)
                        sp = np.where(b["day"] >= D.E_VAL_FROM, "val", "res")
                        for nm, mask, dd in (("res", sp == "res", dres), ("val", sp == "val", dval)):
                            s = screen.split_stats(b, mask, dd); s.pop("_dr", None)
                            w.writerow(dict(trial_id=i, ts=time.strftime("%Y-%m-%d %H:%M"), family="F14_report", inst=inst, params=json.dumps(p, default=str), name=b["leg"][0], split=nm, **s))
    fh.close(); print("done")
