"""Lifecycle endpoints (heartbeat, quit), the Agent Desk page and the Research ledger / closed-families page.

One Blueprint so server.py needs a single import + register line. Everything is local; nothing here starts a heavy job.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

desk_bp = Blueprint("desk_extra", __name__)


# ---------------------------------------------------------------------------------------------------------------- lifecycle
@desk_bp.route("/api/heartbeat")
def heartbeat():
    """The open page pings this every 30 s. While pings arrive the app stays up; with no page open and no job running a packaged
    build exits by itself after ``T58_IDLE_EXIT_MIN`` minutes (default 20) instead of lingering in the background."""
    from app import lifecycle
    lifecycle.heartbeat()
    return jsonify({"ok": True, "idle_exit_min": lifecycle._idle_limit_s() / 60.0})


def _is_loopback() -> bool:
    return (request.remote_addr or "") in ("127.0.0.1", "::1", "::ffff:127.0.0.1")


@desk_bp.route("/api/quit", methods=["POST"])
def quit_app():
    """Close the app completely: stops the server, worker pools and every child process. Loopback only (a phone on the LAN cannot do this)."""
    if not _is_loopback():
        return jsonify({"ok": False, "error": "Quit is only available from this computer."}), 403
    import threading
    from app import lifecycle
    threading.Timer(0.4, lambda: lifecycle.shutdown("quit requested from the app")).start()
    return jsonify({"ok": True, "message": "T58 is closing. You can close this tab."})


# ------------------------------------------------------------------------------------------------------------------ desk
def _desk():
    from app.ai.agent_desk import Desk, default_roster
    return Desk(default_roster())


@desk_bp.route("/desk")
def desk_page():
    from app.ai.agent_desk import ROLES, ROLE_ORDER
    d = _desk()
    roles = [{"id": r, "title": ROLES[r].title, "purpose": ROLES[r].purpose, "makes": ROLES[r].makes, "reads": list(ROLES[r].reads),
              "agent": d.by_role[r].id} for r in ROLE_ORDER]
    return render_template("desk.html", roles=roles, board=d.board(), n_artifacts=len(d.artifacts))


@desk_bp.route("/api/desk/board")
def desk_board():
    d = _desk()
    return jsonify({"ok": True, "board": d.board(), "n_artifacts": len(d.artifacts)})


@desk_bp.route("/api/desk/scout", methods=["POST"])
def desk_scout():
    """Ask the scout for leads: open, well-evidenced, under-tested families. Cheap (reads ledgers); starts no backtest."""
    from app.ai.agent_desk import Context
    from app.ai.agent_desk.agents import act_scout
    body = request.get_json(silent=True) or {}
    ctx = Context(candidate="", instrument=str(body.get("instrument", "")), timeframe=str(body.get("timeframe", "")))
    d = _desk()
    leads = act_scout(d, d.by_role["scout"].id, ctx, limit=int(body.get("limit", 5)))
    return jsonify({"ok": True, "leads": [{"id": a.id, "candidate": a.candidate, **a.body} for a in leads]})


# ------------------------------------------------------------------------------------------------------------------ research
@desk_bp.route("/research-ledger")
def research_ledger_page():
    from app.research_ledger import close_report, coverage_summary, grade_table, validate_coverage
    from app.research_ledger._store import read_rows
    try:
        report = close_report()
    except Exception:  # noqa: BLE001 -- the page is a report; a missing graveyard must not 500 it
        report = {"closed": [], "watch": [], "open": []}
    try:
        cov = coverage_summary()
    except Exception:  # noqa: BLE001
        cov = {"families": [], "never_tested": [], "thin_high_evidence": [], "instruments": [], "timeframes": []}
    return render_template("research_ledger.html", grades=grade_table(), coverage=cov, closure=report, check=validate_coverage(),
                           sources=read_rows("sources")[-50:][::-1], queries=read_rows("queries")[-50:][::-1])


@desk_bp.route("/api/research-ledger/reopen", methods=["POST"])
def research_reopen():
    from app.research_ledger import reopen_family
    b = request.get_json(silent=True) or {}
    try:
        res = reopen_family(str(b.get("family", "")), reason=str(b.get("reason", "")), what_changed=str(b.get("what_changed", "")))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "result": res if isinstance(res, dict) else str(res)})
