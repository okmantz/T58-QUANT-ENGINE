"""Every repo path a GitHub workflow runs or checks must exist.

When ``scripts/`` was deleted wholesale, ``full-tests.yml`` (``python scripts/build_data_manifest.py``) and ``web-cross-platform.yml``
(``scripts/web_smoke_test.py`` in the structure check and the smoke step) failed before a single test ran, on every platform. Nothing in the
Python suite noticed, because no test read the workflows. This one does.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

# a repo-relative file path under one of the folders the workflows invoke (ignores URLs, globs and ${{ expressions }})
_PATH = re.compile(r"(?<![\w/.\-$])((?:scripts|build_tools|launchers|tests|config|tools|app)/[A-Za-z0-9_./\-]+\.(?:py|spec|txt|toml|json|sh))\b")


def _referenced_paths(text: str) -> set[str]:
    return {m.group(1) for m in _PATH.finditer(text)}


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_every_file_a_workflow_names_exists(wf):
    missing = sorted(p for p in _referenced_paths(wf.read_text(encoding="utf-8")) if "*" not in p and not (ROOT / p).exists())
    assert not missing, f"{wf.name} references files that are not in the repo: {missing}"


def test_the_workflows_are_found_and_scanned():
    assert WORKFLOWS, "no workflows found under .github/workflows"
    assert {"scripts/build_data_manifest.py", "scripts/web_smoke_test.py"} <= set().union(*(_referenced_paths(w.read_text(encoding="utf-8")) for w in WORKFLOWS))
