@echo off
REM Build the closable DEV version: flip DEV_BUILD on, build HardLockDev.exe,
REM then restore DEV_BUILD=False so the repo stays prod (committed-capable).
setlocal
copy /y hard_lock\build.py hard_lock\build.py.bak >nul
py -3.12 -c "p='hard_lock/build.py'; s=open(p,encoding='utf-8').read().replace('DEV_BUILD = False','DEV_BUILD = True'); open(p,'w',encoding='utf-8').write(s)"
py -3.12 -m PyInstaller --noconfirm --clean HardLock-dev.spec
copy /y hard_lock\build.py.bak hard_lock\build.py >nul
del hard_lock\build.py.bak >nul 2>&1
echo Done: dist\HardLockDev\HardLockDev.exe  (DEV_BUILD restored to False)
endlocal
