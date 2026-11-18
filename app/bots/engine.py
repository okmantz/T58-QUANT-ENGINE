"""BotEngine: one bar at a time, the decision loop of a Trading Bot.

Per 1-minute bar (UTC bar-start time, OHLC):
  1. a decision taken at the previous leg-bar close is FILLED at this bar's open (the engine's next-bar-open rule);
  2. an open position's stop / target is checked against this bar's high-low (stop wins a same-bar tie, like the backtest engine);
  3. at the session flatten time anything still open is closed;
  4. when a leg's own timeframe bar has just closed, its strategy signal is read: signal-off or reversal exits at the next open, a NEW signal
     (an edge, never a level that was already on when the bot started) becomes an entry candidate;
  5. the entry is sized by the risk governor from the live account state, converted to whole contracts (mini else micro, floor, never above the
     cap), and queued for the next open.

Several instruments: every instrument a bot's legs use gets its own LANE (one open position and one pending order per instrument). ``on_bars`` feeds
one minute of bars for any number of instruments; ``on_bar`` is the single-instrument shorthand for the primary lane. The account, the day stop, the
trade cap and the open-risk budget are shared, so a second instrument can never take the account past what one position was allowed to.

Swing legs (``BotLeg.kind == "gate27"``) are not intraday strategies: they follow the monthly Gate 27 cycle (see ``app.bots.gate27``), are held through
the flatten window and are only run on a rule-free live account (NET), never on a prop account that requires flat positions.

All money is dollars. The engine never talks to a clock or the network: the runner feeds bars and persists the result, so the same code runs the
simulation, the real-time loop and the unit tests.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

from app.bots.models import BotConfig, BotRuntime, OpenPos, now_iso
from app.bots.risk_governor import AccountRulesLite, AccountState, contracts_for_risk, decide_risk
from app.bots.signals import LegSignal
from app.bots import gate27 as g27
from app.objectives import governor_objective

ET = "America/New_York"


@dataclass(frozen=True)
class InstrumentCosts:
    pv_mini: float
    pv_micro: float
    comm_mini: float
    comm_micro: float
    slip: float                  # price points per fill, adverse


def instrument_costs(symbol: str) -> InstrumentCosts:
    from app.backtest.risk import RiskConfig
    from app.data.instrument_specs import apply_instrument_spec
    r = apply_instrument_spec(RiskConfig(), symbol)
    return InstrumentCosts(pv_mini=float(r.contract_size or 20.0), pv_micro=float(r.micro_contract_size or (r.contract_size or 20.0) / 10.0),
                           comm_mini=float(r.commission_per_contract or 0.0), comm_micro=float(r.micro_commission_per_contract or 0.0),
                           slip=float(r.slippage_pips or 0.0) * float(r.pip_size or 1.0))


def _hhmm(s: str) -> int:
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def rules_for_account(account, preset_override: Optional[AccountRulesLite] = None, objective: Optional[str] = None) -> tuple[AccountRulesLite, int, int]:
    """(rules for the governor, max minis, max micros) for a bot's AccountLink.

    Objective NET on a sandbox ("paper") account or an account with no prop-firm rule set is a LIVE account: no evaluation to pass, no
    trailing floor, no daily limit (``AccountRulesLite.live_account``). NET on a demo / prop-rule account keeps that account's rules."""
    if preset_override is not None:
        return preset_override, 4, 40
    if objective is not None and governor_objective(objective) == "NET" and account.venue != "demo" and (account.venue == "paper" or not account.preset_key):
        k = float(account.size) / 50_000.0
        return AccountRulesLite.live_account(account.size), max(1, int(round(4 * k))), max(10, int(round(40 * k)))
    if account.venue == "demo":
        from app.demo_account import account as demo
        a = demo.load()
        return AccountRulesLite.from_v2(a.rules), 4, 40
    if account.preset_key:
        try:
            from app.prop.lifecycle_v2 import V2Rules
            from app.prop.presets import get_preset
            pr = get_preset(account.preset_key).to_prop_rules()
            rl = AccountRulesLite.from_v2(V2Rules.from_prop_rules(pr))
            mc = int(getattr(pr, "max_contracts", 0) or 4)
            return rl, mc, mc * 10
        except Exception:  # noqa: BLE001 - unknown preset: fall back to the Lucid-shaped default scaled to the account size
            pass
    k = float(account.size) / 50_000.0
    base = AccountRulesLite.lucid_50k()
    return AccountRulesLite.tier(account.size), max(1, int(round(4 * k))), max(10, int(round(40 * k)))


