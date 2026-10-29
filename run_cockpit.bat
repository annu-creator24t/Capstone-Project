@echo off
title Connected Vehicle Digital Twin - Cockpit Launcher
echo ======================================================================
echo   CONNECTED VEHICLE DIGITAL TWIN - LIVE COCKPIT
echo ======================================================================
echo.
echo Starting Web Cockpit...
echo Opening: http://localhost:8050
echo.
start http://localhost:8050
python dashboard/server.py --port 8050
pause
