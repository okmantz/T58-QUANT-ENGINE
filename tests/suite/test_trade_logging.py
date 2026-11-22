"""Every trade a deployed bot or strategy takes lands in the Trading Journal's trade log, and every trade log exports to CSV."""
from __future__ import annotations

import csv
import io
import time

import pytest

from app.bots import runner, store
from app.journal import capture, export
from app.web import journal_store as js
from app.web.server import app


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture(autouse=True)
def _bots_in_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "get_app_base_dir", lambda: tmp_path)
    yield


def _run_bot(bot_id: str, months: float = 1):
    store.list_bots()
    assert runner.start_simulation(bot_id, months=months, speed="instant")["ok"]
    t0 = time.time()
    while runner.is_running(bot_id) and time.time() - t0 < 180:
        time.sleep(0.3)


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))


def test_bot_trades_reach_journal_demo_account_and_exports(client):
    _run_bot("bot-pass")
    rec = store.get_bot("bot-pass")
    n = len(rec["trades"])
    assert n > 0, "the shipped pass bot should trade a month of replay"
    rt = rec["runtime"]
    assert rt["trades_total"] == n and rt["journal_cursor"] == n          # every booked trade was flushed to the journal

    # 1) the journal's trade log has one entry per bot trade, with entry/exit times and the account it traded
    j = [t for t in js.load()["trades"] if t.get("source") == "Trading Bot"]
    assert len(j) == n
    t0 = j[0]
    assert t0["entryTime"] and t0["exitTime"] and t0["account"].startswith("T58 Demo") and t0["bot"] and t0["exitReason"] is not None

    # 2) syncing again (the journal page does this on every load) never duplicates
    assert capture.sync_bots() == 0
    assert len([t for t in js.load()["trades"] if t.get("source") == "Trading Bot"]) == n

    # 3) the demo account's own trade log carries the same trades with entry times and the bot's name
    d = client.get("/api/demo-account/trades").get_json()
    assert d["ok"] and d["n"] == n
    assert d["trades"][0]["opened_at"] and d["trades"][0]["bot"]

    # 4) CSV exports: journal, journal stats, demo account, bot trades, bot stats
    jr = _rows(client.get("/api/journal/export.csv").data.decode())
    assert len(jr) == n and {"entry_time", "exit_time", "duration_min", "pnl_usd", "r_multiple", "cumulative_pnl_usd"} <= set(jr[0])
    assert abs(float(jr[-1]["cumulative_pnl_usd"]) - sum(float(r["pnl_usd"]) for r in jr)) < 0.05
    assert len(_rows(client.get("/api/journal/export.csv?source=Manual").data.decode())) == 0
    st = {r["metric"]: r["value"] for r in _rows(client.get("/api/journal/export-stats.csv").data.decode())}
    assert int(st["trades"]) == n and "profit_factor" in st and "max_drawdown_usd" in st
    dr = _rows(client.get("/api/demo-account/trades.csv").data.decode())
    assert len(dr) == n and dr[0]["entry_time"] and dr[0]["bot"]
    br = client.get("/trading-bots/api/bot/bot-pass/trades.csv")
    assert br.status_code == 200 and "text/csv" in br.content_type and "attachment" in br.headers["Content-Disposition"]
    brows = _rows(br.data.decode())
    assert len(brows) == n and brows[0]["entry_time"] and brows[0]["exit_reason"] != "x"
    bs = {r["metric"]: r["value"] for r in _rows(client.get("/trading-bots/api/bot/bot-pass/stats.csv").data.decode())}
    assert int(bs["trades"]) == n and "win_rate_pct" in bs


def test_sync_backfills_trades_booked_before_capture_existed():
    store.list_bots()
    row = {"n": 1, "bot": "Old run", "leg": "Open Drive", "symbol": "NQ", "side": "long", "qty": 2, "kind": "micro",
           "entry_time": "2026-03-02T14:35:00+00:00", "exit_time": "2026-03-02T15:10:00+00:00", "entry": 18000.0, "exit": 18010.0, "pnl": 38.5,
           "r_multiple": 0.8, "risk": 48.0, "reason": "target", "mult": 1.0, "day": "2026-03-02", "balance": 50038.5}
    store.update_bot("bot-pass", lambda r: r["trades"].append(row))
    assert capture.sync_bots() == 1
    e = [t for t in js.load()["trades"] if t.get("source") == "Trading Bot"][0]
    assert e["pnl"] == 38.5 and e["durationMin"] == 35.0 and e["setup"] == "target hit"


def test_notes_typed_on_a_captured_trade_survive_a_resync():
    store.list_bots()
    row = {"n": 1, "bot": "B", "leg": "L", "symbol": "ES", "side": "short", "qty": 1, "entry_time": "2026-03-03T14:00:00+00:00",
           "exit_time": "2026-03-03T14:20:00+00:00", "entry": 5000.0, "exit": 4990.0, "pnl": 100.0, "risk": 50.0, "reason": "stop"}
    cfg = {"id": "bot-pass", "name": "B", "account": {"venue": "paper", "size": 50000}}
    assert capture.capture_bot_trades(cfg, [row]) == 1
    t = js.load()["trades"][0]
    js.upsert_trade({**t, "notes": "my own note"})
    assert capture.capture_bot_trades(cfg, [row]) == 0                      # already journaled: untouched
    assert js.load()["trades"][0]["notes"] == "my own note"


def test_manual_demo_trade_is_journaled(client):
    r = client.post("/demo-account/sim-trade", json={"pnl": 125.5, "root": "NQ", "side": "long"})
    assert r.status_code == 200
    e = [t for t in js.load()["trades"] if t.get("source") == "Demo"]
    assert len(e) == 1 and e[0]["pnl"] == 125.5 and e[0]["account"] == "T58 Demo"


def test_relay_paper_trades_are_journaled():
    from app.webhook_relay import config as rc, engine as rl
    from app.webhook_relay.signals import Signal
    relay = rc.create_relay({"name": "TV test"})
    rl.handle(relay, Signal(ticker="NQ1!", target="long", price=18000.0, quantity=1, passphrase=relay.passphrase))
    out = rl.handle(relay, Signal(ticker="NQ1!", target="flat", price=18020.0, quantity=None, passphrase=relay.passphrase))
    assert out["status"] == "executed", out
    e = [t for t in js.load()["trades"] if t.get("source") == "Demo"]
    assert len(e) == 1 and e[0]["pnl"] > 0 and e[0]["strategy"] == "TV test"


def test_csv_cells_cannot_run_as_spreadsheet_formulas():
    text = export.to_csv(["a", "b", "c"], [{"a": "=HYPERLINK(\"x\")", "b": "-5.5", "c": "-evil"}])
    row = _rows(text)[0]
    assert row["a"].startswith("'=") and row["b"] == "-5.5" and row["c"].startswith("'-")


def test_summary_stats_math():
    st = dict(export.summary_stats([100, -50, 100, -25, -25], days={"d1": 50, "d2": 50}, start_balance=1000))
    assert st["trades"] == 5 and st["win_rate_pct"] == 40.0 and st["net_pnl_usd"] == 100
    assert st["profit_factor"] == 2.0 and st["max_loss_streak"] == 2 and st["max_drawdown_usd"] == 50
    assert st["ending_balance_usd"] == 1100 and st["green_days"] == 2
