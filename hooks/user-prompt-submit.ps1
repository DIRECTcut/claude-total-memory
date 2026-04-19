# ===========================================
# UserPromptSubmit Hook (PowerShell) — capture each user prompt into `intents`
#
# Port of hooks/user-prompt-submit.sh for Windows.
# Fires on every prompt the user submits. Reads the full hook JSON from
# stdin, extracts the prompt + session_id + cwd and calls save_intent()
# asynchronously so the hook NEVER blocks input.
#
# Env:
#   CLAUDE_MEMORY_INSTALL_DIR — install root (auto-resolved)
#   CLAUDE_MEMORY_DIR         — memory storage (%USERPROFILE%\.claude-memory)
#
# Hook: UserPromptSubmit (matcher: "")
# ===========================================

$ErrorActionPreference = "SilentlyContinue"

# Resolve install / memory dirs (same layout as other hooks).
$InstallDir = if ($env:CLAUDE_MEMORY_INSTALL_DIR) {
    $env:CLAUDE_MEMORY_INSTALL_DIR
} else {
    Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$MemoryDir = if ($env:CLAUDE_MEMORY_DIR) { $env:CLAUDE_MEMORY_DIR } else { Join-Path $env:USERPROFILE ".claude-memory" }

$HookPython = [System.IO.Path]::Combine($InstallDir, ".venv", "Scripts", "python.exe")
if (-not (Test-Path $HookPython)) {
    # Fallback to PATH python on Windows
    $HookPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $HookPython) {
        $HookPython = (Get-Command python3 -ErrorAction SilentlyContinue).Source
    }
}
if (-not $HookPython) { exit 0 }

$SrcDir = [System.IO.Path]::Combine($InstallDir, "src")
$DbPath = [System.IO.Path]::Combine($MemoryDir, "memory.db")

# Cache stdin to a temp file so the background Python can read it after
# this shell exits.
$TmpInput = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "cmm-uprompt-$(New-Guid).json")
$stdin = [Console]::In.ReadToEnd()
[System.IO.File]::WriteAllText($TmpInput, $stdin)

# Inline Python payload — identical logic to the bash version.
$PyScript = @'
import json, os, sys
from pathlib import Path

src_dir = sys.argv[1]
db_path = sys.argv[2]
tmp = sys.argv[3]

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    raw = Path(tmp).read_text()
except Exception:
    raw = ""
finally:
    try:
        os.unlink(tmp)
    except Exception:
        pass

if not raw:
    sys.exit(0)

try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)

prompt = data.get("prompt")
if not prompt:
    user_msg = data.get("user_message") or {}
    if isinstance(user_msg, dict):
        prompt = user_msg.get("content") or ""
prompt = (prompt or "").strip()
if not prompt:
    sys.exit(0)

session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown"
cwd = data.get("cwd") or os.getcwd()
project = os.path.basename(cwd) or "unknown"

if not Path(db_path).exists():
    sys.exit(0)

try:
    from intents import save_intent
    save_intent(db_path, prompt, session_id, project)
except Exception:
    # Hook must never crash the user session.
    pass
'@

# Fire-and-forget - Start-Process detaches so main hook returns immediately.
# WindowStyle Hidden keeps the python console off-screen; no -NoNewWindow
# (they are mutually exclusive in Start-Process).
$arguments = @("-c", $PyScript, $SrcDir, $DbPath, $TmpInput)
try {
    Start-Process -FilePath $HookPython `
        -ArgumentList $arguments `
        -WindowStyle Hidden `
        -ErrorAction SilentlyContinue | Out-Null
} catch {
    # Never fail the user session.
}

exit 0
