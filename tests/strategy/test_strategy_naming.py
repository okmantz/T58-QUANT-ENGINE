"""[STRATEGY_NAME]_[MARKET]_[TIMEFRAME]_[VERSION]: the parser, the formatter, and a guard that every committed strategy file follows it."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.strategy import naming as N

ROOT = Path(__file__).resolve().parents[2]
EXT = {".py", ".pine", ".mq5", ".json"}


@pytest.mark.parametrize("fn,parts", [
    ("IndRule_NQ_15m_v1.py", ("IndRule", "NQ", "15m", 1)),
    ("OpenDrive_NQ_5m_v1.pine", ("OpenDrive", "NQ", "5m", 1)),
    ("ContextDrive_NQ_1m_v2.json", ("ContextDrive", "NQ", "1m", 2)),
    ("Gate27_Gold_Daily_v1.mq5", ("Gate27", "Gold", "Daily", 1)),
])
def test_owner_examples_parse(fn, parts):
    s = N.parse_strategy_filename(fn)
    assert s is not None and (s.name, s.market, s.timeframe, s.version) == parts


@pytest.mark.parametrize("bad", ["NQ1! Ind Rule 15m.py", "ind_rule_nq_15m_v1.py", "IndRule_NQ_15m.py", "IndRule_NQ_v1.py", "IndRule_NQ_15m_1.py", "IndRule NQ 15m v1.py"])
def test_old_style_names_do_not_conform(bad):
    assert not N.is_conforming(bad)


def test_formatter_round_trips():
    fn = N.format_strategy_filename("ind rule", "NQ1!", "15 min", 3, ".py")
    assert fn == "IndRule_NQ_15m_v3.py" and N.parse_strategy_filename(fn).version == 3


def test_next_version_never_overwrites(tmp_path):
    (tmp_path / "IndRule_NQ_15m_v1.py").write_text("x")
    (tmp_path / "IndRule_NQ_15m_v2.py").write_text("x")
    assert N.next_version_filename(tmp_path, "IndRule", "NQ", "15m", ".py") == "IndRule_NQ_15m_v3.py"


def _committed_strategy_files() -> list[Path]:
    """Files git tracks under strategies/{python,pinescript,mql5}. Asking git (not the folder) keeps the guard about COMMITTED
    files: other tests write scratch strategies into the same folders (and run in parallel under xdist), and a glob would
    flake whenever one of them happened to be mid-write. Falls back to a folder scan only when git is unavailable."""
    import subprocess
    subs = ("python", "pinescript", "mql5")
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--", *[f"strategies/{s}" for s in subs]], cwd=ROOT,
                             capture_output=True, text=True, check=True, timeout=30).stdout
        files = [ROOT / rel for rel in out.split("\0") if rel]
        if files:
            return sorted(files)
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(p for sub in subs for p in (ROOT / "strategies" / sub).glob("*") if not p.name.startswith(("stub.", "searchlab_")))


def test_every_committed_strategy_file_follows_the_convention():
    bad = [str(p.relative_to(ROOT)) for p in _committed_strategy_files()
           if p.suffix.lower() in EXT and not p.name.startswith("stub.")  # gitignored scratch other tests write
           and not N.is_conforming(p.name)]
    assert not bad, f"strategy files that break [STRATEGY_NAME]_[MARKET]_[TIMEFRAME]_[VERSION]: {bad}"


def test_generated_run_names_use_the_convention():
    from app.strategy.library import simple_run_filename
    assert simple_run_filename("ES1!", "15m", "RSI", "optimized", ".json") == "RSIOptimized_ES_15m_v1.json"
    assert N.is_conforming(simple_run_filename("NQ1!", "5m", "", "full pipeline", ".json"))
