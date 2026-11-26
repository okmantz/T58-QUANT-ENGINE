"""Process lifecycle: the app must not outlive its window or its install folder, and must never recreate that folder.

Why this module exists (the "t58 folder keeps coming back" bug):
  * ``get_app_base_dir()`` used to ``mkdir(parents=True)`` the folder holding the executable on EVERY call. A server, a vault thread or a
    worker process still alive after the folder was deleted called it again and recreated the folder (and the vault restore then refilled it).
  * nothing stopped those processes: closing the browser tab left the server running; deleting the folder left it running too.

What it does now:
  * ``install_present()``    is the install folder (and, when packaged, the executable) still there?
  * ``start_watchdog()``     a tiny daemon thread: when the install folder disappears, or the app has had no browser heartbeat for
                             ``T58_IDLE_EXIT_MIN`` minutes (default 20) with no job running, run ``shutdown()``. Packaged builds only
                             (a developer's ``python -m app.web.server`` is never auto-killed unless T58_IDLE_EXIT_MIN is set).
  * ``shutdown()``           run the registered cleanup hooks (vault final backup, worker pools, memory watchdog), terminate child processes,
                             then exit. Idempotent.
  * ``heartbeat()``          called by the page every 30 s (``/api/heartbeat``) and by any API call; resets the idle clock.
Nothing here ever creates a folder.
"""
from __future__ import annotations

import atexit
import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable

_HOOKS: list[tuple[str, Callable[[], None]]] = []
_LOCK = threading.RLock()
_STOP = threading.Event()
_started = False
_down = False
_last_beat = time.time()
_busy_probe: Callable[[], bool] | None = None


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def install_present() -> bool:
    """False once the install folder (or the packaged executable) has been deleted or moved away. Never creates anything."""
    try:
        root = install_root()
        if not root.is_dir():
            return False
        if is_frozen() and not Path(sys.executable).exists():
            return False
        return True
    except OSError:
        return False


def register(name: str, fn: Callable[[], None]) -> None:
    """Add a cleanup hook for ``shutdown()``. Hooks must be quick and must not raise (exceptions are swallowed)."""
    with _LOCK:
        if all(n != name for n, _ in _HOOKS):
            _HOOKS.append((name, fn))


def heartbeat() -> None:
    global _last_beat
    _last_beat = time.time()


def set_busy_probe(fn: Callable[[], bool]) -> None:
    """``fn()`` returns True while a job the person started is running; the idle exit never fires during one."""
    global _busy_probe
    _busy_probe = fn


def idle_seconds() -> float:
    return max(0.0, time.time() - _last_beat)


def _idle_limit_s() -> float:
    raw = os.environ.get("T58_IDLE_EXIT_MIN")
    if raw is None:
        return 20 * 60.0 if is_frozen() else 0.0
    try:
        return max(0.0, float(raw)) * 60.0
    except ValueError:
        return 0.0


def _terminate_children() -> None:
    try:
        import psutil
        me = psutil.Process()
        kids = me.children(recursive=True)
        for k in kids:
            try:
                k.terminate()
            except psutil.Error:
                pass
        psutil.wait_procs(kids, timeout=2.0)
        for k in kids:
            try:
                if k.is_running():
                    k.kill()
            except psutil.Error:
                pass
        return
    except Exception:  # noqa: BLE001 -- psutil missing: fall back to multiprocessing's own list
        pass
    try:
        import multiprocessing
        for p in multiprocessing.active_children():
            p.terminate()
    except Exception:  # noqa: BLE001
        pass


def run_hooks() -> None:
    with _LOCK:
        hooks = list(_HOOKS)
    for _name, fn in reversed(hooks):
        try:
            fn()
        except Exception:  # noqa: BLE001
            pass


def shutdown(reason: str = "", *, exit_process: bool = True) -> None:
    """Stop everything this app started. Safe to call twice. ``exit_process=False`` is for tests."""
    global _down
    with _LOCK:
        if _down:
            return
        _down = True
    _STOP.set()
    if reason:
        try:
            print(f"T58 shutting down: {reason}", flush=True)
        except Exception:  # noqa: BLE001
            pass
    if install_present():
        run_hooks()                      # a final backup only makes sense while the install folder still exists
    else:
        _skip_hooks_that_write()
    _terminate_children()
    if exit_process:
        os._exit(0)


def _skip_hooks_that_write() -> None:
    """The install folder is gone: run only the hooks that release resources (pools, threads), never the ones that write."""
    with _LOCK:
        hooks = [(n, f) for n, f in _HOOKS if not n.startswith("write:")]
    for _n, fn in reversed(hooks):
        try:
            fn()
        except Exception:  # noqa: BLE001
            pass


def is_down() -> bool:
    return _down


def stop_event() -> threading.Event:
    """Background loops wait on this instead of ``time.sleep`` so they end the moment the app shuts down."""
    return _STOP


def _loop(poll_s: float) -> None:
    while not _STOP.wait(poll_s):
        if not install_present():
            shutdown("the install folder was removed")
            return
        limit = _idle_limit_s()
        if limit and idle_seconds() >= limit:
            busy = False
            try:
                busy = bool(_busy_probe()) if _busy_probe else False
            except Exception:  # noqa: BLE001
                busy = False
            if not busy:
                shutdown(f"no browser activity for {limit / 60:.0f} min and no job running")
                return


def start_watchdog(poll_s: float = 5.0) -> None:
    """Start once per process. Registers the standard resource hooks."""
    global _started
    with _LOCK:
        if _started:
            return
        _started = True
    _register_standard_hooks()
    atexit.register(lambda: shutdown("exit", exit_process=False))
    threading.Thread(target=_loop, args=(poll_s,), name="t58-lifecycle", daemon=True).start()


def _register_standard_hooks() -> None:
    def stage_pool():
        from app.orchestration.stage_pool import shutdown_stage_pool
        shutdown_stage_pool(wait=False)

    def mc_pool():
        from app.monte_carlo.shared_pool import shutdown_shared_mc_pool
        shutdown_shared_mc_pool(wait=False)

    def mem_watchdog():
        from app.orchestration.memory_hygiene import stop_idle_watchdog
        stop_idle_watchdog()

    def vault_final():
        from app.persistence import vault
        vault.stop_background()
        vault._safe_final_backup()

    register("stage_pool", stage_pool)
    register("mc_pool", mc_pool)
    register("memory_watchdog", mem_watchdog)
    register("write:vault_final_backup", vault_final)
