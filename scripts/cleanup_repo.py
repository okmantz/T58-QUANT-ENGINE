"""One-shot repo cleanup. A zip cannot delete files, so run this once after pasting the update in:

    python scripts/cleanup_repo.py            # show what would go
    python scripts/cleanup_repo.py --apply    # do it (git rm for tracked files, plain delete for local junk)

Removes: the four docs merged into docs/RESEARCH_AND_AUDIT.md and docs/ENGINES.md, the root phone guide (now docs/PHONE_ACCESS.md), and the
files test runs used to leave in data/, reports/ and strategies/ (numbered import copies like "AAA (7).csv", sample AAA/BBB/EURUSD files,
timestamped reports, saved searchlab strategies, journal / forward-test / achievement state). The three shipped parquet files, reports/prop30,
and the four example strategies are kept. Anything the script would touch that you actually use is listed first; nothing is removed without --apply."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKED_REMOVE = ["docs/PROP30_AUDIT.md", "docs/PROP30_RESEARCH_REPORT.md", "docs/DISCOVERY_ENGINE.md", "docs/GLOBAL_EVENTS.md",
                  "HOW TO OPEN ON YOUR PHONE.md"]
JUNK_PATTERNS = [
    ("data/raw/EURUSD", r".*"), ("data/raw", r"^(AAA|BBB|CCC|EURUSD|TEST|SAMPLE)[^/]*\.(csv|parquet)$|^.* \(\d+\)\.csv$"),
    ("data", r"^(achievements\.json|ui_prefs\.json)$"),
    ("data/journal", r".*"), ("data/forward_test", r".*"), ("data/buy_challenge", r".*"), ("data/guardian", r".*"), ("data/prop_desk", r".*"),
    ("data/config", r"^(issue_reports\.jsonl|validation_checklist\.json)$"),
    ("reports", r"^[^/]+\.(html|json|csv|jsonl|head|lock)$"), ("reports/full_pipeline", r".*"),
    ("strategies", r".*(searchlab_|stub\.|FULL PIPELINE|\.meta\.json|\.versions).*"),
]


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _tracked() -> set:
    r = _git("ls-files")
    return set(r.stdout.splitlines()) if r.returncode == 0 else set()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
    a = ap.parse_args(argv)
    tracked = _tracked()
    keep = {"strategies/python/", "reports/prop30/"}
    doomed_tracked = [p for p in TRACKED_REMOVE if p in tracked]
    local: list = []
    for base, pat in JUNK_PATTERNS:
        b = ROOT / base
        if not b.exists():
            continue
        rx = re.compile(pat)
        for f in (b.rglob("*") if base in ("strategies", "reports/full_pipeline", "data/journal", "data/forward_test", "data/buy_challenge",
                                           "data/guardian", "data/prop_desk", "data/raw/EURUSD") else b.glob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(ROOT).as_posix()
            if rel in tracked or any(rel.startswith(k) for k in keep) or rel.endswith(".gitkeep") or rel.endswith(".parquet") and rel.count("/") == 3:
                continue
            if rx.match(f.relative_to(b).as_posix()):
                local.append(f)
    print(f"{len(doomed_tracked)} tracked file(s) to git rm, {len(local)} local junk file(s) to delete.")
    for p in doomed_tracked:
        print("  git rm", p)
    for f in local[:40]:
        print("  del   ", f.relative_to(ROOT).as_posix())
    if len(local) > 40:
        print(f"  ... and {len(local) - 40} more")
    if not a.apply:
        print("\nDry run. Re-run with --apply to do it.")
        return 0
    for p in doomed_tracked:
        _git("rm", "-q", "--", p)
    for f in local:
        try:
            f.unlink()
        except OSError as exc:
            print("could not delete", f, exc)
    print("Done. Review with `git status`, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
