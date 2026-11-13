# Technical Architecture Document

This document provides a detailed technical overview of the Voice-Controlled Operating System Assistant, including design patterns, component interactions, safety models, and data flows.

---

## 🏛 High-Level Architecture Overview

The system is designed with a strict separation of concerns across 6 decoupled subsystems:

```
[ Microphone Input ]  ──>  [ SpeechRecognizer ]
                                    │ (Transcribed Text)
                                    ▼
[ User Input Box ]   ──>  [ InstructionParser (NLP) ]
                                    │ (Parsed Clauses & Entities)
                                    ▼
                          [ TaskPlanner ] ◄── [ ContextManager ]
                                    │ (Topological Execution Plan)
                                    ▼
                          [ TaskExecutor ]
                                    │ (Sandboxed Operations)
                                    ▼
                          [ WorkspaceManager ]
                                    │ (Physical Execution)
                                    ▼
                          [ Independent Verifier ]
                                    │ (Disk Verification)
                                    ▼
                          [ Desktop UI & VoiceSpeaker ]
```

---

## 🧩 Subsystem Breakdown

### 1. Voice Recognition Subsystem (`src/voice/`)
- **`SpeechRecognitionEngine`**:
  - Handles PyAudio audio stream capture.
  - Dynamically adjusts energy thresholds for ambient noise.
  - Uses `recognizer.listen_in_background` for non-blocking continuous speech recognition.
  - Supports audio file transcription for offline/simulated CI test pipelines.
- **`VoiceSpeaker`**:
  - Utilizes Windows SAPI5 (`pyttsx3`) for local, offline speech synthesis.
  - Offloads speech requests to an asynchronous worker queue (`queue.Queue`) so the GUI event loop never freezes.

### 2. Natural Language Understanding (NLP) (`src/nlp/`)
- **`IntentClassifier`**:
  - Categorizes user intentions into standardized `IntentType` enums.
  - Evaluates patterns hierarchically, supporting syntactic variations (e.g., *"Make a new folder called Games"*, *"Create a Games directory"*, *"mkdir Games"*).
- **`EntityExtractor`**:
  - Extracts parameters including targets, multiple item lists, parent destinations, extensions, and content.
  - Excludes quoted content when searching for file/folder names to avoid misidentifying content strings as filenames.
- **`InstructionParser`**:
  - Decomposes compound spoken sentences (split by commas, *"then"*, *"and then"*, conjunctions) into atomic parsed instructions.
  - Recombines prepositional prefixes (*"Inside it, create..."*) to prevent orphaned fragments.
- **`ContextManager`**:
  - Maintains dialogue history and active entities.
  - Resolves pronouns (*"it"*, *"that folder"*, *"inside it"*) to the last active folder/file.

### 3. Task Planning Subsystem (`src/planner/`)
- **`TaskPlanner`**:
  - Converts parsed instructions into a sequence of `TaskItem` objects.
  - Performs dynamic relative path resolution across hierarchically nested tasks.
  - Maps dependencies (e.g. child folder creation depends on parent folder creation task).
  - Performs topological sort to ensure prerequisite tasks execute first.

### 4. Task Execution & Verification Subsystem (`src/planner/executor.py`)
- **`TaskExecutor`**:
  - Dispatches tasks to `WorkspaceManager`.
  - Checks prerequisite dependencies; if any parent task fails, dependent tasks are marked `SKIPPED` and not executed.
  - **Independent Verification**: Checks real filesystem state on physical disk (`exists()`, `is_file()`, `is_dir()`, `read_text()`) before certifying success.
  - Generates comprehensive natural English summaries describing successes, failures, and skips.

### 5. Workspace Sandboxing & Security (`src/workspace/`)
- **`SecurityManager`**:
  - Enforces canonical containment within `workspace_data/`.
  - Blocks directory traversal attacks (`../../`, `.\..\..`).
  - Blocks absolute paths outside workspace (`C:\Windows`, `C:\Users`).
  - Sanitizes invalid Windows characters (`< > : " / \ | ? *`) and reserved DOS device names (`CON`, `PRN`, `AUX`, `NUL`).
  - Detects and rejects dangerous destructive commands (`format`, `del /f /s /q`, `rmdir /s`).
- **`WorkspaceManager`**:
  - Full implementation of folder/file operations, search, duplicate detection (MD5 hash table), file organization, document summarization, and safe script execution.

### 6. Desktop Dashboard (`src/ui/`)
- **`VoiceAssistantApp`**:
  - Built with Tkinter and ttk styled with modern dark palette (`#181825`, `#1e1e2e`).
  - Utilizes a thread-safe message queue polled via `root.after(100)` to update the GUI without cross-thread race conditions.
  - Visual status pill clearly transitions: `LISTENING`, `PROCESSING`, `PLANNING`, `EXECUTING`, `VERIFYING`, `COMPLETED`, `FAILED`.

---

## 🔒 Security Policy & Sandboxing Boundaries

| Threat Vector | Mitigation Strategy | Implementation |
|---|---|---|
| Directory Traversal (`../../`) | Path canonicalization via `Path.resolve()` and checking `is_relative_to(workspace_root)` | `SecurityManager.validate_path` |
| System Directory Escape | Absolute path validation against authorized root | `SecurityManager.validate_path` |
| Shell Command Injection | Command argument inspection and blacklisting of dangerous system utilities | `SecurityManager.validate_command_safety` |
| Resource Exhaustion | File read limit (5 MB) and Python execution timeout (15 seconds) | `WorkspaceManager` configuration |
| Unsanitized Filenames | Regex character replacement and DOS reserved name prefixing (`safe_CON.txt`) | `SecurityManager.sanitize_filename` |
