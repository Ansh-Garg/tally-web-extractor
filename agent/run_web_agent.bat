@echo off
title Universal Tally Data Extractor - Web Agent v3.4
color 0B
cls
echo ======================================================================
echo       UNIVERSAL TALLY DATA EXTRACTOR - WEB AGENT v3.4
echo                 Developed By : Ansh Garg
echo        Enterprise Accounting & Consolidated Audit Suite
echo ======================================================================
echo.
echo [1/3] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

echo [2/3] Checking dependencies (Flask)...
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing required lightweight dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Could not install requirements. Please check internet connection.
        pause
        exit /b 1
    )
)

echo [3/3] Starting Local Web Agent on http://localhost:5000 ...
echo Browser will open automatically. Press Ctrl+C in this window to stop the agent.
echo.
python tally_agent.py

pause
