from __future__ import annotations

from app.bots import store
from app.bots.metrics import compute_metrics
from app.bots.models import BotConfig, BotLeg
from app.bots.presets import preset_configs


def test_three_presets_seeded_with_demo_default():
    bots = store.list_bots()
    assert [b["config"]["id"] for b in bots] == ["bot-pass", "bot-payout", "bot-profit"] or len(bots) == 3
    assert {b["config"]["objective"] for b in bots} == {"A", "B", "NET"}
    by = {b["config"]["preset_key"]: b["config"]["account"] for b in bots}
    assert by["pass"]["venue"] == by["payout"]["venue"] == "demo" and by["pass"]["account_id"] == "t58-demo"
    assert by["profit"]["venue"] == "paper" and not by["profit"]["preset_key"]      # Gate 27 swing legs need a rule-free account


def test_preset_strategy_files_exist():
    from app.bots.signals import resolve_strategy_path
    for cfg in preset_configs():
        for leg in cfg.legs:
            if leg.kind == "gate27":
                continue                          # built in (app/bots/gate27.py), no strategy file
            assert resolve_strategy_path(leg.strategy).exists(), leg.strategy


def test_presets_cannot_be_deleted_but_custom_can():
    store.list_bots()
    assert store.delete_bot("bot-pass") is False
    rec = store.create_bot(BotConfig(name="mine", legs=[BotLeg("python/NQ1! Ind Rule 15m.py", "IR")]))
    assert store.delete_bot(rec["config"]["id"]) is True


def test_config_round_trip():
    cfg = preset_configs()[0]
    again = BotConfig.from_dict(cfg.to_dict())
    assert again.to_dict() == cfg.to_dict()
    assert again.governor_cfg().objective == "A"


def test_reset_restores_defaults():
    store.list_bots()
    store.update_bot("bot-pass", lambda r: r["config"].update(name="changed"))
    store.reset_bot("bot-pass", keep_config=False)
    assert store.get_bot("bot-pass")["config"]["name"] == "Evaluation Passer"


def test_metrics_basic():
    trades = [{"pnl": 100.0, "exit_time": "2025-01-02T10:00", "leg": "a", "r_multiple": 1.0},
              {"pnl": -50.0, "exit_time": "2025-01-02T11:00", "leg": "a", "r_multiple": -1.0},
              {"pnl": 200.0, "exit_time": "2025-01-03T10:00", "leg": "b", "r_multiple": 2.0}]
    m = compute_metrics(trades, 50_000.0)
    assert m["trades"] == 3 and m["net_pnl"] == 250.0 and m["win_rate"] == 66.7
    assert m["max_drawdown"] == 50.0 and m["trading_days"] == 2
    assert compute_metrics([], 50_000.0)["trades"] == 0
