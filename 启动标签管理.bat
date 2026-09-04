@echo off
setlocal
cd /d "%~dp0"

set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV_EXE%" set "UV_EXE=uv"

"%UV_EXE%" --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] uv was not found. Please install the project runtime first.
  pause
  exit /b 1
)

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel%==0 (
  start "" "http://127.0.0.1:8787/"
  exit /b 0
)

echo Starting the tag manager...
start "" /b "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8787/'"
"%UV_EXE%" run python scripts\tag_admin.py

if errorlevel 1 pause
