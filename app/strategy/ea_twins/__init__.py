"""Vectorised "engine twins" of the T58 MQL5 EAs. See ``_common`` (why) and ``twins`` (what)."""
from __future__ import annotations

import re

import pandas as pd

from app.strategy.base import StrategyError, StrategyResult
from app.strategy.ea_twins._common import Ctx, Inputs
from app.strategy.ea_twins.twins import TUNABLE, TWINS

_TWIN_RE = re.compile(r"T58_TWIN\s*=\s*([A-Za-z0-9_]+)")


def twin_name(code: str) -> str | None:
    m = _TWIN_RE.search(code or "")
    return m.group(1).lower() if m else None


def run_twin(code: str, df: pd.DataFrame) -> StrategyResult:
    name = twin_name(code)
    if name not in TWINS:
        raise StrategyError(f"MQL5: unknown engine twin '{name}' (known: {', '.join(sorted(TWINS))}).")
    n_real = len(df)
    if n_real < 50:
        raise StrategyError("MQL5 engine twin: not enough bars.")
    # One flat placeholder bar is appended so an entry decided on the LAST real bar (filled at the next open) is represented exactly as it would
    # be if that next bar existed: the level on bar k then never depends on whether bar k+1 has arrived yet (prefix invariance). The placeholder
    # (open = high = low = close = the last close, timestamp = one bar later) is cut off again before the result is returned.
    pad = df.iloc[[-1]].copy()
    pad.index = [df.index[-1] + 1] if pd.api.types.is_integer_dtype(df.index) else [df.index[-1] + (df.index[-1] - df.index[-2])]
    ts_col = "timestamp" if "timestamp" in df.columns else None
    if ts_col is not None:
        step = pd.to_datetime(df[ts_col]).iloc[-1] - pd.to_datetime(df[ts_col]).iloc[-2]
        pad[ts_col] = pd.to_datetime(df[ts_col]).iloc[-1] + step
    for c in ("open", "high", "low"):
        pad[c] = df["close"].iloc[-1]
    if "volume" in pad.columns:
        pad["volume"] = 0
    padded = pd.concat([df, pad])
    ctx = Ctx(padded)
    level, sl, tp = TWINS[name](ctx, Inputs(code))
    level, sl, tp = level[:n_real], sl[:n_real], tp[:n_real]
    sig = pd.Series(level.astype(int), index=df.index)
    sl_s = pd.Series(sl, index=df.index)
    tp_s = pd.Series(tp, index=df.index)
    return StrategyResult(name=f"MQL5 EA (engine twin: {name})", source_type="mql5", signals=sig,
                          stop_loss_distance=sl_s if sl_s.notna().any() else None,
                          take_profit_distance=tp_s if tp_s.notna().any() else None)


def twin_genes(code: str):
    """CodeGene list for a twin EA: only the inputs the twin declares tunable, with its own bounds."""
    from app.optimize.code_parameter_space import CodeGene
    name = twin_name(code)
    if name not in TUNABLE:
        return []
    genes = []
    pat = re.compile(r"^(\s*(?:input|sinput)\s+(int|uint|long|double|float)\s+([A-Za-z_]\w*)\s*=\s*)(-?\d+(?:\.\d+)?)(\s*;)")
    for i, line in enumerate(code.splitlines()):
        m = pat.match(line)
        if not m or m.group(3) not in TUNABLE[name]:
            continue
        lo, hi = TUNABLE[name][m.group(3)]
        is_int = m.group(2) in ("int", "uint", "long")
        genes.append(CodeGene(name=m.group(3), kind="mql5_input", is_int=is_int, lo=float(lo), hi=float(hi), base_value=float(m.group(4)),
                              label=f"{m.group(3)}", line_index=i, span=(m.start(4), m.end(4))))
    return genes
