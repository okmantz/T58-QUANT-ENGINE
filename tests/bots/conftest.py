from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_bot_store(monkeypatch, tmp_path):
    """Every bots test gets its own base dir so trading_bots.json never touches the repo's data/ folder."""
    from app.bots import store
    monkeypatch.setattr(store, "get_app_base_dir", lambda: tmp_path)
    yield
