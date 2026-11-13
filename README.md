# Voice-Controlled Operating System Assistant

A modern, offline-capable desktop assistant that translates natural English spoken instructions into verified local filesystem and developmental operations on Windows.

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-34%20passed-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

---

## 🌟 Key Features

- **🎙 Local Voice & Speech Processing**: Continuous microphone listening or push-to-talk speech recognition with ambient noise calibration and Windows SAPI5 offline Text-to-Speech feedback.
- **🧠 Natural Language Understanding (NLP)**: Modular intent classification and entity slot extraction capable of understanding varied phrasing (e.g., *"Make a new folder called Games"*, *"Create a Games directory"*, *"I need a folder named Games"*).
- **🔗 Compound Multi-Step Execution**: Understands multiple operations within a single spoken instruction (e.g., *"Create a folder called College Projects, create another folder inside it called Python, and create a Python file called calculator.py"*).
- **💬 Conversational Context & Memory**: Preserves context across follow-up queries, resolving anaphoric pronouns such as *"it"*, *"that folder"*, and *"inside it"*.
- **🛡 Workspace Sandboxing & Security**: Strict boundary confinement preventing directory traversal (`../../`) and blocking dangerous system shell commands.
- **🔍 Independent Filesystem Verification**: Operations are checked on physical storage before reporting success to ensure complete reliability.
- **🖥 Modern Desktop Dashboard**: Dark slate Tkinter/ttk interface with visual status indicators: `LISTENING`, `PROCESSING`, `PLANNING`, `EXECUTING`, `VERIFYING`, `COMPLETED`, and `FAILED`.
- **🚀 One-Click Windows Launchers**: Double-click `START.bat` to verify dependencies and launch the dashboard; `INSTALL.bat` for one-click setup.

---

## 🏗 System Architecture

The assistant is built on a modular, decoupled architecture:

```
Voice Controled OS/
├── START.bat                 # One-click Windows application launcher
├── INSTALL.bat               # Automated environment & dependency setup
├── requirements.txt          # Python dependency manifest
├── src/
│   ├── main.py               # Application entry point (GUI & CLI)
│   ├── config.py             # Global constants, paths, and limits
│   ├── workspace/
│   │   ├── security.py       # Sandboxing, path normalization, safety checks
│   │   └── manager.py        # File, folder, search, organize, script execution
│   ├── nlp/
│   │   ├── intents.py        # Semantic intent classification rules
│   │   ├── entities.py       # Filename, path, content, and parameter extractor
│   │   ├── context.py        # Dialogue memory and pronoun resolution
│   │   └── parser.py         # Compound clause splitting and task planning specs
│   ├── planner/
│   │   ├── task.py           # Atomic task models and status tracking
│   │   ├── planner.py        # Dependency graph and topological ordering
│   │   └── executor.py       # Execution dispatcher and independent verification
│   ├── voice/
│   │   ├── recognizer.py     # Speech capture, noise adjustment, offline fallback
│   │   └── speaker.py        # Asynchronous TTS worker using pyttsx3
│   └── ui/
│       ├── theme.py          # Professional dark palette and typography
│       └── app.py            # Desktop UI dashboard (Tkinter/ttk)
├── tests/                    # Comprehensive unit and integration test suite
│   ├── test_startup.py
│   ├── test_security.py
│   ├── test_workspace.py
│   ├── test_nlp.py
│   ├── test_planner.py
│   ├── test_voice.py
│   └── test_integration.py
└── docs/                     # Detailed technical documentation
```

---

## ⚡ Quick Start

### 1. Installation
Clone the repository and run the automated installer:
```bat
INSTALL.bat
```
Or install dependencies manually using Python 3.10+:
```bash
python -m pip install -r requirements.txt
```

### 2. Launching the Assistant
Double-click `START.bat` or run:
```bash
python src/main.py
```

For headless terminal CLI mode:
```bash
python src/main.py --cli
```

To run a single automated command:
```bash
python src/main.py --command "Create a folder called Projects, and create a file inside it called notes.txt"
```

---

## 🗣 Example Voice Instructions

| Spoken Utterance | Resulting Action |
|---|---|
| *"Create a folder called College Projects, create another folder inside it called Python, and create a Python file called calculator.py."* | Creates nested folder tree `College Projects/Python/calculator.py` and independently verifies disk state. |
| *"Create a folder named Semester 7, create three folders inside it called SNA, AI, and Projects, then create a README file inside the Projects folder."* | Creates `Semester 7`, subdirectories `SNA`, `AI`, `Projects`, and `Semester 7/Projects/README.md`. |
| Turn 1: *"Create a folder called Projects."*<br>Turn 2: *"Inside it, create a folder called College."* | Turn 2 identifies *"it"* refers to `Projects/`, creating `Projects/College/`. |
| *"Organize all files in my workspace."* | Automatically sorts files into structured folders (`Python_Scripts`, `Text_Documents`, `Markdown_Docs`, etc.). |
| *"Find duplicate files."* | Scans workspace with MD5 checksums and identifies identical duplicate files. |
| *"Run the Python script calculator.py."* | Safely executes Python script with timeout enforcement and reports stdout/stderr. |

---

## 🛡 Security & Safety Boundaries

The assistant enforces a strict sandboxing boundary:
1. **Workspace Boundary**: All file and directory modifications are restricted to `workspace_data/`. Any attempt to escape via directory traversal (`../../`) or absolute system paths (`C:\Windows`) raises `SecurityException` and fails immediately.
2. **Command Validation**: Destructive shell injection commands (such as `format`, `del /f /s /q`, `rmdir /s`) are detected and blocked.
3. **Execution Limits**: Script executions have a 15-second timeout and file reads are capped at 5 MB to prevent resource exhaustion.

---

## 🧪 Testing & Verification

The project includes an automated test suite covering all functional and security layers:
```bash
python -m pytest tests/ -v
```
**Results**: `34 passed, 0 failed, 100% pass rate`.

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
