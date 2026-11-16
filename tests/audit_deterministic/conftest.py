"""Makes the T58 repo importable. Drop this folder into <repo>/tests/ (it then finds the repo automatically) or set T58_REPO."""
import os, sys
from pathlib import Path

def _find_repo() -> Path:
    env = os.environ.get("T58_REPO")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "app" / "backtest" / "execution.py").exists():
            return p
    return Path("/home/claude/okmantz/t58-quant-engine")

REPO = _find_repo()
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
