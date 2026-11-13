@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv .venv 2>nul
    if errorlevel 1 (
        python -m venv .venv
        if errorlevel 1 (
            echo Python 3 was not found. Install Python 3.10 or newer from python.org, then run this file again.
            pause
            exit /b 1
        )
    )
)

".venv\Scripts\python.exe" -c "import rdflib, dotenv" >nul 2>&1
if errorlevel 1 (
    echo Installing requirements...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Dependency installation failed. Check your internet connection and run this file again.
        pause
        exit /b 1
    )
)

if not exist ".env" copy /y ".env.example" ".env" >nul

".venv\Scripts\python.exe" scripts\run_queries.py
echo.
pause
