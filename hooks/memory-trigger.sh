#!/usr/bin/env bash
# ===========================================
# Memory Trigger Hook — Portable version
#
# PostToolUse:Bash — detects errors, fix pairs, significant commands
#
# 1. Auto-detects bash ERRORS -> logs via auto_self_improve.py
# 2. Tracks error->fix pairs -> prompts to save solutions
# 3. Detects significant commands -> reminds memory_save
# 4. Detects test/build/lint success -> rates SOUL rules
# 5. Detects task completion patterns -> prompts reusable save
#
# Hook: PostToolUse (matcher: "Bash")
# ===========================================

source "$(dirname "$0")/lib/common.sh"

COMMAND=$(hook_get 'tool_input.command')
EXIT_CODE=$(hook_get 'tool_output.exit_code')
[ -z "$EXIT_CODE" ] && EXIT_CODE=$(hook_get 'tool_output.exitCode')
[ -z "$EXIT_CODE" ] && EXIT_CODE="0"
STDERR=$(hook_get 'tool_output.stderr')
[ -z "$STDERR" ] && STDERR=$(hook_get 'tool_output.error')
PROJECT=$(hook_project_name)

# Skip if no command
[ -z "$COMMAND" ] && exit 0

# State directory for tracking error->fix pairs
mkdir -p "$HOOK_STATE_DIR"

# ===========================================
# PART 1: ERROR DETECTION -> self_error_log + track for fix
# ===========================================
if [ "$EXIT_CODE" != "0" ] && [ "$EXIT_CODE" != "" ] && [ "$EXIT_CODE" != "null" ]; then
    # Determine error category
    CATEGORY="code_error"
    SEVERITY="medium"

    if echo "$STDERR" | grep -qiE "timeout|timed out|deadline exceeded"; then
        CATEGORY="timeout"; SEVERITY="high"
    elif echo "$STDERR" | grep -qiE "connection refused|ECONNREFUSED|network|dns|resolve"; then
        CATEGORY="api_error"; SEVERITY="high"
    elif echo "$STDERR" | grep -qiE "permission denied|EACCES|forbidden|401|403"; then
        CATEGORY="config_error"; SEVERITY="medium"
    elif echo "$STDERR" | grep -qiE "not found|No such file|ENOENT|404|unknown command"; then
        CATEGORY="wrong_assumption"; SEVERITY="low"
    elif echo "$STDERR" | grep -qiE "syntax error|parse error|unexpected token|SyntaxError"; then
        CATEGORY="code_error"; SEVERITY="medium"
    elif echo "$STDERR" | grep -qiE "out of memory|OOM|memory limit|Cannot allocate"; then
        CATEGORY="config_error"; SEVERITY="critical"
    fi

    # Truncate for readability
    ERR_SHORT=$(echo "$STDERR" | head -5 | head -c 500)
    CMD_SHORT=$(echo "$COMMAND" | head -c 200)

    echo ""
    echo "SELF_LEARNING_ERROR: Bash command failed (exit=$EXIT_CODE). You MUST call self_error_log NOW:"
    echo "  self_error_log("
    echo "    description='Command failed: ${CMD_SHORT}. Error: ${ERR_SHORT}',"
    echo "    category='${CATEGORY}',"
    echo "    severity='${SEVERITY}',"
    echo "    context='project: ${PROJECT}',"
    echo "    project='${PROJECT}'"
    echo "  )"
    echo ""

    # Direct DB write via auto_self_improve.py (don't depend on Claude)
    hook_run_script "auto_self_improve.py" error \
        --description "Command failed: ${CMD_SHORT}. Error: ${ERR_SHORT}" \
        --category "${CATEGORY}" \
        --severity "${SEVERITY}" \
        --project "${PROJECT}"

    # Save error state for fix tracking
    ERROR_HASH=$(echo "${CMD_SHORT}" | md5sum 2>/dev/null | cut -c1-12 || echo "$(date +%s)")
    cat > "$HOOK_STATE_DIR/last-error-${PROJECT}" <<ERRSTATE
ERROR_CMD=${CMD_SHORT}
ERROR_MSG=${ERR_SHORT}
ERROR_CATEGORY=${CATEGORY}
ERROR_TIME=$(date +%s)
ERROR_HASH=${ERROR_HASH}
ERRSTATE

    # Check for repeated patterns (3+ same category)
    ERROR_COUNTS_DIR="${HOOK_STATE_DIR}/error-counts"
    mkdir -p "$ERROR_COUNTS_DIR"
    ERROR_KEY=$(echo "${CATEGORY}:${PROJECT}" | md5sum 2>/dev/null | cut -c1-8 || echo "nomd5")
    COUNT_FILE="${ERROR_COUNTS_DIR}/${ERROR_KEY}"

    if [ -f "$COUNT_FILE" ]; then
        COUNT=$(cat "$COUNT_FILE")
        COUNT=$((COUNT + 1))
    else
        COUNT=1
    fi
    echo "$COUNT" > "$COUNT_FILE"

    if [ "$COUNT" -ge 3 ]; then
        echo "SELF_LEARNING_PATTERN: ${COUNT}x errors in category '${CATEGORY}' for project '${PROJECT}'!"
        echo "  Consider: self_insight(action='add', content='...', category='${CATEGORY}', project='${PROJECT}')"
        echo "0" > "$COUNT_FILE"

        # Auto-check patterns via direct DB write
        hook_run_script "auto_self_improve.py" check-patterns \
            --project "${PROJECT}"
    fi

    exit 0
fi

# ===========================================
# PART 2: ERROR->FIX PAIR DETECTION
# ===========================================
LAST_ERROR_FILE="$HOOK_STATE_DIR/last-error-${PROJECT}"

