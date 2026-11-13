"""
Regression tests for Desktop UI Dashboard and Layout.
Validates that Tkinter and ttk widgets, PanedWindows, Treeview,
and Dashboard controls construct without TclError.
"""

import tkinter as tk
from tkinter import ttk
import pytest

from src.ui.app import VoiceAssistantApp
from src.ui import theme


def test_ui_dashboard_initialization():
    """
    Regression test for:
    _tkinter.TclError: unknown option "-weight"
    Ensures VoiceAssistantApp initializes without TclError and renders widgets.
    """
    root = tk.Tk()
    root.withdraw()  # Do not display window on screen during automated test
    try:
        app = VoiceAssistantApp(root)
        root.update()

        # Check key components exist
        assert app.status_pill is not None
        assert app.txt_conversation is not None
        assert app.tree_plan is not None
        assert app.txt_history is not None
        assert app.txt_logs is not None
        assert app.txt_input is not None

        # Verify status updates work
        app._update_status_badge("PLANNING")
        assert app.status_var.get() == "PLANNING"

        app._update_status_badge("IDLE")
        assert app.status_var.get() == "IDLE"

    finally:
        root.destroy()


def test_ttk_panedwindow_weights():
    """Verifies ttk.PanedWindow accepts proportional pane weights."""
    root = tk.Tk()
    root.withdraw()
    try:
        paned = ttk.PanedWindow(root, orient=tk.VERTICAL)
        f1 = ttk.Frame(paned)
        f2 = ttk.Frame(paned)
        paned.add(f1, weight=3)
        paned.add(f2, weight=2)
        root.update()
        assert paned.pane(f1)["weight"] == 3
        assert paned.pane(f2)["weight"] == 2
    finally:
        root.destroy()
