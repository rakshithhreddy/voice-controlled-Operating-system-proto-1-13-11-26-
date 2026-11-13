"""
Security and Sandboxing Module.
Enforces workspace boundaries, validates paths against directory traversal,
and inspects commands to ensure safe local execution.
"""

import os
import re
import logging
from pathlib import Path
from typing import Union, Tuple, List
from src.config import WORKSPACE_DIR, LOG_FILE

# Set up dedicated logger for security events
logger = logging.getLogger("VoiceOS.Security")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [Security] %(message)s"))
    logger.addHandler(fh)


class SecurityException(Exception):
    """Raised when an operation violates workspace sandboxing or security policy."""
    pass


class SecurityManager:
    """
    Manages security boundaries, validates file paths,
    and prevents directory traversal or unauthorized external modifications.
    """

    def __init__(self, workspace_root: Union[str, Path] = None):
        if workspace_root is None:
            workspace_root = WORKSPACE_DIR
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized SecurityManager with workspace root: {self.workspace_root}")

    def get_workspace_root(self) -> Path:
        """Returns the canonical workspace root directory."""
        return self.workspace_root

    def validate_path(self, user_path: Union[str, Path]) -> Path:
        """
        Validates that a path is contained strictly within the workspace root.
        Resolves symlinks, relative traversal segments ('..'), and absolute paths.

        Returns:
            Path: Canonical, validated Path object inside workspace.

        Raises:
            SecurityException: If path attempts to escape the workspace boundary.
        """
        if not user_path:
            raise SecurityException("Path cannot be empty.")

        path_obj = Path(user_path)

        # If user provides a path with leading slash or drive letter outside workspace,
        # we check if it starts inside workspace_root.
        if path_obj.is_absolute():
            resolved = path_obj.resolve()
        else:
            # Relative to workspace root
            resolved = (self.workspace_root / path_obj).resolve()

        # Enforce boundary: resolved path must be relative to workspace_root
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError:
            logger.warning(f"BLOCKED: Directory traversal or out-of-boundary access attempt: '{user_path}' -> '{resolved}'")
            raise SecurityException(
                f"Access denied: '{user_path}' is outside the authorized workspace boundary '{self.workspace_root}'."
            )

        return resolved

    def sanitize_filename(self, name: str) -> str:
        """
        Sanitizes a file or folder name to prevent illegal Windows/OS characters.
        """
        name = name.strip()
        # Remove invalid Windows filename characters: < > : " / \ | ? *
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Avoid reserved DOS device names (CON, PRN, AUX, NUL, COM1, LPT1, etc.)
        reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                    "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
                    "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
        base = sanitized.split(".")[0].upper()
        if base in reserved:
            sanitized = f"safe_{sanitized}"
        return sanitized

    def validate_command_safety(self, cmd_args: List[str]) -> bool:
        """
        Validates that command line execution arguments do not contain forbidden,
        destructive, or dangerous system commands.
        """
        dangerous_tokens = [
            "rmdir /s", "del /f /s /q", "format", "shutdown",
            "net user", "reg delete", "powershell -enc",
            "takeown", "icacls", "mklink", "vssadmin"
        ]
        cmd_str = " ".join(cmd_args).lower()
        for token in dangerous_tokens:
            if token in cmd_str:
                logger.warning(f"BLOCKED dangerous command execution attempt: {cmd_str}")
                raise SecurityException(f"Execution of dangerous command token '{token}' is blocked by security policy.")
        return True
