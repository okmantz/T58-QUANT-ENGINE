"""Market data for the final-bots research (T58 final bots, 2026-11-23).

Source: the repo's 1-minute continuous futures (ES, NQ, GC), loaded through the repo's own importer (app.data.importer.import_csv),
which back-adjusts at rolls (adj_offset) and stamps exchange time. Points differences inside a session are unchanged by the
adjustment; multi-day indicators use the adjusted series (Spec 6.1: back-adjusted only for indicator continuity).

Session day (Spec 2.5 [ASM]): 18:00 ET of the prior calendar day to 16:45 ET (Lucid flat time). Minute index m = minutes since 18:00 ET
of the prior day, 0..1364. RTH 09:30 = 930, 16:00 = 1320, 16:45 = 1365 (exclusive). Saturdays/Sundays never form a session day.

SPLITS (chronological, ~60/25/15 over 2020-01 .. 2026-09):
  research   2020-01-01 .. 2023-12-31
  validation 2024-01-01 .. 2025-08-31
  holdout    2025-09-01 .. end of data (ES to 2026-09-01, NQ to 2026-03-01, GC to 2026-07-31)  -- SEALED.
Mats built here keep the holdout days in a separate file; research code calls load(..., sealed=False) which never returns them.
"""
from __future__ import annotations
import sys, hashlib, pickle
from pathlib import Path
import numpy as np, pandas as pd

REPO = Path(__import__("os").environ.get("T58_REPO", "."))
CACHE = Path(__import__("os").environ.get("T58_CACHE", "research/t58_final_bots/.cache"))
WORK = Path("research/t58_final_bots")
import os
R5 = os.environ.get("T58_R5") == "1"      # round 5: dev = 2016-11-24 .. 2026-11-20 (H3 read once in round 4, now dev); holdout H4 = Owen's
                                          # pre-2016-11-24 pack if he sends it (session days < 2016-11-24), sealed in data_holdout4/SEAL.sha256
R4 = os.environ.get("T58_R4") == "1" or R5      # round 4: dev = 2020-01 .. 2026-11-20 (H2 unsealed, read once in round 3); holdout H3 = Owen's
                                          # 2016-11-24 .. 2020-01-01 pack (session days < 2020-01-02), sealed in data_holdout3/SEAL.sha256
R3 = os.environ.get("T58_R3") == "1" or R4      # round 3: validation runs to 2026-03-01, holdout H2 = Owen's 2026-03-02 .. 2026-11-20 pack
H2_FROM = np.datetime64("2026-03-02")
H3_TO = np.datetime64("2020-01-02")
H4_TO = np.datetime64("2016-11-24")
HOLD_FROM = np.datetime64("2026-11-21") if R4 else (H2_FROM if R3 else np.datetime64("2025-09-01"))   # R4: nothing in dev is dropped
VAL_FROM = np.datetime64("2024-01-01")
FILES = {"NQ": "data/raw/NQ1!/futures_NQ.F_1m.parquet", "ES": "data/raw/ES1!/futures_ES.F_1m.parquet", "GC": "data/raw/GC1!/futures_GC.F_1m.parquet"}
NMIN = 1365
RTH0, RTH1, FLAT = 930, 1320, 1365

# contract specs (Spec 4.1) and costs (Spec 2.3). Mini first, micro second.
PV = {"ES": 50.0, "NQ": 20.0, "GC": 100.0}          # $/point, mini
TICK = {"ES": 0.25, "NQ": 0.25, "GC": 0.10}
MICRO_PV = {k: v / 10 for k, v in PV.items()}
COMM = {"base": {"ES": 3.50, "NQ": 3.50, "GC": 4.60, "MES": 1.00, "MNQ": 1.00, "MGC": 1.60},
        "stress": {"ES": 4.78, "NQ": 4.78, "GC": 5.22, "MES": 1.32, "MNQ": 1.32, "MGC": 1.82}}
