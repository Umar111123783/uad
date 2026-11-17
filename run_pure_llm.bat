@echo off
title UiPath to PAD Robin Pure LLM Converter (app_llm)
echo ============================================================
echo   UiPath to PAD Pure LLM Engine (PwC GenAI Gateway)
echo ============================================================
echo.
cd /d "%~dp0"
echo Starting Pure LLM Streamlit App on http://localhost:8503 ...
python -m streamlit run app_llm.py --server.port 8503
pause
