# Hooks reference

Hooks fire automatically on agent-runtime events and call MCP tools
without you having to remember to. They are **optional** — the
protocol works without them, but with them everything happens at the
right moment by default.

Each hook ships in two forms:

- `hooks/<name>.sh` — bash, for macOS / Linux / WSL2 / cygwin
- `hooks/<name>.ps1` — PowerShell 5.1+ / 7+ for native Windows

The same hook is wired up differently per IDE (see `ide-setup.md`).

---

## How a hook works

All hooks read **stdin** (JSON event payload from the IDE), do their
work, and either exit 0 (continue) or print a message + exit non-zero
(block / warn). They never read or write user files directly — they
shell out to the MCP server (or to `lookup_memory.sh`).

Common environment:

| Variable | Purpose |
|---|---|
| `CLAUDE_MEMORY_DIR` | DB location, default `~/.claude-memory` |
| `MEMORY_PROJECT` | Override auto-detected project name |
| `MEMORY_HOOK_TIMEOUT_SEC` | Max time a hook may run (default 5) |
| `MEMORY_HOOK_DEBUG` | If `1`, hook logs to `~/.claude-memory/hooks.log` |

If a hook hits the timeout it is killed — never blocks the IDE
indefinitely.

---

## 1. `session-start.{sh,ps1}`

**Fires:** every time a new agent session starts (Claude Code: on
`claude` launch; Codex: on `codex`; Cursor / Cline: on first prompt
of the session).

**Reads:** event JSON containing `cwd`, sometimes `git_branch`.

**Does:**
1. Calls `session_init(project=<basename of cwd>)` via MCP.
2. If a recovery file exists in `~/.claude/recovery/pending-*.md`
   (left by `on-stop`), prints its content as `additionalContext` so
   the agent sees it on the first turn.
3. Generates the A2A self-label (`<basename>-<4hex>`) at
   `/tmp/a2a-label-<PID>` if A2A protocol is in use.
4. Reindexes self-improvement rules to the graph.

**Skip if:** you don't want auto-resume; e.g. throwaway shell.

**IDE wiring:** see `ide-setup.md` per platform.

---

## 2. `pre-edit.{sh,ps1}`

**Fires:** **before** the agent calls `Edit` / `Write` (Claude Code
hook event `PreToolUse`).

**Reads:** event JSON with `tool_name` and `tool_input.file_path`.

**Does:**
1. Calls `file_context(path=<file_path>)` via MCP.
2. If `risk_score > 0.5`, prints the warnings as `additionalContext`
   so the agent sees "this file has 3 prior bugs in this region" on
   the same turn.
3. Exits 0 — never blocks. The agent decides.

**Skip if:** you want zero pre-edit overhead. Without this hook you
still get the data when the agent calls `file_context()` manually.

**Cost:** ~80 ms when warm; one DB query.

---

## 3. `post-tool-use.{sh,ps1}`

**Fires:** after every successful tool call (Claude Code hook event
`PostToolUse`).

**Reads:** `tool_name`, `tool_input`, `tool_output`.

**Does:** opt-in only. With `MEMORY_POST_TOOL_CAPTURE=1`:
1. Calls `memory_observe(tool_name, summary, files_affected, project)`
   so the reflection cycle has raw observations to pattern-match
   against.

**Skip:** by default. Enable only if you're studying tool-use patterns
or the reflection agent's quality is degrading.

**Cost:** ~30 ms / call. Cumulative — at 100 tool calls per session,
it adds up.

---

## 4. `user-prompt-submit.{sh,ps1}`

**Fires:** every time the user sends a prompt (Claude Code hook event
`UserPromptSubmit`).

**Reads:** `prompt`, `cwd`, `session_id`.

**Does:**
1. Calls `save_intent(prompt, project=<basename>)` via MCP.
2. Returns the inbox snapshot for A2A (if A2A peers exist) so the
   agent sees pending peer messages on the same turn.
3. Exits 0.

**Skip if:** you don't care about prompt history. Keep if you ever
want `list_intents()` / `search_intents()` to be useful.

**Cost:** ~50 ms.

---

## 5. `on-stop.{sh,ps1}`

**Fires:** when the agent session ends abnormally — context limit
reached, Ctrl-C, IDE close (Claude Code hook event `Stop`).

**Reads:** `session_id`, `cwd`, `reason`.

**Does:**
1. Snapshots git state (`status`, recent commits) — not committed,
   just recorded.
