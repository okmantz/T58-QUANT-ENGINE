"""Search Lab-style parameter search for the Ind Rule family on a chosen timeframe (hypothesis A1 / B1).

Random search (fixed seed) over the Ind Rule parameter family, scored through the REAL backtest engine. Every candidate's trade list is
stored so selection (train + validate only) and the locked-test read-out can be done afterwards without re-running the engine.

    python scripts/t58_ir_search.py --tf 5m --n 60 --seed 1 --data /path/futures_NQ.F_1m.parquet --out cache/ir_5m_seed1.pkl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import warnings; warnings.filterwarnings("ignore")
import bundle_research as br  # noqa: E402

BASE = ROOT / "strategies" / "python" / "NQ1! Ind Rule 15m.py"
TF_MIN = {"5m": 5, "15m": 15, "30m": 30}

GRID = {
    "period": [5, 7, 10, 14],
    "win": [150, 250, 400],
    "k": [1.5, 2.0, 2.5],
    "mode": ["trend"],
    "stop_atr": [2, 3, 4],
    "target_r": [0.5, 0.75, 1.0, 1.5],
    "hold_hours": [12, 30, 48],      # time limit in HOURS so the same setting means the same clock time on every timeframe
    "hours": ["afternoon", "all", "rth", "overnight", "us_open"],
    "trend": [0, 100, 200],
    "side": ["long"],
}


def render(params: dict, tf: str) -> str:
    src = BASE.read_text(encoding="utf-8")
    bars = int(round(params["hold_hours"] * 60 / TF_MIN[tf]))
    cfg = {"family": "ind_rule", "params": {"kind": "base_signal_expectancy", "period": params["period"], "win": params["win"], "k": params["k"], "mode": params["mode"]}}
    flt = {"side": params["side"], "trend": params["trend"], "hours": params["hours"]}
    src = re.sub(r'^TIMEFRAME = ".*"$', f'TIMEFRAME = "{tf}"', src, flags=re.M)
    src = re.sub(r"^CONFIG = .*$", "CONFIG = " + json.dumps(cfg).replace("true", "True"), src, flags=re.M)
    src = re.sub(r"^FILTERS = .*$", "FILTERS = " + json.dumps(flt), src, flags=re.M)
    src = re.sub(r"^STOP_ATR = .*$", f"STOP_ATR = {params['stop_atr']}", src, flags=re.M)
    src = re.sub(r"^TARGET_R = .*$", f"TARGET_R = {params['target_r']}", src, flags=re.M)
    src = re.sub(r"^HOLD_BARS = .*$", f"HOLD_BARS = {bars}", src, flags=re.M)
    src = re.sub(r"^WARMUP = .*$", f"WARMUP = {max(params['win'], 250)}", src, flags=re.M)
    return src


def run(params: dict, tf: str, df, inst: str = "NQ", workdir: Path = Path("/tmp/t58_variants")):
    workdir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5((json.dumps(params, sort_keys=True) + tf).encode()).hexdigest()[:10]
    p = workdir / f"ir_{tf}_{key}.py"
    p.write_text(render(params, tf), encoding="utf-8")
    return br.run_trades(p, inst, df)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", required=True); ap.add_argument("--n", type=int, default=60); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--data", required=True); ap.add_argument("--out", required=True); ap.add_argument("--inst", default="NQ")
    ap.add_argument("--include-base", action="store_true", help="also run the shipped parameters on this timeframe")
    a = ap.parse_args()
    from app.data.importer import import_csv
    df = import_csv(a.data).dataframe.reset_index(drop=True)
    rng = random.Random(a.seed)
    cands = []
    if a.include_base:
        cands.append({"period": 7, "win": 250, "k": 2.0, "mode": "trend", "stop_atr": 3, "target_r": 0.75, "hold_hours": 30, "hours": "afternoon", "trend": 200, "side": "long"})
    seen = {json.dumps(c, sort_keys=True) for c in cands}
    while len(cands) < a.n:
        c = {k: rng.choice(v) for k, v in GRID.items()}
        s = json.dumps(c, sort_keys=True)
        if s not in seen:
            seen.add(s); cands.append(c)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    res = pickle.load(out.open("rb")) if out.exists() else []
    done = {json.dumps(r["params"], sort_keys=True) for r in res}
    for i, c in enumerate(cands):
        if json.dumps(c, sort_keys=True) in done:
            continue
        t0 = time.time()
        try:
            tr = run(c, a.tf, df, a.inst)
        except Exception as e:  # noqa: BLE001
            print("skip", c, type(e).__name__, str(e)[:100], flush=True); continue
        res.append({"params": c, "tf": a.tf, "inst": a.inst, "trades": tr})
        pickle.dump(res, out.open("wb"))
        print(f"{i+1}/{len(cands)} {a.tf} n={len(tr)} {time.time()-t0:.1f}s {c}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
