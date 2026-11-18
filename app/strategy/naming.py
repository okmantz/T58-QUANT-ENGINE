"""The one naming convention for strategy files: ``[STRATEGY_NAME]_[MARKET]_[TIMEFRAME]_[VERSION].<ext>``.

    IndRule_NQ_15m_v1.py          OpenDrive_NQ_5m_v1.pine         ContextDrive_NQ_1m_v2.json        Gate27_Gold_Daily_v1.mq5

  STRATEGY_NAME  CamelCase letters and digits, no separators (``IndRule``, ``ContextDriveLong``). A variant is part of the name (``IndRuleA``).
  MARKET         the instrument the file was written for: ``NQ``, ``ES``, ``GC``, ``Gold``, ``Oil``, a micro (``MNQ``) or ``Basket`` for a
                 multi-market book. Two markets are glued together (``ESNQ``).
  TIMEFRAME      ``30s`` ``1m`` ``5m`` ``15m`` ``4h`` ``Daily`` ``Weekly`` ``Monthly``.
  VERSION        ``v`` and an integer (``v1``, ``v12``). Change the logic and the number goes up; the old file is kept, never overwritten.

Underscore is the only separator, so a name splits unambiguously and sorts by strategy, then market, then timeframe. One function builds a
name (``format_strategy_filename``), one parses it (``parse_strategy_filename``), and ``tests/strategy/test_strategy_naming.py`` fails the
build when a committed strategy file breaks the rule. Pure functions, no I/O.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

STRATEGY_SUFFIXES = (".py", ".pine", ".mq5", ".json")
TIMEFRAME_WORDS = ("Daily", "Weekly", "Monthly")
_TF = r"(?:\d{1,3}[smh]|Daily|Weekly|Monthly)"
_NAME_RE = re.compile(rf"^(?P<name>[A-Z][A-Za-z0-9]*)_(?P<market>[A-Z][A-Za-z0-9]*)_(?P<tf>{_TF})_(?P<version>v\d+)$")

# the instruments the research engine has bundled history for, and every alias a market token may carry
MARKET_ROOTS = {"NQ": "NQ", "MNQ": "NQ", "ES": "ES", "MES": "ES", "GC": "GC", "MGC": "GC", "GOLD": "GC", "XAU": "GC", "CL": "CL", "OIL": "CL",
                "ZN": "ZN", "US10Y": "ZN"}


@dataclass(frozen=True)
class StrategyName:
    name: str
    market: str
    timeframe: str
    version: int

    @property
    def stem(self) -> str:
        return f"{self.name}_{self.market}_{self.timeframe}_v{self.version}"

    @property
    def timeframe_minutes(self) -> int:
        return timeframe_minutes(self.timeframe)

    @property
    def instruments(self) -> list:
        """Research instrument roots the market token names, in order (``ESNQ`` -> ES, NQ). Empty for ``Basket`` and unknown tokens."""
        return market_roots(self.market)


def _camel(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", str(text or ""))
    out = "".join(p[:1].upper() + p[1:] for p in parts)
    if out and not out[0].isalpha():
        out = "S" + out
    return out or "Strategy"


def normalize_timeframe(tf: str) -> str:
    """'15 min' / '15M' / 'M15' / '1D' / 'd' / '240' -> '15m' / '15m' / '15m' / 'Daily' / 'Daily' / '4h'."""
    s = str(tf or "").strip().lower().replace(" ", "")
    if not s:
        return "1m"
    if s in ("d", "1d", "d1", "day", "daily"):
        return "Daily"
    if s in ("w", "1w", "w1", "week", "weekly"):
        return "Weekly"
    if s in ("mn", "mo", "1mo", "monthly", "month"):
        return "Monthly"
    m = re.fullmatch(r"(\d+)(s|sec|m|min|h|hr|hour)?", s) or re.fullmatch(r"([mh])(\d+)", s)
    if not m:
        return "1m"
    if m.re.pattern.startswith("([mh])"):
        unit, n = m.group(1), int(m.group(2))
    else:
        n, unit = int(m.group(1)), (m.group(2) or "m")
    unit = {"sec": "s", "min": "m", "hr": "h", "hour": "h"}.get(unit, unit)
    if unit == "m" and n >= 60 and n % 60 == 0 and n < 1440:
        n, unit = n // 60, "h"
    if unit == "m" and n == 1440:
        return "Daily"
    return f"{n}{unit}"


def timeframe_minutes(tf: str) -> int:
    t = normalize_timeframe(tf)
    if t == "Daily":
        return 1440
    if t == "Weekly":
        return 10080
    if t == "Monthly":
        return 43200
    n, unit = int(t[:-1]), t[-1]
    return max(1, n // 60) if unit == "s" else (n * 60 if unit == "h" else n)


def normalize_market(market: str) -> str:
    """'NQ1!' / 'futures_NQ.F' / 'MNQ' / 'nq' -> 'NQ' / 'NQ' / 'MNQ' / 'NQ'; unknown text becomes CamelCase letters and digits."""
    s = str(market or "").strip()
    s = re.sub(r"^futures_", "", s, flags=re.I)
    s = re.sub(r"\.F$|1!$|!$", "", s, flags=re.I).replace("&", "")
    s = re.sub(r"[^A-Za-z0-9]+", "", s)
    if not s:
        return "Basket"
    if s.upper() in ("GOLD", "OIL"):
        return s.upper().capitalize()
    if s.upper() in MARKET_ROOTS or (len(s) <= 5 and s.isupper()):
        return s.upper()
    return _camel(s)


def market_roots(market: str) -> list:
    """Research instruments (NQ / ES / GC ...) a market token names. ``ESNQ`` -> ['ES', 'NQ']; ``Gold`` -> ['GC']; ``Basket`` -> []."""
    tok = str(market or "")
    hit = MARKET_ROOTS.get(tok.upper())
    if hit:
        return [hit]
    out, i, up = [], 0, tok.upper()
    keys = sorted(MARKET_ROOTS, key=len, reverse=True)
    while i < len(up):
        for k in keys:
            if up.startswith(k, i):
                r = MARKET_ROOTS[k]
                if r not in out:
                    out.append(r)
                i += len(k)
                break
        else:
            return []
    return out


def format_strategy_filename(name: str, market: str, timeframe: str, version: int | str = 1, ext: str = "") -> str:
    """``format_strategy_filename('ind rule', 'NQ1!', '15 min', 1, '.py')`` -> ``'IndRule_NQ_15m_v1.py'``."""
    v = int(re.sub(r"\D", "", str(version)) or 1)
    stem = f"{_camel(name)}_{normalize_market(market)}_{normalize_timeframe(timeframe)}_v{max(v, 1)}"
    if ext and not ext.startswith("."):
        ext = "." + ext
    return stem + ext


def parse_strategy_filename(filename: str) -> Optional[StrategyName]:
    """Split a file name (or path) that follows the convention; None when it does not."""
    stem = Path(str(filename)).name
    suffix = Path(stem).suffix
    if suffix.lower() in STRATEGY_SUFFIXES:
        stem = stem[: -len(suffix)]
    m = _NAME_RE.match(stem)
    if not m:
        return None
    return StrategyName(m["name"], m["market"], m["tf"], int(m["version"][1:]))


def is_conforming(filename: str) -> bool:
    return parse_strategy_filename(filename) is not None


def next_version_filename(directory: Path, name: str, market: str, timeframe: str, ext: str) -> str:
    """The first free ``vN`` for this strategy / market / timeframe in ``directory`` (existing files are never overwritten)."""
    n = 1
    while (Path(directory) / format_strategy_filename(name, market, timeframe, n, ext)).exists():
        n += 1
    return format_strategy_filename(name, market, timeframe, n, ext)


def display_label(filename: str) -> str:
    """'IndRuleA_NQ_30m_v1.py' -> 'Ind Rule A' (CamelCase split for a card title); a non-conforming name falls back to its stem."""
    p = parse_strategy_filename(filename)
    base = p.name if p else Path(str(filename)).stem
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", base).strip()
