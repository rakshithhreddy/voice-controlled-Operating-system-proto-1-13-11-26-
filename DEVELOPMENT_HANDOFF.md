# Development Handoff & Architecture Guide — CAOP Voice OS 2.0

## 1. Project Overview & Working Context
- **Project Root**: `F:\ENGINEERING PROJECTS\Voice Controled OS`
- **Remote Repository**: `https://github.com/rakshithhreddy/voice-controlled-Operating-system-proto-1-13-11-26-`
- **Base Commit**: `7f84680`
- **Python Runtime**: Python 3.12.2 in `venv\` (`.\venv\Scripts\python.exe`)
- **Workspace Sandbox**: All operations strictly confined within `workspace_data/`

---

## 2. Core Subsystem Architecture

### A. Voice Capture & Transcription (`src/voice/`)
- `hold_to_talk.py`: `HoldToTalkManager` handles physical push-to-talk microphone capture. Continuous PCM recording runs in a background thread while Enter is held; no auto-cutoff during thinking pauses. Outputs in-memory WAV bytes on release.
- `recognizer.py`: `SpeechRecognitionEngine` initializes local Vosk acoustic model (`vosk-model-small-en-us`). Uses `transcribe_wav_bytes()` to decode speech buffers offline. Falls back to SpeechRecognition API if model absent.
- `speaker.py`: `VoiceSpeaker` wraps pyttsx3 with multiline truncation and clean text normalization.

### B. Workspace Management, Trash & Undo (`src/workspace/`)
- `security.py`: `SecurityManager` validates every path against `workspace_data/` root using `Path.resolve()`. Blocks relative directory traversal (`..`), absolute external drive paths, and workspace root removal.
- `trash.py`: `TrashManager` provides safe deletions by moving files to `workspace_data/.trash/` with timestamped UUIDs and `metadata.json`. `UndoManager` records an action stack supporting rollback of deletes, renames, moves, and writes.
- `content_generator.py`: `ContentGenerator` generates educational notes (SNA, AI), JSON, CSV, READMEs, and working Python calculator code with self-tests (`run_tests()`).
- `manager.py`: `WorkspaceManager` is the unified facade for directory/file CRUD, copy/move, search, grep, duplicate identification, file organization (`organize_directory`, `organize_files`), and script execution.

### C. Natural Language Processing (`src/nlp/`)
- `intents.py`: `IntentClassifier` categorizes user utterances into 23 `IntentType` enums using prioritized regex patterns and keyword heuristics.
- `entities.py`: `EntityExtractor` extracts target names, destination folders, educational topic prompts, content strings, and rename pairs (`src`, `dst`) with clean punctuation stripping.
- `context.py`: `ContextManager` maintains dialogue turn history, active hierarchy stack, last mentioned folders/files/targets, and pronoun resolution (`it`, `there`, `the last one`, `that folder`).
- `parser.py`: `InstructionParser` splits compound instructions into discrete actionable clauses. Links dependencies and resolves implicit destinations for nested folder sequences.

### D. Planning & Execution (`src/planner/`)
- `planner.py`: `TaskPlanner` sequences `ParsedInstruction` items into an `ExecutionPlan`. Resolves relative destination hierarchies, maps task dependencies, and performs topological sorting.
- `executor.py`: `TaskExecutor` sequentially dispatches tasks to `WorkspaceManager`. Features `_find_item_in_workspace()` for fuzzy location of target items across nested directories. Independently verifies physical disk state after every action.

### E. Desktop User Interface (`src/ui/`)
- `app.py`: `VoiceAssistantApp` Tkinter GUI featuring dark slate theme (`theme.py`), proportional `ttk.PanedWindow`, live conversation log, execution plan tracker with verification badges, system log console, and a live Workspace Data Explorer treeview.
- Keyboard: Root binds `<KeyPress-Return>` and `<KeyRelease-Return>` for Hold-to-Talk while preserving normal Return submission in the text input box.

---

## 3. How to Run & Test

### Run All Automated Tests
```powershell
cd "F:\ENGINEERING PROJECTS\Voice Controled OS"
.\venv\Scripts\pytest tests/ -v
```

### Launch Assistant GUI
```bat
START.bat
```

### Run Automated Installer
```bat
INSTALL.bat
```
