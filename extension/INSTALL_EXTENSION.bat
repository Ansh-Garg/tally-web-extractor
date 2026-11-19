@echo off
setlocal enabledelayedexpansion
title Tally Web Bridge — 1-Click Extension Installer
color 0B
cls
echo.
echo  ================================================================
echo     TALLY WEB BRIDGE — AUTO-INSTALLER
echo     Developed By : Ansh Garg
echo     This installs the Chrome Extension with ONE click.
echo  ================================================================
echo.

REM ---- Get this script's own folder (the extracted extension folder) ----
set "EXT_DIR=%~dp0"
REM Remove trailing backslash
if "%EXT_DIR:~-1%"=="\" set "EXT_DIR=%EXT_DIR:~0,-1%"

echo  [1/4] Extension folder detected:
echo         %EXT_DIR%
echo.

REM ---- Write the extension path to a known temp location for Chrome ----
set "MARKER=%TEMP%\tally_ext_path.txt"
echo %EXT_DIR%> "%MARKER%"

REM ---- Detect Chrome ----
set "CHROME_EXE="
set "BROWSER_NAME="

REM Try registry first (most reliable)
for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul') do (
    if exist "%%B" (
        set "CHROME_EXE=%%B"
        set "BROWSER_NAME=Google Chrome"
    )
)

REM Try HKCU registry
if not defined CHROME_EXE (
    for /f "tokens=2*" %%A in ('reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2^>nul') do (
        if exist "%%B" (
            set "CHROME_EXE=%%B"
            set "BROWSER_NAME=Google Chrome"
        )
    )
)

REM Try common paths
if not defined CHROME_EXE (
    if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
        set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
        set "BROWSER_NAME=Google Chrome"
    )
)
if not defined CHROME_EXE (
    if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
        set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        set "BROWSER_NAME=Google Chrome"
    )
)
if not defined CHROME_EXE (
    if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
        set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
        set "BROWSER_NAME=Google Chrome"
    )
)

REM Try Microsoft Edge (also supports Chrome Extensions natively)
if not defined CHROME_EXE (
    for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe" /ve 2^>nul') do (
        if exist "%%B" (
            set "CHROME_EXE=%%B"
            set "BROWSER_NAME=Microsoft Edge"
        )
    )
)
if not defined CHROME_EXE (
    if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
        set "CHROME_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        set "BROWSER_NAME=Microsoft Edge"
    )
)

echo  [2/4] Browser detection:
if defined CHROME_EXE (
    echo         Found: %BROWSER_NAME%
    echo         Path : %CHROME_EXE%
) else (
    echo         [!] Neither Chrome nor Edge detected.
    goto :MANUAL_INSTALL
)
echo.

