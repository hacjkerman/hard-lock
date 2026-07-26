@echo off
REM Trigger Hard Lock's real shutdown on demand.
REM
REM Shows the grace countdown, then powers the machine off — but holds at zero
REM ("Waiting for Claude Code to finish...") while any Claude Code session is
REM still working, and holds while a defer-for game is running. Writes NO config,
REM so there is nothing to revert and no boot-loop risk.
REM
REM Close the window / kill the process to abort before it fires.
setlocal
set EXE=%~dp0dist\HardLockDev\HardLockDev.exe
if not exist "%EXE%" set EXE=%~dp0dist\HardLock\HardLock.exe
if not exist "%EXE%" (
    echo Could not find HardLockDev.exe or HardLock.exe under dist\ - build first.
    exit /b 1
)
echo Starting Hard Lock shutdown via "%EXE%"
echo A 60s countdown will appear; it waits for Claude Code before powering off.
start "" "%EXE%" --test-shutdown 60 real
endlocal
