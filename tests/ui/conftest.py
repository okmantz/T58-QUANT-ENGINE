"""tests/ui: finalize leftover Tk objects on the main thread, never on whichever thread the garbage collector happens to run on.

Several desktop-UI tests build a Tk root. When the objects they leave behind (``tkinter.Image``/``PhotoImage``) are collected later by the
GC running on a *background* thread -- for instance the Full Pipeline job thread in ``test_v911_stop_hang_layout`` -- ``Image.__del__`` calls
into Tcl from a thread that does not own the interpreter. That raises ``RuntimeError: main thread is not in main loop`` at best and aborts the
whole interpreter (SIGABRT, exit 134, a pytest-xdist worker "node down: Not properly terminated") at worst, depending on when the GC fires.
Collecting after every test here pins the finalizers to the main thread, where Tcl allows them. A no-op when tkinter was never imported.
"""
from __future__ import annotations

import gc
import sys

import pytest


@pytest.fixture(autouse=True)
def _finalize_tk_objects_on_the_main_thread():
    yield
    if "tkinter" in sys.modules:
        gc.collect()
