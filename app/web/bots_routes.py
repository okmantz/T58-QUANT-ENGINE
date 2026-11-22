"""Trading Bots: the page (/trading-bots) and its JSON API.

Three shipped bots (pass / get paid / net profit) plus the user's own. Default venue is the T58 demo account; a connected broker /
prop-firm account is a one-step switch, and starting on a broker is guarded exactly like /deploy-live/start (enable flag, app password,
unlocked session, Live mode, typed phrase).
"""
from __future__ import annotations

import copy
import uuid

from flask import Blueprint, jsonify, render_template, request, session

from app.bots import builder, runner, store
from app.bots.metrics import compute_metrics
from app.bots.models import DEMO_ACCOUNT_ID, OBJECTIVE_NAMES, AccountLink, BotConfig
from app.bots.risk_governor import GovernorConfig

bots_bp = Blueprint("trading_bots", __name__)

SIM_MONTHS = (1, 3, 6, 12, 24)
EDITABLE_GOV = {"base_risk_pct": (0.05, 3.0), "day_stop_frac": (0.05, 1.0), "late_mult": (0.1, 1.5), "cushion_risk_frac": (0.05, 1.0),
                "dd_throttle_tol_pct": (2.0, 40.0), "max_trades_hint": (1, 50)}


def _public(rec: dict, full: bool = False) -> dict:
    cfg, rt = rec["config"], rec["runtime"]
    start = float((rt.get("state") or {}).get("start_balance") or cfg.get("account", {}).get("size") or 50_000.0)
    trades = rec.get("trades", [])
    m = compute_metrics(trades, start)
    out = {"config": cfg, "runtime": rt, "metrics": m, "objective_name": OBJECTIVE_NAMES.get(cfg.get("objective"), cfg.get("objective")),
           "running": runner.is_running(cfg["id"]), "n_trades": len(trades)}
    if full:
        out["trades"] = list(reversed(trades))[:500]
        out["events"] = list(reversed(rec.get("events", [])))[:120]
    else:
        m = dict(m)
        m["equity"] = m.get("equity", [])[-80:]
        out["metrics"] = m
    return out


def _auth_state():
    try:
        from app.accounts.settings import load_account_settings
        has_password = bool(load_account_settings().has_password)
    except Exception:  # noqa: BLE001 -- fail closed
        has_password = False
    return has_password, bool(session.get("t58_unlocked"))


def _live_guard():
    """Refusal (response, status) or None. Same gate as /deploy-live/start."""
    from app.live_deploy.web_deploy_config import check_web_live_deploy
    has_password, unlocked = _auth_state()
    allowed, code, message = check_web_live_deploy(has_password, unlocked)
    if not allowed:
        return jsonify({"ok": False, "error": message}), code
    from app.demo_account import get_mode
    if get_mode() != "live":
        return jsonify({"ok": False, "error": "You are in Demo mode. Switch to Live in Account settings before trading a real account."}), 409
    return None


def _clamp(v, lo, hi):
    return max(lo, min(hi, float(v)))


@bots_bp.route("/trading-bots")
def trading_bots_page():
    from app.demo_account import account as demo, get_mode
    try:
        a = demo.load()
        demo_view = {"status": a.status, "balance": a.balance, "size": a.size}
    except Exception:  # noqa: BLE001
        demo_view = {"status": "active", "balance": 50_000.0, "size": 50_000.0}
    return render_template("trading_bots.html", mode=get_mode(), demo=demo_view, sim_months=SIM_MONTHS)


@bots_bp.route("/trading-bots/api/directive")
def api_directive():
    """The three objective directives and the engine directive, verbatim from app/objectives.py (the page shows the goal under each bot)."""
    from dataclasses import asdict
    from app.objectives import DIRECTIVES, ENGINE_DIRECTIVE
    return jsonify({"ok": True, "engine_directive": ENGINE_DIRECTIVE, "objectives": {k: asdict(v) for k, v in DIRECTIVES.items()}})


@bots_bp.route("/trading-bots/api/bots")
def api_list():
    return jsonify({"ok": True, "bots": [_public(r) for r in store.list_bots()]})


