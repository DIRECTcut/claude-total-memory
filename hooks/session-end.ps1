#
# SessionEnd hook — auto-save session context to memory on session end
#
# Runs auto_session_save.py to preserve lightweight session summary.
#

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Split-Path -Parent $ScriptDir
$VenvPython = Join-Path $InstallDir ".venv" "Scripts" "python.exe"
$AutoSave = Join-Path $InstallDir "src" "auto_session_save.py"

$Project = Split-Path -Leaf (Get-Location)

if ((Test-Path $AutoSave) -and (Test-Path $VenvPython)) {
    Start-Process -NoNewWindow -FilePath $VenvPython -ArgumentList "`"$AutoSave`" --project `"$Project`""
}

Write-Output "Session ended. Context auto-saved for project: $Project"