2. Writes `~/.claude/recovery/pending-<timestamp>.md` with everything
   needed to resume.
3. Keeps the last 5 recovery files; older ones auto-purged.

**Skip if:** you want a clean shutdown without recovery files.

**Cost:** runs in background, doesn't block shutdown.

---

## 6. `auto-capture.{sh,ps1}`

**Fires:** periodic (every N tool calls or on context-pressure
warning).

**Reads:** session id, current context fill %.

**Does:** writes a checkpoint to `extract-queue/` for later
reflection processing. Different from `on-stop` — this is
*proactive* checkpointing during a healthy session.

**Skip:** unless you run very long sessions (3+ hours).

---

## 7. `on-bash-error.ps1` (Codex / Windows)

**Fires:** Codex `BashErrorHook` — bash exited non-zero, error worth
recording.

**Reads:** command, exit code, stderr.

**Does:** calls `learn_error(file, error, root_cause, fix, pattern)`
with placeholder `root_cause`/`fix` if not provided — agent fills
them in later via `memory_update`.

**Skip:** never (cheap and high-signal).

---

## 8. `memory-trigger.{sh,ps1}`

**Fires:** custom trigger — usually invoked via slash-command or
keyboard shortcut, not by IDE event.

**Does:** runs `memory_recall` with a user-provided query, prints
result. Convenience for "give me the recipe for X" without leaving
the editor.

---

## 9. `codex-notify.{sh,ps1}`

**Fires:** Codex notification hook — used to surface MCP events
(superseded knowledge, quality-gate drops, contradiction supersede)
to the user via desktop notification.

**Skip:** if you don't want desktop popups.

---

## 10. `session-end.{sh,ps1}`

**Fires:** clean session end (user typed `/quit`, IDE closed
normally).

**Does:** calls `session_end(session_id, summary, next_steps)` with
LLM-generated summary if `auto_compress=true` was set; otherwise
expects the agent to have called `session_end` already and is a
no-op.

---

## Hook compatibility matrix

| Hook | Claude Code | Codex CLI | Cursor | Cline | Continue | Aider | Windsurf | Gemini CLI | OpenCode |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `session-start` | ✅ | ✅ | ⚠️ ¹ | ⚠️ ¹ | ⚠️ ¹ | ❌ | ⚠️ ¹ | ⚠️ ¹ | ✅ |
| `pre-edit` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ ² |
| `post-tool-use` | ✅ | ⚠️ ³ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `user-prompt-submit` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ ² |
| `on-stop` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `on-bash-error` | ❌ ⁴ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `auto-capture` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

¹ No native hook API — `session_init` runs at first user message
through skill activation instead. The agent calls it, not the IDE.

² OpenCode supports custom commands; the hook is wired as a manual
command rather than an event.

³ Codex `PostToolUse` is rate-limited — keep `MEMORY_POST_TOOL_CAPTURE=0`
or use sampling.

⁴ Claude Code surfaces bash errors via tool result — use the
agent-side `learn_error` call instead of an IDE hook.

---

## Where to install hooks per IDE

| IDE | Hooks live in |
|---|---|
| Claude Code | `~/.claude/settings.json` → `"hooks"` map |
| Codex CLI | `~/.codex/config.toml` → `[hooks]` section |
| Cursor | not supported — use skill triggers |
| Cline | not supported — manual recall in user prompts |
| Continue | not supported |
| Aider | not supported |
| Windsurf | not supported (planned) |
| Gemini CLI | not supported |
| OpenCode | `.opencode/hooks/<event>.json` (custom event API) |

The installer (`install.sh --ide <name>`) writes the right config in
each case. Manual setup blueprints are in `templates/`.

---

## Debugging hooks

```bash
# Watch every hook fire in real time:
tail -f ~/.claude-memory/hooks.log

# Run a hook manually with a fake event:
echo '{"cwd":"/tmp/x","tool_name":"Edit","tool_input":{"file_path":"/tmp/x/a.py"}}' \
  | MEMORY_HOOK_DEBUG=1 ~/.claude/hooks/pre-edit.sh

# Disable a single hook without uninstalling:
chmod -x ~/.claude/hooks/<name>.sh   # makes it skipped
```

If `~/.claude-memory/hooks.log` is silent and you expected fires:
the IDE's hook config is not picking the file up. Re-run
`install.sh --ide <name>` (idempotent) and restart the IDE.
