@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo   Voice-Controlled Operating System Assistant
echo =====================================================================
echo.

:: 1. Detect project directory
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
echo Project Directory: %PROJECT_DIR%

:: 2. Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not found on PATH.
    echo Please install Python 3.10+ and add it to your system PATH.
    goto :ERROR_EXIT
)

:: 3. Activate venv if present, otherwise use system Python
if exist "venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [*] Virtual environment not found. Using system Python...
)

:: 4. Verify core dependencies
echo [*] Checking core dependencies...
python -c "import speech_recognition, pyttsx3, pyaudio" >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Missing dependencies detected. Installing required packages...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install missing dependencies automatically.
        echo Please run INSTALL.bat manually.
        goto :ERROR_EXIT
    )
)
echo [OK] Dependencies verified.

:: 5. Launch the Application
echo [*] Launching VoiceOS Assistant Dashboard...
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