if [ -f "$LAST_ERROR_FILE" ]; then
    source "$LAST_ERROR_FILE" 2>/dev/null
    NOW=$(date +%s)
    ELAPSED=$(( NOW - ${ERROR_TIME:-0} ))

    # If error was within last 10 minutes
    if [ "$ELAPSED" -lt 600 ]; then
        SIMILAR=false
        CMD_BASE=$(echo "$COMMAND" | awk '{print $1}')
        ERR_BASE=$(echo "${ERROR_CMD:-}" | awk '{print $1}')

        # Same base command succeeding = likely fixed
        [ "$CMD_BASE" = "$ERR_BASE" ] && SIMILAR=true

        # Tests/build passing after error = fix confirmed
        if echo "$COMMAND" | grep -qE "(go test|phpunit|npm test|npm run test|jest|pytest|go build|npm run build|make build|composer check)"; then
            SIMILAR=true
        fi

        if [ "$SIMILAR" = "true" ]; then
            echo ""
            echo "ERROR_FIXED: Previous error appears resolved!"
            echo "  Error was: ${ERROR_CMD}"
            echo "  Error msg: $(echo "${ERROR_MSG:-}" | head -c 200)"
            echo ""
            echo "  SAVE THE FIX to memory NOW:"
            echo "  memory_save(type='solution', content='PROBLEM: ${ERROR_MSG}\\nFIX: <describe what fixed it>\\nPROJECT: ${PROJECT}', project='${PROJECT}', tags=['reusable', 'bugfix'])"
            echo ""

            # Direct DB write -- resolve the error
            hook_run_script "auto_self_improve.py" fix \
                --description "Fixed: ${ERROR_CMD}" \
                --category "${ERROR_CATEGORY}" \
                --fix "Command succeeded after previous failure" \
                --project "${PROJECT}"

            rm -f "$LAST_ERROR_FILE"
        fi
    else
        # Error too old, clean up
        rm -f "$LAST_ERROR_FILE"
    fi
fi

# ===========================================
# PART 3: SUCCESS DETECTION -> rate SOUL rules
# ===========================================

# Tests passed
if echo "$COMMAND" | grep -qE "(go test|phpunit|npm test|npm run test|jest|pytest|vendor/bin/phpunit)"; then
    if [ "$EXIT_CODE" = "0" ] || [ -z "$EXIT_CODE" ]; then
        echo ""
        echo "SELF_LEARNING_SUCCESS: Tests passed. If SOUL rules were relevant, rate them:"
        echo "  self_rules(action='rate', id=<rule_id>, success=true)"
    fi
fi

# Build succeeded
if echo "$COMMAND" | grep -qE "(go build|npm run build|composer check|make build)"; then
    if [ "$EXIT_CODE" = "0" ] || [ -z "$EXIT_CODE" ]; then
        echo ""
        echo "SELF_LEARNING_SUCCESS: Build succeeded. Rate relevant SOUL rules if any."
    fi
fi

# ===========================================
# PART 4: SIGNIFICANT COMMANDS -> memory_save
# ===========================================

case "$COMMAND" in
    *"git commit"*)
        echo "MEMORY_TRIGGER: Git commit completed. Save commit summary:"
        echo "  memory_save(type='fact', content='Committed: <scope and changes>', project='${PROJECT}', tags=['commit'])"
        ;;
    *"docker compose up"*|*"docker-compose up"*|*"docker build"*)
        echo "MEMORY_TRIGGER: Docker operation. If setup was non-trivial, save config details."
        ;;
    *"migrate"*)
        if [[ "$COMMAND" != *"--status"* ]] && [[ "$COMMAND" != *"status"* ]]; then
            echo "MEMORY_TRIGGER: Migration executed. Save schema changes as fact."
        fi
        ;;
    *"make setup"*|*"make init"*)
        echo "MEMORY_TRIGGER: Project setup completed. Save infrastructure facts."
        ;;
    *"npm install"*|*"npm ci"*|*"yarn add"*|*"pnpm add"*)
        echo "MEMORY_TRIGGER: Package install detected. Save dependency changes."
        ;;
    *"pip install"*|*"poetry add"*|*"pipenv install"*)
        echo "MEMORY_TRIGGER: Python package install detected. Save dependency changes."
        ;;
    *"go mod"*|*"go get"*)
        echo "MEMORY_TRIGGER: Go module change detected. Save dependency changes."
        ;;
    *"composer require"*|*"composer install"*)
        echo "MEMORY_TRIGGER: Composer operation detected. Save dependency changes."
        ;;
esac

# ===========================================
# PART 5: TASK COMPLETION HEURISTICS
# ===========================================

# Full test suite passing
if echo "$COMMAND" | grep -qE "^(go test|phpunit|npm test).*(\.\.\.|--all|-A)"; then
    if [ "$EXIT_CODE" = "0" ] || [ -z "$EXIT_CODE" ]; then
        echo ""
        echo "MEMORY_TRIGGER: Full test suite passed. If you completed a significant feature, save it:"
        echo "  memory_save(type='solution', content='WHAT: ..., PROJECT: ${PROJECT}, FILES: ..., APPROACH: ...', project='${PROJECT}', tags=['reusable'])"
    fi
fi

# Linter passed
if echo "$COMMAND" | grep -qE "(golangci-lint|phpstan|eslint|npm run lint)"; then
    if [ "$EXIT_CODE" = "0" ] || [ -z "$EXIT_CODE" ]; then
        echo ""
        echo "SELF_LEARNING_SUCCESS: Linter passed. If conventions were established, save:"
        echo "  memory_save(type='convention', content='<convention>', project='${PROJECT}', tags=['convention'])"
    fi
fi

exit 0
