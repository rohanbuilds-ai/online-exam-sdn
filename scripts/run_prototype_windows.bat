@echo off
title SDN Online Examination Network Launcher
cd /d "%~dp0\.."

echo ==============================================================================
echo       SDN ONLINE EXAMINATION NETWORK — PROTOTYPE LAUNCHER (WINDOWS)
echo ==============================================================================
echo.
echo   [1] Start TCP Examination Server (port 5000)
echo   [2] Start FastAPI Web Gateway (port 8000)
echo   [3] Start React + Vite Frontend (http://localhost:5173)
echo   [4] Start SDN OpenFlow Controller (port 6653)
echo   [5] Launch ALL Components (Opens 3 separate windows: Server + Gateway + Frontend)
echo   [6] Run Full Unit & Concurrency Test Suite (35 tests)
echo   [7] Exit
echo.
set /p opt="Select an option [1-7]: "

if "%opt%"=="1" (
    python app/server.py --host 0.0.0.0 --port 5000 --duration 300 --questions 5
    pause
    goto end
)
if "%opt%"=="2" (
    python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    pause
    goto end
)
if "%opt%"=="3" (
    cd frontend && npm run dev
    pause
    goto end
)
if "%opt%"=="4" (
    python sdn/controller.py --host 0.0.0.0 --port 6653 --bw 10.0 --threshold 70.0
    pause
    goto end
)
if "%opt%"=="5" (
    echo Starting TCP Server in new window...
    start "TCP Exam Server (5000)" cmd /k "cd /d \"%~dp0\..\" && python app/server.py --host 0.0.0.0 --port 5000 --duration 300 --questions 5"
    timeout /t 2 >nul

    echo Starting FastAPI Gateway in new window...
    start "FastAPI Gateway (8000)" cmd /k "cd /d \"%~dp0\..\" && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
    timeout /t 2 >nul

    echo Starting React Frontend in new window...
    start "React Frontend (5173)" cmd /k "cd /d \"%~dp0\..\frontend\" && npm run dev"
    
    echo.
    echo All 3 components launched successfully!
    echo Access the Web Prototype at: http://localhost:5173
    echo API Docs (Swagger):          http://localhost:8000/docs
    pause
    goto end
)
if "%opt%"=="6" (
    python -m unittest discover -s tests -v
    pause
    goto end
)

:end
