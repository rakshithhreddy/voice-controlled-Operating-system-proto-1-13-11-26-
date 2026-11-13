@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo   Voice-Controlled Operating System Assistant - Launcher
echo =====================================================================
echo.

:: 1. Detect project directory
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
echo [*] Project Directory: %PROJECT_DIR%

:: 2. Check for base Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not found on PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    echo Ensure "Add Python to PATH" is checked during setup.
    goto :ERROR_EXIT
)

:: 3. Manage Virtual Environment
if exist "venv\Scripts\activate.bat" goto :ACTIVATE_VENV

echo [*] Virtual environment (venv) not found. Setting up environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [!] Warning: Could not create venv. Falling back to system Python...
    goto :VERIFY_ENV
)
echo [OK] Virtual environment created successfully.

:ACTIVATE_VENV
echo [*] Activating dedicated virtual environment (venv)...
call venv\Scripts\activate.bat

:VERIFY_ENV
for /f "tokens=*" %%i in ('python -c "import sys; print(sys.prefix)" 2^>nul') do set "ENV_PATH=%%i"
echo [OK] Running Python Environment: %ENV_PATH%

:: 4. Verify Core Dependencies
echo [*] Verifying required dependencies...
python -c "import speech_recognition, pyttsx3, pyaudio, tkinter, pytest, vosk" >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Installing or repairing missing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Please run INSTALL.bat.
        goto :ERROR_EXIT
    )
)
echo [OK] Core dependencies verified.

:: 5. Launch the Application
echo [*] Starting VoiceOS Assistant Dashboard...
echo.
python src\main.py %*

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with error code %errorlevel%.
    goto :ERROR_EXIT
)

exit /b 0

:ERROR_EXIT
echo.
echo =====================================================================
echo   Application Stopped or Startup Failed.
echo   Press any key to close this terminal.
echo =====================================================================
echo.
pause
exit /b 1
