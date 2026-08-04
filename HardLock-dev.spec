# PyInstaller spec for the Hard Lock DEV build (closable, guardian-free).
# Build via build-dev.bat, which flips hard_lock/build.py DEV_BUILD to True first.
# Produces dist/HardLockDev/HardLockDev.exe with its own %APPDATA%\HardLockDev data.

from PyInstaller.utils.hooks import collect_all

datas = [("hard_lock/webui", "hard_lock/webui")]
binaries = []
hiddenimports = ["hard_lock.guardian", "hard_lock.winstyle"]

for pkg in ("webview", "pystray", "PIL"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["launch.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter.test", "test"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HardLockDev",
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/hardlock.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="HardLockDev",
)
