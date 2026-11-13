"""
Unit tests for Security and Sandboxing Layer.
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path

from src.workspace.security import SecurityManager, SecurityException


@pytest.fixture
def temp_workspace():
    td = tempfile.mkdtemp()
    yield Path(td)
    shutil.rmtree(td, ignore_errors=True)


def test_valid_path_within_workspace(temp_workspace):
    sec = SecurityManager(temp_workspace)
    valid_subpath = sec.validate_path("subfolder/file.txt")
    assert valid_subpath.is_relative_to(temp_workspace)
    assert valid_subpath == (temp_workspace / "subfolder" / "file.txt").resolve()


def test_directory_traversal_blocked(temp_workspace):
    sec = SecurityManager(temp_workspace)
    with pytest.raises(SecurityException):
        sec.validate_path("../../outside.txt")

    with pytest.raises(SecurityException):
        sec.validate_path("folder/../../../secret.txt")


def test_absolute_path_outside_workspace_blocked(temp_workspace):
    sec = SecurityManager(temp_workspace)
    # Attempting to access Windows system directories
    with pytest.raises(SecurityException):
        sec.validate_path("C:\\Windows\\System32\\cmd.exe")

    with pytest.raises(SecurityException):
        sec.validate_path("C:\\Users")


def test_filename_sanitization(temp_workspace):
    sec = SecurityManager(temp_workspace)
    dirty = 'test<file>:name*?"|.txt'
    clean = sec.sanitize_filename(dirty)
    assert "<" not in clean
    assert ">" not in clean
    assert ":" not in clean
    assert "*" not in clean
    assert "?" not in clean
    assert "|" not in clean

    # DOS reserved device name protection
    reserved_clean = sec.sanitize_filename("CON.txt")
    assert reserved_clean.startswith("safe_")


def test_dangerous_command_filtering(temp_workspace):
    sec = SecurityManager(temp_workspace)
    # Safe command passes
    assert sec.validate_command_safety(["python", "script.py"]) is True

    # Dangerous commands get blocked
    with pytest.raises(SecurityException):
        sec.validate_command_safety(["cmd", "/c", "del /f /s /q c:\\"])

    with pytest.raises(SecurityException):
        sec.validate_command_safety(["rmdir /s /q", "test"])

    with pytest.raises(SecurityException):
        sec.validate_command_safety(["format", "D:"])
