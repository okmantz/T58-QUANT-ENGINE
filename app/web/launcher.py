"""
T58 Quant Engine — phone-friendly launcher.

This is the entry point behind the "T58-Web-App.exe" build. It exists so
Owen (or anyone else) can:

    1. Download a zip from GitHub Releases.
    2. Extract it.
    3. Double-click T58-Web-App.exe.
    4. Get a QR code on screen -- scan it with a phone camera on the same
       Wi-Fi -- and the full backtester opens in the phone's browser,
       installable as a home-screen app (PWA) via "Add to Home Screen".

No hosting account, no app store, no Termux/third-party runtime on the
phone. The only requirement is that the PC running this .exe stays on
and both devices share the same Wi-Fi network while the phone is used.

This module does NOT duplicate the Flask app in app.web.server -- it
only adds the "find my LAN IP / show a QR code / open a browser" glue
around the exact same server, via app.web.network_info (shared with
app.web.server itself -- see that module's docstring for why running
`python -m app.web.server` used to show none of this).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from app.web.network_info import (
    PORT, ensure_utf8_console, find_free_port, get_lan_ip, is_running_under_wine, print_startup_banner, qr_code_file,
    set_active_port,
)


# ---- single launch, single tab -------------------------------------------------------------------------------------
# 2026-11-14 audit: double-clicking the app opened TWO browser tabs. Root cause: in a packaged .exe ``sys.executable`` IS the app,
# so any background job that re-launches ``sys.executable -m something`` (the surrogate study did) started a second copy of this
# launcher, and the second copy opened its own tab. Three guards, any one of which is enough on its own:
#   1. child processes are marked (T58_CHILD_PROCESS=1) and the launcher refuses to run in them;
#   2. if a T58 server already answers on the preferred port, a second launch just focuses it (one tab) instead of starting another;
#   3. the browser is opened at most once per ``_BROWSER_STAMP_SECONDS`` (a stamp file), whatever starts it.
CHILD_ENV = "T58_CHILD_PROCESS"
NO_BROWSER_ENV = "T58_NO_BROWSER"
_BROWSER_STAMP_SECONDS = 45.0


def is_child_process() -> bool:
    """True inside a worker or helper process that must never start a server or open a tab."""
    return os.environ.get(CHILD_ENV, "") == "1"


def child_env(base: dict | None = None) -> dict:
    """Environment for any subprocess this app spawns: marks it as a child so a re-launched frozen exe exits at once."""
    env = dict(os.environ if base is None else base)
    env[CHILD_ENV] = "1"
    env[NO_BROWSER_ENV] = "1"
    return env


def _stamp_path() -> Path:
    return Path(tempfile.gettempdir()) / "t58_browser_opened.json"


def browser_recently_opened(now: float | None = None, path: Path | None = None) -> bool:
    now = time.time() if now is None else now
    try:
        data = json.loads((path or _stamp_path()).read_text(encoding="utf-8"))
        return (now - float(data.get("t", 0.0))) < _BROWSER_STAMP_SECONDS
    except Exception:  # noqa: BLE001
        return False


def open_browser_once(url: str, *, opener=None, now: float | None = None, path: Path | None = None) -> bool:
    """Open ``url`` in the default browser unless one was opened in the last few seconds or this is a child / headless run.
    Returns True when it actually opened a tab."""
    if is_child_process() or os.environ.get(NO_BROWSER_ENV, "") == "1":
        return False
    now = time.time() if now is None else now
    stamp = path or _stamp_path()
    if browser_recently_opened(now, stamp):
        return False
    try:
        stamp.write_text(json.dumps({"t": now, "url": url}), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    (opener or webbrowser.open)(url)
    return True


def t58_server_running(port: int, timeout: float = 1.5) -> bool:
    """True when a T58 web server already answers on 127.0.0.1:port (identified by the /health payload, not just an open port)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/health", timeout=timeout) as r:  # noqa: S310 -- loopback only
            return json.loads(r.read().decode("utf-8", "replace")).get("app") == "t58"
    except Exception:  # noqa: BLE001
        return False


