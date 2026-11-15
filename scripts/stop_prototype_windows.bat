@echo off
setlocal enabledelayedexpansion
title SDN Online Examination Network — Windows Process Shutdown
cd /d "%~dp0\.."

echo ==============================================================================
echo       SDN ONLINE EXAMINATION NETWORK — SHUTDOWN UTILITY (WINDOWS)
echo ==============================================================================
echo.
echo Stopping running prototype processes on ports 5000, 8000, and 5173...
echo.

set TARGET_PORTS=5000 8000 5173
set KILLED=0

for %%P in (%TARGET_PORTS%) do (
    echo [*] Checking port %%P...
    for /f "tokens=5" %%A in ('netstat -aon ^| findstr /r ":%%P\>.*LISTENING"') do (
        set PID=%%A
        if defined PID (
            if not "!PID!"=="0" (
                echo     Found process !PID! listening on port %%P. Terminating...
                taskkill /F /PID !PID! >nul 2>&1
                if !errorlevel! equ 0 (
                    echo     [OK] Successfully terminated process !PID! (Port %%P).
                    set /a KILLED+=1
                ) else (
                    echo     [!] Could not terminate process !PID!. It may have already exited.
                )
            )
        )
    )
)

echo.
if %KILLED% gtr 0 (
    echo [OK] Stopped %KILLED% running prototype service(s). Ports are now free.
) else (
    echo [INFO] No active listeners found on ports 5000, 8000, or 5173.
)
echo.
echo ==============================================================================
