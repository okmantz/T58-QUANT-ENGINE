"""Objective C finals: the intraday NET book alone and with the Gate 27 swing basket (original and tuned parameters), scored on train / val / test.
Reads the cached trades and the Gate 27 daily-return streams written by run_gate27_study.py. Nothing here is typed in."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_objective_scores as R  # noqa: E402
from app.prop import objective_scorecard as sc  # noqa: E402


def main(cache: str, out: str) -> None:
    S = {k: R.at_1x(v) for k, v in R.load(Path(cache)).items()}
    books = json.loads(Path(out, "books.json").read_text())
    legs = books["books"]["NET"]["chosen"]["legs"]
    book = R.bundle([(n, S[n], m, i) for i, (n, m) in enumerate(legs)], daily_cap=None, max_open=R.MAX_OPEN["NET"])
    prev_legs = R.OLD_PRESETS["NET"]
    prev_book = R.bundle([(n, S[n], m, i) for i, (n, m) in enumerate(prev_legs)], daily_cap=None, max_open=R.MAX_OPEN["NET"])
    gov = R.gov_for("NET")
    streams = {"original": pd.read_parquet(Path(out, "gate27_2leg_daily_returns.parquet"))["ret"], "tuned": pd.read_parquet(Path(out, "gate27_best_daily_returns.parquet"))["ret"]}
    res = {}
    cases = {"intraday book (chosen)": (book, None), "previous preset (IR + CAD)": (prev_book, None), "Gate 27 alone (original)": (None, streams["original"]),
             "Gate 27 alone (tuned)": (None, streams["tuned"]), "intraday + Gate 27 original": (book, streams["original"]), "intraday + Gate 27 tuned": (book, streams["tuned"]),
             "previous preset + Gate 27 original": (prev_book, streams["original"])}
    for name, (b, ex) in cases.items():
        res[name] = {}
        for sp in ("train", "val", "test"):
            a, z = R.SPLITS[sp]
            x = R.cut(b, sp) if b is not None else None
            e = ex[(ex.index >= pd.Timestamp(a)) & (ex.index < pd.Timestamp(z))] if ex is not None else None
            r = sc.score_net(x, gov=gov, extra_daily=e)
            r.pop("curve", None)
            res[name][sp] = r
        print(name, {sp: (res[name][sp].get("cagr"), res[name][sp].get("max_dd_pct"), res[name][sp].get("calmar")) for sp in res[name]}, flush=True)
    Path(out, "net_finals.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
