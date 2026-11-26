"""A-D evidence grade for each of the 100 v13 strategy families.

    A  Replicated, peer-reviewed evidence of a net-of-cost premium at the horizon and asset class the family trades, and the family
       can be run as written on the data this app has.
    B  Published evidence for the mechanism or a close cousin, but weaker replication, a different asset class or horizon,
       a documented post-publication decay, or heavy cost sensitivity.
    C  Practitioner rule or plausible mechanism. No credible out-of-sample evidence. Often a re-skin of a tested idea.
    D  No evidence for the mechanism, the published evidence points the other way, or the family cannot be tested honestly here
       (tick / order-book / scale-in families, or a feed the app has no adapter for).

HOW TO READ THIS. A grade is a PRIOR about where to spend search budget and how much graveyard evidence it takes to close a family
(see ``closure``). It is not a result and it never lifts a candidate over a gate: the engine's own tests are the authority. Grades were
assigned from the published literature as recalled when this module was written, with references only where the citation is well
known. Treat a reference as a pointer to check, not as proof, and re-grade a family whenever you read something that changes the
picture (``ledger.log_source`` records what you read and which families it touches).
"""
from __future__ import annotations

GRADE_TEXT = {
    "A": "Replicated published evidence; runnable as written",
    "B": "Published evidence for the mechanism or a close cousin; decayed, different asset class, or cost-sensitive",
    "C": "Practitioner rule or plausible mechanism; no credible out-of-sample evidence",
    "D": "No evidence, evidence points the other way, or not testable honestly with this data",
}

