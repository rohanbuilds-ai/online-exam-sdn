@echo off
setlocal enabledelayedexpansion
title SDN Online Examination Network — Windows Launcher
cd /d "%~dp0\.."

:menu
cls
echo ==============================================================================
echo       SDN ONLINE EXAMINATION NETWORK — PROTOTYPE LAUNCHER (WINDOWS)
echo ==============================================================================
echo.
echo   [1] Start TCP Examination Server     (authoritative daemon on port 5000)
echo   [2] Start FastAPI Web Gateway        (adapter on port 8000 + /docs)
echo   [3] Start React + Vite Frontend      (web UI on http://localhost:5173)
echo   [4] Start SDN OpenFlow Controller    (OpenFlow 1.3 on port 6653)
echo   [5] Launch ALL 3 Web Components      (Server + Gateway + Frontend)
echo   [6] Run Full Test Suite              (36 unit, concurrency & API tests)
echo   [7] Stop Running Components          (release ports 5000, 8000, 5173)
echo   [8] Exit
echo.
echo ==============================================================================
set /p opt="Select an option [1-8]: "

if "%opt%"=="1" goto start_server
if "%opt%"=="2" goto start_gateway
if "%opt%"=="3" goto start_frontend
if "%opt%"=="4" goto start_controller
if "%opt%"=="5" goto launch_all
if "%opt%"=="6" goto run_tests
if "%opt%"=="7" goto stop_all
if "%opt%"=="8" goto exit_script

echo.
echo [!] Invalid selection. Please enter a number between 1 and 8.
timeout /t 2 >nul
goto menu

:start_server
echo.
echo [*] Starting TCP Examination Server on 127.0.0.1:5000...
python app/server.py --host 0.0.0.0 --port 5000 --duration 300 --questions 5
pause
goto menu

:start_gateway
echo.
call :check_python_deps
if !errorlevel! neq 0 (
    pause
    goto menu
)
echo [*] Starting FastAPI Web Gateway on http://127.0.0.1:8000...
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
pause
goto menu

:start_frontend
echo.
call :check_node_deps
if !errorlevel! neq 0 (
    pause
    goto menu
)
echo [*] Starting React + Vite Frontend on http://localhost:5173...
cd frontend && npm run dev
pause
goto menu

:start_controller
echo.
echo [*] Starting Pure-Python OpenFlow 1.3 SDN Controller on 0.0.0.0:6653...
python sdn/controller.py --host 0.0.0.0 --port 6653 --bw 10.0 --threshold 70.0
pause
goto menu

:launch_all
echo.
echo [*] Checking system dependencies before concurrent launch...
call :check_python_deps
if !errorlevel! neq 0 (
    pause
    goto menu
)
call :check_node_deps
if !errorlevel! neq 0 (
    pause
    goto menu
)

echo.
echo [*] 1/3 Spawning TCP Examination Server on port 5000...
start "SDN: TCP Exam Server (Port 5000)" cmd /k "cd /d \"%~dp0\..\" && title SDN: TCP Exam Server (Port 5000) && python app/server.py --host 0.0.0.0 --port 5000 --duration 300 --questions 5"
timeout /t 2 >nul

echo [*] 2/3 Spawning FastAPI Web Gateway on port 8000...
start "SDN: FastAPI Gateway (Port 8000)" cmd /k "cd /d \"%~dp0\..\" && title SDN: FastAPI Gateway (Port 8000) && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 2 >nul

echo [*] 3/3 Spawning React Frontend Dev Server on port 5173...
start "SDN: React Frontend (Port 5173)" cmd /k "cd /d \"%~dp0\..\frontend\" && title SDN: React Frontend (Port 5173) && npm run dev"
timeout /t 2 >nul

echo.
echo ==============================================================================
echo [OK] All 3 Online Examination SDN components launched successfully!
echo.
echo   Student Portal:        http://localhost:5173
echo   Admin Dashboard:       http://localhost:5173/admin
echo   SDN NOC Monitor:       http://localhost:5173/sdn
echo   FastAPI Swagger Docs:  http://localhost:8000/docs
echo   TCP Exam Server:       127.0.0.1:5000
echo ==============================================================================
echo.
set /p open_browser="Open web prototype in default browser now? [Y/n]: "
if /i not "%open_browser%"=="n" (
    start http://localhost:5173
)
echo.
pause
goto menu

:run_tests
echo.
echo [*] Executing Complete Test Suite across all modules...
python -m unittest discover -s tests -v
echo.
pause
goto menu

:stop_all
echo.
call "%~dp0stop_prototype_windows.bat"
pause
goto menu

:: -----------------------------------------------------------------------------
:: Helper checks
:: -----------------------------------------------------------------------------
:check_python_deps
python -c "import fastapi, uvicorn, pydantic" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Missing required Python packages for the Web Gateway.
    echo Please install them with:
    echo     pip install -r api/requirements.txt
    exit /b 1
)
exit /b 0

:check_node_deps
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not found in PATH.
    echo Please install Node.js 18+ from https://nodejs.org/ to run the frontend.
    exit /b 1
)
if not exist "%~dp0..\frontend\node_modules" (
    echo [WARNING] frontend\node_modules not found.
    echo Running 'npm install' in frontend directory...
    cd /d "%~dp0..\frontend" && npm install
    cd /d "%~dp0\.."
)
exit /b 0

:exit_script
exit /b 0