SLIP_TICKS = {"base": 1.0, "stress": 1.5}            # per side, market/stop orders; stress = 1.5x (Owen's prompt; methodology 6.9 also runs 2x)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def _build(inst):
    sys.path.insert(0, str(REPO))
    from app.data.importer import import_csv
    df = import_csv(str(REPO / FILES[inst])).dataframe
    ts = pd.DatetimeIndex(pd.to_datetime(df["timestamp"], utc=True)).tz_convert("America/New_York")
    mod = ts.hour * 60 + ts.minute
    m = (mod - 1080) % 1440
    cal = ts.tz_localize(None).normalize()
    sday = np.where(mod >= 1080, cal + pd.Timedelta(days=1), cal)
    sday = pd.DatetimeIndex(sday)
    keep = (m < NMIN) & (sday.dayofweek < 5)
    sday, m = sday[keep], np.asarray(m)[keep]
    o, h, l, c, v = (df[k].to_numpy(float)[keep] for k in ("open", "high", "low", "close", "volume"))
    days, di = np.unique(sday.values.astype("datetime64[D]"), return_inverse=True)
    nd = len(days)
    O = np.full((nd, NMIN), np.nan); H = O.copy(); L = O.copy(); C = O.copy(); V = np.zeros((nd, NMIN))
    O[di, m] = o; H[di, m] = h; L[di, m] = l; C[di, m] = c; V[di, m] = v
    # count real bars in RTH before filling; days with <80% RTH bars are flagged (holidays / early closes / gaps)
    rth_bars = np.isfinite(C[:, RTH0:RTH1]).sum(1)
    # fill gaps: flat bar at the previous close (first bars of a day: next real open)
    for A in (C,):
        pass
    Cf = pd.DataFrame(C).ffill(axis=1).bfill(axis=1).to_numpy()
    miss = ~np.isfinite(O)
    O[miss] = Cf[miss]; H[miss] = Cf[miss]; L[miss] = Cf[miss]; C = np.where(np.isfinite(C), C, Cf)
    last_real = np.array([np.flatnonzero(np.isfinite(r))[-1] if np.isfinite(r).any() else -1 for r in np.where(miss, np.nan, 1.0)])
    full = rth_bars >= 0.8 * (RTH1 - RTH0)
    return dict(inst=inst, days=days, O=O, H=H, L=L, C=C, V=V, full=full, rth_bars=rth_bars, last_real=last_real)


def build_all():
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    for inst in FILES:
        d = _build(inst)
        hold = d["days"] >= HOLD_FROM
        dev = {k: (v[~hold] if isinstance(v, np.ndarray) and len(v) == len(d["days"]) else v) for k, v in d.items()}
        pickle.dump(dev, open(CACHE / f"mat_{inst}_dev.pkl", "wb"), protocol=4)
        pickle.dump(d, open(CACHE / f"mat_{inst}_full.pkl", "wb"), protocol=4)   # sealed: only holdout scripts read this
        out[inst] = dict(dev_days=int((~hold).sum()), hold_days=int(hold.sum()), first=str(d["days"][0]), last=str(d["days"][-1]),
                         sha_raw=sha(REPO / FILES[inst]))
    return out


def load(inst, sealed=False):
    """sealed=False (research/validation): days < 2025-09-01 only. sealed=True is for the single holdout read (code/holdout.py)."""
    if R5:
        p = CACHE / f"mat_{inst}_{'full5' if sealed else 'full4'}.pkl"
        if sealed:
            assert (WORK / "research/FROZEN_PICKS_R5.sha256").exists(), "H4 is sealed until research/FROZEN_PICKS_R5.md is written and hashed"
        return pickle.load(open(p, "rb"))
    if R4:
        p = CACHE / f"mat_{inst}_{'full4' if sealed else 'full2'}.pkl"
        if sealed:
            assert (WORK / "research/FROZEN_PICKS_R4.sha256").exists(), "H3 is sealed until research/FROZEN_PICKS_R4.md is written and hashed"
        return pickle.load(open(p, "rb"))
    if R3:
        p = CACHE / f"mat_{inst}_{'full2' if sealed else 'dev2'}.pkl"
        if sealed:
            assert (WORK / "research/FROZEN_PICKS_R3.sha256").exists(), "H2 is sealed until research/FROZEN_PICKS_R3.md is written and hashed"
        return pickle.load(open(p, "rb"))
    p = CACHE / f"mat_{inst}_{'full' if sealed else 'dev'}.pkl"
    if sealed:
        assert (WORK / "research/FROZEN_PICKS.sha256").exists(), "holdout is sealed until research/FROZEN_PICKS.md is written and hashed"
    return pickle.load(open(p, "rb"))


def split_of(days):
    d = np.asarray(days).astype("datetime64[D]")
    if R5:
        return np.where(d < H4_TO, "hold", np.where(d < H3_TO, "h3", np.where(d >= VAL_FROM, "val", "res")))
    if R4:
        return np.where(d < H3_TO, "hold", np.where(d >= VAL_FROM, "val", "res"))
    return np.where(d >= HOLD_FROM, "hold", np.where(d >= VAL_FROM, "val", "res"))


if __name__ == "__main__":
    import json
    print(json.dumps(build_all(), indent=1))
