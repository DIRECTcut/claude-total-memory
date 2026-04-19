# ===========================================
# PreToolUse Hook (PowerShell) — v7.0/v8.0 file_context guard
#
# Port of ~/.claude/hooks/pre-edit.sh for Windows.
# Emits a reminder to call file_context(path) BEFORE editing a file.
# The agent then calls the tool itself and reads warnings/risk_score.
#
# Hook: PreToolUse (matcher: "Write|Edit")
# ===========================================

$ErrorActionPreference = "SilentlyContinue"

# Parse stdin JSON (Claude Code hook payload).
$stdinRaw = [Console]::In.ReadToEnd()
if (-not $stdinRaw) { exit 0 }

try {
    $data = $stdinRaw | ConvertFrom-Json
} catch {
    exit 0
}

$tool = $data.tool_name
$filePath = $null
if ($data.tool_input) {
    $filePath = $data.tool_input.file_path
}

# Only guard Write/Edit, not NotebookEdit
if ($tool -ne "Write" -and $tool -ne "Edit") { exit 0 }
if (-not $filePath) { exit 0 }

# Skip trivial / dotfile / vendored / temp paths (Windows + POSIX separators).
$normalized = $filePath.Replace("\", "/")
$skipPatterns = @("/.git/", "/node_modules/", "/.venv/", "/tmp/", "/Temp/")
foreach ($pat in $skipPatterns) {
    if ($normalized -like "*$pat*") { exit 0 }
}

# Emit the system-reminder on stdout (Claude Code reads it).
$reminder = @"
<system-reminder>
v7.0 pre-edit guard: before editing ``$filePath``, call
  file_context(path="$filePath")
If risk_score > 0.3, read the returned warnings (past errors / hot spots) and
incorporate them into the edit. Skip if file_context was already called for this
path in the current turn.
</system-reminder>
"@

Write-Output $reminder
exit 0
