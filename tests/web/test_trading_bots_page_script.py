"""Regression: a single JS syntax error in the Trading Bots page left it on "Loading bots" with dead buttons. Every inline script must parse."""
from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from app.web.server import app


def _scripts(html: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S | re.I) if m.group(1).strip()]


def test_page_renders_and_wires_its_buttons():
    r = app.test_client().get("/trading-bots")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    for ident in ("tb-cards", "tb-new", "tb-kill", "wz-back"):
        assert f'id="{ident}"' in html
    js = "\n".join(_scripts(html))
    assert "$('tb-new').onclick" in js and "$('tb-kill').onclick" in js


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_inline_scripts_are_valid_javascript(tmp_path):
    html = app.test_client().get("/trading-bots").get_data(as_text=True)
    for i, code in enumerate(_scripts(html)):
        f = tmp_path / f"s{i}.js"
        f.write_text(code, encoding="utf-8")
        p = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr[:800]
