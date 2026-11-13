"""
Configuration module for the Voice-Controlled OS Assistant.
Defines paths, logging, safety parameters, and engine settings.
"""

import os
from pathlib import Path

# Workspace Root - defaults to a dedicated 'workspace_root' directory inside the project
# or the project directory itself if specified.
# Keeping a dedicated workspace directory ensures complete sandboxing safety.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = PROJECT_ROOT / "workspace_data"

# Create workspace directory if it doesn't exist
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# Application Information
APP_NAME = "VoiceOS Assistant"
APP_VERSION = "1.0.0"

# Audio Settings
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHUNK_SIZE = 1024
ENERGY_THRESHOLD = 300
DYNAMIC_ENERGY_THRESHOLD = True
PAUSE_THRESHOLD = 0.8
PHRASE_TIME_LIMIT = 15

# TTS Settings
TTS_RATE = 185
TTS_VOLUME = 0.9

# Safety Settings
ALLOWED_EXTENSIONS = {
    ".txt", ".py", ".md", ".json", ".csv", ".log", ".html", ".css",
    ".js", ".bat", ".sh", ".yaml", ".yml", ".ini", ".cfg", ".sql"
}

FORBIDDEN_OPERATIONS = [
    "format", "rmdir /s", "del /f /s /q c:\\", "shutdown", "powershell -c rm"
]

MAX_FILE_SIZE_READ_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_SEARCH_DEPTH = 10

# Logging Config
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "assistant.log"
