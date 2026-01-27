@echo off
cd /d "%~dp0"
echo Starting XLIFF Assistant Desktop App...

REM Try explicit virtual environment paths
if exist ".venv\Scripts\python.exe" (
    echo Using Virtual Environment .venv...
    ".venv\Scripts\python.exe" "desktop_app.py"
) else (
    echo Virtual environment not found at .venv\Scripts\python.exe
    echo Attempting to use system python...
    python "desktop_app.py"
)

if %errorlevel% neq 0 (
    echo Application exited with error code %errorlevel%
)

pause
