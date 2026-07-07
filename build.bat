@echo off
REM Build a self-contained Hard Lock release into dist\HardLock\.
REM   1. py -3.12 -m pip install -r requirements-dev.txt   (first time only)
REM   2. build.bat
cd /d "%~dp0"

py -3.12 -m PyInstaller --noconfirm --clean HardLock.spec
if %errorlevel% NEQ 0 (
  echo Build failed.
  exit /b 1
)

REM Ship the autostart helpers next to the exe so users can install with a click.
copy /y "packaging\install-autostart.bat"   "dist\HardLock\" >nul
copy /y "packaging\uninstall-autostart.bat" "dist\HardLock\" >nul

REM Optional Authenticode signing. Unsigned exes trip SmartScreen ("unknown
REM publisher"). Set HARDLOCK_PFX (and optionally HARDLOCK_PFX_PASS) to a code-
REM signing cert to sign automatically. Needs signtool.exe on PATH (Windows SDK).
if defined HARDLOCK_PFX (
  echo Signing HardLock.exe...
  signtool sign /f "%HARDLOCK_PFX%" /p "%HARDLOCK_PFX_PASS%" /fd sha256 /tr http://timestamp.digicert.com /td sha256 "dist\HardLock\HardLock.exe"
  if errorlevel 1 echo WARNING: signing failed ^(is signtool on PATH?^). Exe is unsigned.
) else (
  echo [skip] Code signing - set HARDLOCK_PFX to sign ^(unsigned exes trip SmartScreen^).
)

echo.
echo Built dist\HardLock\HardLock.exe
echo Release folder: dist\HardLock\
