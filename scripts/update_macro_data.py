"""Fetch the free macro/regime series into data/macro (VIX, VIX3M from CBOE; 10y, 2y, dollar index from FRED).

    python -m scripts.update_macro_data

Run it on a machine with internet access (the backtest sandbox usually has none). Safe to re-run daily.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # also runnable as `python scripts/<name>.py`, not only `python -m scripts.<name>`

from app.data.macro_data import update_all  # noqa: E402

if __name__ == "__main__":
    done = update_all()
    print("updated:", ", ".join(done) or "nothing (check your connection)")
