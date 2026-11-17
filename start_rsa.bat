@echo off
REM Double-click to start RSA from THIS folder (uses this folders rsa.db).
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" run_rsa.py
) else (
  python run_rsa.py
)
echo.
echo RSA has stopped. Press any key to close this window.
pause >nul
