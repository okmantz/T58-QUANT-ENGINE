"""The Bot interface and the target-level signal semantics.

SIGNAL SEMANTICS. A strategy does not say "buy" or "sell". On every bar it returns a TARGET LEVEL: the position it wants to hold right now, as a signed
fraction of the bot's unit size for that instrument:

    +1.0   full long      +0.5  half long      0.0  flat      -0.5  half short      -1.0  full short

A level can also carry the protective stop distance (price points from the entry) and an optional target distance. The bot owns the difference between
the level it wants and the position it has; turning that difference into orders is ``LevelMapper`` (pure, no I/O, unit-tested):

    held 0, level +1            -> ENTRY (market, or a limit / stop entry order when ``entry_order`` says so)
    held +1, level +1.5         -> ADD   (the extra half)            [only when ``allow_scaling``]
    held +1.5, level +1         -> TRIM  (reduce-only, the half that is no longer wanted)
    held +1, level 0            -> EXIT  (close, cancel the protective orders)
    held +1, level -1           -> EXIT then ENTRY (a flip is two steps; the entry is only released once the exit has filled)

ONE-POSITION MODE (``allow_scaling=False``, the prop-account default). The level collapses to its sign: in, out, or flipped, never a partial size, so
there is exactly one position per instrument and add / trim never happens.

STOP / TARGET MANAGEMENT. After any fill that changes the position, the mapper emits the protective orders for the NEW size: a reduce-only STOP on the closing side
at ``entry -/+ stop`` and, when a target is set, a reduce-only LIMIT at the target. A size change MODIFIES the working protective orders instead of stacking new
ones; a flat position CANCELS them. A position never exists without a working stop (``BotState.unprotected`` flags it for the caller).

THE BOT INTERFACE.

    on_bar(bar)    a completed bar of one instrument  -> orders to place now (the decision of a closed bar, filled by the venue)
    on_fill(fill)  an execution report from the venue  -> the protective / follow-up orders it triggers (e.g. the stop after an entry, the entry after a flip's exit)
    on_tick(tick)  a quote between bars                -> orders only when ``tick_management`` is on (a break-even / trailing stop move), otherwise []

Every method returns ``list[OrderIntent]``: plain data, no broker calls. ``route(intents, adapter)`` sends them through ``BrokerAdapter.place_order`` /
``cancel_order`` / ``modify_order`` and returns the results, so the same bot logic drives the simulation, the paper venue and a real broker.
"""
from __future__ import annotations

import abc
import math
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

# ----------------------------------------------------------------------------------------------------------------------------- data
@dataclass(frozen=True)
class Bar:
    symbol: str
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class Tick:
    symbol: str
    time: str
    bid: float
    ask: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


@dataclass(frozen=True)
class Fill:
    symbol: str
    order_id: str
    side: int                 # +1 buy, -1 sell
    qty: float
    price: float
    time: str = ""
    purpose: str = ""         # echoes OrderIntent.purpose: entry | add | trim | exit | stop | target


@dataclass(frozen=True)
class TargetLevel:
    """What a strategy returns for one bar. ``level`` is the signed fraction of unit size; ``stop`` / ``target`` are distances in price points."""
    level: float
    stop: float = 0.0
    target: float = 0.0
    tag: str = ""


@dataclass(frozen=True)
class OrderIntent:
    action: str               # "place" | "cancel" | "modify"
    symbol: str = ""
    side: int = 0             # +1 buy, -1 sell (the side of the ORDER)
    qty: float = 0.0
    order_type: str = "market"            # market | limit | stop | stop_limit
    price: float = 0.0                    # limit price (limit, stop_limit)
    stop_price: float = 0.0               # trigger (stop, stop_limit)
    reduce_only: bool = False
    purpose: str = ""                     # entry | add | trim | exit | stop | target
    order_id: str = ""                    # for cancel / modify
    tag: str = ""