@bots_bp.route("/trading-bots/api/bot/<bot_id>")
def api_get(bot_id):
    rec = store.get_bot(bot_id)
    if rec is None:
        return jsonify({"ok": False, "error": "Unknown bot."}), 404
    return jsonify({"ok": True, "bot": _public(rec, full=True)})


@bots_bp.route("/trading-bots/api/accounts")
def api_accounts():
    """Connected broker / prop-firm accounts (never credentials) plus the demo account, for the one-step account picker."""
    out = [{"id": DEMO_ACCOUNT_ID, "name": "T58 demo account", "kind": "demo", "usable": True}]
    try:
        from app.live_deploy import connect_flow
        from app.live_deploy.live_settings import load_accounts
        for a in load_accounts():
            out.append({"id": a.id, "name": a.nickname or a.id, "kind": "broker", "platform": connect_flow.normalize_platform(a.platform),
                        "firm": a.firm_name, "live": connect_flow.account_is_live(a), "usable": bool(a.is_usable)})
    except Exception:  # noqa: BLE001
        pass
    return jsonify({"ok": True, "accounts": out})


@bots_bp.route("/trading-bots/api/history")
def api_history():
    try:
        lo, hi = runner.history_span("NQ")
        return jsonify({"ok": True, "from": str(lo.date()), "to": str(hi.date())})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 500


@bots_bp.route("/trading-bots/api/bot/<bot_id>/start", methods=["POST"])
def api_start(bot_id):
    rec = store.get_bot(bot_id)
    if rec is None:
        return jsonify({"ok": False, "error": "Unknown bot."}), 404
    body = request.get_json(silent=True) or request.form
    cfg = BotConfig.from_dict(rec["config"])
    if cfg.account.venue == "broker":
        guard = _live_guard()
        if guard:
            return guard
        if (body.get("confirm_text") or "").strip() != "DEPLOY LIVE":
            return jsonify({"ok": False, "error": "Type DEPLOY LIVE exactly, in capitals, to confirm this trades real money."}), 400
        from app.live_deploy.broker_registry import build_adapter
        from app.live_deploy.live_settings import load_accounts
        acct = next((a for a in load_accounts() if a.id == cfg.account.account_id), None)
        if acct is None:
            return jsonify({"ok": False, "error": "That broker account is not saved any more. Pick another."}), 400
        try:
            adapter = build_adapter(acct)
            cr = adapter.connect()
            if not getattr(cr, "ok", True):
                return jsonify({"ok": False, "error": f"Could not connect: {getattr(cr, 'message', 'broker refused the connection')}"}), 502
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": f"Could not connect: {exc}"}), 502
        res = runner.start_feed(bot_id, adapter, live_ok=True)
    else:
        try:
            months = _clamp(body.get("months", 3), 0.25, 36)
        except (TypeError, ValueError):
            months = 3.0
        speed = body.get("speed") if body.get("speed") in runner.SIM_SPEEDS else "fast"
        res = runner.start_simulation(bot_id, months=months, speed=speed, from_date=(body.get("from_date") or None))
    return jsonify({"ok": bool(res.get("ok")), "message": res.get("message", ""), "error": None if res.get("ok") else res.get("message")}), (200 if res.get("ok") else 409)


@bots_bp.route("/trading-bots/api/bot/<bot_id>/stop", methods=["POST"])
def api_stop(bot_id):
    if store.get_bot(bot_id) is None:
        return jsonify({"ok": False, "error": "Unknown bot."}), 404
    return jsonify(runner.stop_bot(bot_id))


@bots_bp.route("/trading-bots/api/bot/<bot_id>/reset", methods=["POST"])
def api_reset(bot_id):
    body = request.get_json(silent=True) or {}
    runner.stop_bot(bot_id, wait=3.0)
    rec = store.reset_bot(bot_id, keep_config=not bool(body.get("restore_defaults")))
    if rec is None:
        return jsonify({"ok": False, "error": "Unknown bot."}), 404
    return jsonify({"ok": True, "bot": _public(rec, full=True)})


