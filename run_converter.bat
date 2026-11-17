@echo off
title UiPath to Power Automate Desktop (Robin) Migration Tool
echo ============================================================
echo   UiPath to Power Automate Desktop (PAD Robin) Converter
echo   Configured for PwC GenAI Gateway (APAC)
echo ============================================================
echo.
cd /d "%~dp0"
echo Starting Streamlit App on http://localhost:8502 ...
python -m streamlit run nupkg_browser.py --server.port 8502
pause
