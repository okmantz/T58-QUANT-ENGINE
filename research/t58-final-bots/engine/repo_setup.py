"""First-run setup inside the T58-QUANT-ENGINE repo: builds the session matrices the engine reads (mat_<I>_dev2.pkl = every session
before 2026-03-02) from the repo's own data/raw files. The Mar-Nov 2026 holdout (mat_<I>_full2.pkl) is NOT rebuilt here: put Owen's three
2026-03-01..2026-11-24 parquet files in research/t58_final_bots/data_holdout2/ (they must match SEAL.sha256 there) and run
engine/data_h2.py to rebuild it."""
import pickle, numpy as np
import data as D

def ensure():
    D.CACHE.mkdir(parents=True, exist_ok=True)
    for inst in D.FILES:
        p = D.CACHE / f"mat_{inst}_dev2.pkl"
        if p.exists(): continue
        d = D._build(inst); keep = d["days"] < np.datetime64("2026-03-02")
        dev = {k: (v[keep] if isinstance(v, np.ndarray) and len(v) == len(d["days"]) else v) for k, v in d.items()}
        pickle.dump(dev, open(p, "wb"), protocol=4)
