#!/usr/bin/env bash
# ===========================================
# Auto Capture Hook — Portable version
#
# PostToolUse:Write|Edit — suggests memory_observe after file changes
#
# Hook: PostToolUse (matcher: "Write|Edit")
# ===========================================

source "$(dirname "$0")/lib/common.sh"

TOOL_NAME=$(hook_get 'tool_name')
FILE_PATH=$(hook_get 'tool_input.file_path')

if [ -z "$TOOL_NAME" ] || [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Skip config/doc files — usually not worth observing
case "$FILE_PATH" in
    *.md|*.txt|*.log|*.json|*.yaml|*.yml|*.toml|*.lock|*.sum)
        exit 0
        ;;
esac

FILENAME=$(basename "$FILE_PATH")
echo "MEMORY_HINT: File changed: ${FILENAME}. Consider: memory_observe(tool_name=\"${TOOL_NAME}\", summary=\"Modified ${FILENAME}\", files_affected=[\"${FILE_PATH}\"])"
