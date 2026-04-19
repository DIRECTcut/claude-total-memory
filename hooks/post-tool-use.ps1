# ===========================================
# PostToolUse Hook (PowerShell) — opt-in capture of tool observations
#
# Port of hooks/post-tool-use.sh for Windows.
# Opt-in via env MEMORY_POST_TOOL_CAPTURE=1. When enabled, enqueues a
# deferred observation for the extractor to pick up. Non-blocking.
#
# Env:
#   MEMORY_POST_TOOL_CAPTURE  — "1" to enable, anything else -> no-op
#   CLAUDE_MEMORY_INSTALL_DIR — install root (auto-resolved)
#   CLAUDE_MEMORY_DIR         — memory storage
#
# Hook: PostToolUse (matcher: "*")
# ===========================================

$ErrorActionPreference = "SilentlyContinue"

# Opt-in guard — absence of the flag is a no-op.
if ($env:MEMORY_POST_TOOL_CAPTURE -ne "1") {
    exit 0
}

$InstallDir = if ($env:CLAUDE_MEMORY_INSTALL_DIR) {
    $env:CLAUDE_MEMORY_INSTALL_DIR
} else {
    Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$MemoryDir = if ($env:CLAUDE_MEMORY_DIR) { $env:CLAUDE_MEMORY_DIR } else { Join-Path $env:USERPROFILE ".claude-memory" }

$HookPython = [System.IO.Path]::Combine($InstallDir, ".venv", "Scripts", "python.exe")
if (-not (Test-Path $HookPython)) {
    $HookPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $HookPython) {
        $HookPython = (Get-Command python3 -ErrorAction SilentlyContinue).Source
    }
}
if (-not $HookPython) { exit 0 }

$SrcDir = [System.IO.Path]::Combine($InstallDir, "src")

# Cache stdin so the background process can read it after this shell exits.
$TmpInput = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "cmm-pthook-$(New-Guid).json")
$stdin = [Console]::In.ReadToEnd()
[System.IO.File]::WriteAllText($TmpInput, $stdin)

$PyScript = @'
import json, os, sys
from pathlib import Path

src_dir = sys.argv[1]
memory_dir = sys.argv[2]
tmp = sys.argv[3]

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

os.environ.setdefault("CLAUDE_MEMORY_DIR", memory_dir)

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

tool_name = data.get("tool_name") or ""
if not tool_name:
    sys.exit(0)

tool_response = data.get("tool_response") or {}
if isinstance(tool_response, str):
    combined = tool_response
else:
    parts = []
    for key in ("stdout", "stderr", "output", "content"):
        val = tool_response.get(key) if isinstance(tool_response, dict) else None
        if val:
            parts.append(val if isinstance(val, str) else json.dumps(val))
    combined = "\n".join(parts)

combined = (combined or "").strip()
if not combined:
    sys.exit(0)

session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown"
cwd = data.get("cwd") or os.getcwd()
project = os.path.basename(cwd) or "unknown"

try:
    from auto_extract_active import capture_tool_observation
    queue_dir = Path(memory_dir) / "extract-queue"
    capture_tool_observation(
        tool_name, combined, session_id, project, queue_dir=queue_dir,
    )
except Exception:
    pass
'@

$arguments = @("-c", $PyScript, $SrcDir, $MemoryDir, $TmpInput)
try {
    Start-Process -FilePath $HookPython `
        -ArgumentList $arguments `
        -WindowStyle Hidden `
        -ErrorAction SilentlyContinue | Out-Null
} catch {
    # Never fail the user session.
}

exit 0
