"""BotEngine: one bar at a time, the decision loop of a Trading Bot.

Per 1-minute bar (UTC bar-start time, OHLC):
  1. a decision taken at the previous leg-bar close is FILLED at this bar's open (the engine's next-bar-open rule);
  2. an open position's stop / target is checked against this bar's high-low (stop wins a same-bar tie, like the backtest engine);
  3. at the session flatten time anything still open is closed;
  4. when a leg's own timeframe bar has just closed, its strategy signal is read: signal-off or reversal exits at the next open, a NEW signal
     (an edge, never a level that was already on when the bot started) becomes an entry candidate;
  5. the entry is sized by the risk governor from the live account state, converted to whole contracts (mini else micro, floor, never above the
     cap), and queued for the next open.

All money is dollars. The engine never talks to a clock or the network: the runner feeds bars and persists the result, so the same code runs the
simulation, the real-time loop and the unit tests.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from app.bots.models import BotConfig, BotRuntime, OpenPos, now_iso
from app.bots.risk_governor import AccountRulesLite, AccountState, contracts_for_risk, decide_risk
from app.bots.signals import LegSignal

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


def rules_for_account(account, preset_override: Optional[AccountRulesLite] = None) -> tuple[AccountRulesLite, int, int]:
    """(rules for the governor, max minis, max micros) for a bot's AccountLink."""
    if preset_override is not None:
        return preset_override, 4, 40
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


