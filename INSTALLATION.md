# Installation Guide

This document describes hardware requirements, software prerequisites, and installation instructions for the Voice-Controlled Operating System Assistant.

---

## 💻 System Requirements

### Minimum Requirements
- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Processor**: Intel Core i3 / AMD Ryzen 3 or equivalent
- **Memory**: 4 GB RAM
- **Disk Space**: 500 MB free disk space
- **Audio**: Working audio input (microphone) and output (speakers/headphones)
- **Python**: Version 3.10, 3.11, or 3.12 (64-bit)

### Recommended Requirements
- **Processor**: Intel Core i5 / AMD Ryzen 5 or higher
- **Memory**: 8 GB RAM
- **Audio**: Dedicated USB or noise-canceling headset microphone

---

## 📦 Automated Installation (Recommended)

1. Open File Explorer and navigate to the project directory:
   ```
   F:\ENGINEERING PROJECTS\Voice Controled OS
   ```
2. Double-click `INSTALL.bat`.
3. The script will:
   - Check for Python on your system PATH.
   - Create an isolated virtual environment (`venv`).
   - Upgrade `pip`.
   - Install all required libraries (`SpeechRecognition`, `pyttsx3`, `PyAudio`, `pytest`).
4. Once completed, press any key to close the installer.

---

## 🛠 Manual Installation

If you prefer installing dependencies manually via terminal:

### 1. Verify Python
Ensure Python is installed and added to your PATH:
```powershell
python --version
```
Expected output: `Python 3.10.x`, `3.11.x`, or `3.12.x`.

### 2. Create and Activate Virtual Environment
```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Install Requirements
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Verify Audio Libraries
Test that PyAudio and the Windows TTS engine initialize correctly:
```powershell
python -c "import speech_recognition, pyttsx3, pyaudio; print('Dependencies OK')"
```

---

## ❓ Troubleshooting Installation

### Issue 1: `PyAudio` installation fails
- **Cause**: Missing C++ Build Tools when compiling PyAudio on some Windows systems.
- **Solution**: Pre-built wheels are installed automatically on Python 3.10 - 3.12 via pip. If pip cannot find a wheel, install `pipwin` or install the pre-compiled wheel directly:
  ```powershell
  pip install pipwin
  pipwin install pyaudio
  ```

### Issue 2: `pyttsx3` Voice engine error
- **Cause**: Missing Windows SAPI5 drivers or COM registration.
- **Solution**: Re-register `pypiwin32` and `comtypes`:
  ```powershell
  pip install --upgrade comtypes pypiwin32 pywin32
  ```

### Issue 3: Microphone not detected
- **Cause**: Windows Privacy settings blocking microphone access.
- **Solution**: Open Windows **Settings** > **Privacy & Security** > **Microphone**, and ensure:
  - *Microphone access* is **On**.
  - *Let desktop apps access your microphone* is **On**.