# family number -> (grade, basis, references)
EVIDENCE: dict[int, tuple[str, str, tuple[str, ...]]] = {
    1: ("A", "Time-series momentum and volatility scaling are documented across futures markets for decades", ("Moskowitz, Ooi, Pedersen 2012", "Barroso, Santa-Clara 2015")),
    2: ("C", "Evidence supports trend, not the Kalman filter as the better timer", ()),
    3: ("C", "Ehlers filters are practitioner tools; the kill condition itself calls it a re-skin of an EMA cross", ()),
    4: ("B", "Cross-sectional plus absolute momentum is documented; the rotation form needs a basket and decays", ("Jegadeesh, Titman 1993",)),
    5: ("C", "Volatility-expansion exits are plausible risk control with no published edge", ()),
    6: ("D", "Blocked: the engine cannot scale in, so a faithful test does not exist", ()),
    7: ("C", "Slope significance is a filter on trend with no direct evidence", ()),
    8: ("C", "Hurst / DFA gating of pullbacks is unvalidated; estimates are noisy on short windows", ()),
    9: ("C", "Multi-timeframe agreement is practitioner lore; the gain over one trend filter is untested", ()),
    10: ("D", "Dominant-cycle detection on noisy bars has not been shown to add edge", ()),
    11: ("C", "Adaptive fair-value reversion is plausible; no direct evidence for the adaptive part", ()),
    12: ("C", "OU half-life gating comes from pairs trading; the single-instrument form is unvalidated", ()),
    13: ("C", "Variance-ratio tests document short-horizon anti-persistence; the trading rule is untested", ("Lo, MacKinlay 1988",)),
    14: ("C", "Prior-close magnet is a plausible anchor effect with no published net edge", ()),
    15: ("C", "Anchored VWAP reversion is practitioner lore", ()),
    16: ("C", "Support / resistance bounces have some intraday FX evidence; a multi-touch box fade is a stretch", ("Osler 2000",)),
    17: ("B", "Pairs and basket reversion earned returns historically, then decayed", ("Gatev, Goetzmann, Rouwenhorst 2006",)),
    18: ("D", "Blocked: needs a front / next contract spread series the bundled data does not have", ()),
    19: ("D", "Published intraday momentum finds the first half-hour predicts the LAST half-hour with the same sign, the opposite of this fade", ("Gao, Han, Li, Zhou 2018",)),
    20: ("C", "Order clustering at round numbers is documented in FX; a net edge from fading the first tag is not", ("Osler 2003",)),
    21: ("C", "Short-term reversal is a stock-level result; at index level the evidence is mixed", ("Lehmann 1990", "Jegadeesh 1990")),
    22: ("C", "Opening-drive failure is a practitioner pattern", ()),
    23: ("C", "NR4 / NR7 compression is practitioner lore", ()),
    24: ("C", "Inside-bar resolution in trend direction is practitioner lore", ()),
    25: ("B", "Trading-range breaks showed predictive power in early studies, then weakened under data-snooping corrections", ("Brock, Lakonishok, LeBaron 1992", "Sullivan, Timmermann, White 1999")),
    26: ("C", "Monthly opening-range setting is a calendar heuristic", ()),
    27: ("C", "Vol-of-vol compression is a plausible regime-shift flag with no direct evidence", ()),
    28: ("C", "Breakout-retest is practitioner lore", ()),
    29: ("D", "Chart-pattern geometry (triangles, wedges) carries little tradable information once costs are paid", ("Lo, Mamaysky, Wang 2000",)),
    30: ("C", "Volume-profile traversal is auction-theory folklore without published tests", ()),
    31: ("C", "Value-area acceptance is auction-theory folklore without published tests", ()),
    32: ("C", "Gap-and-hold acceptance is a practitioner pattern", ()),
    33: ("C", "Nested squeeze release is a practitioner pattern", ()),
    34: ("D", "Accumulation / manipulation / distribution is an interpretive narrative with no falsifiable published test", ()),
    35: ("B", "Intraday FX return and order-flow patterns across sessions are documented", ("Breedon, Ranaldo 2013",)),
    36: ("B", "Intraday momentum and opening-range breakout evidence exist, mostly for US equities and index futures", ("Gao, Han, Li, Zhou 2018", "Zarattini, Aziz 2023")),
    37: ("C", "Midday compression then a 2 pm expansion is a practitioner pattern", ()),
    38: ("B", "Intraday momentum into the close is documented; decays and is cost-sensitive", ("Gao, Han, Li, Zhou 2018",)),
    39: ("D", "Blocked: needs the published closing-imbalance feed and there is no adapter", ()),
    40: ("C", "Weekend-gap fill is a practitioner pattern", ()),
    41: ("C", "The weekend effect is documented but has decayed", ("French 1980",)),
    42: ("B", "Pre-announcement drift is published, and it weakened after publication", ("Lucca, Moench 2015",)),
    43: ("C", "Month-end rebalancing flows are plausible; the reversal rule is untested", ()),
    44: ("C", "Roll and expiry week volatility is a practitioner pattern", ()),
    45: ("D", "Blocked: needs a per-contract roll calendar and the bundled series are continuous", ()),
    46: ("C", "Thin-session fades are plausible liquidity effects without published tests", ()),
    47: ("C", "Calendar anomalies mostly fail data-snooping tests", ("Sullivan, Timmermann, White 2001",)),
    48: ("B", "Intraday seasonality in returns is documented in equities and FX", ("Heston, Korajczyk, Sadka 2010", "Breedon, Ranaldo 2013")),
    49: ("D", "VPIN's predictive power is largely mechanical (volume and volatility); the bar-based version is weaker still", ("Andersen, Bondarenko 2014",)),
    50: ("D", "Cumulative delta divergence needs true trade-sign data; the bar approximation has no evidence", ()),
    51: ("D", "Naked POC magnet is trading folklore with no published test", ()),
    52: ("D", "Poor high / low repair is trading folklore with no published test", ()),
    53: ("C", "Stop clustering near round numbers and highs is documented; a net edge from fading the sweep is not", ("Osler 2003",)),
    54: ("C", "Spread estimators exist; the fade of a spread spike is untested", ("Corwin, Schultz 2012",)),
    55: ("C", "The illiquidity premium is a cross-sectional stock result; a single-instrument form is a stretch", ("Amihud 2002",)),
    56: ("D", "Blocked: needs trade-level data", ()),
    57: ("D", "Blocked: needs tick data to build dollar bars", ()),
    58: ("C", "Pre-market levels as support and resistance is practitioner lore", ()),
    59: ("D", "Blocked: needs level-2 data and a queue-position model", ()),
    60: ("B", "The variance risk premium predicts equity returns at monthly horizons", ("Bollerslev, Tauchen, Zhou 2009",)),
    61: ("C", "VIX curve inversion as a risk-off flag is practitioner lore", ()),
    62: ("B", "Volatility-managed portfolios improve Sharpe in-sample; out-of-sample results are disputed", ("Moreira, Muir 2017", "Cederburg et al. 2020")),
    63: ("C", "VVIX spikes as a regime flag are untested", ()),
    64: ("C", "SKEW extremes as a contrarian signal are untested", ()),
    65: ("B", "Volatility rises into scheduled announcements and falls after; the fade trade itself is less certain", ("Ederington, Lee 1993",)),
    66: ("C", "Range-exhaustion fades are practitioner lore", ()),
    67: ("C", "Forecast-versus-realized volatility gating is plausible with no direct evidence", ()),
    68: ("C", "Jump detection is established; the reversion of undetected-news jumps is untested", ("Lee, Mykland 2008",)),
    69: ("B", "Downside semivariance carries volatility-forecasting information", ("Patton, Sheppard 2015",)),
    70: ("C", "A credit-plus-dollar composite is plausible; no direct test", ()),
    71: ("C", "Dollar-trend carry-through to the majors is practitioner lore", ()),
    72: ("C", "The curve predicts recessions; a tradable tilt in index and gold is untested", ("Estrella, Hardouvelis 1991",)),
    73: ("C", "The gold / real-yield link is contemporaneous; a lead-lag edge is unproven", ("Erb, Harvey 2013",)),
    74: ("C", "Copper / gold as a growth proxy is practitioner lore", ()),
    75: ("C", "Commodity-currency lead-lag evidence runs from the currency to the commodity, not this way", ("Chen, Rogoff, Rossi 2010",)),
    76: ("C", "Same caveat as the oil / USDCAD family", ("Chen, Rogoff, Rossi 2010",)),
    77: ("C", "Gold / silver ratio reversion is practitioner lore", ()),
    78: ("C", "Announcement surprises move FX and gold within minutes; a bar-based edge is unproven", ("Andersen, Bollerslev, Diebold, Vega 2003",)),
    79: ("C", "COT extremes have mixed evidence", ("Wang 2003",)),
    80: ("C", "Index put / call extremes as a contrarian signal are untested; signed option volume carries information at stock level", ("Pan, Poteshman 2006",)),
    81: ("B", "Credit spreads lead real activity and equity risk; the trading rule is untested", ("Gilchrist, Zakrajsek 2012",)),
    82: ("B", "Cross-sectional momentum is documented across asset classes; a narrow FX / crypto basket is thin and cost-heavy", ("Jegadeesh, Titman 1993", "Menkhoff et al. 2012")),
    83: ("A", "Carry and momentum premia in currencies are replicated across samples and authors", ("Lustig, Roussanov, Verdelhan 2011", "Asness, Moskowitz, Pedersen 2013")),
    84: ("C", "Relative strength inside metals is the same construction as xs_momentum_basket without its evidence", ()),
    85: ("C", "Regime-switching models are established; their trading value is mixed", ("Hamilton 1989",)),
    86: ("C", "Change-point entries are plausible; the false-alarm rate is high", ()),
    87: ("C", "CUSUM drift detection is a standard test; a continuation edge is untested", ()),
    88: ("C", "Time-varying hedge ratios are plausible with no direct evidence of a better spread", ()),
    89: ("C", "Meta-labeling is a methodology with little independent replication", ("Lopez de Prado 2018",)),
    90: ("C", "A supervised model on barrier labels has little independent replication", ("Lopez de Prado 2018",)),
    91: ("B", "Combining many weak forecasts improves out-of-sample stability in return prediction", ("Rapach, Strauss, Zhou 2010",)),
    92: ("C", "Return predictors usually fail out of sample; a small causal ridge on price features is no exception without evidence", ("Welch, Goyal 2008",)),
    93: ("D", "Nearest-neighbour analogs on price windows have no evidence of beating chance", ()),
    94: ("C", "Seasonal-term forecasts under purged CV test the method, not an edge", ()),
    95: ("D", "Blocked: the engine cannot add to a position", ()),
    96: ("D", "Equity-curve timing re-times a signal after the fact; there is no evidence it adds expectancy", ()),
    97: ("C", "Time stops are risk control; the premise that no follow-through predicts a loser is untested", ()),
    98: ("C", "Funding-rate extremes in crypto perpetuals are plausible; evidence is thin", ()),
    99: ("C", "Open-interest drops as forced selling is plausible; evidence is thin", ()),
    100: ("B", "Perpetual-spot basis carry in crypto is documented in recent work and is capacity- and cost-limited", ("Schmeling, Schrimpf, Todorov 2023",)),
}


