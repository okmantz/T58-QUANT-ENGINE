"""Weekly digest email: rendering, schedule anchor, opt-out and delivery gating."""
from __future__ import annotations

import time
from datetime import datetime

from app.inbox import digest_email as de

DG = {"title": "Your week in the lab (Nov 16 - Nov 23)", "subtitle": "s", "empty": False, "empty_line": "",
      "stats": {"experiments": 5, "passed": 2, "failed": 3, "buried": 1},
      "sections": [{"id": "tested", "title": "Tested", "headline": "5 experiments", "items": ["a <b>", "b"]}]}


def test_render_escapes_and_has_parts():
    subject, html, text = de.render(DG, "me@example.com", "Owen")
    assert "5 experiments" in subject
    assert "a &lt;b&gt;" in html and "<b>" not in html.split("Tested")[1].split("Your next step")[0]
    assert "Account settings" in html and "Account settings" in text
    assert "Open T58" in html


def test_due_anchor_is_a_sunday_8am():
    key, ts = de.due_anchor(time.time())
    dt = datetime.fromtimestamp(ts)
    assert dt.weekday() == 6 and dt.hour == 8 and key == "weekly-" + dt.strftime("%Y-%m-%d")
    assert ts <= time.time()


def test_opt_out_blocks_send(tmp_path, monkeypatch):
    monkeypatch.setattr(de, "_prefs_path", lambda: tmp_path / "p.json")
    assert de.load_prefs()["enabled"] is True          # default on
    de.save_prefs(enabled=False)
    assert de.send_due_digest()["reason"] == "opted_out"
    de.save_prefs(enabled=True, last_sent_key=de.due_anchor()[0])
    assert de.send_due_digest()["reason"] == "already_sent"
