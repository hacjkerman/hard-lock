@echo off
REM Debug launcher: keeps the console window so you can see dry-run output.
cd /d "%~dp0"
py -3.12 -m hard_lock
pause
