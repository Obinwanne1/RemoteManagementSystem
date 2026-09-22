@echo off
:: Set RMM_SERVER_IP and RMM_ORG_TOKEN env vars beforehand to skip the prompts,
:: e.g.: set RMM_SERVER_IP=192.168.1.100 & set RMM_ORG_TOKEN=... & install.bat
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
if "%RMM_SERVER_IP%"=="" set /p RMM_SERVER_IP="RMM server IP (e.g. 192.168.1.100): "
if "%RMM_ORG_TOKEN%"=="" set /p RMM_ORG_TOKEN="Org registration token (from Admin panel): "
python setup_agent.py %RMM_SERVER_IP% %RMM_ORG_TOKEN%
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
