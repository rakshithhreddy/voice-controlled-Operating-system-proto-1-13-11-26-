"""
Unit tests for Application Startup, Configuration, and CLI Dispatch.
"""

import sys
import subprocess
from pathlib import Path
import pytest

from src.config import PROJECT_ROOT, WORKSPACE_DIR, APP_NAME, APP_VERSION
from src.main import main, run_cli_session


def test_configuration_loading():
    assert PROJECT_ROOT.exists()
    assert WORKSPACE_DIR.exists()
    assert APP_NAME == "VoiceOS Assistant"
    assert APP_VERSION == "1.0.0"


def test_batch_launchers_exist():
    start_bat = PROJECT_ROOT / "START.bat"
    install_bat = PROJECT_ROOT / "INSTALL.bat"
    assert start_bat.exists()
    assert install_bat.exists()

    content_start = start_bat.read_text(encoding="utf-8")
    assert "main.py" in content_start
    assert "requirements.txt" in content_start

    content_install = install_bat.read_text(encoding="utf-8")
    assert "venv" in content_install
    assert "pip install" in content_install


def test_cli_execution_session():
    # Test executing a non-destructive command via run_cli_session
    success = run_cli_session("list contents")
    assert success is True
