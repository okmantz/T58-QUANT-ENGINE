"""Write event schedules into data/events.

    python -m scripts.update_event_calendar --fred-key YOUR_FREE_FRED_KEY

FOMC and NFP come from built-in tables/rules (no key). CPI (FRED release 10) and PCE (release 54) need the free FRED API key.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # also runnable as `python scripts/<name>.py`, not only `python -m scripts.<name>`

from app.data.event_calendar import fetch_fred_release_dates, write_events_csv  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fred-key", default="")
    a = ap.parse_args()
    if not a.fred_key:
        print("No --fred-key given: built-in FOMC/NFP only. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html for CPI/PCE.")
    else:
        for name, rid in (("CPI", 10), ("PCE", 54)):
            try:
                print(name, write_events_csv(fetch_fred_release_dates(a.fred_key, rid, name), name))
            except Exception as exc:  # noqa: BLE001
                print(f"{name}: {exc}")
