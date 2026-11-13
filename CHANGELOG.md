# Changelog

All notable changes to the Voice-Controlled Operating System Assistant are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-11-13

### Added
- **Hold-to-Talk (Push-to-Talk) Key Engine (`src/voice/hold_to_talk.py`)**:
  - Hold Enter to capture microphone audio with debounced key press/release and continuous PCM streaming.
  - In-memory WAV container generation upon release with live duration ticker in UI.
- **Offline Vosk Speech Recognition (`src/voice/recognizer.py`)**:
  - Offline Vosk acoustic engine (`vosk-model-small-en-us`) integrated and verified.
  - In-memory WAV buffer transcription via `transcribe_wav_bytes()`.
- **Trash & Undo Rollback Subsystem (`src/workspace/trash.py`)**:
  - Safe deletion moves files/directories to `workspace_data/.trash/` with JSON recovery metadata.
  - Reversible action stack supporting rollback of deletes, renames, moves, and writes via `ws.undo()`.
- **Intelligent Content Generator (`src/workspace/content_generator.py`)**:
  - Rich educational notes (Social Network Analysis, Artificial Intelligence), CSV, JSON, READMEs.
  - Generates syntactically validated Python calculator programs with built-in self-tests (`run_tests()`).
- **Live Workspace Explorer Tab (`src/ui/app.py`)**:
  - Integrated `ttk.Treeview` explorer displaying real-time directory and file hierarchy within `workspace_data/`.
- **12-Turn Acceptance Scenario Test (`tests/test_integration.py`)**:
  - Full end-to-end multi-turn acceptance scenario passing 100% on disk.

### Fixed
- **Rename Extraction Bug (`src/nlp/entities.py`)**:
  - Stripped trailing descriptor words (`folder`, `directory`, `file`) and leading articles (`the`, `a`, `an`).
- **Context Pronoun Resolution (`src/nlp/context.py`)**:
  - Added backward-compatible `resolve_pronoun()` alias for `resolve_reference()`.
- **Workspace Manager Compatibility (`src/workspace/manager.py`)**:
  - Added backward-compatible `organize_files()` alias for `organize_directory()`.
- **Compound Instruction Context Tracking (`src/nlp/parser.py`)**:
  - Contextual destination inheritance for coordinated child-folder creation sequences.
- **Subprocess Execution Hanging (`src/workspace/manager.py`)**:
  - Safe piped script execution with `sys.executable`, closed stdin (`input=""`), and non-interactive `--test` flags.

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
