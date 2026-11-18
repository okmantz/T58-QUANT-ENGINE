"""SQLite state (a restart forgets nothing), the central risk arbiter, and broker reconciliation on start."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from app.bots import store
from app.bots.arbiter import Arbiter, Limits, account_key
from app.bots.engine import BotEngine
from app.bots.models import BotConfig, BotLeg, BotRuntime, OpenPos
from app.bots.reconcile import reconcile
from app.bots.signals import LegSignal
from app.bots.venues import BrokerVenue, PaperVenue


# ------------------------------------------------------------------------------------------------------------------------ SQLite
def test_state_survives_a_restart_and_is_atomic():
    store.list_bots()
    pos = OpenPos("Ind Rule", "NQ", 1, "micro", 3, "2026-01-02T15:00:00+00:00", 21000.0, 20950.0, None, 150.0, 50.0, 2.0, ticket="T9", broker=True).to_dict()

    def fn(rec):
        rec["runtime"].update(status="running", position=pos, day_trades=2, day_key="2026-01-02", day_realised=-120.5)
        rec["trades"].append({"n": 1, "pnl": 12.0})
        rec["events"].append({"t": "x", "kind": "entry", "text": "Long"})
    store.update_bot("bot-pass", fn)
    again = store.get_bot("bot-pass")                      # a fresh connection each call == a new process reading the file
    assert again["runtime"]["position"]["ticket"] == "T9" and again["runtime"]["day_trades"] == 2 and again["runtime"]["day_realised"] == -120.5
    assert again["trades"][-1]["pnl"] == 12.0 and again["events"][-1]["kind"] == "entry"
    assert (store._path()).exists() and store._path().suffix == ".sqlite"


def test_update_rolls_back_when_the_mutation_raises():
    store.list_bots()
    before = store.get_bot("bot-pass")["runtime"]["message"]

    def boom(rec):
        rec["runtime"]["message"] = "half written"
        raise RuntimeError("crash mid-update")
    try:
        store.update_bot("bot-pass", boom)
    except RuntimeError:
        pass
    assert store.get_bot("bot-pass")["runtime"]["message"] == before


def test_legacy_json_is_imported_once(tmp_path):
    d = tmp_path / "data" / "config"
    d.mkdir(parents=True)
    cfg = BotConfig(id="old-bot", name="Legacy").to_dict()
    (d / "trading_bots.json").write_text(json.dumps({"bots": {"old-bot": {"config": cfg, "runtime": BotRuntime(status="stopped", passes=3).to_dict(),
                                                                          "trades": [{"n": 1}], "events": []}}}))
    rows = {r["config"]["id"]: r for r in store.list_bots()}
    assert rows["old-bot"]["runtime"]["passes"] == 3 and rows["old-bot"]["trades"] == [{"n": 1}]
    assert {"bot-pass", "bot-payout", "bot-profit"} <= set(rows)            # presets still seeded
    assert (d / "trading_bots.json.migrated").exists() and not (d / "trading_bots.json").exists()


def test_delete_and_reset_keep_presets():
    store.list_bots()
    assert not store.delete_bot("bot-pass")
    c = store.create_bot(BotConfig(id="mine", name="Mine"))
    assert store.delete_bot("mine") and store.get_bot("mine") is None
    store.update_bot("bot-pass", lambda r: r["trades"].append({"n": 1}))
    assert store.reset_bot("bot-pass")["trades"] == [] and store.get_bot("bot-pass")["trades"] == []
    assert c["config"]["id"] == "mine"


# ---------------------------------------------------------------------------------------------------------------------- arbiter
def _lim(**k):
    return Limits(**{"max_open_positions": 1, "max_trades_per_day": 3, **k})


def test_one_position_per_account_across_bots_and_legs():
    a = Arbiter.memory("acct")
    assert a.request_entry("botA", "IndRule", "NQ", 1, 100, "d1", _lim()).allow
    v = a.request_entry("botB", "OpenDrive", "ES", -1, 100, "d1", _lim())
    assert not v.allow and "one position at a time" in v.reason
    a.on_open("botA", "IndRule", "NQ", 1, 2, 100, "d1")
    a.on_close("botA", "IndRule", 40.0, "d1")
    assert a.request_entry("botB", "OpenDrive", "ES", -1, 100, "d1", _lim()).allow


def test_same_instrument_is_refused_even_with_room_for_two_positions():
    a = Arbiter.memory("acct")
    assert a.request_entry("botA", "L1", "NQ", 1, 50, "d", _lim(max_open_positions=2)).allow
    v = a.request_entry("botB", "L2", "NQ", -1, 50, "d", _lim(max_open_positions=2))
    assert not v.allow and "one position per instrument" in v.reason
    assert a.request_entry("botB", "L2", "ES", -1, 50, "d", _lim(max_open_positions=2)).allow


def test_combined_daily_cap_and_day_stop_span_all_strategies():
    a = Arbiter.memory("acct")
    for i, bot in enumerate(["b1", "b2", "b3"]):
        assert a.request_entry(bot, "L", "NQ", 1, 10, "d", _lim()).allow
        a.on_open(bot, "L", "NQ", 1, 1, 10, "d")
        a.on_close(bot, "L", -100.0, "d")
    v = a.request_entry("b4", "L", "NQ", 1, 10, "d", _lim())
    assert not v.allow and "daily trade cap" in v.reason
    assert a.request_entry("b4", "L", "NQ", 1, 10, "d2", _lim()).allow                      # a new day starts clean
    a2 = Arbiter.memory("x")
    a2.on_open("b1", "L", "NQ", 1, 1, 10, "d")
    a2.on_close("b1", "L", -450.0, "d")
    v = a2.request_entry("b2", "L", "ES", 1, 10, "d", _lim(max_trades_per_day=9, daily_loss_cap_usd=400))
    assert not v.allow and "day stop" in v.reason


def test_open_risk_budget_and_release():
    a = Arbiter.memory("acct")
    assert a.request_entry("b", "L1", "NQ", 1, 300, "d", _lim(max_open_positions=3, max_open_risk_usd=500)).allow
    assert not a.request_entry("b", "L2", "ES", 1, 300, "d", _lim(max_open_positions=3, max_open_risk_usd=500)).allow
    a.release("b", "L1")
    assert a.request_entry("b", "L2", "ES", 1, 300, "d", _lim(max_open_positions=3, max_open_risk_usd=500)).allow


def test_persistent_backend_shared_between_instances():
    a1, a2 = Arbiter.persistent("demo:acc"), Arbiter.persistent("demo:acc")
    assert a1.request_entry("botA", "L", "NQ", 1, 100, "d", _lim()).allow
    a1.on_open("botA", "L", "NQ", 1, 2, 100, "d")
    assert not a2.request_entry("botB", "L", "ES", 1, 100, "d", _lim()).allow             # the second process sees the first one's position
    a1.on_close("botA", "L", -25.0, "d")
    assert a2.day_state("d") == {"trades": 1, "realised": -25.0} and a2.open_positions() == []
    assert Arbiter.persistent("other:acc").day_state("d")["trades"] == 0                  # accounts are isolated


def test_account_key():
    assert account_key(SimpleNamespace(venue="broker", account_id="123")) == "broker:123"


# ----------------------------------------------------------------------------------- engine integration + reconciliation
class _Src:
    tf = 1

    def __init__(self, sig=1):
        self.sig = sig

    def at(self, bar_end):
        return LegSignal(self.sig, 20.0, float("nan"), bar_end)


def _eng(arb, bot_id, symbol="NQ", venue=None, rt=None, rules_cap=6):
    cfg = BotConfig(id=bot_id, name=bot_id, objective="A", max_trades_per_day=rules_cap, legs=[BotLeg("x", "Leg", symbol, 1.0, 0, 30)])
    cfg.account.venue = "paper"
    return BotEngine(cfg, rt or BotRuntime(status="running"), [], [], venue or PaperVenue(), {"Leg": _Src(1)}, arbiter=arb)


def _drive(eng, minutes=6, start="2026-03-03 15:00", price=21000.0, sig=None):
    t0 = pd.Timestamp(start, tz="UTC")
    for i in range(minutes):
        if sig is not None:
            eng.sources["Leg"].sig = sig
        eng.on_bar(t0 + pd.Timedelta(minutes=i), price, price + 2, price - 2, price)
    return t0 + pd.Timedelta(minutes=minutes)


def test_two_bots_on_one_account_never_hold_two_positions():
    arb = Arbiter.memory("paper:shared")
    e1, e2 = _eng(arb, "b1", "NQ"), _eng(arb, "b2", "NQ")
    for e in (e1, e2):
        e.sources["Leg"].sig = 0
    _drive(e1, 2); _drive(e2, 2)                         # arm both (a level that is already on at start is not an entry)
    for e in (e1, e2):
        e.sources["Leg"].sig = 1
    for i in range(2, 8):
        t = pd.Timestamp("2026-03-03 15:00", tz="UTC") + pd.Timedelta(minutes=i)
        e1.on_bar(t, 21000, 21002, 20998, 21000)
        e2.on_bar(t, 21000, 21002, 20998, 21000)
    held = [p for e in (e1, e2) for p in e.open_positions()]
    assert len(held) == 1 and len(arb.open_positions()) == 1
    assert any("risk arbiter" in ev["text"] for e in (e1, e2) for ev in e.events)


def test_reconcile_restores_clears_and_adopts_against_the_broker():
    class Ad:
        def __init__(self, held):
            self.held = held

        def get_open_positions(self, symbol=None):
            return [p for p in self.held if not symbol or p.symbol == symbol]

        def get_pending_orders(self, symbol=None):
            return []

        def account_summary(self):
            return {"balance": 50_000.0}

    def bp(ticket, sym="MNQ", sl=0.0):
        return SimpleNamespace(ticket=ticket, symbol=sym, direction=1, volume=2, open_price=21000.0, sl=sl, tp=0.0, open_time=pd.Timestamp("2026-03-03", tz="UTC"), profit=0.0)

    saved = OpenPos("Leg", "NQ", 1, "micro", 2, "2026-03-03T15:00:00+00:00", 21000.0, 20980.0, None, 80.0, 20.0, 2.0, ticket="A1", broker=True)
    # 1) saved position still at the broker -> restored
    rt = BotRuntime(status="running", position=saved.to_dict(), day_key="2026-03-03", day_trades=2, day_realised=-60.0)
    ven = BrokerVenue(Ad([bp("A1")]), "MNQ")
    arb = Arbiter.memory("broker:x")
    eng = _eng(arb, "bx", venue=ven, rt=rt)
    msgs = reconcile(eng, ven)
    assert eng.pos is not None and eng.pos.ticket == "A1" and len(arb.open_positions()) == 1
    assert arb.day_state("2026-03-03") == {"trades": 2, "realised": -60.0}               # the day's trades survive the restart
    # 2) saved position gone at the broker -> cleared, no invented P&L
    rt2 = BotRuntime(status="running", position=saved.to_dict())
    ven2 = BrokerVenue(Ad([]), "MNQ")
    arb2 = Arbiter.memory("broker:y")
    eng2 = _eng(arb2, "by", venue=ven2, rt=rt2)
    msgs2 = reconcile(eng2, ven2)
    assert eng2.pos is None and arb2.open_positions() == [] and eng2.trades == [] and any("gone at the broker" in m for m in msgs2)
    # 3) an unknown broker position -> adopted and flagged, never closed
    ven3 = BrokerVenue(Ad([bp("Z7", sl=20950.0)]), "MNQ")
    arb3 = Arbiter.memory("broker:z")
    eng3 = _eng(arb3, "bz", venue=ven3)
    msgs3 = reconcile(eng3, ven3)
    assert eng3.pos is not None and eng3.pos.ticket == "Z7" and eng3.pos.leg.startswith("(adopted") and any("UNMANAGED" in m for m in msgs3)
    assert len(arb3.open_positions()) == 1 and msgs and msgs2