@dataclass
class BotState:
    """Per instrument: the net position, the working protective orders, and what is waiting for an exit to fill."""
    symbol: str
    qty: float = 0.0                      # signed net position in units
    entry_price: float = 0.0
    stop_dist: float = 0.0
    target_dist: float = 0.0
    stop_order_id: str = ""
    target_order_id: str = ""
    stop_price: float = 0.0
    target_price: float = 0.0
    deferred_entry: Optional[TargetLevel] = None      # a flip: the new side waits until the old one is flat
    last_level: float = 0.0

    @property
    def unprotected(self) -> bool:
        return abs(self.qty) > 1e-12 and not self.stop_price

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["deferred_entry"] = self.deferred_entry.__dict__ if self.deferred_entry else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BotState":
        d = dict(d or {})
        de = d.pop("deferred_entry", None)
        st = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__ and k != "deferred_entry"})
        st.deferred_entry = TargetLevel(**de) if de else None
        return st


@dataclass(frozen=True)
class MapperConfig:
    unit_qty: float = 1.0                 # units that level 1.0 means
    allow_scaling: bool = False           # add / trim. False = one-position mode
    entry_order: str = "market"           # market | limit | stop  (entry orders for a flat -> position change)
    entry_offset: float = 0.0             # points away from the close for a limit / stop entry
    min_step: float = 1.0                 # smallest quantity change that is worth an order (whole contracts)
    tick_management: bool = False
    breakeven_after: float = 0.0          # on_tick: move the stop to entry once price is this many points in profit (0 = off)
    round_qty: Callable[[float], float] = field(default=lambda q: float(math.floor(abs(q) + 1e-9)), compare=False)


