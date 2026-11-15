"""
Run the frozen Gate 27 V1 basket (monthly SMA210 long/flat, inverse-vol ERC sizing at
0.5%/day, 5x leverage cap, 3-day phase-in) and report how profitable it is.

Gate 27 is a 4-leg DAILY basket (US500 / Gold / Oil / USD index), so it cannot run through the
single-instrument bar engine; this runner uses the strategy's own frozen backtest() and prints
net profit, CAGR, Sharpe, max drawdown. Use --prices-csv for your own 4-column daily closes, or
--from-repo to build the US500 (ES) and GOLD (GC) legs from the repo's 1-minute data (OIL/USD legs
then need --oil-csv / --usd-csv, or use --legs to run only the legs you have).

    python scripts/run_gate27_basket.py --prices-csv closes.csv
    python scripts/run_gate27_basket.py --from-repo --legs US500 GOLD
"""
from __future__ import annotations
import argparse, importlib.util, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_gate27():
    p = ROOT / "strategies" / "gate27" / "gate27_v1_longterm.py"
    spec = importlib.util.spec_from_file_location("gate27_v1_longterm", p)
    m = importlib.util.module_from_spec(spec); sys.modules["gate27_v1_longterm"] = m
    spec.loader.exec_module(m); return m


def _daily_close_from_repo(folder: str) -> pd.Series:
    from app.data.importer import import_csv
    f = next((ROOT / "data" / "raw" / folder).glob("*_1m.parquet"))
    df = import_csv(str(f)).dataframe
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("America/New_York")
    s = pd.Series(df["close"].to_numpy(float), index=ts)
    d = s.groupby(s.index.date).last(); d.index = pd.to_datetime(d.index); return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prices-csv"); ap.add_argument("--date-col", default="date")
    ap.add_argument("--from-repo", action="store_true")
    ap.add_argument("--oil-csv"); ap.add_argument("--usd-csv")
    ap.add_argument("--legs", nargs="+", default=None, help="subset of US500 GOLD OIL USD")
    ap.add_argument("--equity", type=float, default=100_000.0)
    a = ap.parse_args()
    g = _load_gate27()
    if a.prices_csv:
        px = g.load_price_data_from_csv(a.prices_csv, a.date_col)
    elif a.from_repo:
        cols = {"US500": _daily_close_from_repo("ES1!"), "GOLD": _daily_close_from_repo("GC1!")}
        for k, path in (("OIL", a.oil_csv), ("USD", a.usd_csv)):
            if path:
                x = pd.read_csv(path, parse_dates=[0], index_col=0).iloc[:, 0]; cols[k] = x
        px = pd.DataFrame(cols).sort_index().dropna(how="all")
    else:
        ap.error("give --prices-csv or --from-repo")
    legs = a.legs or list(px.columns)
    px = px[legs].dropna(how="all").ffill().dropna()
    # compute SMA/vol on whatever legs exist (module helpers iterate columns)
    eq = g.backtest(px, starting_equity=a.equity)
    if eq.empty:
        print("No trades/equity produced - need > ~210 daily bars per leg."); return 1
    s = g.performance_summary(eq, a.equity)
    net = float(eq["equity"].iloc[-1] - a.equity)
    print(f"Gate 27 V1 | legs={legs} | {eq.index[0].date()} -> {eq.index[-1].date()}")
    print(f"  Net profit : ${net:,.2f}  ({s['total_return_pct']:.1f}% on ${a.equity:,.0f})")
    print(f"  CAGR       : {s['cagr_pct']:.2f}%   Sharpe: {s['sharpe']:.2f}   MaxDD: {s['max_drawdown_pct']:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
