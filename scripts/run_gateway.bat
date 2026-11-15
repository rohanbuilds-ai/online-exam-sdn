@echo off
cd /d "%~dp0\.."
echo ==============================================================================
echo Starting FastAPI Web Gateway on port 8000
echo Bridges Browser HTTP/WS to TCP Examination Server on port 5000
echo ==============================================================================
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
pause
