"""Gate G2/G3 statistics for screen trials: DSR (N_eff over all trials), PBO per family x instrument (CSCV S=16), placebo p."""
import sys, pickle, json
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import data as D, screen, stats as S, factory as F

def load_daily():
    out = {}
    for p in screen.DAILY.glob("*.pkl"):
        out[p.stem] = pickle.load(p.open("rb"))
    return out

def dsr_table(ids):
    dl = load_daily()
    allsr, allR = [], []
    idx = {}
    for k, v in dl.items():
        R = v["R"]
        for j, i in enumerate(v["ids"]):
            idx[i] = (k, j)
        allsr += [S.sharpe(R[:, j]) for j in range(R.shape[1])]
    sr_var = float(np.var(allsr))
    # N_eff: within each family x instrument the trials are highly correlated; sum of per-group effective counts
    neff = sum(S.n_eff(v["R"]) for v in dl.values() if v["R"].shape[1] > 1) + sum(1 for v in dl.values() if v["R"].shape[1] == 1)
    rows = []
    for i in ids:
        k, j = idx[i]; x = dl[k]["R"][:, j]
        rows.append(dict(trial_id=i, group=k, sr_daily=S.sharpe(x), dsr=S.dsr(x, neff, sr_var)))
    return pd.DataFrame(rows), neff, len(allsr), sr_var

def pbo_table():
    rows = []
    for k, v in load_daily().items():
        R = v["R"]
        if R.shape[1] >= 4:
            rows.append(dict(group=k, n_trials=R.shape[1], n_eff=S.n_eff(R), pbo=S.pbo(R)))
    return pd.DataFrame(rows)
