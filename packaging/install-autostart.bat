@echo off
REM Install the Hard Lock logon task so it launches automatically at sign-in.
REM Creating an ONLOGON scheduled task needs admin rights, so this self-elevates.
net session >nul 2>&1
if %errorlevel% NEQ 0 (
  echo Requesting administrator rights...
  powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
"%~dp0HardLock.exe" --install
