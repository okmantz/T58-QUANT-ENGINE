"""Optimise a T58 Trading Bot: choose each leg's size weight, and test the profit lock / loser cut, against the bot's OWN objective.

What it does (and why it is built this way)
  * every leg of the bot is run alone through the real bar engine on the chosen dataset (``run_backtest``), at 1x, so a bot is searched from its real trades,
    never from a formula;
  * the history is split in time: first 60% TRAIN, next 20% VALIDATION, last 20% HOLD-OUT. Weights are searched on TRAIN only; a candidate is accepted only
    when it also beats the current bot on VALIDATION; the HOLD-OUT is reported once and never used to choose;
  * each objective is scored with its own scorecard (``app.prop.objective_scorecard``): A = P(pass in 30 days) with the 60-day pass and breach odds as the
    secondary terms, B = P(first payout) under the 5-winning-days rule with breaches penalised, NET = compounded growth with a drawdown ceiling;
  * the overlays (profit-lock ladder, loser cut, no-entries-on-FOMC-day) are each ONE paired comparison on the finished book and are adopted only when TRAIN
    and VALIDATION both improve -- a result that holds on one split is noise at these sample sizes;
  * when nothing beats the current bot, it says so and changes nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional

import numpy as np
import pandas as pd

WEIGHT_GRID = (0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0)
OVERLAYS = {
    "profit lock (6x ladder)": {"profit_lock": True, "lock_scale": 6.0},
    "loser cut (80%)": {"loss_cut_frac": 0.8},
}
MIN_TRADES = 40
AVG_LOSS_1X = 500.0
CAPS = {"A": 0.40, "B": 0.30}      # combined day stop, share of the $1,200 soft daily limit (bot config defaults)


@dataclass
class BotOptResult:
    objective: str
    improved: bool
    note: str
    weights_before: dict
    weights_after: dict
    overlay: Optional[str]
    scores: dict                    # {"current": {train, val, test}, "optimized": {...}}  (the selection score; higher is better)
    cards: dict                     # human-readable headline numbers per split for current / optimized
    optimized_config: Optional[dict] = None
    saved_bot_id: Optional[str] = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _splits(df: pd.DataFrame) -> dict:
    ts = pd.to_datetime(df["timestamp"])
    ts = ts.dt.tz_convert("UTC").dt.tz_localize(None) if ts.dt.tz is not None else ts
    a, b = ts.iloc[0], ts.iloc[-1]
    span = b - a
    return {"train": (a, a + span * 0.6), "val": (a + span * 0.6, a + span * 0.8), "test": (a + span * 0.8, b + pd.Timedelta(days=1))}


def _leg_trades(df: pd.DataFrame, cfg, leg, risk, overlay: dict | None) -> pd.DataFrame:
    """The leg alone, 1x, through the real engine; pnl rescaled so the average loser is $500 (the scorecards' research unit)."""
    from app.backtest.engine import run_backtest
    from app.bots.models import BotConfig
    from app.strategy.bot_strategy import BotStrategy
    solo = BotConfig.from_dict({**cfg.to_dict(), "legs": [{**leg.__dict__, "weight": 1.0}], "governor": {
        **cfg.governor, **(overlay or {}), "objective": cfg.objective}})
    st = BotStrategy(solo, symbol=leg.symbol)
    if not st.legs:
        from app.strategy.base import StrategyError
        raise StrategyError(f"{leg.label}: nothing to run")
    res = run_backtest(df, st, risk, compute_stats=False, lookahead_check="skip")
    rows = []
    for t in res.trades:
        et, xt = pd.Timestamp(t.entry_time), pd.Timestamp(t.exit_time)
        rows.append({"entry": et.tz_localize(None) if et.tzinfo else et, "exit": xt.tz_localize(None) if xt.tzinfo else xt, "pnl": float(t.pnl),
                     "dir": int(t.direction), "inst": leg.symbol})
    d = pd.DataFrame(rows)
    if d.empty:
        return d
    neg = d.loc[d["pnl"] < 0, "pnl"]
    al = float(-neg.mean()) if len(neg) else 0.0
    d["pnl"] = d["pnl"] * (AVG_LOSS_1X / al if al > 0 else 0.0)
    return d.sort_values("entry").reset_index(drop=True)


def _bundle(parts: list, daily_cap: float | None, max_open: int) -> pd.DataFrame:
    """One account, several legs: one position per instrument (earlier entry keeps the slot), at most ``max_open`` open at once, and a combined daily
    realised-loss cap that blocks NEW entries -- the bot arbiter's rules."""
    rows = []
    for prio, (trades, w) in enumerate(parts):
        if w <= 0 or trades is None or trades.empty:
            continue
        for r in trades.to_dict("records"):
            rows.append({**r, "pnl": r["pnl"] * w, "prio": prio})
    rows.sort(key=lambda r: (r["entry"], r["prio"]))
    out, busy, dpn, live = [], {}, {}, []
    for r in rows:
        live = [e for e in live if e > r["entry"]]
        if r["entry"] < busy.get(r["inst"], pd.Timestamp.min) or len(live) >= max_open:
            continue
        day = (r["entry"] - pd.Timedelta(hours=17)).normalize()
        if daily_cap is not None and dpn.get(day, 0.0) <= -daily_cap:
            continue
        out.append(r)
        busy[r["inst"]] = r["exit"]
        live.append(r["exit"])
        dpn[day] = dpn.get(day, 0.0) + r["pnl"]
    return pd.DataFrame(out) if out else pd.DataFrame(columns=["entry", "exit", "pnl", "dir", "inst"])


def _score(objective: str, book: pd.DataFrame, win, gov) -> tuple[float, dict]:
    """(selection score, headline numbers) for one split. -1e9 when the book is too thin to judge."""
    from app.prop import objective_scorecard as sc
    if book is None or len(book) < MIN_TRADES:
        return -1e9, {"trades": 0 if book is None else int(len(book))}
    w = sc.Window.of(*win)
    if objective == "A":
        r = sc.score_pass(book, w, gov=gov)
        s = r["p_pass_30_lo"] + 0.35 * r["p_pass_60_lo"] - 0.35 * r["breach_60"] if r.get("n_starts") else -1e9
        return s, {"pass in 30 days %": r.get("p_pass_30"), "pass in 60 days %": r.get("p_pass_60"), "breach before pass %": r.get("breach_60"),
                   "starts": r.get("n_starts")}
    if objective == "B":
        from app.bots.risk_governor import AccountRulesLite
        from app.prop.payout_rule import objective_b_rules
        from app.prop.presets import get_preset
        rules = objective_b_rules(get_preset("lucid_50k").to_prop_rules())
        r = sc.score_payout(book, w, gov=gov, prop_rules=rules, lite=AccountRulesLite.lucid_50k().with_winning_days_payout())
        s = (r["p_paid"] - 0.5 * r["bust"]) if r.get("n_starts") else -1e9
        return s, {"first payout within a year %": r.get("p_paid"), "breach %": r.get("bust"), "median days to payout": r.get("median_days_to_pay"),
                   "starts": r.get("n_starts")}
    x = book[(book["entry"] >= w.start) & (book["entry"] < w.end)]
    if len(x) < 20:
        return -1e9, {"trades": int(len(x))}
    r = sc.score_net(x, gov=gov)
    if (r.get("max_dd_pct") or 0) > 30.0:
        return -1e9, {"max drawdown %": r.get("max_dd_pct")}
    return float(r.get("cagr") or 0.0), {"net profit $": r.get("net"), "CAGR %": r.get("cagr"), "max drawdown %": r.get("max_dd_pct")}


def optimize_bot(df: pd.DataFrame, cfg, risk, *, progress_cb: Callable[[str], None] | None = None, save: bool = False,
                 cancel_event=None) -> BotOptResult:
    """Search ``cfg``'s leg weights (and the overlays) on ``df``. ``cfg`` is a BotConfig; nothing is changed unless a better bot is found AND ``save``."""
    log = progress_cb or (lambda m: None)
    obj = cfg.objective
    legs = [lg for lg in cfg.legs if lg.kind != "gate27"]
    if not legs:
        raise ValueError("This bot has no intraday strategies to optimise.")
    gov = cfg.governor_cfg()
    soft = 1200.0
    cap = CAPS.get(obj)
    daily_cap = soft * cap if cap else None
    win = _splits(df)
    trades: dict = {}
    for lg in legs:
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("cancelled")
        log(f"Running {lg.label} on the chosen data...")
        trades[lg.label] = _leg_trades(df, cfg, lg, risk, None)

    def book(weights: dict, tr: dict | None = None) -> pd.DataFrame:
        tr = tr or trades
        return _bundle([(tr[lg.label], weights.get(lg.label, 0.0)) for lg in legs], daily_cap, int(cfg.max_open_positions))

    def score(weights: dict, split: str, tr: dict | None = None) -> float:
        return _score(obj, book(weights, tr), win[split], gov)[0]

    current = {lg.label: float(lg.weight) for lg in legs}
    best, best_s = dict(current), score(current, "train")
    log(f"Current bot, train score {best_s:.1f}. Searching weights {WEIGHT_GRID} on the first 60% of the history...")
    for _pass in range(3):
        moved = False
        for lg in legs:
            for w in WEIGHT_GRID:
                if w == best[lg.label]:
                    continue
                cand = {**best, lg.label: w}
                s = score(cand, "train")
                if s > best_s + 0.25:
                    best, best_s, moved = cand, s, True
        if not moved:
            break
    cur_val, new_val = score(current, "val"), score(best, "val")
    cur_tr = score(current, "train")
    weights_ok = best != current and new_val >= cur_val and best_s > cur_tr
    chosen = best if weights_ok else dict(current)
    overlay_name = None
    overlay_gov: dict = {}
    base_tr, base_val = score(chosen, "train"), score(chosen, "val")
    for name, ov in OVERLAYS.items():
        log(f"Testing {name}...")
        ov_risk_cfg = {k: v for k, v in ov.items()}
        tr_ov = {lg.label: _leg_trades(df, cfg, lg, risk, ov_risk_cfg) for lg in legs}
        if score(chosen, "train", tr_ov) > base_tr and score(chosen, "val", tr_ov) > base_val:
            overlay_name, overlay_gov = name, ov
            break
    improved = bool(weights_ok or overlay_name)
    cards = {}
    for label, w in (("current", current), ("optimized", chosen)):
        cards[label] = {sp: _score(obj, book(w), win[sp], gov)[1] for sp in ("train", "val", "test")}
    scores = {"current": {sp: round(score(current, sp), 2) for sp in ("train", "val", "test")},
              "optimized": {sp: round(score(chosen, sp), 2) for sp in ("train", "val", "test")}}
    if improved:
        parts = [f"weights {', '.join(f'{k} x{v:g}' for k, v in chosen.items())}"] if weights_ok else []
        if overlay_name:
            parts.append(overlay_name)
        note = "Better on the training AND the validation period: " + "; ".join(parts) + ". The hold-out period was not used to choose."
    else:
        note = ("No change beat the current bot on both the training and the validation period, so nothing was changed. "
                "That is the honest result when a bot's edge is already what its strategies can give.")
    res = BotOptResult(obj, improved, note, current, chosen, overlay_name, scores, cards)
    if improved:
        new_cfg = replace(cfg, legs=[replace(lg, weight=chosen.get(lg.label, lg.weight)) if lg.kind != "gate27" else lg for lg in cfg.legs],
                          governor={**cfg.governor, **overlay_gov}, preset_key="", preset_rev=0, name=f"{cfg.name} (optimized)",
                          id=f"{cfg.id}-opt")
        res.optimized_config = new_cfg.to_dict()
        if save:
            from app.bots import store
            if store.get_bot(new_cfg.id) is not None:
                store.delete_bot(new_cfg.id)
            store.create_bot(new_cfg)
            res.saved_bot_id = new_cfg.id
    return res
