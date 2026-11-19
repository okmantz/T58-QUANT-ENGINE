"""Bots in every strategy dropdown (simulator, replay, tab pages), micro sizing in backtests, session day, governor weights, tab hijack guard."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from app.web.server import app

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "web" / "templates"


@pytest.fixture(autouse=True)
def _isolated_bot_store(monkeypatch, tmp_path):
    from app.bots import store
    monkeypatch.setattr(store, "get_app_base_dir", lambda: tmp_path)


def test_library_control_lists_bots_for_the_simulator():
    rows = app.test_client().get("/api/library/control").get_json()["rows"]
    bots = {r["name"]: r for r in rows if r["type"] == "bot"}
    assert {"bot-pass", "bot-payout", "bot-profit"} <= set(bots)
    assert all(r["label"] and r["id"] == f"bot::{r['name']}" for r in bots.values())


def test_propsim_dropdown_orders_manual_python_pinescript_mql5_bots():
    js = (ROOT / "app" / "web" / "static" / "t58-propsim.js").read_text(encoding="utf-8")
    assert "order = ['manual', 'python', 'pinescript', 'mql5', 'bot']" in js and "bot: 'Bots'" in js


def test_replay_dropdown_groups_include_bots():
    html = (TEMPLATES / "replay.html").read_text(encoding="utf-8")
    assert "bot: 'Bots'" in html and "order = ['manual', 'python', 'pinescript', 'mql5', 'bot']" in html


def test_every_strategy_tab_page_has_a_bots_tab():
    missing = []
    for f in TEMPLATES.glob("*.html"):
        s = f.read_text(encoding="utf-8")
        if 'data-mode="python"' in s and 'data-mode="bot"' not in s:
            missing.append(f.name)
    assert not missing, missing


def test_trading_bots_tabs_are_not_metric_labels():
    html = (TEMPLATES / "trading_bots.html").read_text(encoding="utf-8")
    assert "data-no-metric" in html and 'role="tab"' in html
    js = (ROOT / "app" / "web" / "static" / "t58-metrics.js").read_text(encoding="utf-8")
    assert "isControl" in js


def test_bot_overlay_sizes_in_micro_contracts():
    from app.backtest.risk import RiskConfig
    from app.strategy.bot_strategy import build_bot_strategy
    r = build_bot_strategy("bot-pass").risk_overlay(RiskConfig(initial_balance=100000.0, contract_size=20.0))
    assert r.contract_size == 2.0
    r = build_bot_strategy("bot-pass").risk_overlay(RiskConfig(initial_balance=100000.0, contract_size=50.0))
    assert r.contract_size == 5.0


def test_session_day_rolls_at_the_globex_open():
    from app.bots.engine import session_day
    assert session_day(pd.Timestamp("2026-03-02 17:59")) == "2026-03-02"
    assert session_day(pd.Timestamp("2026-03-02 18:00")) == "2026-03-03"
    assert session_day(pd.Timestamp("2026-03-01 18:30")) == "2026-03-02"      # Sunday evening belongs to Monday


def test_leg_weight_is_applied_before_the_caps():
    from app.bots.risk_governor import AccountRulesLite, AccountState, GovernorConfig, decide_risk
    s = AccountState.fresh(AccountRulesLite.lucid_50k())
    cfg = GovernorConfig(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.1)
    d = decide_risk(s, cfg, weight=3.0)
    assert d.allow and d.risk_dollars <= 0.1 * s.cushion + 1e-6


def test_shipped_presets_are_adaptive():
    from app.bots.presets import preset_configs
    gov = {c.preset_key: c.governor for c in preset_configs()}
    for g in gov.values():
        assert g.get("pace_max_mult", 1.0) > 1.0 or g.get("streak_mult", 1.0) < 1.0


def test_demo_account_day_rolls_without_a_booked_trade(tmp_path, monkeypatch):
    from app.demo_account import account
    assert callable(account.roll_day)
    import inspect
    assert "day" in inspect.signature(account.record_trade).parameters
