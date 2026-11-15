"""The 60-hypothesis registry of the T58 audit (Futures Prop-Firm Evaluation Research: A Unified Study, Appendix D).

Evidence grades (A strongest .. D weakest) and the audit's confidence are LITERATURE judgments, not results from this project's data.
Scores are (research merit, experimental priority, evaluation-stage potential, funded-stage potential), each 1 to 5.
Only A02 and F01 (as ORB-type breakout cells) were actually tested in the study's Phases 2 and 3. Counts: Active 47, low confidence 5,
rejected for account type 4 (E05, H01, I05, K03), conditional and rule-blocked 2 (F05, F06), rejected as a standalone signal 1 (E03), rejected 1 (I01).
"""
from __future__ import annotations

from dataclasses import dataclass

CATEGORIES = {
    "A": "Momentum and trend",
    "B": "Mean reversion",
    "C": "Volatility",
    "D": "Volume",
    "E": "Microstructure and order flow",
    "F": "Opening range and session structure",
    "G": "Liquidity and auction",
    "H": "Statistical arbitrage and cross-instrument",
    "I": "Calendar and seasonality",
    "J": "Macro and event",
    "K": "Advanced quantitative and ML",
    "L": "Prop structure, execution and risk overlay"
}


@dataclass(frozen=True)
class Hypothesis:
    id: str
    name: str
    evidence: str            # A..D
    confidence: str          # H | M | L
    scores: tuple            # (merit, priority, eval_potential, funded_potential)
    status: str

    @property
    def category(self) -> str:
        return CATEGORIES[self.id[0]]

    @property
    def merit(self) -> int:
        return self.scores[0]

    @property
    def priority(self) -> int:
        return self.scores[1]

    @property
    def eval_potential(self) -> int:
        return self.scores[2]

    @property
    def funded_potential(self) -> int:
        return self.scores[3]

    @property
    def runnable(self) -> bool:
        """Can be searched for an account like the project's: active or low-confidence. Rejected / rule-blocked ones are kept, with their status."""
        return self.status in ("Active", "Low confidence")


# Not testable on bar data: they need ticks, signed flow or a limit-order book (study section on data compatibility).
NOT_TESTABLE_ON_BARS = frozenset({"B07", "E01", "E02", "E03", "E04", "E05", "E06", "K03"})

