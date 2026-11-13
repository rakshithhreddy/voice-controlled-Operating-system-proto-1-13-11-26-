# User Guide & Operations Manual

This guide covers how to launch, interact with, and operate the Voice-Controlled Operating System Assistant.

---

## 🚀 Launching the Assistant

### Desktop Dashboard Mode (Default)
To launch the graphical desktop interface, simply double-click:
```bat
START.bat
```
Or execute from terminal:
```powershell
python src\main.py
```

### Headless CLI Mode
For interactive terminal usage without a GUI:
```powershell
python src\main.py --cli
```

### Direct Command Execution
For single-shot automated operations or testing scripts:
```powershell
python src\main.py --command "Create a folder called Data, and create a file inside it called log.txt"
```

---

## 🎙 Voice Interaction Modes

The application supports two microphone modes accessible from the top control bar:

1. **Push-to-Talk (🎤 Speak Command)**:
   - Click the button once.
   - The status indicator switches to `LISTENING`.
   - Speak your instruction clearly in natural English.
   - When you finish speaking, the assistant automatically switches to `PROCESSING` -> `PLANNING` -> `EXECUTING` -> `VERIFYING` -> `COMPLETED`.

2. **Continuous Background Listening (Continuous Mic: ON/OFF)**:
   - Click to toggle background listening on or off.
   - When active, the assistant listens continuously in the background and processes instructions as soon as speech is detected.

3. **Manual Command Box (Or Type: ...)**:
   - Type commands directly into the input bar and press Enter or click `Send`.
   - Ideal for quiet environments or automated command testing.

---

## 📋 Supported Operations Reference

### 1. Folder Operations
- **Create Folder**:
  - *"Create a folder called Projects"*
  - *"Make a new directory named Downloads"*
  - *"Set up a folder titled Archive"*
- **Nested Folder Structures**:
  - *"Create a folder called Master, and create a folder inside it called Worker"*
- **Delete Folder**:
  - *"Delete the folder OldProjects"*
- **Rename Folder**:
  - *"Rename the folder Temp to Finished"*
- **List Contents**:
  - *"List all contents in this folder"*
  - *"Show me the files in the workspace"*

### 2. File Operations
- **Create File**:
  - *"Create a Python file called calculator.py"*
  - *"Make a file named notes.txt with content 'Meeting at 3 PM'"*
  - *"Create a README file inside the Projects folder"*
- **Read File**:
  - *"Read the contents of notes.txt"*
  - *"Show me calculator.py"*
- **Write / Append Content**:
  - *"Write content 'Updated details' to file notes.txt"*
  - *"Append 'New log entry' to log.txt"*
- **Delete File**:
  - *"Delete the file temp.txt"*
- **Rename File**:
  - *"Rename old.txt to new.txt"*
- **Copy & Move**:
  - *"Copy notes.txt to Archive"*
  - *"Move calculator.py to Scripts"*

### 3. Search & Discovery
- **Search by Name**:
  - *"Search for report"*
  - *"Find file named database.json"*
- **Find by Extension**:
  - *"Find all Python files"*
  - *"Show all files ending with .txt"*
- **Search Text in Files (Grep)**:
  - *"Search for text 'TODO' inside files"*
  - *"Which files contain 'API_KEY'"*
- **Identify Duplicates**:
  - *"Find duplicate files"*

### 4. Workspace Organization & Development
- **Organize Workspace**:
  - *"Organize the files in my workspace"*
  - (Automatically sorts files into `Python_Scripts`, `Text_Documents`, `Markdown_Docs`, etc.)
- **Summarize Documents**:
  - *"Summarize the file report.txt"*
- **Execute Python Scripts**:
  - *"Run the Python script calculator.py"*
- **Open Item**:
  - *"Open the folder Projects"*
  - *"Open notes.txt with default application"*

---

## 💬 Conversational Context Examples

The assistant remembers recent entities for natural dialogue turns:

**Example Turn 1:**
> User: *"Create a folder called College Projects."*  
> Assistant: *"Folder 'College Projects' created successfully."*

**Example Turn 2:**
> User: *"Inside it, create a folder called Python."*  
> Assistant: *"Folder 'College Projects/Python' created successfully."*

**Example Turn 3:**
> User: *"Create a file inside it called run.py."*  
> Assistant: *"File 'run.py' created inside 'College Projects/Python'."*
