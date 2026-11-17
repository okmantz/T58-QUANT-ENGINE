"""Optional ``T58_*`` directives a strategy source can carry (a ``// T58_MIN_TRADES=30`` / ``# T58_MIN_TRADES=30`` comment line)."""
from __future__ import annotations

import re
from pathlib import Path

_MIN_TRADES_RE = re.compile(r"T58_MIN_TRADES\s*=\s*(\d+)")


def _source_text(strategy) -> str:
    code = getattr(strategy, "code", None)
    if code:
        return str(code)
    fp = getattr(strategy, "file_path", None)
    if fp:
        try:
            return Path(fp).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
    return ""


def declared_min_trades(strategy) -> int | None:
    """The preflight minimum-trades floor the strategy itself declares, or None.

    A swing/monthly strategy (Gate 27 books ~1 trade a month) can never reach the 100-trade default over a 4-5 year sample; it declares
    its own honest floor instead of being refused before any search. The declaration only ever LOWERS the configured floor (see
    ``effective_min_trades``), never raises it, and READY still needs ``min_trades_for_ready`` -- a thin sample can't earn a READY verdict.
    """
    m = _MIN_TRADES_RE.search(_source_text(strategy))
    return int(m.group(1)) if m else None


def effective_min_trades(strategy, configured: int) -> int:
    d = declared_min_trades(strategy)
    return int(configured) if d is None else max(1, min(int(configured), d))
