@echo off
cd /d "%~dp0"
echo Starting XLIFF Assistant (Streamlit Mode)...
streamlit run streamlit_app.py
pause
