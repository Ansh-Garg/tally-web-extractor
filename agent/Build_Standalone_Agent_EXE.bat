@echo off
title Build Standalone Tally Web Agent EXE
color 0A
cls
echo ======================================================================
echo    BUILDING STANDALONE TALLY WEB AGENT EXE (Zero Python Required)
echo                 Developed By : Ansh Garg
echo ======================================================================
echo.

echo Packaging Flask templates, static assets, engine and licensing...
pyinstaller --noconfirm --onedir --windowed ^
    --name "TallyWebAgent" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "config.json;." ^
    tally_agent.py

if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo Build SUCCESSFUL!
echo Distributable folder created in: dist\TallyWebAgent\
echo Run dist\TallyWebAgent\TallyWebAgent.exe to launch the agent.
echo ======================================================================
pause