@bots_bp.route("/trading-bots/api/bot/<bot_id>/settings", methods=["POST"])
def api_settings(bot_id):
    rec = store.get_bot(bot_id)
    if rec is None:
        return jsonify({"ok": False, "error": "Unknown bot."}), 404
    if runner.is_running(bot_id):
        return jsonify({"ok": False, "error": "Stop the bot before changing its settings."}), 409
    b = request.get_json(silent=True) or {}
    cfg = BotConfig.from_dict(rec["config"])
    if "name" in b and str(b["name"]).strip():
        cfg.name = str(b["name"]).strip()[:60]
    gov = GovernorConfig.from_dict(cfg.governor)
    kw = {}
    for k in ("base_risk_pct", "day_stop_frac", "late_mult", "cushion_risk_frac", "dd_throttle_tol_pct"):
        if k in b and b[k] not in (None, ""):
            lo, hi = EDITABLE_GOV[k]
            try:
                kw[k] = _clamp(b[k], lo, hi)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": f"{k} must be a number."}), 400
    if "compounding" in b:
        kw["compounding"] = bool(b["compounding"])
    cfg.governor = gov.with_(**kw).to_dict()
    if "max_trades_per_day" in b:
        cfg.max_trades_per_day = int(_clamp(b["max_trades_per_day"], 1, 50))
    legs_in = b.get("legs")
    if isinstance(legs_in, list):
        # Per-strategy tuning that keeps every leg's own instrument and settings: switch a leg off, or change its size (0.1 to 3).
        by_label = {lg.label: lg for lg in cfg.legs}
        off: set = set()
        for item in legs_in:
            lg = by_label.get(str((item or {}).get("label") or ""))
            if lg is None:
                continue
            if item.get("enabled") is False:
                off.add(lg.label)
                continue
            if item.get("weight") not in (None, ""):
                try:
                    lg.weight = round(_clamp(item["weight"], 0.1, 3.0), 3)
                except (TypeError, ValueError):
                    return jsonify({"ok": False, "error": f"The size of {lg.label} must be a number."}), 400
        kept = [lg for lg in cfg.legs if lg.label not in off]
        if not kept:
            return jsonify({"ok": False, "error": "Keep at least one strategy switched on."}), 400
        cfg.legs = kept
    acc = b.get("account")
    if isinstance(acc, dict):
        a = cfg.account
        venue = acc.get("venue", a.venue)
        if venue not in ("demo", "paper", "broker"):
            return jsonify({"ok": False, "error": "Venue must be demo, paper or broker."}), 400
        a.venue = venue
        if venue == "demo":
            a.account_id = DEMO_ACCOUNT_ID
        elif venue == "broker":
            if not acc.get("account_id") or acc["account_id"] == DEMO_ACCOUNT_ID:
                return jsonify({"ok": False, "error": "Pick a connected broker account."}), 400
            a.account_id = str(acc["account_id"])
        if acc.get("size"):
            a.size = _clamp(acc["size"], 1_000, 5_000_000)
        if acc.get("broker_symbol"):
            a.broker_symbol = str(acc["broker_symbol"])[:12]
        if "preset_key" in acc:
            a.preset_key = str(acc["preset_key"] or "")
    def fn(r):
        r["config"] = cfg.to_dict()
    store.update_bot(bot_id, fn)
    return jsonify({"ok": True, "bot": _public(store.get_bot(bot_id), full=True)})


@bots_bp.route("/trading-bots/api/bot/<bot_id>/duplicate", methods=["POST"])
def api_duplicate(bot_id):
    rec = store.get_bot(bot_id)
    if rec is None:
        return jsonify({"ok": False, "error": "Unknown bot."}), 404
    d = copy.deepcopy(rec["config"])
    d.update(id=uuid.uuid4().hex[:10], name=f"{d.get('name', 'Bot')} (copy)", preset_key="")
    return jsonify({"ok": True, "bot": _public(store.create_bot(BotConfig.from_dict(d)))})


