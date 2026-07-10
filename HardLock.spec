# PyInstaller spec for Hard Lock. Build:  py -3.12 -m PyInstaller HardLock.spec
# Produces dist/HardLock/HardLock.exe (onedir — faster start, easy to inspect).

from PyInstaller.utils.hooks import collect_all

datas = [("hard_lock/webui", "hard_lock/webui")]
binaries = []
hiddenimports = []

# pywebview pulls in its platform backends dynamically; pystray likewise loads a
# platform backend by name. collect_all so the frozen build finds them at runtime.
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
    name="HardLock",
    console=False,          # windowed — no stray console at logon
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
    name="HardLock",
)
