@echo off
cd /d "%~dp0"
echo Starting XLIFF AI Assistant (Modern UI)...

REM Try explicit virtual environment paths
if exist ".venv\Scripts\python.exe" (
    echo Using Virtual Environment .venv...
    ".venv\Scripts\python.exe" -m ui.modern.main_window
) else (
    echo Virtual environment not found at .venv\Scripts\python.exe
    echo Attempting to use system python...
    python -m ui.modern.main_window
)

if %errorlevel% neq 0 (
    echo Application exited with error code %errorlevel%
    pause
)
