"""Round 3 data: Owen's 1-minute pack for 2026-03-01 .. 2026-11-20 (data_holdout2/, sealed by SEAL.sha256) becomes the new final
holdout H2 (session days >= 2026-03-02). The round-1/2 holdout window (2025-09-01 .. 2026-03-01) joins validation.

Builds, without printing a single return or trade statistic:
  cache/mat_<I>_dev2.pkl   = round-1/2 full mats, session days < 2026-03-02 (values identical to before)
  cache/mat_<I>_full2.pkl  = dev2 + H2 days from the new files (sealed: only read by round-3 holdout scripts)
  cache/raw/<stem>__<I>__h2.pkl = repo-strategy trades in H2 (repo engine on old raw < 2026-03-01 18:00 ET + new raw, for warm-up)
Splice: old raw rows before Sun 2026-03-01 18:00 ET + new rows; the repo importer back-adjusts the combined file; H2 prices are then
shifted by one constant per instrument so they sit on the same adjusted basis as the old mats (offset measured on the last 5 old
sessions, where both series hold the same bars). Mini files (NQ, ES, GC) are used, as in rounds 1-2; micros trade the same price.
Usage: python3 data_h2.py  -> prints integrity facts only (row counts, roll dates found, offsets, sessions)."""
import sys, json, pickle, hashlib
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).parent))
import data as D
H2_FROM = np.datetime64("2026-03-02")
NEW = D.WORK / "data_holdout2"
NEWF = {"NQ": "NASDAQ100_futures_1m_2026-03-01_2026-11-24.parquet", "ES": "SP500_futures_1m_2026-03-01_2026-11-24.parquet",
        "GC": "GOLD_futures_1m_2026-03-01_2026-11-24.parquet"}
CUT = pd.Timestamp("2026-03-01 23:00", tz="UTC")          # Sun 18:00 ET: first bar of session day 2026-03-02
H2 = D.CACHE / "h2"; H2.mkdir(parents=True, exist_ok=True)
STEMS = {"NQ": ["OpenDrive_NQ_5m_v1", "IndRule_NQ_15m_v1", "ContextDriveLong_NQ_1m_v2"],
         "ES": ["OpenDrive_NQ_5m_v1", "ContextDriveLong_NQ_1m_v2", "CompressionORB_ES_5m_v1"], "GC": []}

def check_seal():
    lines = [l.split() for l in (NEW / "SEAL.sha256").read_text().splitlines() if l and not l.startswith("sealed")]
    for h, f in lines: assert D.sha(NEW / f) == h, f
    return len(lines)

def combined(inst):
    out = H2 / f"{inst}_combined.parquet"
    if out.exists(): return out
    old = pq.read_table(D.REPO / D.FILES[inst]).to_pandas()
    old = old[old.ts < CUT]
    new = pq.read_table(NEW / NEWF[inst]).to_pandas().rename(columns={"time": "ts"}).drop(columns=["trades"])
    new["ts"] = new["ts"].astype(old["ts"].dtype); new["symbol"] = f"{inst}1!"
    df = pd.concat([old, new[old.columns]], ignore_index=True).sort_values("ts").drop_duplicates("ts")
    df.to_parquet(out, index=False)
    return out

def mats_from(path, inst):
    """Same construction as data._build, on another file."""
    sys.path.insert(0, str(D.REPO))
    from app.data.importer import import_csv
    res = import_csv(str(path)); df = res.dataframe
    keep_files = D.FILES[inst]
    D.FILES[inst] = str(path)                                   # data._build reads D.REPO / D.FILES[inst]; an absolute path wins
    try: m = D._build(inst)
    finally: D.FILES[inst] = keep_files
    rolls = df.attrs.get("roll_adjustment", "")
    return m, rolls

if __name__ == "__main__":
    print("seal ok, files:", check_seal())
    info = {}
    for inst in ("NQ", "ES", "GC"):
        old = pickle.load(open(D.CACHE / f"mat_{inst}_full.pkl", "rb"))
        dev2 = {k: (v[old["days"] < H2_FROM] if isinstance(v, np.ndarray) and len(v) == len(old["days"]) else v) for k, v in old.items()}
        pickle.dump(dev2, open(D.CACHE / f"mat_{inst}_dev2.pkl", "wb"), protocol=4)
        p = combined(inst); m, rolls = mats_from(p, inst)
        # offset on the last 5 old sessions present in both (same raw bars): old_adj - combined_adj
        last = dev2["days"][-5:]; ia = np.searchsorted(dev2["days"], last); ib = np.searchsorted(m["days"], last)
        assert (m["days"][ib] == last).all()
        diff = (dev2["C"][ia] - m["C"][ib])[:, D.RTH0:D.RTH1].ravel(); off = float(np.median(diff)); spread = float(np.ptp(diff))
        h = m["days"] >= H2_FROM
        new = {k: (v[h] if isinstance(v, np.ndarray) and len(v) == len(m["days"]) else v) for k, v in m.items()}
        for k in ("O", "H", "L", "C"): new[k] = new[k] + off
        full2 = {k: (np.concatenate([dev2[k], new[k]]) if isinstance(dev2[k], np.ndarray) and len(dev2[k]) == len(dev2["days"]) else dev2[k])
                 for k in dev2}
        pickle.dump(full2, open(D.CACHE / f"mat_{inst}_full2.pkl", "wb"), protocol=4)
        # repo-strategy trades over the combined file; keep H2 entries only, shifted onto the old basis
        import book
        ntr = {}
        for stem in STEMS[inst]:
            tag = f"{stem}__cmb"
            rows = book.gen(stem, inst, tag=tag, src=None, datafile=str(p))
            keep = []
            for r in rows:
                sd, _ = book._sess([r["entry"]])
                if sd[0] >= H2_FROM:
                    r = dict(r); r.update(ep=r["ep"] + off, xp=r["xp"] + off, worst=r["worst"] + off); keep.append(r)
            pickle.dump(keep, open(D.CACHE / "raw" / f"{stem}__{inst}__h2.pkl", "wb")); ntr[stem] = len(keep)
        info[inst] = dict(dev2_days=int(len(dev2["days"])), dev2_last=str(dev2["days"][-1]), h2_days=int(h.sum()),
                          h2_first=str(new["days"][0]) if h.any() else None, h2_last=str(new["days"][-1]) if h.any() else None,
                          h2_full_days=int(new["full"].sum()), offset=off, offset_spread=spread, roll_note=str(rolls)[:400],
                          h2_trade_rows=ntr)
    json.dump(info, open(D.WORK / "research/data_h2_info.json", "w"), indent=1, default=str)
    print(json.dumps(info, indent=1, default=str))