@bots_bp.route("/trading-bots/api/bot/<bot_id>/delete", methods=["POST"])
def api_delete(bot_id):
    runner.stop_bot(bot_id, wait=3.0)
    if not store.delete_bot(bot_id):
        return jsonify({"ok": False, "error": "The three shipped bots cannot be deleted (reset them instead)."}), 400
    return jsonify({"ok": True})


@bots_bp.route("/trading-bots/api/kill", methods=["POST"])
def api_kill():
    return jsonify({"ok": True, "stopped": runner.kill_all()})


# ---------------------------------------------------------------------------------------------------------------- bot builder
@bots_bp.route("/trading-bots/api/builder")
def api_builder():
    """Everything the New-bot wizard needs in one call: strategies, goals, risk styles, advanced fields, rule sets, defaults per goal."""
    from app.objectives import OBJECTIVES, SPECS
    goals = [{"key": k, "name": SPECS[k].name, "question": SPECS[k].question, "rewards": SPECS[k].what_it_rewards,
              "punishes": SPECS[k].what_it_punishes, "uses_prop_rules": SPECS[k].uses_prop_rules} for k in OBJECTIVES]
    defaults = {k: {st: builder.style_governor(k, st).to_dict() for st in builder.RISK_STYLES} for k in OBJECTIVES}
    return jsonify({"ok": True, "strategies": builder.strategy_catalog(), "goals": goals, "styles": builder.RISK_STYLES,
                    "style_labels": builder.STYLE_LABELS, "fields": builder.GOVERNOR_FIELDS, "defaults": defaults,
                    "rule_sets": builder.prop_rule_sets(), "instruments": builder.INSTRUMENTS, "max_legs": builder.MAX_LEGS})


@bots_bp.route("/trading-bots/api/builder/preview", methods=["POST"])
def api_builder_preview():
    """Validate a wizard payload and return the plain-words summary without saving anything."""
    body = request.get_json(silent=True) or {}
    existing = None
    if body.get("bot_id"):
        rec = store.get_bot(str(body["bot_id"]))
        existing = BotConfig.from_dict(rec["config"]) if rec else None
    cfg, errors, warnings = builder.build_config(body, existing=existing)
    out = {"ok": not errors, "errors": errors, "warnings": warnings}
    if cfg is not None:
        out["summary"] = builder.describe(cfg)
        out["governor"] = cfg.governor
    return jsonify(out), (200 if not errors else 400)


@bots_bp.route("/trading-bots/api/bots/create", methods=["POST"])
def api_create_bot():
    body = request.get_json(silent=True) or {}
    cfg, errors, warnings = builder.build_config(body)
    if cfg is None:
        return jsonify({"ok": False, "error": errors[0], "errors": errors, "warnings": warnings}), 400
    rec = store.create_bot(cfg)
    return jsonify({"ok": True, "warnings": warnings, "bot": _public(rec, full=True)})


@bots_bp.route("/trading-bots/api/bot/<bot_id>/update", methods=["POST"])
def api_update_bot(bot_id):
    """Full edit with the same form as the wizard (name, goal, strategies, risk, limits, account)."""
    rec = store.get_bot(bot_id)
    if rec is None:
        return jsonify({"ok": False, "error": "Unknown bot."}), 404
    if runner.is_running(bot_id):
        return jsonify({"ok": False, "error": "Stop the bot before changing its settings."}), 409
    body = request.get_json(silent=True) or {}
    cfg, errors, warnings = builder.build_config(body, existing=BotConfig.from_dict(rec["config"]))
    if cfg is None:
        return jsonify({"ok": False, "error": errors[0], "errors": errors, "warnings": warnings}), 400
    store.update_bot(bot_id, lambda r: r.__setitem__("config", cfg.to_dict()))
    return jsonify({"ok": True, "warnings": warnings, "bot": _public(store.get_bot(bot_id), full=True)})


@bots_bp.route("/trading-bots/api/strategies/add", methods=["POST"])
def api_add_strategy():
    body = request.get_json(silent=True) or {}
    row, err = builder.add_strategy(body.get("filename", ""), body.get("code", ""), body.get("type", ""))
    if err:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "strategy": row})
