@echo off
REM Hard Lock launcher. On first run this creates config.json and state.json
REM in this directory. Edit config.json and set "dry_run": false to arm.
REM First-time setup: py -3.12 -m pip install -r requirements.txt
cd /d "%~dp0"
start "" pyw -3.12 -m hard_lock