REM ---- Write a minimal installer HTML page to guide through the last step ----
set "GUIDE_HTML=%TEMP%\tally_ext_install_guide.html"
(
echo ^<!DOCTYPE html^>
echo ^<html lang="en"^>
echo ^<head^>
echo   ^<meta charset="UTF-8"^>
echo   ^<meta name="viewport" content="width=device-width, initial-scale=1.0"^>
echo   ^<title^>Tally Web Bridge — Extension Installer^</title^>
echo   ^<style^>
echo     * { margin:0; padding:0; box-sizing:border-box; }
echo     body { font-family: 'Segoe UI', Arial, sans-serif; background:#0f1117; color:#e2e8f0; min-height:100vh; display:flex; align-items:center; justify-content:center; }
echo     .card { background:#1a1f2e; border-radius:16px; padding:40px 48px; max-width:700px; width:95%%; box-shadow:0 0 60px rgba(99,102,241,0.15); border:1px solid #2d3748; }
echo     .header { text-align:center; margin-bottom:32px; }
echo     .logo { font-size:3rem; margin-bottom:12px; }
echo     h1 { font-size:1.6rem; color:#a78bfa; font-weight:800; }
echo     .sub { color:#94a3b8; margin-top:6px; font-size:0.9rem; }
echo     .steps { margin:28px 0; }
echo     .step { display:flex; align-items:flex-start; gap:16px; padding:18px; background:#111827; border-radius:12px; margin-bottom:12px; border:1px solid #2d3748; }
echo     .step.done { border-color:#10b981; background:#0d2b1f; }
echo     .step.active { border-color:#6366f1; background:#1a1033; }
echo     .num { width:36px; height:36px; border-radius:50%%; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:1rem; flex-shrink:0; }
echo     .step.done .num { background:#10b981; color:#fff; }
echo     .step.active .num { background:#6366f1; color:#fff; }
echo     .step:not(.done):not(.active) .num { background:#374151; color:#9ca3af; }
echo     .step-content h3 { font-size:1rem; font-weight:700; margin-bottom:4px; }
echo     .step-content p { font-size:0.85rem; color:#94a3b8; line-height:1.5; }
echo     code { background:#374151; padding:2px 7px; border-radius:5px; font-family:monospace; font-size:0.85rem; color:#fbbf24; }
echo     .path-box { background:#111827; border:1px solid #374151; border-radius:8px; padding:14px 16px; margin:20px 0; font-family:monospace; font-size:0.85rem; color:#fbbf24; word-break:break-all; }
echo     .path-label { font-size:0.75rem; color:#6b7280; margin-bottom:6px; }
echo     .btn-open { display:block; width:100%%; padding:16px; background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff; border:none; border-radius:10px; font-size:1.05rem; font-weight:800; cursor:pointer; text-decoration:none; text-align:center; margin-top:24px; letter-spacing:0.5px; }
echo     .btn-open:hover { opacity:0.9; }
echo     .footer-note { text-align:center; margin-top:20px; font-size:0.78rem; color:#6b7280; }
echo   ^</style^>
echo ^</head^>
echo ^<body^>
echo   ^<div class="card"^>
echo     ^<div class="header"^>
echo       ^<div class="logo"^>⚡^</div^>
echo       ^<h1^>Tally Web Bridge — Extension Installer^</h1^>
echo       ^<div class="sub"^>Developed By : Ansh Garg &bull; Almost done — just 3 quick steps below^</div^>
echo     ^</div^>
echo.
echo     ^<div class="steps"^>
echo       ^<div class="step done"^>
echo         ^<div class="num"^>✓^</div^>
echo         ^<div class="step-content"^>
echo           ^<h3^>Step 1: Downloaded &amp; Extracted^</h3^>
echo           ^<p^>You already unzipped this folder. ^<strong^>Done!^</strong^>^</p^>
echo         ^</div^>
echo       ^</div^>
echo.
echo       ^<div class="step active"^>
echo         ^<div class="num"^>2^</div^>
echo         ^<div class="step-content"^>
echo           ^<h3^>Step 2: Open Extensions Page (Auto-Opening Now...)</h3^>
echo           ^<p^>Your browser is opening ^<code^>chrome://extensions^</code^>. Enable the toggle ^<strong^>"Developer mode"^</strong^> in the top-right corner.^</p^>
echo         ^</div^>
echo       ^</div^>
echo.
echo       ^<div class="step active"^>
echo         ^<div class="num"^>3^</div^>
echo         ^<div class="step-content"^>
echo           ^<h3^>Step 3: Click "Load unpacked"^</h3^>
echo           ^<p^>A folder picker will appear. Navigate to this exact folder and click ^<strong^>Select Folder^</strong^>:^</p^>
echo           ^<div class="path-box"^>
echo             ^<div class="path-label"^>COPY THIS FOLDER PATH:^</div^>
echo             %EXT_DIR%
echo           ^</div^>
echo           ^<p^>^<strong^>Tip:^</strong^> You can copy the path above, paste it into the folder picker's address bar, and press Enter.^</p^>
echo         ^</div^>
echo       ^</div^>
echo     ^</div^>
echo.
echo     ^<a class="btn-open" href="javascript:void(0)" onclick="window.open('https://tally-web-extractor.onrender.com/dashboard')"^>
echo       ✓ Extension Installed? Open Web Extractor Dashboard →
echo     ^</a^>
echo     ^<div class="footer-note"^>Once installed, the extension auto-detects Tally on port 8080 each time you visit the dashboard.^</div^>
echo   ^</div^>
echo ^</body^>
echo ^</html^>
) > "%GUIDE_HTML%"

echo  [3/4] Launching browser with installer guide + Extensions page...
echo.

REM Open the extensions page (this opens chrome://extensions or edge://extensions)
start "" "%CHROME_EXE%" "chrome://extensions"
timeout /t 2 /nobreak >nul

REM Open the local installer guide in the same browser
start "" "%CHROME_EXE%" "%GUIDE_HTML%"

echo  [4/4] Done! Follow the 3 steps shown in your browser.
echo.
echo  ================================================================
echo   NEXT ACTION IN YOUR BROWSER:
echo   1. Enable "Developer mode" toggle (top-right of Extensions page)
echo   2. Click "Load unpacked"
echo   3. Paste or navigate to: %EXT_DIR%
echo   4. Click "Select Folder" — extension installed!
echo  ================================================================
echo.
pause
goto :EOF

:MANUAL_INSTALL
echo.
echo  ================================================================
echo   MANUAL INSTALLATION (Chrome/Edge not found automatically)
echo  ================================================================
echo.
echo   1. Open Google Chrome or Microsoft Edge
echo   2. In the address bar type:  chrome://extensions
echo      (or for Edge:  edge://extensions)
echo   3. Turn ON "Developer mode" (toggle, top-right corner)
echo   4. Click "Load unpacked"
echo   5. Select this folder:
echo      %EXT_DIR%
echo   6. Click "Select Folder"
echo.
echo   Extension will appear as "Tally Web Bridge" and start automatically.
echo.
pause
