@echo off
setlocal
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js is not installed or not available in PATH.
  pause
  exit /b 1
)

node scripts\worldcup-final-four-official-fix.mjs
if errorlevel 1 (
  echo [ERROR] The World Cup final-four correction failed.
  pause
  exit /b 1
)

echo.
echo [OK] Corrected:
echo      M101 Spain 2-0 France
echo      M102 Argentina 2-1 England
echo      M103 France vs England
echo      M104 Spain vs Argentina
echo.
echo Review git status, then commit and push the changed files.
git status --short 2>nul
pause
