#!/usr/bin/env python3
"""Objective study, step 1: run EVERY library strategy (and the recently deleted ones, recovered from git history) through the bar engine.

    python scripts/run_objective_study.py trades --cache /path/to/cache --deleted /path/to/recovered_files [--workers 2] [--only STEM ...]

Writes ``<cache>/trades/{stem}__{NQ|ES|GC}.pkl`` (one list of trade dicts per strategy and instrument, 1x prop sizing, costs and slippage from the
bar engine: ``scripts/bundle_research.run_trades``) plus ``<cache>/trades/_manifest.json`` with trade counts and wall time. Resumable: a pickle that
already exists is skipped. Strategies are run on every instrument so a "works only on NQ" claim is a measurement, not an assumption.

The later steps (``scripts/run_objective_study_scores.py``) read this cache and score every strategy and every combination under the three objectives.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import pickle
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
warnings.filterwarnings("ignore")

INSTRUMENTS = ("NQ", "ES", "GC")
# recovered from git history (strategies the repo deleted in 2026-11): file name -> the stem they are reported under
DELETED = {
    "NQ1! Context Aligned Drive 1m v2.py": "ContextDrive_NQ_1m_v2",
    "MNQ1! Gap Aligned Drive RW Tight Stop 1m.py": "GapAlignedDriveRWTight_NQ_1m_v1",
    "NQ1! Liquidity Sweep Reclaim 5m.py": "LiquiditySweepReclaim_NQ_5m_v1",
    "T58 Ninja Turtle Scalper EA.mq5": "NinjaTurtleScalper_ESNQ_5m_v1",
    "T58 Fisherman EA.mq5": "Fisherman_ESNQ_5m_v1",
    "T58 Turnaround Tuesday EA.mq5": "TurnaroundTuesday_ESNQ_5m_v1",
    "T58 ATR Candle Breakout EA.mq5": "ATRCandleBreakout_ESNQ_5m_v1",
}
SKIP_LIBRARY = ("Gate27_",)      # multi-market daily baskets are scored by scripts/run_gate27_study.py


def jobs(deleted_dir: Path | None) -> list[tuple[str, Path]]:
    out = []
    for f in sorted(list((ROOT / "strategies").glob("*/*.py")) + list((ROOT / "strategies").glob("*/*.mq5")) + list((ROOT / "strategies").glob("*/*.pine"))):
        if f.stem.startswith(SKIP_LIBRARY):
            continue
        out.append((f.stem, f))
    if deleted_dir is not None:
        for fn, stem in DELETED.items():
            p = deleted_dir / fn
            if p.exists():
                out.append((stem, p))
    return out


_FRAMES: dict = {}


def _frame(inst: str):
    if inst not in _FRAMES:
        import bundle_research as br
        from app.data.importer import import_csv
        _FRAMES[inst] = import_csv(str(ROOT / br.DATA[inst])).dataframe.reset_index(drop=True)
    return _FRAMES[inst]


def _work(task):
    stem, path, inst, out = task
    key = Path(out) / f"{stem}__{inst}.pkl"
    if key.exists():
        return stem, inst, "cached", None, 0.0
    import bundle_research as br
    t0 = time.time()
    try:
        tr = br.run_trades(Path(path), inst, _frame(inst))
    except Exception as e:  # noqa: BLE001
        return stem, inst, f"error: {type(e).__name__}: {str(e)[:160]}", None, time.time() - t0
    pickle.dump(tr, key.open("wb"))
    return stem, inst, "ok", br.trade_stats(tr), time.time() - t0


def cmd_trades(a) -> int:
    out = Path(a.cache) / "trades"
    out.mkdir(parents=True, exist_ok=True)
    js = [(s, p) for s, p in jobs(Path(a.deleted) if a.deleted else None) if not a.only or s in a.only]
    tasks = [(s, str(p), i, str(out)) for s, p in js for i in INSTRUMENTS]
    man_path = out / "_manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {}
    print(f"{len(tasks)} runs ({len(js)} strategies x {len(INSTRUMENTS)} instruments), {a.workers} workers", flush=True)
    with mp.get_context("spawn").Pool(a.workers) as pool:
        for stem, inst, status, stats, secs in pool.imap_unordered(_work, tasks):
            if status != "cached":
                man[f"{stem}__{inst}"] = {"status": status, "stats": stats, "seconds": round(secs, 1)}
                man_path.write_text(json.dumps(man, indent=1, default=str))
            print(f"{stem:42s} {inst}  {status:10s} {secs:6.0f}s  {stats if stats else ''}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trades")
    t.add_argument("--cache", required=True)
    t.add_argument("--deleted", default="")
    t.add_argument("--workers", type=int, default=2)
    t.add_argument("--only", nargs="*", default=[])
    t.set_defaults(fn=cmd_trades)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
