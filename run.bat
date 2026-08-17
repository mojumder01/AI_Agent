@echo off
setlocal

cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Is Python installed and on PATH?
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

set "REQ_STAMP=venv\.requirements.stamp"
set "NEED_INSTALL=0"

if not exist "%REQ_STAMP%" set "NEED_INSTALL=1"
if "%NEED_INSTALL%"=="0" (
    fc /b requirements.txt "%REQ_STAMP%" >nul 2>&1
    if errorlevel 1 set "NEED_INSTALL=1"
)

if "%NEED_INSTALL%"=="1" (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency install failed.
        pause
        exit /b 1
    )
    copy /y requirements.txt "%REQ_STAMP%" >nul
) else (
    echo Dependencies already up to date, skipping install.
)

if not exist venv\.playwright_chromium_installed (
    echo Installing Playwright Chromium ^(first time only^)...
    python -m playwright install chromium
    if errorlevel 1 (
        echo Playwright browser install failed.
        pause
        exit /b 1
    )
    echo done > venv\.playwright_chromium_installed
) else (
    echo Playwright Chromium already installed, skipping.
)

echo.
echo Starting AI Product Agent...
echo.
streamlit run app.py

pause
