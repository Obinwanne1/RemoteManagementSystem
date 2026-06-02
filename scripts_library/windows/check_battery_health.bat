@echo off
echo === Battery Health Report ===
powercfg /batteryreport /output "%TEMP%\battery_report.html" >nul 2>&1
if exist "%TEMP%\battery_report.html" (
    echo Battery report generated at: %TEMP%\battery_report.html
    powercfg /batteryreport /output "%TEMP%\battery_report.html" /duration 14
) else (
    echo No battery detected or powercfg not available.
)
echo === WMIC Battery Status ===
wmic path Win32_Battery get BatteryStatus, EstimatedChargeRemaining, Name 2>nul
echo Done.
