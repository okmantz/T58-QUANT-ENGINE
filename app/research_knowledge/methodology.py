"""SF1-SF11 families, the G0-G7 decision gates, the zero-edge null and the LucidPro rules (with evidence tiers)."""
from __future__ import annotations

import math

# family id -> (name, hypothesis ids, treatment). Ranges in the study ("F01-F03") are expanded here.
FAMILIES: dict = {
    "SF1": ("Intraday time-series momentum", ("A01", "A03", "A04"), "Fixed or volatility-adaptive threshold"),
    "SF2": ("Breakout and opening range", ("A02", "A05", "A07", "F01", "F02", "F03"), "Adaptive or fixed-tick buffer"),
    "SF3": ("Mean reversion to an anchor", ("B01", "B02", "B03", "B05", "B06", "G01"), "z-score or fixed ticks"),
    "SF4": ("Volatility-state conditioned", ("C01", "C02", "C03", "C04", "C05", "C06"), "Adaptive"),
    "SF5": ("Volume confirmation", ("D01", "D02", "D03", "D04"), "Fixed or percentile"),
    "SF6": ("Order flow and microstructure", ("E01", "E02", "E03", "E04", "E05", "E06"), "Excluded from evaluation search"),
    "SF7": ("Session and clock structure", ("F04", "F05", "F06", "G03", "I02", "I03", "I04", "I05"), "Fixed clock"),
    "SF8": ("Cross-instrument, single-leg", ("H02", "H03", "A06"), "Hedged forms excluded"),
    "SF9": ("Event-driven", ("J01", "J02", "I01"), "Calendar"),
    "SF10": ("ML-selected", ("K01", "K02", "K03", "K04", "K05"), "Trial-heavy; last"),
    "SF11": ("Overlay layer", ("L01", "L02", "L03", "L04", "L05", "C03"), "Adaptive"),
}

# Gate -> requirement (Statistical_Methodology section 7; thresholds are the document's [PROPOSED] values).
GATES: dict = {
    "G0": "Registration: hypothesis, family, grid, cost model, metrics and thresholds written before the run",
    "G1": "Integrity: data/backtest checklist green; firm-engine unit tests green",
    "G2": "Research-set sanity: net expectancy > 0 on base AND stress costs; >= 300 trades and >= 250 trading days; parameter plateau",
    "G3": "Validation: OOS expectancy lower 95% bound > 0 after FDR; PBO <= 0.20; DSR >= 0.95; placebo p < 0.05",
    "G4": "Evaluation engine: OOS P_pass(<=30d) >= 55% with 95% lower bound >= 40%; P_breach <= 40%; beats placebo by >= 20 points",
    "G5": "Funded engine: S30 >= 90%, R30 >= 60%, consistency-block <= 15%, positive E[Net]",
    "G6": "Final holdout: single look; no re-tuning afterwards",
    "G7": "Forward shadow: >= 20 sessions; measured slippage within 1.5x of model",
}

EVIDENCE_TIERS = {
    "OFF": "read from an official firm page", "RPT": "from the rules report, which cites an official page",
    "SEC": "secondary source only", "DER": "derived arithmetically", "ASM": "a modelling assumption",
    "OPEN": "unverified or conflicting - resolve before any purchase decision",
}

# LucidPro (Project_Specifications sections 2-3). tier tags in the *_tier fields.
LUCIDPRO = {
    "50K": {"start": 50_000, "target": 3_000, "mll": 2_000, "dll": 1_200, "lock_level": 50_100, "lock_trigger": 52_100,
            "payout_min": 500, "payout_goal": 500, "buffer": 52_100, "max_payout_first": 2_000, "max_payout_next": 2_500},
    "100K": {"start": 100_000, "target": 6_000, "mll": 3_000, "dll": 1_800, "lock_level": 100_100, "lock_trigger": 103_100,
             "payout_min": 500, "payout_goal": 750, "buffer": 103_100, "max_payout_first": 2_500, "max_payout_next": 3_000},
    "common": {"drawdown": "EOD trailing, locks at start + $100", "consistency_funded": 0.40, "split": (0.90, 0.10),
               "eval_consistency": None, "open_items": ("DLL hard vs soft", "minimum trading days", "time limit", "max contracts")},
}


def zero_edge_pass_probability(target: float, mll: float, lock_extra: float = 100.0) -> float:
    """Closed-form pass probability of a driftless walk (Statistical_Methodology 2.5).

    P = exp(-(M + 100) / M) * M / (M + (T - M - 100)).  50K: 0.241, 100K: 0.181.
    """
    m, t = float(mll), float(target)
    return math.exp(-(m + lock_extra) / m) * m / (m + (t - m - lock_extra))


def assistant_brief() -> str:
    """Compact, factual brief the AI assistant gets as context."""
    from .hypotheses import status_counts
    p50 = zero_edge_pass_probability(3000, 2000)
    p100 = zero_edge_pass_probability(6000, 3000)
    fams = "; ".join(f"{k} {v[0]}" for k, v in FAMILIES.items())
    gates = " | ".join(f"{k}: {v}" for k, v in GATES.items())
    return (
        "RESEARCH BASELINE (from the T58 audit; literature grades, not results from this app's data). "
        f"60 hypotheses ({status_counts()}). Families: {fams}. No hypothesis has evidence grade A for a net-of-cost intraday futures "
        f"strategy. Zero-edge benchmark: a strategy with no edge still passes about {p50:.0%} (50K) / {p100:.0%} (100K) with unlimited time, "
        "so a pass rate is only skill above that null. Gates: " + gates + ". Treat anything tagged OPEN as unverified."
    )