def _meta_by_number() -> dict:
    from app.search.families_v13 import V13_BLOCKED, V13_META
    return {m.number: m for m in list(V13_META.values()) + list(V13_BLOCKED.values())}


def family_grade(family: str | int) -> dict | None:
    """{number, family, grade, basis, refs, group, status} for a v13 family name or number; None for any other family
    (the other 117 registered families are not graded here)."""
    try:
        meta = _meta_by_number()
    except Exception:  # noqa: BLE001
        return None
    num = family if isinstance(family, int) else next((n for n, m in meta.items() if m.name == family), None)
    if num is None or num not in EVIDENCE or num not in meta:
        return None
    g, basis, refs = EVIDENCE[num]
    m = meta[num]
    return {"number": num, "family": m.name, "grade": g, "basis": basis, "refs": list(refs), "group": m.group, "status": m.status,
            "hypothesis": m.hypothesis}


def grade_table() -> list[dict]:
    """All 100 rows in family-number order."""
    rows = [family_grade(n) for n in range(1, 101)]
    return [r for r in rows if r]


def validate_coverage() -> dict:
    """Every one of the 100 numbered families must carry exactly one grade in A-D, a basis, and a blocked family may not be graded above D."""
    problems: list[str] = []
    meta = _meta_by_number()
    for n in range(1, 101):
        if n not in meta:
            problems.append(f"family {n}: missing from families_v13")
        if n not in EVIDENCE:
            problems.append(f"family {n}: no evidence grade")
            continue
        g, basis, _refs = EVIDENCE[n]
        if g not in GRADE_TEXT:
            problems.append(f"family {n}: grade {g!r} is not one of A-D")
        if not basis.strip():
            problems.append(f"family {n}: empty basis")
        if n in meta and meta[n].status == "blocked" and g != "D":
            problems.append(f"family {n}: blocked families cannot be graded above D")
    extra = sorted(set(EVIDENCE) - set(range(1, 101)))
    if extra:
        problems.append(f"grades for unknown family numbers: {extra}")
    counts = {k: sum(1 for v in EVIDENCE.values() if v[0] == k) for k in GRADE_TEXT}
    return {"ok": not problems, "problems": problems, "counts": counts, "n": len(EVIDENCE)}
