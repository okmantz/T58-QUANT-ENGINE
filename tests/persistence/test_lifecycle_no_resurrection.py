"""The "t58 folder reappears after I delete it" regression: nothing may recreate a deleted install folder."""
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast


def _frozen(monkeypatch, tmp_path):
    install = tmp_path / "t58"
    install.mkdir()
    exe = install / "T58.exe"
    exe.write_bytes(b"x")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    import app.data.storage as st
    monkeypatch.setattr(st, "_BASE_CACHE", None)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "xdg"))
    return install, exe, st


def test_get_app_base_dir_never_recreates_a_deleted_install_folder(monkeypatch, tmp_path):
    install, exe, st = _frozen(monkeypatch, tmp_path)
    assert st.get_app_base_dir() == install
    shutil.rmtree(install)
    for _ in range(3):                                   # a lingering thread calling it repeatedly
        st._BASE_CACHE = None if not install.exists() else st._BASE_CACHE
        st.get_app_base_dir()
    assert not install.exists(), "get_app_base_dir() recreated the deleted install folder"


def test_base_dir_is_probed_once_and_cached(monkeypatch, tmp_path):
    install, exe, st = _frozen(monkeypatch, tmp_path)
    a = st.get_app_base_dir()
    (install / ".t58_write_test").write_text("sentinel")   # a later call must not touch the probe file again
    assert st.get_app_base_dir() == a
    assert (install / ".t58_write_test").read_text() == "sentinel"


def test_install_present_tracks_the_folder(monkeypatch, tmp_path):
    install, exe, st = _frozen(monkeypatch, tmp_path)
    from app import lifecycle
    assert lifecycle.install_present()
    shutil.rmtree(install)
    assert not lifecycle.install_present()


def test_vault_loop_and_restore_do_nothing_without_an_install_folder(monkeypatch, tmp_path):
    install, exe, st = _frozen(monkeypatch, tmp_path)
    from app import lifecycle
    from app.persistence import vault
    shutil.rmtree(install)
    assert vault._restore_everything() == {"skipped": "install folder missing"}
    vault._safe_final_backup()                           # must be a silent no-op
    assert not install.exists()
    assert lifecycle.install_present() is False


def test_shutdown_runs_hooks_once_and_skips_writers_when_folder_is_gone(monkeypatch, tmp_path):
    install, exe, st = _frozen(monkeypatch, tmp_path)
    from app import lifecycle
    calls = []
    monkeypatch.setattr(lifecycle, "_HOOKS", [])
    monkeypatch.setattr(lifecycle, "_down", False)
    monkeypatch.setattr(lifecycle, "_terminate_children", lambda: calls.append("kids"))
    lifecycle.register("pool", lambda: calls.append("pool"))
    lifecycle.register("write:backup", lambda: calls.append("backup"))
    shutil.rmtree(install)
    lifecycle.shutdown("test", exit_process=False)
    lifecycle.shutdown("again", exit_process=False)      # idempotent
    assert calls == ["pool", "kids"]
    monkeypatch.setattr(lifecycle, "_down", False)
    lifecycle._STOP.clear()


def test_qr_code_is_written_to_temp_not_home(monkeypatch, tmp_path):
    pytest.importorskip("qrcode")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    from app.web.network_info import qr_code_file
    p = qr_code_file("http://127.0.0.1:5000")
    assert p is not None and "t58-phone-qr-code" in p.name
    assert not (tmp_path / "home").exists()
