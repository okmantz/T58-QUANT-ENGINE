"""Round 4 data: Owen's 1-minute files for 2016-11-24 .. 2020-12-31 (data_holdout3/, sealed by SEAL.sha256 at 18:19Z / 18:21Z on
2026-11-24 before any price was read). Session days 2016-11-24 .. 2020-01-01 (before the first repo session, 2020-01-02) are the
round-4 final holdout H3. The rest of those files overlaps the repo data already used (2020) and is not used.

Builds, without printing a single return or trade statistic:
  cache/mat_<I>_full4.pkl = H3 days (from the new files, shifted onto the adjusted basis of the existing mats) + mat_<I>_full2
                            (sealed: only read by round-4 holdout scripts, after research/FROZEN_PICKS_R4.sha256 exists)
  cache/raw/<stem>__<I>__h3.pkl = repo-strategy trades entered in H3 (repo engine on new raw + repo raw, for warm-up), shifted.
Splice: new raw rows before the first repo bar + all repo raw rows; the repo importer back-adjusts the combined file. The repo part
then sits on the same basis as the old mats up to one constant, measured on the first 5 repo sessions (same raw bars in both).
Mini files (NQ, ES, GC) are used, as in rounds 1-3; micros trade the same price, so the MES and MNQ files are sealed but not used.
GC: the repo GC file starts 2020-08-02, so new GC rows up to then are spliced in for warm-up; only H3 days (< 2020-01-02) are kept.
Usage: python3 data_h3.py  -> integrity facts only (rows, sessions, full-RTH days, rolls found, offsets)."""
import sys, json, pickle
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).parent))
import data as D
H3_TO = np.datetime64("2020-01-02")
NEW = D.WORK / "data_holdout3"
NEWF = {"NQ": "NASDAQ100_futures_1m_2016-11-24_2021-01-01.parquet", "ES": "SP500_futures_1m_2016-11-24_2021-01-01.parquet",
        "GC": "GOLD_futures_1m_2016-11-24_2021-01-01.parquet"}
H3 = D.CACHE / "h3"; H3.mkdir(parents=True, exist_ok=True)
STEMS = {"NQ": ["OpenDrive_NQ_5m_v1", "IndRule_NQ_15m_v1", "ContextDriveLong_NQ_1m_v2"],
         "ES": ["OpenDrive_NQ_5m_v1", "ContextDriveLong_NQ_1m_v2", "CompressionORB_ES_5m_v1"], "GC": []}

def check_seal():
    lines = [l.split() for l in (NEW / "SEAL.sha256").read_text().splitlines() if l and not l.startswith("sealed")]
    for h, f in lines: assert D.sha(NEW / f) == h, f
    return len(lines)

def combined(inst):
    """New raw before the first repo bar, then the round-3 combined file (repo raw + H2 pack) so the series ends where full2 ends."""
    out = H3 / f"{inst}_combined.parquet"
    if out.exists(): return out
    later = pq.read_table(D.CACHE / "h2" / f"{inst}_combined.parquet").to_pandas()
    first = later.ts.min()
    new = pq.read_table(NEW / NEWF[inst]).to_pandas().rename(columns={"time": "ts"}).drop(columns=["trades"])
    new["ts"] = new["ts"].astype(later["ts"].dtype); new["symbol"] = f"{inst}1!"
    new = new[new.ts < first]
    df = pd.concat([new[later.columns], later], ignore_index=True).sort_values("ts").drop_duplicates("ts")
    df.to_parquet(out, index=False)
    return out

if __name__ == "__main__":
    import data_h2
    print("seal ok, files:", check_seal())
    info = {}
    for inst in ("NQ", "ES", "GC"):
        full2 = pickle.load(open(D.CACHE / f"mat_{inst}_full2.pkl", "rb"))
        p = combined(inst); m, rolls = data_h2.mats_from(p, inst)
        first = full2["days"][:5]; ia = np.arange(5); ib = np.searchsorted(m["days"], first)
        assert (m["days"][ib] == first).all()
        diff = (full2["C"][ia] - m["C"][ib])[:, D.RTH0:D.RTH1].ravel(); off = float(np.median(diff)); spread = float(np.ptp(diff))
        h = m["days"] < H3_TO
        new = {k: (v[h] if isinstance(v, np.ndarray) and len(v) == len(m["days"]) else v) for k, v in m.items()}
        for k in ("O", "H", "L", "C"): new[k] = new[k] + off
        full4 = {k: (np.concatenate([new[k], full2[k]]) if isinstance(full2[k], np.ndarray) and len(full2[k]) == len(full2["days"]) else full2[k])
                 for k in full2}
        assert np.all(np.diff(full4["days"].astype("int64")) > 0)
        pickle.dump(full4, open(D.CACHE / f"mat_{inst}_full4.pkl", "wb"), protocol=4)
        import book
        ntr = {}
        for stem in STEMS[inst]:
            rows = book.gen(stem, inst, tag=f"{stem}__cmb4", src=None, datafile=str(p))
            keep = []
            for r in rows:
                sd, _ = book._sess([r["entry"]])
                if sd[0] < H3_TO:
                    r = dict(r); r.update(ep=r["ep"] + off, xp=r["xp"] + off, worst=r["worst"] + off); keep.append(r)
            pickle.dump(keep, open(D.CACHE / "raw" / f"{stem}__{inst}__h3.pkl", "wb")); ntr[stem] = len(keep)
        info[inst] = dict(h3_days=int(h.sum()), h3_first=str(new["days"][0]), h3_last=str(new["days"][-1]),
                          h3_full_days=int(new["full"].sum()), full2_first=str(full2["days"][0]), offset=off, offset_spread=spread,
                          roll_note=str(rolls)[:600], h3_trade_rows=ntr)
    json.dump(info, open(D.WORK / "research/data_h3_info.json", "w"), indent=1, default=str)
    print(json.dumps(info, indent=1, default=str))
