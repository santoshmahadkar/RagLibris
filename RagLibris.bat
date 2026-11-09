@echo off
setlocal

REM ============================================================
REM RagLibris Launcher
REM ============================================================

cd /d C:\ubuntu\RagLibris

echo.
echo ==========================================
echo          Starting RagLibris
echo ==========================================
echo.

REM ============================================================
REM Start FastAPI Backend
REM ============================================================

echo [1/2] Starting FastAPI backend...

start "RagLibris Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn backend:app --host 0.0.0.0 --port 8000"

echo Backend process started.
echo.
echo Waiting for FastAPI to become available...

REM ============================================================
REM Wait for FastAPI
REM ============================================================

:CHECK_API

powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/docs' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"

IF %ERRORLEVEL% EQU 0 GOTO API_READY

timeout /t 1 /nobreak >nul

GOTO CHECK_API

:API_READY

echo.
echo ==========================================
echo FastAPI backend is READY
echo ==========================================
echo.

REM ============================================================
REM Start Streamlit Frontend
REM ============================================================

echo [2/2] Starting Streamlit frontend...

start "RagLibris Frontend" cmd /k ".venv\Scripts\python.exe -m streamlit run frontend.py"

echo Frontend process started.
echo.

echo ==========================================
echo          RagLibris Started
echo ==========================================
echo.
echo Backend  : http://localhost:8000
echo Frontend : http://localhost:8501
echo.

endlocal