@dataclass
class Lane:
    """Everything the engine tracks for ONE instrument: its open position, its pending order and the per-leg signal memory."""
    symbol: str
    pos: Optional[OpenPos] = None
    pending: Optional[dict] = None
    prev_sig: dict = field(default_factory=dict)
    skip_until_flat: dict = field(default_factory=dict)
    leg_day_trades: dict = field(default_factory=dict)
    last_price: float = 0.0
    last_time: str = ""


class BotEngine:
    def __init__(self, cfg: BotConfig, rt: BotRuntime, trades: list, events: list, venue, sources: dict, *,
                 rules: Optional[AccountRulesLite] = None, max_minis: int = 4, max_micros: int = 40,
                 on_trade: Optional[Callable[[dict], None]] = None):
        self.cfg, self.rt, self.trades, self.events, self.venue, self.sources = cfg, rt, trades, events, venue, sources
        self.gov = cfg.governor_cfg()
        self.rules = rules or (AccountRulesLite.live_account(cfg.account.size) if (governor_objective(cfg.objective) == "NET" and cfg.account.venue == "paper")
                               else AccountRulesLite.tier(cfg.account.size))
        if self.rules.profit_target >= 1e11 and self.gov.cushion_risk_frac is not None:
            self.gov = self.gov.with_(cushion_risk_frac=None)        # rule-free account: there is no prop cushion to cap the risk against
        self.max_minis, self.max_micros = max_minis, max_micros
        self.on_trade = on_trade
        self.costs = {lg.symbol: instrument_costs(lg.symbol) for lg in cfg.legs}
        self.leg_by_label = {lg.label: lg for lg in cfg.legs}
        self.tf = {lg.label: int(getattr(sources[lg.label], "tf", 1)) for lg in cfg.legs if lg.label in sources}
        self.intraday_legs = [lg for lg in cfg.legs if lg.kind != "gate27"]
        self.swing_legs = [lg for lg in cfg.legs if lg.kind == "gate27" and lg.label in sources]
        syms: list = []
        for lg in self.intraday_legs + self.swing_legs:
            if lg.symbol not in syms:
                syms.append(lg.symbol)
        self.primary = self.intraday_legs[0].symbol if self.intraday_legs else (syms[0] if syms else "NQ")
        self.lanes: dict = {s: Lane(s) for s in (syms or [self.primary])}
        self._lane: Lane = self.lanes[self.primary]
        self._last_skip: dict = {}
        self.acct = AccountState.fresh(self.rules)
        if rt.state:
            self._restore(rt.state)
        self.flatten_min = _hhmm(cfg.flatten_hhmm_et)
        self.reopen_min = _hhmm(cfg.reopen_hhmm_et)
        self.lanes[self.primary].pos = OpenPos.from_dict(rt.position) if rt.position else None
        self.lanes[self.primary].pending = rt.pending
        for sym, d in ((rt.state or {}).get("lanes") or {}).items():
            if sym in self.lanes and sym != self.primary:
                self.lanes[sym].pos = OpenPos.from_dict(d["position"]) if d.get("position") else None
                self.lanes[sym].pending = d.get("pending")
        self.detached = bool(rt.state.get('detached')) if rt.state else False   # funded simulation: no longer mirrors the demo account
        # ---- swing (Gate 27) state: open tranches and the monthly cycle
        self.swing_pos: list = [OpenPos.from_dict(d) for d in ((rt.state or {}).get("swing_pos") or [])]
        self.g27: dict = dict((rt.state or {}).get("g27") or {"month": 0, "step": g27.PHASE_IN_DAYS, "start": {}, "target": {}, "session": "", "done": False})
        self._swing_warned = False
        self.swing_enabled = bool(self.swing_legs) and self.rules.profit_target >= 1e11
        if self.swing_legs and not self.swing_enabled:
            self._event("warn", "Gate 27 legs hold positions overnight and for weeks. This account has prop-firm rules that require flat positions, so they stay off; run the bot on a rule-free live or sandbox account to use them.")

    # ------------------------------------------------------------------------------------------------------------ primary-lane views
    @property
    def pos(self) -> Optional[OpenPos]:
        """The primary lane's open position (the only one for a single-instrument bot)."""
        return self.lanes[self.primary].pos

    @pos.setter
    def pos(self, v: Optional[OpenPos]) -> None:
        self.lanes[self.primary].pos = v

    def open_positions(self) -> list:
        return [ln.pos for ln in self.lanes.values() if ln.pos is not None] + list(self.swing_pos)

    def _open_risk(self, exclude: Optional[Lane] = None) -> float:
        tot = 0.0
        for ln in self.lanes.values():
            if ln is exclude:
                continue
            if ln.pos is not None:
                tot += float(ln.pos.risk_dollars)
            if ln.pending and ln.pending.get("type") == "entry":
                tot += float(ln.pending.get("risk", 0.0))
        return tot

    @property
    def _objective(self) -> str:
        """The goal this bot runs for: "A" (pass), "B" (payout) or "NET" (net profit); read by the governor and by ``_after_trade``."""
        return governor_objective(self.cfg.objective)

    # ----------------------------------------------------------------------------------------------------------------- state io
    def _restore(self, d: dict) -> None:
        a = self.acct
        for k in ("phase", "balance", "start_balance", "floor", "eod_high", "day_start", "day", "peak_equity", "trades_today", "stopped_today",
                  "last_payout_balance"):
            if k in d:
                setattr(a, k, d[k])

    def _persist_state(self) -> None:
        self.rt.state = self.acct.to_dict()
        self.rt.state.pop("rules", None)
        self.rt.state["detached"] = self.detached
        prim = self.lanes[self.primary]
        self.rt.position = prim.pos.to_dict() if prim.pos else None
        self.rt.pending = prim.pending
        others = {s: {"position": ln.pos.to_dict() if ln.pos else None, "pending": ln.pending} for s, ln in self.lanes.items() if s != self.primary}
        if others:
            self.rt.state["lanes"] = others
        if self.swing_legs:
            self.rt.state["swing_pos"] = [p.to_dict() for p in self.swing_pos]
            self.rt.state["g27"] = self.g27

    def _event(self, kind: str, text: str, t=None) -> None:
        if kind == "skip":                      # level signals re-fire every bar: log each distinct skip once per session day
            key = (text.split(":")[0], text.split("$")[0], self.rt.day_key)
            if self._last_skip.get(key[0]) == key:
                return
            self._last_skip[key[0]] = key
        self.events.append({"t": str(t or now_iso()), "kind": kind, "text": text})
        del self.events[:-300]

    # ----------------------------------------------------------------------------------------------------------------------- bar
    def on_bar(self, t: pd.Timestamp, o: float, h: float, l: float, c: float) -> None:
        """One 1-minute bar of the primary instrument (single-instrument bots and the unit tests)."""
        self.on_bars(t, {self.primary: (o, h, l, c)})

    def on_bars(self, t: pd.Timestamp, bars: dict) -> None:
        """One minute of bars for any of the bot's instruments: ``bars`` = {symbol: (open, high, low, close)}."""
        if self.rt.status != "running":
            return
        t = pd.Timestamp(t)
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        et = t.tz_convert(ET)
        day = str(et.date())
        if day != self.rt.day_key:
            self.rt.day_key, self.rt.day_trades, self.rt.day_realised = day, 0, 0.0
        self.acct.roll_day(day)
        for sym, (o, h, l, c) in bars.items():
            lane = self.lanes.get(sym)
            if lane is None:
                continue
            self._lane = lane
            lane.last_price, lane.last_time = float(c), t.isoformat()
            if sym == self.primary:
                self.rt.last_bar_time, self.rt.last_price = t.isoformat(), float(c)
            self._lane_bar(t, et, o, h, l, c)
            if self.rt.status != "running":
                break
        if self.rt.status == "running" and self.swing_enabled:
            self._swing_step(t, et, bars)
        self._persist_state()

    def _lane_bar(self, t: pd.Timestamp, et: pd.Timestamp, o: float, h: float, l: float, c: float) -> None:
        lane = self._lane
        if lane.pos is not None and not self.venue.simulated_fills:
            gone = self.venue.poll(lane.pos)
            if gone:
                self._close_position(self._broker_exit_price(h, l, c), t, "closed at the broker (stop / target)", broker_closed=True)

        # 1. fill the decision taken at the previous leg-bar close
        pend = lane.pending
        if pend:
            lane.pending = None
            if pend["type"] == "exit" and lane.pos is not None:
                self._close_position(o - lane.pos.direction * self._slip(lane.pos.symbol), t, pend.get("reason", "signal off"))
            elif pend["type"] == "entry" and lane.pos is None and self._entries_allowed(et):
                self._open_position(pend, o, t)

        # 2. stop / target inside this bar
        if lane.pos is not None and self.venue.simulated_fills:
            self._check_stops(h, l, t)

        # 3. flatten
        if lane.pos is not None and self._in_flatten_zone(et):
            self._close_position(c - lane.pos.direction * self._slip(lane.pos.symbol), t, "session flatten")
        if self.rt.status != "running":
            return

        # 4/5. leg-bar closes
        bar_end = t + pd.Timedelta(minutes=1)
        epoch_min = int(bar_end.value // 60_000_000_000)
        reported = {}
        for lg in self.intraday_legs:
            if lg.symbol != lane.symbol:
                continue
            src = self.sources.get(lg.label)
            if src is None or epoch_min % self.tf.get(lg.label, 1) != 0:
                continue
            ls: Optional[LegSignal] = src.at(bar_end)
            if ls is not None:
                reported[lg.label] = ls
        if reported:
            self._decide(reported, et, bar_end)

    def _in_flatten_zone(self, et: pd.Timestamp) -> bool:
        mod = et.hour * 60 + et.minute
        dow = et.weekday()
        if dow == 5:
            return True
        if dow == 6 and mod < self.reopen_min:
            return True
        return self.flatten_min <= mod < self.reopen_min

    def _entries_allowed(self, et: pd.Timestamp) -> bool:
        return not self._in_flatten_zone(et)

    # -------------------------------------------------------------------------------------------------------------- decisions
    def _decide(self, reported: dict, et: pd.Timestamp, bar_end: pd.Timestamp) -> None:
        lane = self._lane
        # exits first
        if lane.pos is not None and lane.pos.leg in reported and not lane.pending:
            ls = reported[lane.pos.leg]
            if ls.sig != lane.pos.direction:
                lane.pending = {"type": "exit", "reason": "strategy signal off" if ls.sig == 0 else "strategy reversed"}
        cands = []
        for label, ls in reported.items():
            prev = lane.prev_sig.get(label)
            if prev is None and ls.sig != 0:
                lane.skip_until_flat[label] = True          # a level that was already on when the bot started is not an entry event
            if ls.sig == 0:
                lane.skip_until_flat[label] = False
            elif not lane.skip_until_flat.get(label) and self._leg_may_enter(label):
                cands.append((self.leg_by_label[label].priority, label, ls))   # level-based, exactly like the backtest engine
            lane.prev_sig[label] = ls.sig
        if not cands:
            self._explain_idle()
            return
        if lane.pos is not None or lane.pending:
            self.rt.next_decision = "A signal fired while a position is open: one position at a time, the earlier signal keeps the slot."
            return
        if not self._entries_allowed(et):
            self.rt.next_decision = "Signal during the flat window / weekend: skipped."
            return
        if self.rt.day_trades >= self.cfg.max_trades_per_day:
            self.rt.next_decision = f"Daily trade cap reached ({self.cfg.max_trades_per_day})."
            return
        others = sum(1 for ln in self.lanes.values() if ln is not lane and (ln.pos is not None or (ln.pending and ln.pending.get("type") == "entry")))
        if others >= max(1, int(self.cfg.max_open_positions)):
            self.rt.next_decision = f"{others} positions already open on other instruments (limit {self.cfg.max_open_positions}): skipped."
            return
        cands.sort(key=lambda x: x[0])
        _prio, label, ls = cands[0]
        lg = self.leg_by_label[label]
        if not math.isfinite(ls.stop) or ls.stop <= 0:
            self.rt.next_decision = f"{lg.label}: strategy gave no stop distance, skipped."
            return
        if self.venue.supports_sync and not self.detached:
            self.venue.sync_state(self.acct)
        dec = decide_risk(self.acct, self.gov, open_risk=self._open_risk(exclude=lane))
        if not dec.allow:
            self.rt.next_decision = f"Standing down: {dec.reason}."
            self._event("skip", f"{lg.label} signal skipped: {dec.reason}", bar_end)
            return
        cs = self.costs[lg.symbol]
        risk = dec.risk_dollars * float(lg.weight)
        kind, n = contracts_for_risk(risk, ls.stop, cs.pv_mini, cs.pv_micro, self.max_minis, self.max_micros,
                                     cost_per_contract=cs.comm_mini)
        if n < 1:
            self.rt.next_decision = f"{lg.label}: risk ${risk:,.0f} is below one micro contract at a {ls.stop:,.1f}-point stop, skipped."
            self._event("skip", self.rt.next_decision, bar_end)
            return
        lane.pending = {"type": "entry", "leg": lg.label, "symbol": lg.symbol, "direction": int(ls.sig), "stop": float(ls.stop),
                        "tp": float(ls.tp) if math.isfinite(ls.tp) and ls.tp > 0 else None, "kind": kind, "qty": int(n),
                        "risk": float(risk), "mult": float(dec.multiplier), "why": dec.reason}
        self.rt.next_decision = f"Entering {'long' if ls.sig > 0 else 'short'} {n} {kind} on {lg.label} at the next open (risk ${risk:,.0f})."

    def _leg_may_enter(self, label: str) -> bool:
        cap = getattr(self.sources.get(label), "max_trades_per_day", None)
        if not cap:
            return True
        return self._lane.leg_day_trades.get((label, self.rt.day_key), 0) < int(cap)

    def _explain_idle(self) -> None:
        if self._lane.pos is not None:
            p = self._lane.pos
            self.rt.next_decision = f"In a {'long' if p.direction > 0 else 'short'} ({p.leg}); watching the stop and the strategy's exit."
            return
        dec = decide_risk(self.acct, self.gov, open_risk=self._open_risk(exclude=self._lane))
        self.rt.next_decision = (f"Watching for a signal. Next trade would risk ${dec.risk_dollars:,.0f} ({dec.reason})."
                                 if dec.allow else f"Standing down: {dec.reason}.")

    # --------------------------------------------------------------------------------------------------------------------- fills
    def _slip(self, symbol: str) -> float:
        return self.costs.get(symbol, next(iter(self.costs.values()))).slip

    def _open_position(self, pend: dict, open_px: float, t: pd.Timestamp) -> None:
        lane = self._lane
        d = int(pend["direction"])
        fill = open_px + d * self._slip(pend["symbol"])
        pos = OpenPos(leg=pend["leg"], symbol=pend["symbol"], direction=d, kind=pend["kind"], qty=int(pend["qty"]), entry_time=t.isoformat(),
                      entry_price=float(fill), stop_price=float(fill - d * pend["stop"]),
                      tp_price=(float(fill + d * pend["tp"]) if pend.get("tp") else None), risk_dollars=float(pend["risk"]),
                      stop_points=float(pend["stop"]), mult=float(pend["mult"]))
        ok, price, ticket, msg = self.venue.open(pos)
        if not ok:
            self._event("error", f"Order rejected: {msg}", t)
            self.rt.message = f"Order rejected: {msg}"
            return
        if price:
            pos.entry_price = float(price)
            pos.stop_price, pos.tp_price = float(price - d * pend["stop"]), (float(price + d * pend["tp"]) if pend.get("tp") else None)
        pos.ticket, pos.broker = ticket, not self.venue.simulated_fills
        lane.pos = pos
        self.rt.day_trades += 1
        k = (pos.leg, self.rt.day_key)
        lane.leg_day_trades[k] = lane.leg_day_trades.get(k, 0) + 1
        self._event("entry", f"{'Long' if d > 0 else 'Short'} {pos.qty} {pos.kind} {pos.symbol} @ {pos.entry_price:,.2f} "
                             f"(stop {pos.stop_price:,.2f}{', target %.2f' % pos.tp_price if pos.tp_price else ''}, risk ${pos.risk_dollars:,.0f}) · {pos.leg}", t)

    def _check_stops(self, h: float, l: float, t: pd.Timestamp) -> None:
        p = self._lane.pos
        assert p is not None
        slip = self._slip(p.symbol)
        if p.direction > 0:
            if l <= p.stop_price:
                return self._close_position(p.stop_price - slip, t, "stop loss")
            if p.tp_price is not None and h >= p.tp_price:
                return self._close_position(p.tp_price, t, "target")
        else:
            if h >= p.stop_price:
                return self._close_position(p.stop_price + slip, t, "stop loss")
            if p.tp_price is not None and l <= p.tp_price:
                return self._close_position(p.tp_price, t, "target")

    def _broker_exit_price(self, h: float, l: float, c: float) -> float:
        p = self._lane.pos
        if p is None:
            return c
        if p.direction > 0:
            return p.stop_price if l <= p.stop_price else (p.tp_price if p.tp_price and h >= p.tp_price else c)
        return p.stop_price if h >= p.stop_price else (p.tp_price if p.tp_price and l <= p.tp_price else c)

    def _close_position(self, price: float, t: pd.Timestamp, reason: str, *, broker_closed: bool = False) -> None:
        p = self._lane.pos
        if p is None:
            return
        if self._book_close(p, price, t, reason, broker_closed=broker_closed):
            self._lane.pos = None
            self._after_trade(t)

    def _book_close(self, p: OpenPos, price: float, t: pd.Timestamp, reason: str, *, broker_closed: bool = False) -> bool:
        """Close ``p`` at the venue and book the trade row. True when it closed (the caller clears its own reference)."""
        if not broker_closed:
            ok, fill, msg = self.venue.close(p, price, reason)
            if not ok:
                self._event("error", f"Close failed: {msg}", t)
                self.rt.message = f"Close failed: {msg}. The position is still open at the broker."
                return False
            if fill:
                price = float(fill)
        cs = self.costs[p.symbol]
        pv, comm = (cs.pv_mini, cs.comm_mini) if p.kind == "mini" else (cs.pv_micro, cs.comm_micro)
        gross = p.direction * (price - p.entry_price) * p.qty * pv
        pnl = gross - comm * p.qty
        n = len(self.trades) + 1
        row = {"n": n, "bot": self.cfg.name, "leg": p.leg, "symbol": p.symbol, "side": "long" if p.direction > 0 else "short",
               "qty": p.qty, "kind": p.kind, "entry_time": p.entry_time, "exit_time": t.isoformat(), "entry": round(p.entry_price, 2),
               "exit": round(price, 2), "pnl": round(pnl, 2), "r_multiple": round(pnl / p.risk_dollars, 2) if p.risk_dollars else None,
               "risk": round(p.risk_dollars, 2), "reason": reason, "mult": round(p.mult, 2)}
        self.rt.day_realised += pnl
        self.acct.update(pnl, str(t.tz_convert(ET).date()))
        row["balance"] = round(self.acct.balance, 2)
        self.trades.append(row)
        del self.trades[:-5000]
        self.venue.book(row)
        self._event("exit", f"{'Win' if pnl > 0 else 'Loss' if pnl < 0 else 'Flat'} ${pnl:+,.2f} · {p.leg} · {reason} · balance ${self.acct.balance:,.2f}", t)
        if self.on_trade:
            self.on_trade(row)
        return True

    def close_all(self, reason: str = "bot stopped: flattened") -> None:
        """Flatten every open position (intraday lanes and swing tranches) at each instrument's last price."""
        for ln in self.lanes.values():
            if ln.pos is not None and ln.last_price:
                self._lane = ln
                self._close_position(ln.last_price, pd.Timestamp(ln.last_time or self.rt.last_bar_time or pd.Timestamp.now(tz="UTC")), reason)
        for p in list(self.swing_pos):
            ln = self.lanes.get(p.symbol)
            if ln is not None and ln.last_price:
                t = pd.Timestamp(ln.last_time or self.rt.last_bar_time)
                if self._book_close(p, ln.last_price, t, reason):
                    self.swing_pos.remove(p)
        self._persist_state()

    def _after_trade(self, t: pd.Timestamp) -> None:
        a = self.acct
        if self.venue.supports_sync and not self.detached:
            self.venue.sync_state(a)
        if a.phase == "breached":
            self.rt.status, self.rt.halted_reason = "halted", "The account breached its loss floor."
            self.rt.breaches += 1
            for ln in self.lanes.values():
                ln.pending = None
            self._event("halt", "Account breached: bot halted. Reset the bot to start a new attempt.", t)
        elif a.phase == "passed":
            self.rt.passes += 1
            if self._objective == "A":
                self.rt.status, self.rt.message = "complete", "Evaluation passed. Objective complete."
                for ln in self.lanes.values():
                    ln.pending = None
                self._event("pass", f"Evaluation PASSED at ${a.balance:,.2f}: objective A complete.", t)
            else:
                self._event("pass", f"Evaluation PASSED at ${a.balance:,.2f}: continuing on the funded stage.", t)
                a.to_funded()
                self.detached = True
        elif a.phase == "funded":
            amt = a.take_payout()
            if amt > 0:
                self.rt.payouts += amt
                self._event("payout", f"Payout available: ${amt:,.0f} withdrawn (floor does not move down).", t)
        self.rt.message = {"running": "Running.", "complete": self.rt.message, "halted": self.rt.halted_reason}.get(self.rt.status, self.rt.message)

    # ------------------------------------------------------------------------------------------------------------ swing: Gate 27
    def _swing_session(self, et: pd.Timestamp) -> str:
        """CME session day: the New York calendar day shifted by the 18:00 ET Globex open (Sunday 18:00 belongs to Monday)."""
        return str((et + pd.Timedelta(hours=6)).date())

    def _swing_qty(self, leg_label: str) -> int:
        return sum(p.qty for p in self.swing_pos if p.leg == leg_label)

    def _swing_step(self, t: pd.Timestamp, et: pd.Timestamp, bars: dict) -> None:
        sess = self._swing_session(et)
        g = self.g27
        if g.get("session") != sess:
            sd = pd.Timestamp(sess)
            if sd.weekday() >= 5:
                return
            g["session"], g["done"] = sess, False
        if g.get("done"):
            return
        legs = self.swing_legs
        if any(lg.symbol not in bars for lg in legs):
            return                                   # wait for the next minute that has a bar for every leg
        sd = pd.Timestamp(sess)
        src = self.sources[legs[0].label]
        month = sd.year * 12 + sd.month
        thr = self.acct.drawdown_from_peak / max(self.acct.peak_equity, 1.0) * 100.0
        guard = float(getattr(src, "dd_guard_pct", 25.0))
        if thr >= guard and self.swing_pos:
            for p in list(self.swing_pos):
                if self._book_close(p, bars[p.symbol][0], t, f"Gate 27 drawdown guard ({thr:.0f}% below the equity peak)"):
                    self.swing_pos.remove(p)
            g.update(month=month, step=g27.PHASE_IN_DAYS, start={}, target={lg.label: 0.0 for lg in legs}, done=True)
            self._event("halt", f"Gate 27 flattened: account is {thr:.0f}% below its peak. It rebuilds at the next monthly cycle.", t)
            return
        mult = 1.0
        dec = decide_risk(self.acct, self.gov)
        if self._objective == "NET":
            mult = float(dec.multiplier) if dec.multiplier else 1.0
        if g.get("month") != month:                                   # first session of a new month: a new cycle
            sigs = src.signals(sd)
            if sigs is not None:
                keyed = {lg.symbol: sigs.get(lg.symbol) for lg in legs}
                tgt = g27.target_notionals(keyed, self.acct.balance * mult, getattr(src, "cfg", g27.Gate27Config()))
                start = {}
                for lg in legs:
                    px = float(bars[lg.symbol][0])
                    cs = self.costs[lg.symbol]
                    unit = cs.pv_mini if any(p.kind == "mini" and p.leg == lg.label for p in self.swing_pos) else cs.pv_micro
                    start[lg.label] = self._swing_qty(lg.label) * px * unit
                g.update(month=month, step=0, start=start,
                         target={lg.label: float(tgt.get(lg.symbol, g.get("target", {}).get(lg.label, 0.0))) * float(lg.weight) for lg in legs})
                self._event("info", "Gate 27 cycle: " + ", ".join(f"{lg.label} {'LONG' if g['target'][lg.label] > 0 else 'FLAT'}" for lg in legs), t)
        cfg27 = getattr(src, "cfg", g27.Gate27Config())
        if g.get("step", cfg27.phase_in_days) < cfg27.phase_in_days:
            g["step"] = int(g["step"]) + 1
            for lg in legs:
                self._swing_adjust(lg, g27.phase_notional(float(g["start"].get(lg.label, 0.0)), float(g["target"].get(lg.label, 0.0)), int(g["step"]), cfg27),
                                   float(bars[lg.symbol][0]), t)
        g["done"] = True

    def _swing_adjust(self, lg, want_notional: float, price: float, t: pd.Timestamp) -> None:
        cs = self.costs[lg.symbol]
        n_mini = g27.contracts_for_notional(want_notional, price, cs.pv_mini)
        kind, unit_pv = ("mini", cs.pv_mini) if n_mini >= 2 else ("micro", cs.pv_micro)
        want = n_mini if kind == "mini" else g27.contracts_for_notional(want_notional, price, cs.pv_micro, max_contracts=self.max_micros * 10)
        have_kinds = {p.kind for p in self.swing_pos if p.leg == lg.label}
        if have_kinds and kind not in have_kinds:                       # the leg changed contract size: close the old tranches first
            for p in [p for p in self.swing_pos if p.leg == lg.label]:
                if self._book_close(p, price - self._slip(lg.symbol), t, "Gate 27 resize"):
                    self.swing_pos.remove(p)
            cur = 0
        else:
            cur = self._swing_qty(lg.label)
        diff = int(want) - cur
        if diff > 0:
            fill = price + self._slip(lg.symbol)
            pos = OpenPos(leg=lg.label, symbol=lg.symbol, direction=1, kind=kind, qty=diff, entry_time=t.isoformat(), entry_price=float(fill),
                          stop_price=0.0, tp_price=None, risk_dollars=0.0, stop_points=0.0, mult=1.0)
            ok, px, ticket, msg = self.venue.open(pos)
            if not ok:
                self._event("error", f"Gate 27 order rejected: {msg}", t)
                return
            if px:
                pos.entry_price = float(px)
            pos.ticket, pos.broker = ticket, not self.venue.simulated_fills
            self.swing_pos.append(pos)
            self._event("entry", f"Gate 27 BUY {diff} {kind} {lg.symbol} @ {pos.entry_price:,.2f} (target {int(want)})", t)
        elif diff < 0:
            remaining = -diff
            for p in [p for p in self.swing_pos if p.leg == lg.label]:           # oldest first
                if remaining <= 0:
                    break
                px = price - self._slip(lg.symbol)
                if p.qty <= remaining:
                    if self._book_close(p, px, t, "Gate 27 reduce"):
                        self.swing_pos.remove(p)
                        remaining -= p.qty
                else:
                    keep = p.qty - remaining
                    old = p.qty
                    p.qty = remaining
                    if self._book_close(p, px, t, "Gate 27 reduce"):
                        self.swing_pos.remove(p)
                        rest = OpenPos(leg=p.leg, symbol=p.symbol, direction=1, kind=p.kind, qty=keep, entry_time=p.entry_time, entry_price=p.entry_price,
                                       stop_price=0.0, tp_price=None, risk_dollars=0.0, stop_points=0.0, mult=1.0)
                        self.swing_pos.append(rest)
                        remaining = 0
                    else:
                        p.qty = old
