@echo off
title Setup Git Repository for Render Deployment
color 0B
cls
echo ======================================================================
echo     TALLY WEB EXTRACTOR — GITHUB ^& RENDER DEPLOYMENT HELPER
echo                 Developed By : Ansh Garg
echo ======================================================================
echo.

REM 1. Re-package the latest agent zip
echo [1/4] Ensuring latest agent download bundle is packaged...
python package_agent.py
if %errorlevel% neq 0 (
    echo [ERROR] Failed to package agent.
    pause
    exit /b 1
)

REM 2. Check git
echo [2/4] Checking Git installation...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not in PATH.
    echo Please install Git from https://git-scm.com/
    pause
    exit /b 1
)

REM 3. Initialize or stage
echo [3/4] Preparing Git repository...
if not exist ".git" (
    git init
    git branch -M main
)

git add .
git commit -m "Deploy Universal Tally Web Extractor v3.4 to Render"

echo.
echo ======================================================================
echo Git repository prepared successfully!
echo.
echo NEXT STEPS TO DEPLOY ON RENDER:
echo.
echo 1. Create a new repository on https://github.com (e.g. tally-web-extractor)
echo 2. Run the following two commands (replace YOUR_GITHUB_URL):
echo.
echo    git remote add origin https://github.com/Ansh-Garg/tally-web-extractor.git
echo    git push -u origin main
echo.
echo 3. Go to https://dashboard.render.com/
echo    - Click 'New +' -^> 'Web Service' (or 'Blueprint')
echo    - Connect your GitHub repository 'tally-web-extractor'
echo    - Render will automatically read render.yaml and deploy!
echo ======================================================================
pause
