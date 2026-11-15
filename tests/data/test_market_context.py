"""Cross-market context: causal alignment, cache keys, resample/slice survival, importer flow columns, D-6 exchange-clock slots."""
import numpy as np
import pandas as pd

from app.data.market_context import attach_companions, align_companion
from app.strategy.indicator_cache import content_hash


def _frames():
    p = pd.DataFrame({"timestamp": pd.date_range("2024-01-02 09:00", periods=10, freq="1h")})
    for c in ("open", "high", "low", "close"):
        p[c] = 100.0
    p["volume"] = 1.0
    c = pd.DataFrame({"timestamp": pd.date_range("2024-01-02 09:00", periods=10, freq="1h")})
    c["open"] = c["high"] = c["low"] = c["close"] = np.arange(10, dtype=float)
    c["volume"] = 1.0
    return p, c


def test_companion_never_uses_unclosed_bar():
    p, c = _frames()
    out = attach_companions(p, {"lead": c})
    col = out["x_lead_close"]
    # primary bar i closes at i+1h; companion bar j closes at j+1h -> same-timestamp bars are both closed at decision time
    assert col.iloc[0] == 0.0 and col.iloc[5] == 5.0
    assert (col.dropna().diff().dropna() >= 0).all()


def test_companion_future_bar_not_visible():
    p, c = _frames()
    c2 = c.copy()
    c2.loc[7:, "close"] = 999.0                      # change only the FUTURE of bar 5
    a = attach_companions(p, {"lead": c})["x_lead_close"].iloc[:6]
    b = attach_companions(p, {"lead": c2})["x_lead_close"].iloc[:6]
    assert a.equals(b)


def test_cache_key_differs_by_companion():
    p, c = _frames()
    c2 = c.copy()
    c2["close"] = c2["close"] + 1
    h1 = content_hash(attach_companions(p, {"lead": c}))
    h2 = content_hash(attach_companions(p, {"lead": c2}))
    assert h1 != h2


def test_columns_survive_slice_and_resample():
    from app.data.timeframe_resample import _resample_ohlcv_uncached
    p, c = _frames()
    out = attach_companions(p, {"lead": c})
    assert "x_lead_close" in out.iloc[2:8].columns
    rs = _resample_ohlcv_uncached(out, 120) if callable(_resample_ohlcv_uncached) else None
    if rs is not None:
        assert "x_lead_close" in rs.columns


def test_slot_clock_uses_exchange_time():
    from app.backtest.time_slots import slot_clock, slot_mask_for_timestamps
    ts = pd.date_range("2024-07-01 14:00", periods=4, freq="1h")
    df = pd.DataFrame({"timestamp": ts})
    df.attrs["source_timezone"] = "UTC"
    df.attrs["exchange_timezone"] = "America/Chicago"
    assert list(slot_clock(df).hour) == [9, 10, 11, 12]
    assert slot_mask_for_timestamps(slot_clock(df), "MON 10").tolist() == [False, True, False, False]


def test_importer_reference_symbol_and_loader(tmp_path):
    from app.data import importer
    ts = pd.date_range("2024-01-02", periods=50, freq="1h")
    pd.DataFrame({"timestamp": ts, "open": 1.0, "close": 1.0}).to_csv(tmp_path / "NQ1_1h.csv", index=False)
    assert importer._reference_symbol("ES1_5m.csv") == "nq"
    ref = importer._load_reference_frame("ES1_5m.csv", pd.DataFrame({"timestamp": ts}), tmp_path)
    assert ref is not None and len(ref) == 50
    assert importer._load_reference_frame("EURUSD_1h.csv", pd.DataFrame({"timestamp": ts}), tmp_path) is None


def test_pooled_step_drops_own_market():
    from app.discovery_engine import engine_steps as es
    seen = {}
    orig = es.per_market_r
    es.per_market_r = lambda spec, frames, risks, cm=2.0, errors=None: (seen.update(keys=sorted(frames)) or {})
    try:
        st = es.build_steps(dev_df=pd.DataFrame(), sealed_df=None, risk=None, frames={"ES": 1, "MES": 1, "NQ": 1}, risks={}, own_symbol="ES")
        try:
            st.pooled_edge({"spec": {}}, {})
        except Exception:
            pass
    finally:
        es.per_market_r = orig
    assert seen.get("keys") == ["NQ"]