class BotEngine:
    def __init__(self, cfg: BotConfig, rt: BotRuntime, trades: list, events: list, venue, sources: dict, *,
                 rules: Optional[AccountRulesLite] = None, max_minis: int = 4, max_micros: int = 40,
                 on_trade: Optional[Callable[[dict], None]] = None):
        self.cfg, self.rt, self.trades, self.events, self.venue, self.sources = cfg, rt, trades, events, venue, sources
        self.gov = cfg.governor_cfg()
        self.rules = rules or AccountRulesLite.tier(cfg.account.size)
        self.max_minis, self.max_micros = max_minis, max_micros
        self.on_trade = on_trade
        self.costs = {lg.symbol: instrument_costs(lg.symbol) for lg in cfg.legs}
        self.leg_by_label = {lg.label: lg for lg in cfg.legs}
        self.tf = {lg.label: int(getattr(sources[lg.label], "tf", 1)) for lg in cfg.legs if lg.label in sources}
        self.prev_sig: dict = {}
        self._last_skip: dict = {}
        self.leg_day_trades: dict = {}
        self.skip_until_flat: dict = {}
        self.acct = AccountState.fresh(self.rules)
        if rt.state:
            self._restore(rt.state)
        self.flatten_min = _hhmm(cfg.flatten_hhmm_et)
        self.reopen_min = _hhmm(cfg.reopen_hhmm_et)
        self.pos: Optional[OpenPos] = OpenPos.from_dict(rt.position) if rt.position else None
        self.detached = bool(rt.state.get('detached')) if rt.state else False   # funded simulation: no longer mirrors the demo account

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
        self.rt.position = self.pos.to_dict() if self.pos else None

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
        if self.rt.status != "running":
            return
        t = pd.Timestamp(t)
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        et = t.tz_convert(ET)
        mod = et.hour * 60 + et.minute
        day = str(et.date())
        if day != self.rt.day_key:
            self.rt.day_key, self.rt.day_trades, self.rt.day_realised = day, 0, 0.0
        self.acct.roll_day(day)
        self.rt.last_bar_time, self.rt.last_price = t.isoformat(), float(c)

        if self.pos is not None and not self.venue.simulated_fills:
            gone = self.venue.poll(self.pos)
            if gone:
                self._close_position(self._broker_exit_price(h, l, c), t, "closed at the broker (stop / target)", broker_closed=True)

        # 1. fill the decision taken at the previous leg-bar close
        pend = self.rt.pending
        if pend:
            self.rt.pending = None
            if pend["type"] == "exit" and self.pos is not None:
                self._close_position(o - self.pos.direction * self._slip(self.pos.symbol), t, pend.get("reason", "signal off"))
            elif pend["type"] == "entry" and self.pos is None and self._entries_allowed(et):
                self._open_position(pend, o, t)

        # 2. stop / target inside this bar
        if self.pos is not None and self.venue.simulated_fills:
            self._check_stops(h, l, t)

        # 3. flatten
        if self.pos is not None and self._in_flatten_zone(et):
            self._close_position(c - self.pos.direction * self._slip(self.pos.symbol), t, "session flatten")
        if self.rt.status != "running":
            self._persist_state()
            return

        # 4/5. leg-bar closes
        bar_end = t + pd.Timedelta(minutes=1)
        epoch_min = int(bar_end.value // 60_000_000_000)
        reported = {}
        for lg in self.cfg.legs:
            src = self.sources.get(lg.label)
            if src is None or epoch_min % self.tf.get(lg.label, 1) != 0:
                continue
            ls: Optional[LegSignal] = src.at(bar_end)
            if ls is not None:
                reported[lg.label] = ls
        if reported:
            self._decide(reported, et, bar_end)
        self._persist_state()

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
        # exits first
        if self.pos is not None and self.pos.leg in reported and not self.rt.pending:
            ls = reported[self.pos.leg]
            if ls.sig != self.pos.direction:
                self.rt.pending = {"type": "exit", "reason": "strategy signal off" if ls.sig == 0 else "strategy reversed"}
        cands = []
        for label, ls in reported.items():
            prev = self.prev_sig.get(label)
            if prev is None and ls.sig != 0:
                self.skip_until_flat[label] = True          # a level that was already on when the bot started is not an entry event
            if ls.sig == 0:
                self.skip_until_flat[label] = False
            elif not self.skip_until_flat.get(label) and self._leg_may_enter(label):
                cands.append((self.leg_by_label[label].priority, label, ls))   # level-based, exactly like the backtest engine
            self.prev_sig[label] = ls.sig
        if not cands:
            self._explain_idle()
            return
        if self.pos is not None or self.rt.pending:
            self.rt.next_decision = "A signal fired while a position is open: one position at a time, the earlier signal keeps the slot."
            return
        if not self._entries_allowed(et):
            self.rt.next_decision = "Signal during the flat window / weekend: skipped."
            return
        if self.rt.day_trades >= self.cfg.max_trades_per_day:
            self.rt.next_decision = f"Daily trade cap reached ({self.cfg.max_trades_per_day})."
            return
        cands.sort(key=lambda x: x[0])
        _prio, label, ls = cands[0]
        lg = self.leg_by_label[label]
        if not math.isfinite(ls.stop) or ls.stop <= 0:
            self.rt.next_decision = f"{lg.label}: strategy gave no stop distance, skipped."
            return
        if self.venue.supports_sync and not self.detached:
            self.venue.sync_state(self.acct)
        dec = decide_risk(self.acct, self.gov)
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
        self.rt.pending = {"type": "entry", "leg": lg.label, "symbol": lg.symbol, "direction": int(ls.sig), "stop": float(ls.stop),
                           "tp": float(ls.tp) if math.isfinite(ls.tp) and ls.tp > 0 else None, "kind": kind, "qty": int(n),
                           "risk": float(risk), "mult": float(dec.multiplier), "why": dec.reason}
        self.rt.next_decision = f"Entering {'long' if ls.sig > 0 else 'short'} {n} {kind} on {lg.label} at the next open (risk ${risk:,.0f})."

    def _leg_may_enter(self, label: str) -> bool:
        cap = getattr(self.sources.get(label), "max_trades_per_day", None)
        if not cap:
            return True
        return self.leg_day_trades.get((label, self.rt.day_key), 0) < int(cap)

    def _explain_idle(self) -> None:
        if self.pos is not None:
            p = self.pos
            self.rt.next_decision = f"In a {'long' if p.direction > 0 else 'short'} ({p.leg}); watching the stop and the strategy's exit."
            return
        dec = decide_risk(self.acct, self.gov)
        self.rt.next_decision = (f"Watching for a signal. Next trade would risk ${dec.risk_dollars:,.0f} ({dec.reason})."
                                 if dec.allow else f"Standing down: {dec.reason}.")

    # --------------------------------------------------------------------------------------------------------------------- fills
    def _slip(self, symbol: str) -> float:
        return self.costs.get(symbol, next(iter(self.costs.values()))).slip

    def _open_position(self, pend: dict, open_px: float, t: pd.Timestamp) -> None:
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
        self.pos = pos
        self.rt.day_trades += 1
        k = (pos.leg, self.rt.day_key)
        self.leg_day_trades[k] = self.leg_day_trades.get(k, 0) + 1
        self._event("entry", f"{'Long' if d > 0 else 'Short'} {pos.qty} {pos.kind} {pos.symbol} @ {pos.entry_price:,.2f} "
                             f"(stop {pos.stop_price:,.2f}{', target %.2f' % pos.tp_price if pos.tp_price else ''}, risk ${pos.risk_dollars:,.0f}) · {pos.leg}", t)

    def _check_stops(self, h: float, l: float, t: pd.Timestamp) -> None:
        p = self.pos
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
        p = self.pos
        if p is None:
            return c
        if p.direction > 0:
            return p.stop_price if l <= p.stop_price else (p.tp_price if p.tp_price and h >= p.tp_price else c)
        return p.stop_price if h >= p.stop_price else (p.tp_price if p.tp_price and l <= p.tp_price else c)

    def _close_position(self, price: float, t: pd.Timestamp, reason: str, *, broker_closed: bool = False) -> None:
        p = self.pos
        if p is None:
            return
        if not broker_closed:
            ok, fill, msg = self.venue.close(p, price, reason)
            if not ok:
                self._event("error", f"Close failed: {msg}", t)
                self.rt.message = f"Close failed: {msg}. The position is still open at the broker."
                return
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
        self.pos = None
        self.rt.day_realised += pnl
        self.acct.update(pnl, str(t.tz_convert(ET).date()))
        row["balance"] = round(self.acct.balance, 2)
        self.trades.append(row)
        del self.trades[:-5000]
        self.venue.book(row)
        self._event("exit", f"{'Win' if pnl > 0 else 'Loss' if pnl < 0 else 'Flat'} ${pnl:+,.2f} · {p.leg} · {reason} · balance ${self.acct.balance:,.2f}", t)
        if self.on_trade:
            self.on_trade(row)
        self._after_trade(t)

    def _after_trade(self, t: pd.Timestamp) -> None:
        a = self.acct
        if self.venue.supports_sync and not self.detached:
            self.venue.sync_state(a)
        if a.phase == "breached":
            self.rt.status, self.rt.halted_reason = "halted", "The account breached its loss floor."
            self.rt.breaches += 1
            self.rt.pending = None
            self._event("halt", "Account breached: bot halted. Reset the bot to start a new attempt.", t)
        elif a.phase == "passed":
            self.rt.passes += 1
            if self.cfg.objective == "A":
                self.rt.status, self.rt.message = "complete", "Evaluation passed. Objective complete."
                self.rt.pending = None
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
