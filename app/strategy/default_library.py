"""The default strategy library: every strategy that ships with the app (strategies/<type>/ in the GitHub repo).

Rules the app follows with it:
  * The list of defaults is DISCOVERED, never hand-maintained: whatever strategy files sit in the shipped
    strategies/ folder (the PyInstaller bundle in a packaged build, this repo's strategies/ folder when running from
    source) are the defaults. Drop a .py / .pine / .mq5 file in strategies/<type>/ and it is preloaded for every user.
  * First sign-in on a device (or a different account signing in): the library holds ONLY these defaults. Anything else found in
    the strategies folder (left over from another account, testing, an old install) is MOVED to a dated backup folder, never deleted.
  * After that the library saves every new strategy normally, and the account's vault brings them back after a reinstall.
  * The master key resets it to the defaults every time it is entered (see app.licensing.fresh_start).
"""
from __future__ import annotations

import fnmatch
import json
import shutil
import sys
import time
from pathlib import Path

_TYPE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "python": (".py",),
    "pinescript": (".pine",),
    "mql5": (".mq5",),
    "manual": (".json",),
}
# Same patterns .gitignore keeps out of the repo: per-user artefacts that are never defaults.
_NOT_DEFAULT_PATTERNS = ("*.meta.json", "searchlab_*", "stub.*", "*FULL PIPELINE*")


def _shipped_dir() -> Path:
    """Folder holding the strategies that ship with this build."""
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle and (Path(bundle) / "strategies").is_dir():
            return Path(bundle) / "strategies"
    return Path(__file__).resolve().parents[2] / "strategies"


def discover_default_files(root: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Scan the shipped strategies folder and return {type: (file names, ...)} (sorted)."""
    root = root or _shipped_dir()
    found: dict[str, tuple[str, ...]] = {}
    for type_dir, exts in _TYPE_EXTENSIONS.items():
        d = root / type_dir
        names: list[str] = []
        if d.is_dir():
            for f in d.iterdir():
                if not f.is_file() or f.suffix.lower() not in exts:
                    continue
                if any(fnmatch.fnmatch(f.name, pat) for pat in _NOT_DEFAULT_PATTERNS):
                    continue
                names.append(f.name)
        found[type_dir] = tuple(sorted(names))
    return found


DEFAULT_STRATEGY_FILES: dict[str, tuple[str, ...]] = discover_default_files()
_KEEP_NAMES = {"readme.md", "strategy_format.md", ".gitkeep"}
_MARKER = "library_account.json"


def _lib_dir() -> Path:
    from app.data.storage import get_app_base_dir
    return get_app_base_dir() / "strategies"


def _marker() -> Path:
    from app.data.storage import user_data_dir
    return user_data_dir() / _MARKER


def _is_default(type_dir: str, name: str) -> bool:
    return name in DEFAULT_STRATEGY_FILES.get(type_dir, ())


def _bust_cache() -> None:
    try:
        from app.strategy import library
        library._LIBRARY_SCAN_CACHE.update(key=None, rows=None)
    except Exception:  # noqa: BLE001
        pass


def reset_to_defaults(backup_dir: Path | None = None) -> int:
    """Move every non-default strategy (and every sidecar, so default strategies also start un-run) into backup_dir.
    Returns how many files were moved. Never raises."""
    moved = 0
    try:
        root = _lib_dir()
        if backup_dir is None:
            from app.data.storage import user_data_dir
            backup_dir = user_data_dir() / "strategy_backups" / time.strftime("%Y%m%d-%H%M%S")
        for type_dir in DEFAULT_STRATEGY_FILES:
            d = root / type_dir
            if not d.is_dir():
                continue
            for f in list(d.iterdir()):
                if not f.is_file() or f.name.lower() in _KEEP_NAMES:
                    continue
                if _is_default(type_dir, f.name):
                    continue
                dest = backup_dir / type_dir / f.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(f), str(dest))
                    moved += 1
                except OSError:
                    pass
    except Exception:  # noqa: BLE001
        pass
    _bust_cache()
    return moved


def _account_id(license_key: str) -> str:
    from app.persistence import vault
    return vault._key_id(license_key)


def forget_account() -> None:
    try:
        _marker().unlink()
    except OSError:
        pass


def prepare_for_account(license_key: str) -> bool:
    """Call right after a successful sign-in, BEFORE the vault restore. Resets the library to the defaults unless this same
    account was already the one using this device. Returns True when it reset. Never raises."""
    try:
        import os
        if "PYTEST_CURRENT_TEST" in os.environ and os.environ.get("T58_FORCE_LIBRARY_RESET") != "1":
            return False
        acct = _account_id(license_key)
        try:
            prev = json.loads(_marker().read_text(encoding="utf-8")).get("account")
        except Exception:  # noqa: BLE001
            prev = None
        if prev == acct:
            return False
        if prev:      # a different account was using this device: park its runs/settings too (its vault keeps a copy)
            try:
                from app.licensing import fresh_start
                fresh_start.clear_for_account_switch()
            except Exception:  # noqa: BLE001
                pass
        reset_to_defaults()
        _marker().parent.mkdir(parents=True, exist_ok=True)
        _marker().write_text(json.dumps({"account": acct, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}), encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001
        return False