# --------------------------------------------------------------------------------------------------------------------------- mapper
class LevelMapper:
    """Pure translation of (held position, wanted level, last price) into order intents. One instance per instrument."""

    def __init__(self, cfg: MapperConfig | None = None) -> None:
        self.cfg = cfg or MapperConfig()

    def desired_qty(self, level: float) -> float:
        c = self.cfg
        if not c.allow_scaling:
            level = float((level > 1e-12) - (level < -1e-12))
        sign = 1.0 if level > 0 else -1.0 if level < 0 else 0.0
        return sign * c.round_qty(abs(level) * c.unit_qty)

    def on_level(self, st: BotState, tl: TargetLevel, last_price: float) -> list[OrderIntent]:
        c = self.cfg
        want = self.desired_qty(tl.level)
        have = st.qty
        st.last_level = tl.level
        out: list[OrderIntent] = []
        if abs(want - have) < c.min_step - 1e-12:
            return self._refresh_protection(st, tl, last_price)             # nothing to trade; a changed stop distance is still honoured
        if have != 0 and want * have <= 0:                                  # exit, or the first leg of a flip
            out += self._exit_all(st)
            if want != 0:
                st.deferred_entry = tl                                      # released by on_fill once flat
            return out
        if have == 0:
            return self._entry(st, tl, want, last_price)
        side = 1 if want > have else -1                                     # same side, different size
        delta = abs(want - have)
        if not c.allow_scaling:
            return self._refresh_protection(st, tl, last_price)
        if abs(want) > abs(have):
            out.append(OrderIntent("place", st.symbol, side, delta, "market", purpose="add", tag=tl.tag))
        else:
            out.append(OrderIntent("place", st.symbol, side, delta, "market", reduce_only=True, purpose="trim", tag=tl.tag))
        st.stop_dist, st.target_dist = tl.stop or st.stop_dist, tl.target or st.target_dist
        return out

    # -- entries
    def _entry(self, st: BotState, tl: TargetLevel, want: float, last_price: float) -> list[OrderIntent]:
        c = self.cfg
        side = 1 if want > 0 else -1
        st.stop_dist, st.target_dist = float(tl.stop), float(tl.target)
        if c.entry_order == "limit" and last_price:
            return [OrderIntent("place", st.symbol, side, abs(want), "limit", price=last_price - side * c.entry_offset, purpose="entry", tag=tl.tag)]
        if c.entry_order == "stop" and last_price:
            return [OrderIntent("place", st.symbol, side, abs(want), "stop", stop_price=last_price + side * c.entry_offset, purpose="entry", tag=tl.tag)]
        return [OrderIntent("place", st.symbol, side, abs(want), "market", purpose="entry", tag=tl.tag)]

    def _exit_all(self, st: BotState) -> list[OrderIntent]:
        out = self._cancel_protection(st)
        out.append(OrderIntent("place", st.symbol, -1 if st.qty > 0 else 1, abs(st.qty), "market", reduce_only=True, purpose="exit"))
        return out

    # -- protection
    def _cancel_protection(self, st: BotState) -> list[OrderIntent]:
        out = []
        for oid in (st.stop_order_id, st.target_order_id):
            if oid:
                out.append(OrderIntent("cancel", st.symbol, order_id=oid, purpose="exit"))
        st.stop_order_id = st.target_order_id = ""
        st.stop_price = st.target_price = 0.0
        return out

    def _protect(self, st: BotState) -> list[OrderIntent]:
        """Place / modify the stop and target for the CURRENT net position (called after every fill that changes it)."""
        out: list[OrderIntent] = []
        if abs(st.qty) < 1e-12:
            return out
        close_side = -1 if st.qty > 0 else 1
        q = abs(st.qty)
        if st.stop_dist > 0:
            px = st.entry_price - (1 if st.qty > 0 else -1) * st.stop_dist
            if st.stop_order_id:
                out.append(OrderIntent("modify", st.symbol, close_side, q, "stop", stop_price=px, reduce_only=True, purpose="stop", order_id=st.stop_order_id))
            else:
                out.append(OrderIntent("place", st.symbol, close_side, q, "stop", stop_price=px, reduce_only=True, purpose="stop"))
            st.stop_price = px
        if st.target_dist > 0:
            px = st.entry_price + (1 if st.qty > 0 else -1) * st.target_dist
            if st.target_order_id:
                out.append(OrderIntent("modify", st.symbol, close_side, q, "limit", price=px, reduce_only=True, purpose="target", order_id=st.target_order_id))
            else:
                out.append(OrderIntent("place", st.symbol, close_side, q, "limit", price=px, reduce_only=True, purpose="target"))
            st.target_price = px
        return out

    def _refresh_protection(self, st: BotState, tl: TargetLevel, last_price: float) -> list[OrderIntent]:
        if abs(st.qty) < 1e-12:
            return []
        changed = (tl.stop and abs(tl.stop - st.stop_dist) > 1e-9) or (tl.target and abs(tl.target - st.target_dist) > 1e-9)
        if not changed:
            return []
        st.stop_dist, st.target_dist = tl.stop or st.stop_dist, tl.target or st.target_dist
        return self._protect(st)

    # -- fills
    def on_fill(self, st: BotState, f: Fill, last_price: float = 0.0) -> list[OrderIntent]:
        out: list[OrderIntent] = []
        if f.purpose in ("stop", "target"):                               # a protective order filled: the other one is now dead weight
            st.qty = st.qty + f.side * f.qty if abs(st.qty) >= f.qty - 1e-12 else 0.0
            if abs(st.qty) < 1e-12:
                st.qty = 0.0
                other = st.target_order_id if f.purpose == "stop" else st.stop_order_id
                st.stop_order_id = st.target_order_id = ""
                st.stop_price = st.target_price = 0.0
                if other:
                    out.append(OrderIntent("cancel", st.symbol, order_id=other, purpose="exit"))
            return out
        prev = st.qty
        st.qty += f.side * f.qty
        if abs(st.qty) < 1e-12:
            st.qty = 0.0
        if prev == 0 and st.qty != 0:
            st.entry_price = f.price
        elif st.qty != 0 and (prev > 0) == (st.qty > 0) and abs(st.qty) > abs(prev):          # an add: volume-weighted entry
            st.entry_price = (st.entry_price * abs(prev) + f.price * f.qty) / abs(st.qty)
        if st.qty == 0:
            out += self._cancel_protection(st)
            if st.deferred_entry is not None:                             # the flip's second step
                tl, st.deferred_entry = st.deferred_entry, None
                want = self.desired_qty(tl.level)
                if want != 0:
                    out += self._entry(st, tl, want, f.price)
            return out
        out += self._protect(st)
        return out

    def on_tick(self, st: BotState, tick: Tick) -> list[OrderIntent]:
        c = self.cfg
        if not c.tick_management or c.breakeven_after <= 0 or abs(st.qty) < 1e-12 or not st.stop_order_id:
            return []
        d = 1 if st.qty > 0 else -1
        px = tick.bid if d > 0 else tick.ask
        be_ok = (px - st.entry_price) * d >= c.breakeven_after
        already = (st.stop_price - st.entry_price) * d >= 0
        if be_ok and not already:
            st.stop_price = st.entry_price
            return [OrderIntent("modify", st.symbol, -d, abs(st.qty), "stop", stop_price=st.entry_price, reduce_only=True, purpose="stop", order_id=st.stop_order_id)]
        return []


