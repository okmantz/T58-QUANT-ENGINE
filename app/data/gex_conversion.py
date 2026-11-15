"""ETF-space -> futures-space conversion for dealer-gamma walls (IV Walls doc, section 2.2).

Walls are computed on an ETF's options (SPY / QQQ / GLD) but traded on the matching future (ES / NQ / GC). A fixed ratio is wrong: ES carries a
cost-of-carry basis, QQQ's index ratio drifts, and GLD's gold backing erodes with its expense ratio. The doc's method is an empirical fit per session:

    futures_price  ~  slope * etf_price + offset        (ordinary least squares on that session's concurrent closes)

then every wall level is mapped through that day's fit. ``fit_conversion`` does the regression, ``convert_levels`` maps a dict of levels,
``daily_fits`` builds one fit per session from two aligned intraday close series. A fit from yesterday must never be applied to today's levels: ``daily_fits`` returns
the fit for each date computed from THAT date's bars only, so the caller applies a date's fit to levels that are valid for the following session (the levels are computed
after the close; the conversion is fitted on the same close window).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_POINTS = 5


class ConversionError(Exception):
    pass


@dataclass(frozen=True)
class Conversion:
    slope: float
    offset: float
    n_points: int
    r2: float

    def apply(self, etf_price: float) -> float:
        return self.slope * float(etf_price) + self.offset


def fit_conversion(etf_close, fut_close, *, min_points: int = MIN_POINTS) -> Conversion:
    x = np.asarray(etf_close, dtype=float)
    y = np.asarray(fut_close, dtype=float)
    if x.shape != y.shape:
        raise ConversionError("ETF and futures closes must be aligned one-to-one.")
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < min_points:
        raise ConversionError(f"Need at least {min_points} concurrent closes, got {len(x)}.")
    if np.ptp(x) <= 0:
        raise ConversionError("ETF closes are constant; the regression slope is undefined.")
    slope, offset = np.polyfit(x, y, 1)
    pred = slope * x + offset
    ss_res, ss_tot = float(np.sum((y - pred) ** 2)), float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return Conversion(float(slope), float(offset), int(len(x)), float(r2))


def convert_levels(levels: dict, conv: Conversion) -> dict:
    """Maps every finite numeric level (call_wall, put_wall, gamma_flip, spot ...) through the fit; None / NaN pass through as None."""
    out = {}
    for k, v in levels.items():
        try:
            f = float(v)
        except (TypeError, ValueError):
            out[k] = None
            continue
        out[k] = round(conv.apply(f), 2) if np.isfinite(f) else None
    return out


def daily_fits(etf_close: pd.Series, fut_close: pd.Series, *, min_points: int = MIN_POINTS) -> dict:
    """One Conversion per session date, from that date's concurrent closes only. Both series need a DatetimeIndex."""
    both = pd.concat([etf_close.rename("etf"), fut_close.rename("fut")], axis=1).dropna()
    fits = {}
    for day, g in both.groupby(both.index.date):
        try:
            fits[day] = fit_conversion(g["etf"].to_numpy(), g["fut"].to_numpy(), min_points=min_points)
        except ConversionError:
            continue
    return fits
