# Changelog

All notable changes to the Voice-Controlled Operating System Assistant are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.1] - 2026-11-13

### Fixed
- **UI Dashboard Initialization**:
  - Resolved `_tkinter.TclError: unknown option "-weight"` during dashboard initialization by migrating `paned` and `top_paned` from `tk.PanedWindow` to `ttk.PanedWindow`.
  - Added `TPanedwindow` dark styling in `_setup_styles`.
  - Verified proportional pane weights (`weight=3`, `weight=4`, `weight=2`) for seamless responsive layout.
- **Python Environment Handling**:
  - Created isolated `venv` virtual environment populated with all project dependencies.
  - Enhanced `START.bat` to detect and activate `venv`, reporting `[OK] Running Python Environment: .../venv`.
  - Added clean label-based flow control in `START.bat` to eliminate Windows batch delayed-expansion parser errors.
  - Added `pytest.ini` with `pythonpath = .` to support direct `pytest` execution from terminal or IDEs.
- **Regression Testing**:
  - Added `tests/test_ui.py` covering dashboard widget initialization and `ttk.PanedWindow` weight configurations.
  - Verified 36/36 tests passing in virtual environment.

---

## [1.0.0] - 2026-11-13

### Added
- Local Speech Recognition Subsystem with continuous listening, push-to-talk, and noise calibration.
- Offline Text-to-Speech (TTS) via Windows SAPI5 (`pyttsx3`).
- Natural Language Understanding (NLP) intent classification, entity extraction, compound clause parsing, and conversational context memory.
- Multi-Step Task Planner & Execution Engine with topological dependency resolution and physical disk verification.
- Safe Workspace Security Sandboxing with traversal prevention and command filtering.
- Complete File/Folder CRUD, search, organize, duplicate detection, and Python script execution.
- Modern dark desktop interface and Windows batch launchers (`START.bat`, `INSTALL.bat`).
