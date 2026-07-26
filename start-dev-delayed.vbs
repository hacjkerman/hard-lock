' Launch the DEV (closable) Hard Lock a little after logon.
'
' Starting straight from the Startup folder raced the desktop/WebView2 environment
' and could leave the app alive but inert (no ticking, no enforcement). Waiting
' ~45s lets the session settle first. Runs silently (no console window).
'
' The Startup shortcut points here; this resolves the exe relative to itself, so
' the repo stays self-contained.

Option Explicit

Dim fso, shell, here, exePath
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
exePath = fso.BuildPath(here, "dist\HardLockDev\HardLockDev.exe")

WScript.Sleep 45000  ' 45s — past the logon storm

If fso.FileExists(exePath) Then
    ' 0 = hidden window (the app makes its own), False = don't wait for exit
    shell.Run """" & exePath & """", 0, False
End If
