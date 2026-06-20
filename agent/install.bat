@echo off
echo ============================================
echo  RMM Agent Installer
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from https://python.org then re-run this script.
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: pip install failed. Check internet connection.
    pause
    exit /b 1
)

echo [2/3] Configuring agent...
python setup_agent.py 192.168.178.23 a8b6ea9bceae8b9cff9e63c2519d3e306453c1325306c64d
if errorlevel 1 (
    echo ERROR: Setup failed.
    pause
    exit /b 1
)

echo [3/3] Starting agent...
echo.
echo Device will appear in RMM dashboard within 60 seconds.
echo Keep this window open. Close it to stop the agent.
echo.
python rmm_agent.py
pause
