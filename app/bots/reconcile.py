"""Restart reconciliation: a bot that was stopped, crashed or redeployed must not forget what it holds, and must not trust its memory over the broker.

``reconcile(engine, venue)`` compares the engine's persisted positions (restored from SQLite) with the broker and fixes the difference, never silently:

  * position in the bot's state AND at the broker   -> kept; quantity / ticket refreshed from the broker.
  * position in the bot's state, GONE at the broker -> it was closed while the bot was down (stop, target or by hand). The lane is cleared; no P&L is
                                                       invented: the event says so and the account balance is re-read from the broker.
  * position at the broker the bot does not know    -> an ORPHAN. It is adopted (so the bot's flatten rules and the arbiter's slot see it) with the broker's
                                                       own stop if it has one, and flagged loudly. It is never closed or opened without a rule saying so.
  * working orders at the broker the bot did not place with this tag are reported, not cancelled.

The arbiter's slots are then rebuilt from the result and the day ledger is raised to the bot's persisted day counters. For simulated venues there is no
broker to ask: only the arbiter is rebuilt from the restored lanes. Returns the list of messages (also written to the bot's event log).
"""
from __future__ import annotations

import pandas as pd

from app.bots.models import OpenPos, now_iso


def _broker_symbol(venue, sym: str) -> str:
    return getattr(venue, "symbol_map", {}).get(sym, getattr(venue, "symbol", sym))


def reconcile(eng, venue) -> list[str]:
    msgs: list[str] = []
    day = eng.rt.day_key or ""

    def say(kind: str, text: str) -> None:
        msgs.append(text)
        eng._event(kind, text)

    if not getattr(venue, "simulated_fills", True):
        adapter = venue.adapter
        try:
            held = list(adapter.get_open_positions())
        except Exception as exc:  # noqa: BLE001
            say("warn", f"Reconcile: could not read the broker's positions ({exc}). Trading continues on the saved state; check the account by hand.")
            held = None
        if held is not None:
            by_ticket = {str(p.ticket): p for p in held}
            used: set = set()
            for sym, lane in eng.lanes.items():
                bsym = _broker_symbol(venue, sym)
                if lane.pos is not None:
                    bp = by_ticket.get(str(lane.pos.ticket))
                    if bp is None:
                        say("warn", f"Reconcile: {lane.pos.leg} {sym} was open in the bot but is gone at the broker (closed while the bot was down: stop, target or manual). "
                                    f"Lane cleared; P&L is not guessed, balance is re-read from the broker.")
                        lane.pos = None
                        lane.pending = None
                    else:
                        used.add(str(bp.ticket))
                        if abs(float(bp.volume) - float(lane.pos.qty)) > 1e-9 and getattr(venue, "contract_size", 0):
                            say("warn", f"Reconcile: {sym} quantity differs (bot {lane.pos.qty}, broker {bp.volume}); the broker's figure is used.")
                            lane.pos.qty = int(round(float(bp.volume)))
                for bp in held:
                    if str(bp.ticket) in used or bp.symbol != bsym or lane.pos is not None:
                        continue
                    stop = float(bp.sl or 0.0)
                    lane.pos = OpenPos(leg="(adopted at restart)", symbol=sym, direction=int(bp.direction), kind="micro", qty=int(round(float(bp.volume))),
                                       entry_time=pd.Timestamp(bp.open_time).isoformat(), entry_price=float(bp.open_price), stop_price=stop,
                                       tp_price=float(bp.tp) if bp.tp else None, risk_dollars=0.0, stop_points=abs(float(bp.open_price) - stop) if stop else 0.0,
                                       mult=1.0, ticket=str(bp.ticket), broker=True)
                    used.add(str(bp.ticket))
                    say("error" if not stop else "warn",
                        f"Reconcile: the broker holds an UNMANAGED {'long' if bp.direction > 0 else 'short'} {bp.volume} {bp.symbol} @ {bp.open_price} that this bot did not "
                        f"know about{'' if stop else ' and it has NO STOP'}. It was adopted so the flatten window and the risk arbiter see it; nothing was closed.")
            try:
                for o in adapter.get_pending_orders():
                    say("warn", f"Reconcile: working {o.order_type} order {o.order_id} on {o.symbol} ({o.volume} @ {o.price or o.stop_price}) found at the broker; left untouched.")
            except Exception:  # noqa: BLE001
                pass
            try:
                venue.sync_state(eng.acct)
            except Exception:  # noqa: BLE001
                pass
    # the arbiter mirrors what is really held now
    rows = [{"leg": ln.pos.leg, "symbol": ln.pos.symbol, "direction": ln.pos.direction, "qty": ln.pos.qty, "risk_dollars": ln.pos.risk_dollars,
             "opened": ln.pos.entry_time} for ln in eng.lanes.values() if ln.pos is not None]
    eng.arbiter.sync_open(eng.cfg.id, rows)
    if day:
        eng.arbiter.ensure_day(day, int(eng.rt.day_trades), float(eng.rt.day_realised))
    if rows and not msgs:
        say("info", f"Reconcile: {len(rows)} open position(s) restored from the saved state: " + ", ".join(f"{r['symbol']} {r['leg']}" for r in rows) + ".")
    eng._persist_state()
    return msgs
