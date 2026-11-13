@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo   Voice-Controlled OS Assistant - Automated Installer
echo =====================================================================
echo.

:: Detect project directory
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
echo Project Directory: %PROJECT_DIR%

:: Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not found on PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    echo Ensure "Add Python to PATH" is checked during installation.
    goto :ERROR_EXIT
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
echo Found: %PY_VER%
echo.

:: Check or create virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [*] Creating virtual environment 'venv'...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        goto :ERROR_EXIT
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: Activate virtual environment
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

:: Upgrade pip
echo [*] Checking pip...
python -m pip install --upgrade pip --quiet

:: Install dependencies
echo [*] Installing required packages from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    goto :ERROR_EXIT
)

echo.
echo =====================================================================
echo   Installation Completed Successfully!
echo   You can now run START.bat to launch the Voice Assistant.
echo =====================================================================
echo.
pause
exit /b 0

:ERROR_EXIT
echo.
echo =====================================================================
echo   Installation Encountered an Error.
echo =====================================================================
echo.
pause
exit /b 1
