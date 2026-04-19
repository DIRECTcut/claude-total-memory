# systemd units (Linux)

Linux equivalent of the macOS LaunchAgents in `../launchagents/`.

`install.sh` auto-installs these when running on Linux — it substitutes
`@INSTALL_DIR@`, `@MEMORY_DIR@`, and `@HOME@`, copies the files to
`${XDG_CONFIG_HOME:-~/.config}/systemd/user/`, and enables them via
`systemctl --user`.

## Units

- **`claude-memory-reflection.path`** — watches `~/.claude-memory/.reflect-pending`
  and fires the service whenever `memory_save` touches the trigger file.
- **`claude-memory-reflection.service`** — `Type=oneshot`, runs
  `src/tools/run_reflection.py`, drains `triple_extraction_queue`,
  `deep_enrichment_queue`, and `representations_queue` through Ollama.
- **`claude-memory-dashboard.service`** — `Type=simple`, keeps the web
  dashboard (`src/dashboard.py`) running on `http://localhost:37737`,
  auto-restarts on failure.
- **`claude-memory-orphan-backfill.service`** + **`.timer`** — periodically
  runs `src/tools/backfill_orphan_edges.py` to consolidate KG edges.
  Timer: `*-*-* 00,06,12,18:00:00` (4× per day, matching the macOS plist).
- **`claude-memory-check-updates.service`** + **`.timer`** — weekly update
  probe via `src/tools/check_updates.py`. Timer: `Mon *-*-* 09:00:00`.

## Manual management

```bash
# Reflection
systemctl --user status claude-memory-reflection.path
systemctl --user status claude-memory-reflection.service
journalctl --user -u claude-memory-reflection.service -f

# Dashboard
systemctl --user status claude-memory-dashboard.service
journalctl --user -u claude-memory-dashboard.service -f

# Timers
systemctl --user list-timers 'claude-memory-*'
systemctl --user start claude-memory-orphan-backfill.service   # one-off run

# Disable all auto-drain / dashboard / timers
systemctl --user disable --now \
    claude-memory-reflection.path \
    claude-memory-dashboard.service \
    claude-memory-orphan-backfill.timer \
    claude-memory-check-updates.timer
```

## Manual install (fallback if `install.sh` couldn't enable)

```bash
INSTALL_DIR="$HOME/claude-memory-server"
MEMORY_DIR="$HOME/.claude-memory"
TARGET="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$TARGET" "$MEMORY_DIR/logs"

for u in \
    claude-memory-reflection.service \
    claude-memory-reflection.path \
    claude-memory-dashboard.service \
    claude-memory-orphan-backfill.service \
    claude-memory-orphan-backfill.timer \
    claude-memory-check-updates.service \
    claude-memory-check-updates.timer
do
    sed -e "s|@INSTALL_DIR@|$INSTALL_DIR|g" \
        -e "s|@MEMORY_DIR@|$MEMORY_DIR|g" \
        -e "s|@HOME@|$HOME|g" \
        "$INSTALL_DIR/systemd/$u" > "$TARGET/$u"
done

systemctl --user daemon-reload
systemctl --user enable --now \
    claude-memory-reflection.path \
    claude-memory-dashboard.service \
    claude-memory-orphan-backfill.timer \
    claude-memory-check-updates.timer
```

## WSL2 caveat

On WSL2, `systemctl --user` only works when systemd is explicitly enabled:

```ini
# /etc/wsl.conf
[boot]
systemd=true
```

Then restart WSL from Windows: `wsl.exe --shutdown`, reopen the shell,
check `systemctl --user show-environment` (exit code 0 = ready).

If systemd is **not** enabled, `install.sh` still copies the unit files to
`~/.config/systemd/user/` but skips activation with a warning. You can
either enable systemd (recommended) or run the reflection drain manually:

```bash
"$HOME/claude-memory-server/.venv/bin/python" \
    "$HOME/claude-memory-server/src/tools/run_reflection.py"
```

## Uninstall

```bash
bash ~/claude-memory-server/install.sh --uninstall
```

or manually:

```bash
systemctl --user disable --now \
    claude-memory-reflection.path \
    claude-memory-dashboard.service \
    claude-memory-orphan-backfill.timer \
    claude-memory-check-updates.timer
rm -f ~/.config/systemd/user/claude-memory-*.service \
      ~/.config/systemd/user/claude-memory-*.path \
      ~/.config/systemd/user/claude-memory-*.timer
systemctl --user daemon-reload
```