def _qr_image_path(url: str) -> Path | None:
    """Generate a QR code image for the given URL and save it to the home directory.
    
    Returns the path to the generated PNG file, or None if generation fails.
    This is a best-effort function -- any failure degrades gracefully to None
    so the launcher can still start the server even if qrcode/Pillow is missing
    or broken.
    """
    try:
        import qrcode
        
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image()
        
        out_path = Path.home() / "qr_code.png"
        img.save(out_path)
        return out_path
    except Exception:
        # Best-effort: any failure in optional qrcode/Pillow install
        # degrades to None, never raises
        return None


def _open_qr_image(path) -> None:
    """Open the QR code image with whatever the OS uses for PNGs.

    Best-effort only -- the real, reliable way to see the QR code is the
    /mobile-access page opened by _open_things_once_server_is_up below
    (rendered inline in a browser tab that's already known to work, no
    OS file-association guesswork involved). This is kept only as an
    extra convenience for people who'd rather have a standalone image
    window; if it fails or opens something broken (e.g. Wine falling
    back to a stub IE with no real PNG support), the browser tab still
    shows the same code, so nothing is actually lost.
    """
    try:
        if is_running_under_wine():
            # Wine has no real image viewer configured on a bare prefix
            # -- os.startfile() here reliably produces the blank/garbled
            # window this bug was reported as. Skip it; the banner
            # already explains why and points at running natively.
            return
        if sys.platform.startswith("win"):
            import os

            os.startfile(path)  # noqa: S606 -- intentional, user-facing helper
        elif sys.platform == "darwin":
            import subprocess

            subprocess.run(["open", str(path)], check=False)
        else:
            import subprocess

            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        # Non-fatal -- the /mobile-access browser tab is enough.
        pass


