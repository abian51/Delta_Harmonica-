@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "PYTHONW=%PROJECT_DIR%.venv\Scripts\pythonw.exe"

if not exist "%PYTHON%" (
    echo Delta Harmonica Studio cannot start.
    echo Missing: %PYTHON%
    echo Please run the project setup first.
    pause
    exit /b 1
)

"%PYTHON%" -c "import dhs, tkinter" >nul 2>&1
if errorlevel 1 (
    echo Delta Harmonica Studio cannot start because the Python environment is invalid.
    echo Please recreate .venv and install the dependencies listed in README.md.
    pause
    exit /b 1
)

start "Delta Harmonica Studio" /D "%PROJECT_DIR%" "%PYTHONW%" -m dhs
exit /b 0
