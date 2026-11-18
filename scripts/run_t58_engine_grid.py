#!/usr/bin/env python
"""Engine-in-the-loop weight grids behind the shipped bot books (see docs/T58_HYPOTHESIS_REPORT.md, section 6).

The research lab scores trade lists; the bot engine trades WHOLE contracts, so a 0.5x leg with a 140-point stop cannot take a single micro. Each shipped book was
therefore confirmed by replaying candidate weight sets through ``BotEngine``:

    python scripts/run_t58_engine_grid.py A IR3+CL1,OD1+IR3+CL1     # 60-day evaluation pass rate, a start every 15 days
    python scripts/run_t58_engine_grid.py B IR1+CL1                  # 365-day paid rate, a start every 60 days
    python scripts/run_t58_engine_grid.py N IR1+CL1+G21.0            # 24-month net profit on a rule-free account

Spec codes: OD / IR / I3 (Ind Rule 30m) / CL (Context Drive long-only) / G2 (Gate 27 basket) followed by the weight, joined with +.
"""
from __future__ import annotations

import copy
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import run_t58_bot_replays as RB  # noqa: E402
from app.bots.models import BotConfig  # noqa: E402
from app.bots.presets import _cad_long, _gate27, _ir, _ir30, _od, preset_configs  # noqa: E402


def legs(spec: str) -> list:
    out = []
    for part in spec.split("+"):
        k, w = part[:2], float(part[2:])
        out += {"OD": lambda: [_od(w, 0)], "IR": lambda: [_ir(w, 1)], "I3": lambda: [_ir30(w, 2)], "CL": lambda: [_cad_long(w, 3)], "G2": lambda: _gate27(w, 4)}[k]()
    return out


def main() -> int:
    mode, specs = sys.argv[1].upper(), sys.argv[2].split(",")
    base = {c.id: c for c in preset_configs()}[{"A": "bot-pass", "B": "bot-payout", "N": "bot-profit"}[mode]]
    hi = pd.Timestamp("2026-02-28", tz="UTC")
    for spec in specs:
        c = BotConfig.from_dict(base.to_dict()); c.legs = legs(spec)
        if mode == "N":
            r = RB.net_run(c, hi - pd.DateOffset(months=24), hi)
            print(spec, {k: r[k] for k in ("net", "cagr_pct", "max_dd_pct", "pf")}, {k: v["net"] for k, v in r["by_leg"].items()}, flush=True)
            continue
        horizon, stride = (60, 15) if mode == "A" else (365, 60)
        s, rows = pd.Timestamp("2022-01-08", tz="UTC"), []
        while s + pd.Timedelta(days=horizon) <= hi:
            rt, tr, ev, eng = RB.replay(c, s, s + pd.Timedelta(days=horizon))
            rows.append((any(e["kind"] == "pass" for e in ev), bool(rt.breaches) or rt.status == "halted", float(rt.payouts), s))
            s += pd.Timedelta(days=stride)
        d = pd.DataFrame(rows, columns=["pass", "bust", "paid", "start"])
        tv, te = d[d.start < "2025-01-01"], d[d.start >= "2025-01-01"]
        print(spec, "n", len(d), "pass%", round(d["pass"].mean() * 100, 1), "paid%", round((d.paid > 0).mean() * 100, 1), "bust%", round(d.bust.mean() * 100, 1),
              "| train+val pass%", round(tv["pass"].mean() * 100, 1), "| test pass%", round(te["pass"].mean() * 100, 1) if len(te) else "-", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
