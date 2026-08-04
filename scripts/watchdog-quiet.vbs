' Windowless wrapper for the AtelierWatchdog scheduled task.
'
' WHY: the task used to invoke powershell.exe -WindowStyle Hidden directly, but that
' flag only hides the console AFTER conhost has already flashed it - a cmd window
' blinked in the user's face every 5 minutes (worst while gaming). wscript.exe has
' no console at all, so Run(..., 0, False) is genuinely invisible.
'
' Resolves start-day.ps1 relative to this file (scripts\ -> repo root), so the repo
' can move without re-registering the task.
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & root & "\start-day.ps1"" -IfOn"
CreateObject("WScript.Shell").Run cmd, 0, False
