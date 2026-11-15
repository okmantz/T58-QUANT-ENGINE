"""Prop-firm fee schedule -- the structured form of ``Prop_Firm_Fees_and_Costs_Report`` (source: Prop_Firm_Rules_Report 2026-11-11).

One place for every cost figure the engines use: per-contract round-turn commissions by firm and platform, and evaluation / activation /
reset prices by plan and size. Every number carries an evidence tag so the engines can refuse to treat a weaker tier as final:

    "official"    read from the firm's own page / help centre
    "secondary"   reported by a reputable secondary source only            (the report's [S])
    "unverified"  could not be confirmed -- the value is None, never guessed
    "assumption"  a modelling choice the project made, not a fact about the firm

List prices before promo codes; every figure is a snapshot dated ``SNAPSHOT``. ``stale_after_days`` tells the UI when to warn.

Consumers: ``app.backtest.cost_policy`` (commissions per profile), ``app.prop.economics`` (cost per funded account), the Rulebook gates
(G0 sourcing check) and the prop-firm pages. Nothing here changes a rule; it only holds money.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SNAPSHOT = "2026-11-11"
STALE_AFTER_DAYS = 30

OFFICIAL, SECONDARY, UNVERIFIED, ASSUMPTION = "official", "secondary", "unverified", "assumption"


# ---- Round-turn commissions ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CommissionRow:
    """Round-turn $ per contract, all-in (exchange + NFA + broker) unless ``all_in`` is False. None = unverified (never guessed)."""
    firm: str
    platform: str
    ES: float | None = None
    NQ: float | None = None
    GC: float | None = None
    MES: float | None = None
    MNQ: float | None = None
    MGC: float | None = None
    tier: str = SECONDARY
    all_in: bool = True
    note: str = ""

    def get(self, symbol: str) -> float | None:
        return getattr(self, symbol.upper(), None)


COMMISSIONS: tuple[CommissionRow, ...] = (
    CommissionRow("alpha", "all", 4.78, 4.78, 5.22, 1.32, 1.32, 1.82, OFFICIAL, note="official 'Permitted Products and Fees' PDF; RTY/YM $4.78, CL $5.02, MCL $1.62, SI $5.22"),
    CommissionRow("apex", "tradovate", 3.10, 3.10, 3.54, 1.04, 1.04, 1.34, OFFICIAL),
    CommissionRow("apex", "wealthcharts", 3.10, 3.10, 3.54, 1.04, None, 1.52, OFFICIAL, note="MNQ unverified"),
    CommissionRow("apex", "rithmic", 3.98, 3.98, 4.62, 1.02, 1.02, 1.52, OFFICIAL),
    CommissionRow("topstep", "topstepx", 3.78, 3.78, 4.32, 1.22, 1.22, 1.92, OFFICIAL,
                  note="updated 2026-09-30; CL 4.02, MCL 1.72. A separate LFA article lists ES 3.80 / NQ 3.80 / GC 4.24 -- which governs is unverified"),
    CommissionRow("lucid", "all", 3.50, 3.50, None, None, None, None, SECONDARY,
                  note="ES/NQ $3.50 [S]; GC and micros unverified in the report. The project specification carries $4.60 GC / $1.00 MES-MNQ / $1.60 MGC "
                       "from secondary reprints -- see LUCID_SPEC_COMMISSIONS (tier secondary)."),
    CommissionRow("mffu", "rithmic", 4.68, 4.68, 5.12, 1.90, 1.90, 2.20, SECONDARY, note="CL 4.92"),
    CommissionRow("mffu", "tradovate", 4.26, 4.26, None, 1.42, None, None, SECONDARY, note="CL 4.60, MCL 1.72 (partial table)"),
    CommissionRow("tradeify", "tradovate", 5.76, 5.76, None, 1.82, 1.82, 1.82, SECONDARY, note="GC 6.20 conflicts with another source -> unverified"),
    CommissionRow("tpt", "all", 4.50, 4.50, 4.50, 1.50, 1.50, 1.50, OFFICIAL, note="uniform $4.50 per standard contract, $1.50 per micro"),
    CommissionRow("earn2trade", "all", None, None, None, None, None, None, OFFICIAL, note="minis unverified; micros $0.82-$1.20 per SIDE ($1.64-$2.40 RT)"),
    CommissionRow("bulenox", "all", 4.18, 4.18, 4.62, 1.22, 1.22, 1.52, OFFICIAL, note="official rate sheet 2026-08-11; per side ES/NQ 2.09, GC 2.31, micros 0.61, MGC 0.76"),
    CommissionRow("elite_trader_funding", "all", 4.08, 4.08, 4.62, 1.12, 1.02, 1.52, OFFICIAL, note="2x per-side; whether exchange/NFA are charged on top is unverified"),
    CommissionRow("tradeday", "all", 5.76, 5.76, 6.20, 1.90, 1.90, 2.40, OFFICIAL, note="per side 2.88 / 3.10 / 0.95 / 1.20; includes brokerage, NFA, clearing and exchange"),
    CommissionRow("oneup", "all", 5.00, 5.00, 5.00, 2.00, 2.00, 2.00, OFFICIAL, note="flat $5.00 RT standard; micros $2.00 eval / $1.20 funded"),
    CommissionRow("leeloo", "all", None, None, None, None, None, None, UNVERIFIED, note="no per-contract table published"),
    CommissionRow("top_one_futures", "all", 5.76, 5.76, 6.20, 1.90, 1.90, 2.40, OFFICIAL, note="MGC secondary; CL 6.00, NG 6.20"),
)

# The project specification (Project_Specifications.md section 2.3) cost model for LucidPro -- the "base" and "stress" columns the
# methodology fixes BEFORE any test. ES/NQ base is the report's $3.50; the other base cells are secondary reprints of Lucid's list
# ($1.75/side minis, $0.50/side micro indices, $2.30/side GC, $0.80/side MGC). Stress = the Alpha official all-in schedule.
LUCID_SPEC_COMMISSIONS = CommissionRow("lucid", "spec_base", 3.50, 3.50, 4.60, 1.00, 1.00, 1.60, SECONDARY,
                                       note="Project_Specifications 2.3 base case; confirm whether exchange/NFA are included (open item 9)")
STRESS_COMMISSIONS = COMMISSIONS[0]      # Alpha all-in, used as the conservative proxy (spec 2.3 stress case)

# Instruments the schedule can price (the others fall back to the instrument registry).
PRICED_SYMBOLS = ("ES", "NQ", "GC", "MES", "MNQ", "MGC")
# Same published schedule applies to the other index futures at the firms that list them (Alpha: RTY, YM = ES; micros follow MES).
_MINI_ALIAS = {"RTY": "ES", "YM": "ES"}
_MICRO_ALIAS = {"M2K": "MES", "MYM": "MES"}


def commission_row(firm: str, platform: str | None = None) -> CommissionRow | None:
    rows = [r for r in COMMISSIONS if r.firm == firm]
    if platform:
        for r in rows:
            if r.platform == platform:
                return r
    return rows[0] if rows else None


def commission_rt(symbol: str, *, firm: str = "lucid", platform: str | None = None, profile: str = "base") -> float | None:
    """Round-turn commission per contract for ``symbol`` under a profile. ``base`` = the firm's own schedule (Lucid: the spec base column);
    ``stress`` = the Alpha all-in schedule (conservative proxy). Returns None when the schedule has no verified figure for that symbol."""
    s = _MINI_ALIAS.get(symbol.upper()) or _MICRO_ALIAS.get(symbol.upper()) or symbol.upper()
    if profile == "stress":
        return STRESS_COMMISSIONS.get(s)
    if firm == "lucid" and platform in (None, "all", "spec_base"):
        v = LUCID_SPEC_COMMISSIONS.get(s)
        if v is not None:
            return v
    row = commission_row(firm, platform)
    return row.get(s) if row else None


# ---- Plan fees --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PlanFee:
    firm: str
    plan: str
    size: int                          # account size, USD
    price: float | None                # evaluation price (one-time, or per billing period when ``monthly``)
    monthly: bool = False              # True = subscription rebilled every ``period_days`` until pass/cancel
    activation: float | None = 0.0     # fee charged when the evaluation is passed
    reset: float | None = None         # None = unverified / not published
    tier: str = SECONDARY
    currency: str = "USD"
    note: str = ""
    period_days: int = 30


def _p(firm, plan, size, price, **kw) -> PlanFee:
    return PlanFee(firm, plan, int(size), price, **kw)


PLANS: tuple[PlanFee, ...] = (
    # Alpha Futures -- monthly until pass (Direct is one-time). Activation $0 (Advanced: $0 for purchases after 2026-07-08).
    _p("alpha", "zero", 25_000, 89, monthly=True, reset=79, tier=OFFICIAL), _p("alpha", "zero", 50_000, 169, monthly=True, reset=149, tier=OFFICIAL),
    _p("alpha", "zero", 100_000, 279, monthly=True, reset=249, tier=OFFICIAL),
    _p("alpha", "standard", 50_000, 129, monthly=True, reset=109, tier=OFFICIAL), _p("alpha", "standard", 100_000, 239, monthly=True, reset=199, tier=OFFICIAL),
    _p("alpha", "standard", 150_000, 349, monthly=True, reset=289, tier=OFFICIAL),
    _p("alpha", "advanced", 50_000, 209, monthly=True, reset=189, tier=OFFICIAL), _p("alpha", "advanced", 100_000, 349, monthly=True, reset=319, tier=OFFICIAL),
    _p("alpha", "advanced", 150_000, 489, monthly=True, reset=449, tier=OFFICIAL),
    _p("alpha", "direct", 25_000, 349, activation=0.0, reset=None, tier=OFFICIAL, note="launched 2026-07-07; no reset listed"),
    _p("alpha", "direct", 50_000, 519, reset=None, tier=OFFICIAL), _p("alpha", "direct", 100_000, 689, reset=None, tier=OFFICIAL),
    _p("alpha", "direct", 150_000, 859, reset=None, tier=OFFICIAL),
    # Apex (one-time 30-day evaluations since 2026-03-01; no resets -- rebuy). All prices are secondary consensus.
    _p("apex", "eod_standard", 25_000, 490, activation=109, reset=None), _p("apex", "eod_standard", 50_000, 590, activation=129),
    _p("apex", "eod_standard", 100_000, 1190, activation=139, note="one source says $129 activation"), _p("apex", "eod_standard", 150_000, 2190, activation=159),
    _p("apex", "eod_no_activation", 25_000, 1090), _p("apex", "eod_no_activation", 50_000, 1190), _p("apex", "eod_no_activation", 100_000, 1590),
    _p("apex", "eod_no_activation", 150_000, 2490),
    _p("apex", "intraday_standard", 25_000, 167, activation=89), _p("apex", "intraday_standard", 50_000, 249, activation=99),
    _p("apex", "intraday_standard", 100_000, 790, activation=129), _p("apex", "intraday_standard", 150_000, 1190, activation=149),
    _p("apex", "intraday_no_activation", 25_000, 690), _p("apex", "intraday_no_activation", 50_000, 799), _p("apex", "intraday_no_activation", 100_000, 999),
    _p("apex", "intraday_no_activation", 150_000, 1890),
    # Topstep -- Trading Combine is a monthly subscription; $149 activation per XFA (Standard path); reset = monthly price.
    _p("topstep", "combine_standard", 50_000, 49, monthly=True, activation=149, reset=49, tier=OFFICIAL),
    _p("topstep", "combine_standard", 100_000, 99, monthly=True, activation=149, reset=99, tier=OFFICIAL),
    _p("topstep", "combine_standard", 150_000, 199, monthly=True, activation=149, reset=199, tier=OFFICIAL),
    _p("topstep", "combine_no_activation", 50_000, 95, monthly=True, activation=0.0, reset=95, note="$85/mo with DLL added"),
    _p("topstep", "combine_no_activation", 100_000, 149, monthly=True, activation=0.0, reset=149, note="$129 with DLL"),
    _p("topstep", "combine_no_activation", 150_000, 229, monthly=True, activation=0.0, reset=229, note="$199 with DLL"),
    # Lucid -- all one-time, $0 activation, 90/10. DLL ON prices. LucidPro 100K is UNVERIFIED in the report ($285 is the project's [ASM] list value).
    _p("lucid", "pro", 25_000, 108, reset=75), _p("lucid", "pro", 50_000, 172, reset=120),
    _p("lucid", "pro", 100_000, 285, reset=None, tier=ASSUMPTION, note="UNVERIFIED in the fee report; $285 = Project_Specifications list value [ASM]; trackers show $215-$314"),
    _p("lucid", "pro", 150_000, 365, reset=255),
    _p("lucid", "flex", 25_000, 65, reset=45), _p("lucid", "flex", 50_000, 115), _p("lucid", "flex", 100_000, 215), _p("lucid", "flex", 150_000, 323),
    _p("lucid", "daily", 25_000, 79, reset=55, note="intraday-eval; $93 / reset $65 for EOD-eval"),
    _p("lucid", "direct", 25_000, 329, reset=None, note="no eval; funded accounts cannot be reset"), _p("lucid", "direct", 150_000, 836, reset=None),
    # MyFundedFutures (one-time, $0 activation, reset not published)
    _p("mffu", "rapid", 25_000, 145), _p("mffu", "rapid", 50_000, 209, note="~$125-157 at promo checkout"), _p("mffu", "rapid_eod", 25_000, 145),
    _p("mffu", "rapid_eod", 50_000, 225), _p("mffu", "builder", 25_000, 105), _p("mffu", "builder", 50_000, 153), _p("mffu", "builder", 100_000, 282),
    _p("mffu", "builder", 150_000, 398), _p("mffu", "pro", 50_000, 265),
    # Tradeify (one-time since 2026-03-31)
    _p("tradeify", "growth", 25_000, 99, reset=60), _p("tradeify", "growth", 50_000, 145, reset=95), _p("tradeify", "growth", 100_000, 255, reset=169),
    _p("tradeify", "growth", 150_000, 369, reset=229), _p("tradeify", "select", 25_000, 109), _p("tradeify", "select", 50_000, 165, reset=109),
    _p("tradeify", "select", 100_000, 265), _p("tradeify", "select", 150_000, 369),
    _p("tradeify", "lightning", 25_000, 345), _p("tradeify", "lightning", 50_000, 492), _p("tradeify", "lightning", 100_000, 660), _p("tradeify", "lightning", 150_000, 796),
    # Take Profit Trader -- Test (monthly) -> PRO ($130 activation)
    _p("tpt", "test", 25_000, 150, monthly=True, activation=130, reset=79, note="official homepage activation"), _p("tpt", "test", 50_000, 170, monthly=True, activation=130, reset=99),
    _p("tpt", "test", 75_000, 245, monthly=True, activation=130, reset=139), _p("tpt", "test", 100_000, 330, monthly=True, activation=130, reset=169),
    _p("tpt", "test", 150_000, 360, monthly=True, activation=130, reset=199),
    # Earn2Trade (monthly; $139 LiveSim activation deducted from the first withdrawal)
    _p("earn2trade", "tcp", 25_000, 150, monthly=True, activation=139, tier=OFFICIAL), _p("earn2trade", "tcp", 50_000, 190, monthly=True, activation=139),
    _p("earn2trade", "tcp", 100_000, 350, monthly=True, activation=139, reset=100), _p("earn2trade", "gauntlet_mini", 50_000, 170, monthly=True, activation=139, tier=OFFICIAL),
    _p("earn2trade", "gauntlet_mini", 100_000, 315, monthly=True, activation=139, reset=100), _p("earn2trade", "gauntlet_mini", 150_000, 375, monthly=True, activation=139, reset=130),
    _p("earn2trade", "gauntlet_mini", 200_000, 550, monthly=True, activation=139, reset=155),
    # Bulenox (one-time, 30-day access since 2026-08)
    _p("bulenox", "qualification", 50_000, 175, activation=148, reset=78),
    # Elite Trader Funding
    _p("elite_trader_funding", "one_step", 50_000, 207, monthly=True, activation=177, reset=47), _p("elite_trader_funding", "one_step", 100_000, 257, monthly=True, activation=247, reset=47),
    _p("elite_trader_funding", "one_step", 150_000, 347, monthly=True, activation=247, reset=47),
    _p("elite_trader_funding", "eod", 50_000, 347, monthly=True, activation=177, reset=47), _p("elite_trader_funding", "eod", 100_000, 487, monthly=True, activation=257, reset=47),
    # TradeDay (list price per month; sale prices are promotions)
    _p("tradeday", "quickpay_intraday", 25_000, 100, monthly=True, reset=45), _p("tradeday", "quickpay_intraday", 50_000, 131, monthly=True, reset=59),
    _p("tradeday", "quickpay_intraday", 100_000, 240, monthly=True, reset=108), _p("tradeday", "quickpay_intraday", 150_000, 360, monthly=True, reset=162),
    _p("tradeday", "quickpay_eod", 25_000, 120, monthly=True, reset=54), _p("tradeday", "quickpay_eod", 50_000, 175, monthly=True, reset=79),
    _p("tradeday", "quickpay_eod", 100_000, 285, monthly=True, reset=129), _p("tradeday", "quickpay_eod", 150_000, 400, monthly=True, reset=180),
    _p("tradeday", "fastpass_eod", 25_000, 130, monthly=True, reset=65), _p("tradeday", "fastpass_eod", 50_000, 189, monthly=True, reset=95),
    _p("tradeday", "fastpass_eod", 100_000, 350, monthly=True, reset=175), _p("tradeday", "fastpass_eod", 150_000, 530, monthly=True, reset=265),
    # OneUp Trader (monthly; half at sign-up, half as activation)
    _p("oneup", "evaluation", 25_000, 65, monthly=True, activation=65, reset=50, tier=OFFICIAL), _p("oneup", "evaluation", 50_000, 75, monthly=True, activation=75, reset=50, tier=OFFICIAL),
    _p("oneup", "evaluation", 100_000, 150, monthly=True, activation=150, reset=100), _p("oneup", "evaluation", 150_000, 175, monthly=True, activation=175, reset=100),
    _p("oneup", "evaluation", 250_000, 325, monthly=True, activation=325, reset=100),
    # Leeloo (per-size prices are [S] and drift)
    _p("leeloo", "foundation_launch", 50_000, 180, monthly=True, activation=0.0, reset=85, note="PA $88/mo or $250 once"),
    # Top One Futures
    _p("top_one_futures", "elite_access", 25_000, 39, activation=139, reset=35, note="EOD activation; intraday activation $69"),
    _p("top_one_futures", "elite_access", 50_000, 39, activation=189, reset=35, note="intraday activation $94"),
    _p("top_one_futures", "elite_access", 100_000, 39, activation=259, reset=35), _p("top_one_futures", "elite_access", 150_000, 39, activation=359, reset=35),
    # CFD / preset firms (EUR figures converted at 1 EUR = 1.16 USD, the report's rate)
    _p("ftmo", "two_step", 10_000, 89, currency="EUR", reset=89, tier=OFFICIAL, note="refunded with first reward; reset = full price"), _p("ftmo", "two_step", 25_000, 250, currency="EUR", reset=250),
    _p("ftmo", "two_step", 50_000, 345, currency="EUR", reset=345), _p("ftmo", "two_step", 100_000, 540, currency="EUR", reset=540), _p("ftmo", "two_step", 200_000, 1080, currency="EUR", reset=1080),
    _p("ftmo", "one_step", 10_000, 79, currency="EUR"), _p("ftmo", "one_step", 25_000, 199, currency="EUR"), _p("ftmo", "one_step", 50_000, 319, currency="EUR"),
    _p("ftmo", "one_step", 100_000, 499, currency="EUR"), _p("ftmo", "one_step", 200_000, 999, currency="EUR"),
    _p("fundednext", "stellar_2step", 25_000, 199.99, tier=OFFICIAL), _p("fundednext", "stellar_2step", 50_000, 299.99, tier=OFFICIAL),
    _p("fundednext", "stellar_2step", 100_000, 549.99, tier=OFFICIAL), _p("fundednext", "stellar_2step", 200_000, 999.99, tier=OFFICIAL, note="blog says $1,099.99; help centre used"),
    _p("fundednext", "stellar_1step", 25_000, 219.99), _p("fundednext", "stellar_1step", 50_000, 329.99), _p("fundednext", "stellar_1step", 100_000, 569.99),
    _p("e8", "one", 25_000, 188), _p("e8", "one", 50_000, 288), _p("e8", "one", 100_000, 488), _p("e8", "one", 200_000, 798),
    _p("the5ers", "high_stakes_new", 25_000, 176, note="$195 on another page"), _p("the5ers", "high_stakes_new", 50_000, 249, note="$279 on another page"),
    _p("the5ers", "high_stakes_new", 100_000, 405), _p("the5ers", "high_stakes_classic", 100_000, 455),
    _p("funderpro", "one_phase", 25_000, 219), _p("funderpro", "one_phase", 100_000, 539), _p("funderpro", "one_phase", 200_000, 989),
)

EUR_USD = 1.16        # the report's own conversion (approx., Nov 2026)


def plan_fees(firm: str, plan: str | None = None, size: int | None = None) -> list[PlanFee]:
    out = [p for p in PLANS if p.firm == firm and (plan is None or p.plan == plan) and (size is None or p.size == int(size))]
    return out


def usd(price: float | None, currency: str = "USD") -> float | None:
    if price is None:
        return None
    return round(price * EUR_USD, 2) if currency == "EUR" else float(price)


def cost_per_funded_account(price: float | None, p_pass: float, *, reset: float | None = None, activation: float = 0.0,
                            monthly: bool = False, months_per_attempt: float = 1.0) -> dict:
    """Expected evaluation cost per funded account obtained (methodology section 3.4): buy-new = P / p; reset route = P + R (1/p - 1).
    Monthly subscriptions are charged ``months_per_attempt`` times per attempt. Activation is paid once, on the pass."""
    if price is None or not (0.0 < p_pass <= 1.0):
        return {"buy_new": None, "reset_route": None, "note": "price unknown or pass probability not positive"}
    per_attempt = price * (months_per_attempt if monthly else 1.0)
    buy_new = per_attempt / p_pass + activation
    reset_route = None if reset is None else per_attempt + reset * (1.0 / p_pass - 1.0) + activation
    return {"buy_new": round(buy_new, 2), "reset_route": None if reset_route is None else round(reset_route, 2)}


def stamp_age_days(today: date | None = None) -> int:
    today = today or date.today()
    return (today - date.fromisoformat(SNAPSHOT)).days


def is_stale(today: date | None = None) -> bool:
    return stamp_age_days(today) > STALE_AFTER_DAYS