def main() -> None:
    # Printed and flushed immediately, before importing the (much heavier)
    # Flask app or generating a QR code -- on a slow machine, antivirus-
    # scanned first run, or a large PyInstaller onefile .exe that has to
    # self-extract before Python even starts running user code, several
    # seconds can pass with the console window sitting there before this
    # point is reached. Without an immediate flushed print, that gap looks
    # indistinguishable from "nothing is happening" (the exact complaint
    # this fixes) -- a person has no way to tell "it's loading" apart from
    # "it silently died."
    if is_child_process():
        # A re-launched copy of the frozen exe (a worker / helper job): never start a server or open a tab.
        return
    ensure_utf8_console()
    if t58_server_running(PORT):
        print(f"T58 is already running on port {PORT} -- opening it (no second copy started).", flush=True)
        open_browser_once(f"http://127.0.0.1:{PORT}/dashboard")
        return
    print("Starting T58 Quant Engine (web/phone edition)...", flush=True)
    print("(First launch can take a little while to unpack -- please wait.)", flush=True)

    # Import here (not at module top) so this launcher's own startup
    # banner logic has zero dependency on the heavier app import graph
    # succeeding before we've at least tried to explain what's happening.
    from app.web.server import app  # noqa: WPS433

    # Startup market-data self-check (Oct 2026): importing app.web.server
    # above already INFO-logged the resolved data dir + file count; echo the
    # one-liner to the console too so a double-clicked .exe user sees it
    # right in the window. data_dir_status() never raises (it returns a
    # "check failed" string on error), so this can't break startup.
    from app.data.storage import data_dir_status  # noqa: WPS433

    print(data_dir_status(), flush=True)

    # 2026-11-05 audit: keep the surrogate-study report fresh in the background (low priority, one at a time, at most weekly) so the
    # new discovery families are not left locked just because nobody remembered to run the study. Never raises; never opens the gate.
    try:
        from app.discovery_engine.surrogate_schedule import maybe_start_background_study  # noqa: WPS433
        _sg = maybe_start_background_study()
        if _sg.get("started"):
            print("Surrogate study started in the background (low priority): " + _sg.get("why", ""), flush=True)
    except Exception:  # noqa: BLE001
        pass

    # Port 5000 may be taken (macOS 12+ runs AirPlay Receiver on it by default, or a
    # previous copy is still running) -- use the next free port instead of failing.
    port = find_free_port(PORT)
    set_active_port(port)
    if port != PORT:
        print(f"Port {PORT} is already in use (on macOS this is usually AirPlay Receiver) -- using {port} instead.", flush=True)

    ip = get_lan_ip()
    url = f"http://{ip}:{port}"
    qr_path = qr_code_file(url)

    def _open_things_once_server_is_up() -> None:
        time.sleep(1.0)
        # Open ONLY the app itself, straight at the Dashboard. A first
        # launch is redirected through the license page (/activate) and
        # lands back on the Dashboard, where the first-run tour starts.
        # The phone QR code lives inside the web app (the /mobile-access
        # page, linked from the sidebar), so we don't pop it open as its
        # own browser tab or picture-viewer window on startup.
        open_browser_once(f"http://127.0.0.1:{port}/dashboard")

    threading.Thread(target=_open_things_once_server_is_up, daemon=True).start()

    # Saved-runs vault: restore anything a reinstall removed, then keep a copy outside the install folder.
    try:
        from app.persistence import vault  # noqa: WPS433
        vault.start_background()
    except Exception:  # noqa: BLE001
        pass

    print_startup_banner(url, qr_path)
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except OSError as exc:
        # Most common real-world case: port 5000 already in use, either by
        # a previous copy of this same app still running in the
        # background, or (on macOS) the AirPlay Receiver service. Flask/
        # Werkzeug's own message for this is a plain OSError with an errno,
        # not obviously about a port conflict at a glance -- spell it out.
        print(flush=True)
        print("=" * 64, flush=True)
        print(f"  Could not start the server: {exc}", flush=True)
        print(f"  This almost always means port {port} is already in use --", flush=True)
        print("  either another copy of this app is already running (check", flush=True)
        print("  for another console window with this same banner already", flush=True)
        print("  open), or something else on this PC is using that port.", flush=True)
        print("=" * 64, flush=True)
        raise


def run() -> None:
    """Entry point used by both `python launchers/run_web.py` and this module's own
    `if __name__ == "__main__"` guard -- wraps main() so an abnormal exit
    is printed AND the console waits for a keypress before closing.

    Why this exists: Windows closes a console window the instant the
    process that opened it exits. If main() failed here with nothing
    catching it, the very message that would explain what went wrong
    flashes past in a fraction of a second and the window vanishes --
    which is exactly what "the terminal appeared, but nothing was
    printed" looks like from the outside: the failure happened too fast
    to read, not that nothing happened at all. This catches BOTH an
    uncaught exception AND Werkzeug's own habit of calling sys.exit()
    directly on a startup failure (e.g. "port 5000 already in use") --
    the latter raises SystemExit, which a plain `except Exception` does
    NOT catch, so it would otherwise still slip through and close the
    window instantly even with error handling in main() itself. A clean
    Ctrl+C (KeyboardInterrupt) or an explicit sys.exit(0) are left alone
    since those are the normal, intentional ways to stop the server --
    pausing on those would just be annoying.
    """
    try:
        main()
    except KeyboardInterrupt:
        pass
    except SystemExit as exc:
        if exc.code in (0, None):
            raise
        _pause_on_abnormal_exit(f"exited with an error (code {exc.code}) -- see the message above, if any.")
    except Exception:
        import traceback

        print(flush=True)
        traceback.print_exc()
        _pause_on_abnormal_exit("crashed on startup -- see the traceback above.")


def _pause_on_abnormal_exit(reason: str) -> None:
    print(flush=True)
    print("=" * 64, flush=True)
    print(f"  T58 Quant Engine {reason}", flush=True)
    print("=" * 64, flush=True)
    try:
        input("Press Enter to close this window...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    run()
