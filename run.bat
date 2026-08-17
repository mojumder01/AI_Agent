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

echo Installing dependencies...
pip install -r requirements.txt

echo Checking Playwright Chromium browser...
python -m playwright install chromium

echo.
echo Starting AI Product Agent...
echo.
streamlit run app.py

pause
