"""Target-level semantics: one-position mode, add/trim, flips, stop/target management, tick break-even, routing to a broker adapter."""
from __future__ import annotations

from app.bots.interface import (Bar, BotState, Fill, LevelBot, LevelMapper, MapperConfig, OrderIntent, TargetLevel, Tick, route)
from app.live_deploy.broker_base import OrderResult
from tests.backtest.test_broker_order_types import _Bare


def _fill(it: OrderIntent, price: float, oid: str = "1") -> Fill:
    return Fill(it.symbol, oid, it.side, it.qty, price, purpose=it.purpose)


def test_one_position_mode_collapses_level_to_sign_and_attaches_protection():
    m = LevelMapper(MapperConfig(unit_qty=2, allow_scaling=False))
    st = BotState("NQ")
    out = m.on_level(st, TargetLevel(0.4, stop=20, target=40), 100.0)
    assert [(o.purpose, o.side, o.qty, o.order_type) for o in out] == [("entry", 1, 2.0, "market")]
    prot = m.on_fill(st, _fill(out[0], 100.0))
    kinds = {(o.purpose, o.order_type, o.side, o.reduce_only) for o in prot}
    assert kinds == {("stop", "stop", -1, True), ("target", "limit", -1, True)}
    assert st.stop_price == 80.0 and st.target_price == 140.0 and not st.unprotected
    assert m.on_level(st, TargetLevel(1.0, stop=20, target=40), 101.0) == []          # same size: nothing to do, no add in one-position mode


def test_scaling_adds_and_trims_and_modifies_protection():
    m = LevelMapper(MapperConfig(unit_qty=2, allow_scaling=True))
    st = BotState("NQ")
    e = m.on_level(st, TargetLevel(1.0, stop=10), 100.0)
    m.on_fill(st, _fill(e[0], 100.0))
    st.stop_order_id = "S1"
    add = m.on_level(st, TargetLevel(1.5, stop=10), 104.0)
    assert [(o.purpose, o.qty) for o in add] == [("add", 1.0)]
    mod = m.on_fill(st, _fill(add[0], 104.0))
    assert st.qty == 3.0 and abs(st.entry_price - (100 * 2 + 104) / 3) < 1e-9
    assert mod[0].action == "modify" and mod[0].order_id == "S1" and mod[0].qty == 3.0
    trim = m.on_level(st, TargetLevel(0.5, stop=10), 105.0)
    assert [(o.purpose, o.qty, o.reduce_only) for o in trim] == [("trim", 2.0, True)]


def test_exit_cancels_protection_and_flip_waits_for_flat():
    m = LevelMapper(MapperConfig(unit_qty=1))
    st = BotState("NQ")
    e = m.on_level(st, TargetLevel(1.0, stop=10, target=20), 100.0)
    m.on_fill(st, _fill(e[0], 100.0))
    st.stop_order_id, st.target_order_id = "S", "T"
    out = m.on_level(st, TargetLevel(-1.0, stop=12), 101.0)
    assert [(o.action, o.purpose) for o in out] == [("cancel", "exit"), ("cancel", "exit"), ("place", "exit")]
    assert st.deferred_entry is not None and st.qty == 1.0                             # not yet short: the exit has not filled
    after = m.on_fill(st, _fill(out[-1], 101.0))
    assert st.qty == 0.0 and [(o.purpose, o.side) for o in after] == [("entry", -1)]
    assert st.deferred_entry is None


def test_target_fill_cancels_the_stop():
    m = LevelMapper(MapperConfig(unit_qty=1))
    st = BotState("NQ")
    e = m.on_level(st, TargetLevel(1.0, stop=10, target=20), 100.0)
    m.on_fill(st, _fill(e[0], 100.0))
    st.stop_order_id, st.target_order_id = "S", "T"
    out = m.on_fill(st, Fill("NQ", "T", -1, 1.0, 120.0, purpose="target"))
    assert st.qty == 0.0 and [(o.action, o.order_id) for o in out] == [("cancel", "S")]


def test_limit_and_stop_entry_orders():
    st = BotState("NQ")
    out = LevelMapper(MapperConfig(entry_order="limit", entry_offset=2.0)).on_level(st, TargetLevel(1.0, stop=5), 100.0)
    assert (out[0].order_type, out[0].price) == ("limit", 98.0)
    st2 = BotState("NQ")
    out = LevelMapper(MapperConfig(entry_order="stop", entry_offset=3.0)).on_level(st2, TargetLevel(-1.0, stop=5), 100.0)
    assert (out[0].order_type, out[0].stop_price, out[0].side) == ("stop", 97.0, -1)


def test_tick_break_even_move_only_once():
    m = LevelMapper(MapperConfig(tick_management=True, breakeven_after=10.0))
    st = BotState("NQ")
    e = m.on_level(st, TargetLevel(1.0, stop=20), 100.0)
    m.on_fill(st, _fill(e[0], 100.0))
    st.stop_order_id = "S"
    assert m.on_tick(st, Tick("NQ", "t", 105.0, 105.25)) == []
    mv = m.on_tick(st, Tick("NQ", "t", 110.5, 110.75))
    assert mv and mv[0].action == "modify" and mv[0].stop_price == 100.0
    assert m.on_tick(st, Tick("NQ", "t", 112.0, 112.25)) == []


def test_level_bot_state_roundtrip_and_routing():
    levels = iter([TargetLevel(1.0, stop=10), TargetLevel(0.0)])
    bot = LevelBot(lambda b: next(levels), MapperConfig(unit_qty=1))
    o1 = bot.on_bar(Bar("NQ", "t1", 100, 101, 99, 100.5))
    assert o1[0].purpose == "entry"
    bot.on_fill(Fill("NQ", "1", 1, 1.0, 100.5, purpose="entry"))
    snap = bot.snapshot()
    bot2 = LevelBot(lambda b: None)
    bot2.restore(snap)
    assert bot2.state["NQ"].qty == 1.0 and bot2.state["NQ"].stop_price == 90.5
    b = _Bare()
    res = route(o1, b)
    assert len(res) == 1 and res[0].ok
    res = route([OrderIntent("place", "NQ", -1, 1, "stop", stop_price=90.0, reduce_only=True, purpose="stop")], b)
    assert not res[0].ok and "does not support" in res[0].message       # honest: this adapter has no stop orders
