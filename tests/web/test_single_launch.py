"""2026-11-14 audit: launching the app must open exactly ONE browser tab, whatever else starts in the background."""
from __future__ import annotations

import json
import sys

from app.web import launcher


def test_open_browser_once_opens_a_single_tab(tmp_path, monkeypatch):
    monkeypatch.delenv(launcher.CHILD_ENV, raising=False)
    monkeypatch.delenv(launcher.NO_BROWSER_ENV, raising=False)
    opened = []
    stamp = tmp_path / "stamp.json"
    assert launcher.open_browser_once("http://127.0.0.1:5000/dashboard", opener=opened.append, now=1000.0, path=stamp) is True
    # a second launcher (for instance a re-launched frozen exe) a few seconds later must NOT open another tab
    assert launcher.open_browser_once("http://127.0.0.1:5001/dashboard", opener=opened.append, now=1003.0, path=stamp) is False
    assert opened == ["http://127.0.0.1:5000/dashboard"]
    # a genuinely later launch (the stamp has expired) opens again
    assert launcher.open_browser_once("http://127.0.0.1:5000/dashboard", opener=opened.append, now=1000.0 + 60.0, path=stamp) is True
    assert len(opened) == 2


def test_child_processes_never_open_a_tab(tmp_path, monkeypatch):
    monkeypatch.setenv(launcher.CHILD_ENV, "1")
    opened = []
    assert launcher.is_child_process()
    assert launcher.open_browser_once("http://x", opener=opened.append, path=tmp_path / "s.json") is False
    assert opened == []


def test_child_env_marks_subprocesses():
    env = launcher.child_env({"A": "1"})
    assert env["A"] == "1" and env[launcher.CHILD_ENV] == "1" and env[launcher.NO_BROWSER_ENV] == "1"


def test_main_is_a_no_op_in_a_child_process(monkeypatch, capsys):
    monkeypatch.setenv(launcher.CHILD_ENV, "1")
    launcher.main()                       # must return immediately: no banner, no server
    assert capsys.readouterr().out == ""


def test_second_launch_reuses_running_server(monkeypatch):
    monkeypatch.delenv(launcher.CHILD_ENV, raising=False)
    monkeypatch.delenv(launcher.NO_BROWSER_ENV, raising=False)
    opened = []
    monkeypatch.setattr(launcher, "t58_server_running", lambda port, timeout=1.5: True)
    monkeypatch.setattr(launcher, "open_browser_once", lambda url, **k: opened.append(url) or True)
    launcher.main()                       # returns without starting a second Flask server
    assert opened == [f"http://127.0.0.1:{launcher.PORT}/dashboard"]


def test_surrogate_study_never_relaunches_a_frozen_exe(monkeypatch, tmp_path):
    from app.discovery_engine import surrogate_schedule as ss
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("T58_AUTO_SURROGATE_STUDY", raising=False)
    monkeypatch.setattr(ss, "study_due", lambda *a, **k: {"due": True, "reasons": ["test"]})
    monkeypatch.setattr(ss, "_read_state", lambda: {})
    monkeypatch.setattr(ss, "_state_path", lambda: tmp_path / "state.json")
    calls = []
    monkeypatch.setattr(ss.subprocess, "Popen", lambda *a, **k: calls.append(a))
    # the function skips itself under pytest unless forced
    out = ss.maybe_start_background_study(force=True)
    assert out["started"] is False and calls == []
