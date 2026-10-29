@echo off
title Connected Vehicle Digital Twin - Dashboard Launcher
echo ======================================================================
echo   CONNECTED VEHICLE DIGITAL TWIN RESEARCH DASHBOARD
echo ======================================================================
echo.
echo Starting Streamlit Research Analytics Dashboard...
echo Opening: http://localhost:8501
echo.
start http://localhost:8501
python -m streamlit run app.py
pause
