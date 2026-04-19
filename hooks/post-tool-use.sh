#!/usr/bin/env bash
# ===========================================
# PostToolUse Hook — opt-in capture of tool observations
#
# Runs AFTER a tool call. When MEMORY_POST_TOOL_CAPTURE=1 is set, enqueues
# a deferred observation for the extractor to pick up. Non-blocking (async
# Python in background). Never fails the user's task.
#
# Env:
#   MEMORY_POST_TOOL_CAPTURE  — "1" to enable, anything else → no-op
#   CLAUDE_MEMORY_INSTALL_DIR — install root (auto-resolved)
#   CLAUDE_MEMORY_DIR         — memory storage (~/.claude-memory)
#
# Hook: PostToolUse (matcher: "*")
# ===========================================

# Opt-in guard — absence of the flag is a no-op.
if [ "${MEMORY_POST_TOOL_CAPTURE:-0}" != "1" ]; then
    exit 0
fi

CLAUDE_MEMORY_INSTALL_DIR="${CLAUDE_MEMORY_INSTALL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)}"
CLAUDE_MEMORY_DIR="${CLAUDE_MEMORY_DIR:-$HOME/.claude-memory}"

HOOK_PYTHON="${CLAUDE_MEMORY_INSTALL_DIR}/.venv/bin/python"
if [ ! -x "$HOOK_PYTHON" ]; then
    HOOK_PYTHON="python3"
fi

SRC_DIR="${CLAUDE_MEMORY_INSTALL_DIR}/src"

# Cache stdin so the background process can read it after this shell exits.
TMP_INPUT="$(mktemp -t cmm-pthook.XXXXXX)"
cat > "$TMP_INPUT"

(
    "$HOOK_PYTHON" -c '
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

# tool_response shape varies across tools; merge stdout+stderr+content.
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
' "$SRC_DIR" "$CLAUDE_MEMORY_DIR" "$TMP_INPUT" >/dev/null 2>&1
) &

disown 2>/dev/null || true
exit 0
