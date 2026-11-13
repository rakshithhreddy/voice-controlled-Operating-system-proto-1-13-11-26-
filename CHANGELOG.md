# Changelog

All notable changes to the Voice-Controlled Operating System Assistant are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-11-13

### Added
- **Local Speech Recognition Subsystem**:
  - Implemented `SpeechRecognitionEngine` supporting continuous background listening and push-to-talk single phrase capture.
  - Added microphone enumeration and dynamic ambient noise calibration.
  - Added audio file transcription for offline integration testing.
- **Offline Text-to-Speech (TTS)**:
  - Implemented `VoiceSpeaker` using Windows SAPI5 (`pyttsx3`) with dedicated worker thread and queue.
- **Natural Language Understanding (NLP)**:
  - Added `IntentClassifier` supporting synonym variations (`CREATE_FOLDER`, `CREATE_FILE`, `DELETE_FOLDER`, `READ_FILE`, `WRITE_FILE`, `APPEND_FILE`, `LIST_FOLDER`, `ORGANIZE_FILES`, `FIND_DUPLICATES`, `EXECUTE_SCRIPT`, `SUMMARIZE_FILE`).
  - Added `EntityExtractor` capable of parsing filenames, folder lists, extensions, destinations, and quoted contents.
  - Added `InstructionParser` for decomposing compound spoken instructions.
  - Added `ContextManager` maintaining dialogue state and resolving pronouns (*"it"*, *"inside it"*, *"in that folder"*).
- **Task Planning & Verification Engine**:
  - Added `TaskPlanner` with hierarchical relative path resolution and topological dependency ordering.
  - Added `TaskExecutor` with step-by-step progress notifications and physical filesystem verification.
  - Added partial failure reporting and automated skipping of dependent tasks.
- **Workspace Operations & Security Sandboxing**:
  - Added `SecurityManager` enforcing strict boundary confinement in `workspace_data/` and blocking directory traversal attacks (`../../`) and dangerous commands.
  - Added `WorkspaceManager` supporting full file/folder CRUD, search, grep, duplicate identification, auto-organization, extractive summarization, and safe script execution.
- **Desktop Graphical User Interface**:
  - Added Tkinter/ttk desktop dashboard with modern dark palette (`#181825`).
  - Visual status indicator clearly transitioning: `IDLE`, `LISTENING`, `PROCESSING`, `PLANNING`, `EXECUTING`, `VERIFYING`, `COMPLETED`, `FAILED`.
  - Added live speech transcription stream, task execution treeview, execution history, and system activity logs.
- **Windows Startup Scripts**:
  - Added `START.bat` for one-click environment detection, dependency verification, and dashboard launch.
  - Added `INSTALL.bat` for automated virtual environment creation and package installation.
- **Automated QA Test Suite**:
  - Added 34 unit and integration tests across 7 categories with 100% pass rate.
