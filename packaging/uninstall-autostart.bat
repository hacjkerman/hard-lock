@echo off
REM Remove the Hard Lock logon task. Self-elevates (deleting the task needs admin).
net session >nul 2>&1
if %errorlevel% NEQ 0 (
  echo Requesting administrator rights...
  powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
"%~dp0HardLock.exe" --uninstall