# ------------------------------------------------------------------------------------------------------------------------------- bot
class Bot(abc.ABC):
    """What the engine / runner call. Implementations decide; they never touch a broker."""

    @abc.abstractmethod
    def on_bar(self, bar: Bar) -> list[OrderIntent]: ...

    @abc.abstractmethod
    def on_fill(self, fill: Fill) -> list[OrderIntent]: ...

    def on_tick(self, tick: Tick) -> list[OrderIntent]:
        return []


class LevelBot(Bot):
    """A bot driven by target levels: ``level_fn(bar) -> TargetLevel`` per instrument, mapped to orders by LevelMapper."""

    def __init__(self, level_fn: Callable[[Bar], Optional[TargetLevel]], cfg: MapperConfig | None = None) -> None:
        self.level_fn = level_fn
        self.mapper = LevelMapper(cfg)
        self.state: dict[str, BotState] = {}
        self.last: dict[str, float] = {}

    def _st(self, sym: str) -> BotState:
        return self.state.setdefault(sym, BotState(sym))

    def on_bar(self, bar: Bar) -> list[OrderIntent]:
        self.last[bar.symbol] = bar.close
        tl = self.level_fn(bar)
        if tl is None:
            return []
        return self.mapper.on_level(self._st(bar.symbol), tl, bar.close)

    def on_fill(self, fill: Fill) -> list[OrderIntent]:
        return self.mapper.on_fill(self._st(fill.symbol), fill, self.last.get(fill.symbol, fill.price))

    def on_tick(self, tick: Tick) -> list[OrderIntent]:
        return self.mapper.on_tick(self._st(tick.symbol), tick)

    def snapshot(self) -> dict:
        return {k: v.to_dict() for k, v in self.state.items()}

    def restore(self, d: dict) -> None:
        self.state = {k: BotState.from_dict(v) for k, v in (d or {}).items()}


def route(intents: list[OrderIntent], adapter, *, to_qty: Optional[Callable[[float], float]] = None) -> list:
    """Send intents through a ``BrokerAdapter``. Returns the ``OrderResult`` of each, in order. A refused protective stop is returned like any other
    result; the caller decides (the default policy is to flatten: a position without a stop is not allowed)."""
    results = []
    for it in intents:
        q = to_qty(it.qty) if (to_qty and it.qty) else it.qty
        if it.action == "cancel":
            results.append(adapter.cancel_order(it.order_id))
        elif it.action == "modify":
            results.append(adapter.modify_order(it.order_id, price=it.price or None, stop_price=it.stop_price or None, volume=q or None))
        else:
            results.append(adapter.place_order(it.order_type, it.symbol, it.side, q, price=it.price or None, stop_price=it.stop_price or None,
                                               comment=f"T58 {it.purpose}"[:31], reduce_only=it.reduce_only))
    return results
