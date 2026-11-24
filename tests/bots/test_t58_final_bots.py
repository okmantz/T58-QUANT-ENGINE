"""T58 final bots (2026-11-24): every leg's strategy file exists and loads, and the configs build."""
import importlib.util
from pathlib import Path
from app.bots.t58_final_bots import t58_final_configs, T58_PICKS, LEG_FILES
from app.bots.presets import preset_configs

ROOT = Path(__file__).resolve().parents[2]


def test_configs_build_and_do_not_clash_with_presets():
    cs = t58_final_configs()
    assert {c.id for c in cs} == {"bot-t58-final-a", "bot-t58-final-b"}
    assert not {c.id for c in cs} & {c.id for c in preset_configs()}


def test_every_leg_file_exists_and_has_generate_signals():
    for obj, pk in T58_PICKS.items():
        for k, w in pk["legs"].items():
            if w <= 0:
                continue
            p = ROOT / "strategies" / LEG_FILES[k][0]
            assert p.exists(), p
            spec = importlib.util.spec_from_file_location(p.stem, p)
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            assert callable(m.generate_signals)


def test_new_strategies_are_flat_on_tiny_data():
    import numpy as np, pandas as pd
    ts = pd.date_range("2026-01-05 14:30", periods=400, freq="1min", tz="UTC")
    px = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.1, len(ts)))
    df = pd.DataFrame({"timestamp": ts, "open": px, "high": px + 0.1, "low": px - 0.1, "close": px, "volume": 1.0})
    for p in (ROOT / "strategies" / "python").glob("*_t58.py"):
        spec = importlib.util.spec_from_file_location(p.stem, p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        s = m.generate_signals(df)
        assert len(s) == len(df) and (s == 0).all()      # no prior sessions -> no ATR -> no trades
