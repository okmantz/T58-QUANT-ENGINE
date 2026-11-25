"""First-run setup inside the T58-QUANT-ENGINE repo. Round-4 scores (the default) need two session-matrix files per market
in T58_CACHE that this zip cannot ship (no market data):
  mat_<I>_full2.pkl  2020-01 .. 2026-11-20: repo data/raw files + Owen's Mar-Nov 2026 pack, put in research/t58_final_bots/data_holdout2/
                     (must match SEAL.sha256 there), then run engine/data_h2.py and engine/data_h2_ports.py.
  mat_<I>_full4.pkl  adds 2016-11-24 .. 2019-12-31: Owen's 2016-2021 pack in research/t58_final_bots/data_holdout3/ (must match
                     SEAL.sha256), then engine/data_h3.py and engine/data_h3_ports.py. Only needed for windows before 2020.
This builds mat_<I>_dev2.pkl (sessions before 2026-03-02, the round-3 dev set) from the repo's own data and stops with a clear
message if the round-4 files are missing."""
import os, pickle, numpy as np
import data as D

def ensure():
    D.CACHE.mkdir(parents=True, exist_ok=True)
    for inst in D.FILES:
        p = D.CACHE / f"mat_{inst}_dev2.pkl"
        if p.exists(): continue
        d = D._build(inst); keep = d["days"] < np.datetime64("2026-03-02")
        dev = {k: (v[keep] if isinstance(v, np.ndarray) and len(v) == len(d["days"]) else v) for k, v in d.items()}
        pickle.dump(dev, open(p, "wb"), protocol=4)
    if D.R4:
        miss = [i for i in D.FILES if not (D.CACHE / f"mat_{i}_full2.pkl").exists()]
        if miss:
            raise SystemExit("round-4 scores need mat_<I>_full2.pkl for " + ", ".join(miss) + ": see engine/repo_setup.py. "
                             "For the round-3 numbers run with T58_R3=1 and params_r3.json.")
