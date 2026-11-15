"""Cross-market data as COLUMNS on the primary frame (audit G-F1..G-F4, section 4.1 of the coverage design).

Companion instruments (a benchmark, a leader, gold, a spread partner ...) used to travel in ``DataFrame.attrs``. That crashed pandas'
attrs comparison (G-F1), was invisible to every cache key (G-F3: ES + NQ got served ES + GC values), was never attached by any search or
discovery path (G-F2) and looked ahead whenever the companion bars are coarser than the primary's (G-F4).

Here a companion is aligned ONCE, causally, into ``x_<SYM>_<field>`` columns:

    decision time  = the primary bar's CLOSE time  (stamp + primary bar)
    companion value = the latest companion bar whose CLOSE time (stamp + companion bar) <= decision time

so a 1-minute bar never sees a 5-minute bar that has not closed yet. A companion bar older than ``tolerance_bars`` companion bars is
NaN (a halt must not be forward-filled into a stale value). Columns are hashed by every cache that hashes columns; the frame also carries
two scalar attrs (``companions``, ``ctx_digest``) that the fingerprints include.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

FIELDS = ("open", "high", "low", "close", "volume")
PREFIX = "x_"


def infer_bar(ts: pd.Series | pd.DatetimeIndex) -> pd.Timedelta:
    """Bar length: the median spacing of the stamps (robust to weekend / maintenance gaps). One minute when it cannot be told."""
    t = pd.to_datetime(pd.Series(ts)).dropna().drop_duplicates().sort_values()
    if len(t) < 3:
        return pd.Timedelta(minutes=1)
    d = t.diff().dropna()
    med = d.median()
    return med if med > pd.Timedelta(0) else pd.Timedelta(minutes=1)


def align_companion(primary_ts, comp_ts, comp_values, primary_bar: pd.Timedelta, comp_bar: pd.Timedelta,
                    tolerance: pd.Timedelta | None = None, index=None) -> pd.Series:
    """Causal alignment of a companion series onto the primary bars (see module docstring). Returns a float Series on ``index``."""
    p = pd.to_datetime(pd.Series(primary_ts)).reset_index(drop=True)
    left = pd.DataFrame({"t": p.to_numpy() + primary_bar.to_timedelta64(), "i": np.arange(len(p))}).sort_values("t")
    c = pd.to_datetime(pd.Series(comp_ts)).reset_index(drop=True)
    right = pd.DataFrame({"t": c.to_numpy() + comp_bar.to_timedelta64(), "v": pd.to_numeric(pd.Series(comp_values), errors="coerce").to_numpy(dtype=float)})
    right = right.dropna(subset=["t"]).sort_values("t")
    m = pd.merge_asof(left, right, on="t", direction="backward", tolerance=tolerance)
    out = m.sort_values("i")["v"].to_numpy(dtype=float)
    return pd.Series(out, index=index if index is not None else getattr(primary_ts, "index", None))


def asof_close(primary: pd.DataFrame, other: pd.DataFrame, col: str = "close") -> pd.Series:
    """``other[col]`` as known at each ``primary`` bar's close (no tolerance). Used by the legacy attrs readers."""
    if other is None or len(other) == 0 or col not in other.columns:
        return pd.Series(np.nan, index=primary.index)
    pts = primary["timestamp"] if "timestamp" in primary.columns else pd.Series(primary.index, index=primary.index)
    ots = other["timestamp"] if "timestamp" in other.columns else pd.Series(other.index)
    return align_companion(pts, ots, other[col], infer_bar(pts), infer_bar(ots), None, index=primary.index)


def _digest(frames: dict[str, pd.DataFrame]) -> str:
    h = hashlib.sha1()
    for sym in sorted(frames):
        f = frames[sym]
        h.update(str(sym).encode())
        h.update(f"{len(f)}".encode())
        if len(f):
            ts = pd.to_datetime(f["timestamp"])
            h.update(f"{ts.iloc[0]}|{ts.iloc[-1]}".encode())
            h.update(np.round(pd.to_numeric(f["close"], errors="coerce").to_numpy(dtype=float)[:: max(1, len(f) // 512)], 6).tobytes())
    return h.hexdigest()[:16]


def attach_companions(primary: pd.DataFrame, companions: dict[str, pd.DataFrame], *, fields=FIELDS, tolerance_bars: int = 3) -> pd.DataFrame:
    """A COPY of ``primary`` with ``x_<SYM>_<field>`` columns for every companion (causal alignment, NaN where there is no fresh bar)."""
    out = primary.copy()
    out.attrs = {k: v for k, v in primary.attrs.items() if not isinstance(v, (pd.DataFrame, pd.Series, dict, list, tuple, set))}
    pbar = infer_bar(out["timestamp"])
    used: dict[str, pd.DataFrame] = {}
    for sym, cf in (companions or {}).items():
        if cf is None or len(cf) == 0 or "timestamp" not in cf.columns:
            continue
        cf = cf.sort_values("timestamp")
        cbar = infer_bar(cf["timestamp"])
        tol = cbar * max(1, int(tolerance_bars))
        for fld in fields:
            if fld in cf.columns:
                out[f"{PREFIX}{sym}_{fld}"] = align_companion(out["timestamp"], cf["timestamp"], cf[fld], pbar, cbar, tol, index=out.index)
        used[str(sym)] = cf
    if used:
        out.attrs["companions"] = ",".join(sorted(used))
        out.attrs["ctx_digest"] = _digest(used)
    return out


def companion_symbols(frame: pd.DataFrame) -> list[str]:
    return [s for s in str((getattr(frame, "attrs", {}) or {}).get("companions", "")).split(",") if s]


def companion_series(frame: pd.DataFrame, sym: str, field: str = "close") -> pd.Series | None:
    col = f"{PREFIX}{sym}_{field}"
    return frame[col] if col in frame.columns else None


def slice_companions(frame: pd.DataFrame, part: pd.DataFrame) -> pd.DataFrame:
    """``part`` (a time slice of ``frame``) keeps the companion columns it already has; carry the scalar attrs across."""
    for k in ("companions", "ctx_digest"):
        if k in frame.attrs:
            part.attrs[k] = frame.attrs[k]
    return part