HYPOTHESES: tuple = (
    Hypothesis('A01', 'Intraday momentum: early-session return predicts late-session return', 'B', 'M', (5, 5, 3, 3), 'Active'),
    Hypothesis('A02', 'Volatility-scaled noise-area breakout with trailing stop', 'C', 'L', (3, 5, 4, 3), 'Active'),
    Hypothesis('A03', 'Daily trend (time-series momentum) as directional filter', 'B', 'M', (4, 3, 2, 3), 'Active'),
    Hypothesis('A04', 'Overnight gap continuation (gap-and-go)', 'D', 'L', (2, 3, 3, 2), 'Active'),
    Hypothesis('A05', 'Prior-day high/low breakout', 'D', 'L', (2, 2, 3, 2), 'Active'),
    Hypothesis('A06', 'Cross-asset signal confirmation', 'C', 'L', (3, 2, 2, 3), 'Active'),
    Hypothesis('A07', 'Overnight-range momentum (Globex high/low break at the RTH open)', 'D', 'L', (2, 3, 3, 2), 'Active'),
    Hypothesis('B01', 'Opening gap fade', 'C', 'M', (3, 4, 3, 3), 'Active'),
    Hypothesis('B02', 'VWAP deviation reversion', 'D', 'L', (2, 3, 3, 3), 'Active'),
    Hypothesis('B03', 'Intraday z-score / Bollinger reversion', 'C', 'L', (3, 3, 2, 3), 'Active'),
    Hypothesis('B04', 'Short-term RSI-type oversold/overbought reversal', 'D', 'L', (1, 1, 2, 2), 'Low confidence'),
    Hypothesis('B05', "End-of-day reversal of the day's move", 'C', 'L', (3, 3, 2, 2), 'Active'),
    Hypothesis('B06', 'Range-extreme fade in low-volatility regimes', 'D', 'L', (2, 2, 3, 3), 'Active'),
    Hypothesis('B07', 'Post-0DTE-gamma reversal in order flow', 'C', 'L', (3, 2, 2, 3), 'Active'),
    Hypothesis('C01', 'Volatility-regime filter', 'B', 'M', (4, 5, 3, 4), 'Active'),
    Hypothesis('C02', 'Volatility compression to expansion (NR7 / squeeze) breakout', 'C', 'L', (3, 3, 3, 3), 'Active'),
    Hypothesis('C03', 'Volatility-targeted position sizing', 'B', 'H', (3, 4, 3, 4), 'Active'),
    Hypothesis('C04', 'Realised-volatility forecast (HAR) to gate and size trades', 'B', 'M', (3, 3, 3, 4), 'Active'),
    Hypothesis('C05', 'Intraday volatility-periodicity time-of-day windows', 'A', 'H', (4, 3, 3, 3), 'Active'),
    Hypothesis('C06', 'VIX/VXN level regime filter for ES/NQ', 'C', 'M', (3, 3, 3, 3), 'Active'),
    Hypothesis('D01', 'Relative-volume (RVOL) confirmation', 'C', 'L', (3, 3, 3, 3), 'Active'),
    Hypothesis('D02', 'Volume-profile (POC / value-area) levels as support-resistance', 'D', 'L', (2, 3, 3, 3), 'Active'),
    Hypothesis('D03', 'Volume-price divergence', 'D', 'L', (1, 1, 2, 2), 'Low confidence'),
    Hypothesis('D04', 'Volume-clock (volume or dollar bars) sampling', 'C', 'L', (2, 2, 2, 2), 'Active'),
    Hypothesis('E01', 'Order-flow imbalance (OFI) short-horizon price pressure', 'B', 'M', (4, 2, 1, 1), 'Active'),
    Hypothesis('E02', 'Signed-volume (trade delta) imbalance over minutes', 'C', 'L', (3, 3, 2, 3), 'Active'),
    Hypothesis('E03', 'VPIN flow toxicity as volatility/crash warning', 'C', 'L', (1, 1, 1, 2), 'Rejected as standalone'),
    Hypothesis('E04', 'Book-depth imbalance / queue imbalance', 'C', 'L', (3, 1, 1, 1), 'Active'),
    Hypothesis('E05', 'E-mini leads ETF/cash price discovery (lead-lag)', 'B', 'H', (3, 1, 1, 1), 'Rejected for account type'),
    Hypothesis('E06', 'Absorption / iceberg detection', 'D', 'L', (1, 1, 1, 1), 'Low confidence'),
    Hypothesis('F01', 'Opening Range Breakout (ORB) with volatility- state conditioning', 'B', 'M', (4, 5, 4, 3), 'Active'),
    Hypothesis('F02', 'Initial balance (first hour) range extension', 'D', 'L', (2, 3, 3, 3), 'Active'),
    Hypothesis('F03', 'Open-drive / first-bar direction persistence', 'C', 'L', (3, 3, 3, 3), 'Active'),
    Hypothesis('F04', 'Midday lunch-lull fade / no-trade window', 'B', 'M', (3, 3, 3, 3), 'Active'),
    Hypothesis('F05', 'Overnight (European-open) drift long', 'B', 'L', (4, 3, 3, 4), 'Conditional, rule-blocked'),
    Hypothesis('F06', 'Gold session structure: overnight/Asia vs US- day asymmetry                                                               blocked', 'C', 'L', (2, 2, 2, 2), 'Conditional, rule-blocked'),
    Hypothesis('G01', 'Value-area rotation (80% rule)', 'D', 'L', (2, 3, 3, 3), 'Low confidence'),
    Hypothesis('G02', 'Prior-extreme liquidity sweep and reversal', 'D', 'L', (2, 2, 3, 3), 'Low confidence'),
    Hypothesis('G03', 'Settlement/fix timing effects (gold PM fix, equity settlement)', 'C', 'L', (2, 1, 1, 1), 'Active'),
    Hypothesis('H01', 'ES-NQ spread mean reversion (two-leg)', 'C', 'L', (2, 1, 1, 1), 'Rejected for account type'),
    Hypothesis('H02', 'NQ/ES relative strength as directional signal for a single leg', 'D', 'L', (2, 2, 3, 3), 'Active'),
    Hypothesis('H03', 'Gold vs dollar/real-yield lead-lag', 'D', 'L', (2, 2, 2, 2), 'Active'),
    Hypothesis('I01', 'Pre-FOMC announcement drift', 'B', 'H', (3, 1, 1, 1), 'Rejected'),
    Hypothesis('I02', 'Turn-of-the-month effect', 'C', 'L', (3, 2, 1, 2), 'Active'),
    Hypothesis('I03', 'Day-of-week effects', 'C', 'L', (2, 1, 2, 2), 'Active'),
    Hypothesis('I04', 'Monthly/weekly option expiration gamma pinning', 'C', 'L', (2, 2, 2, 2), 'Active'),
    Hypothesis('I05', 'Post-FOMC monetary momentum (multi-day drift)                                                                   type', 'C', 'L', (2, 1, 1, 1), 'Rejected for account type'),
    Hypothesis('J01', 'Event-day volatility expansion trading (NFP/CPI/FOMC)', 'C', 'L', (3, 2, 2, 1), 'Active'),
    Hypothesis('J02', 'Scheduled-news exclusion (no-trade) windows', 'B', 'H', (3, 4, 4, 4), 'Active'),
    Hypothesis('J03', 'Intraday post-announcement drift after Fed policy surprises', 'C', 'L', (2, 2, 1, 1), 'Active'),
    Hypothesis('K01', 'Gradient-boosted/linear model on intraday features with purged CV', 'D', 'L', (2, 2, 2, 2), 'Active'),
    Hypothesis('K02', 'Meta-labeling filter on a primary rule', 'D', 'L', (2, 2, 3, 3), 'Active'),
    Hypothesis('K03', 'Deep learning on limit order book (DeepLOB- style)                                                                   type', 'C', 'L', (3, 1, 1, 1), 'Rejected for account type'),
    Hypothesis('K04', 'Hidden-Markov / regime-switching volatility regime', 'C', 'L', (2, 2, 3, 3), 'Active'),
    Hypothesis('K05', 'Online change-point detection for regime breaks', 'D', 'L', (2, 2, 2, 3), 'Active'),
    Hypothesis('L01', 'Trailing vs fixed vs time stops (stop-design family)', 'B', 'M', (4, 4, 4, 4), 'Active'),
    Hypothesis('L02', 'Prop-aware sizing: scale risk to distance from trailing floor', 'C', 'M', (3, 5, 5, 5), 'Active'),
    Hypothesis('L03', 'Consistency-aware profit management (40% best-day rule)', 'C', 'M', (2, 4, 1, 5), 'Active'),
    Hypothesis('L04', 'Trade-count/hold-time design to avoid microscalping flags', 'C', 'M', (1, 3, 4, 4), 'Active'),
    Hypothesis('L05', 'Time-of-day/hours window selection', 'B', 'M', (3, 3, 3, 3), 'Active'),
)

_BY_ID = {h.id: h for h in HYPOTHESES}


def get(hid: str) -> Hypothesis:
    return _BY_ID[hid.upper()]


def by_status(status: str) -> list:
    return [h for h in HYPOTHESES if h.status == status]


def status_counts() -> dict:
    out: dict = {}
    for h in HYPOTHESES:
        out[h.status] = out.get(h.status, 0) + 1
    return out
