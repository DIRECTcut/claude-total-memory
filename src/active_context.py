"""
Active Context — live-doc projection of session_continuity.

Maintains a human-readable markdown file (`activeContext.md`) per project
inside the Obsidian vault. The file is a symlink-style projection of the
latest session summary/next_steps/pitfalls — a dumb Read can pick it up
without going through MCP.

Round-trips with `read_active_context` so integration code can detect
staleness between the DB row and the markdown file.

Env:
    MEMORY_ACTIVECONTEXT_VAULT    — vault root (default ~/Documents/project/Projects)
    MEMORY_ACTIVECONTEXT_DISABLE  — "1"/"true"/"yes" disables markdown writes
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_VAULT = Path.home() / "Documents" / "project" / "Projects"

_UPDATED_RE = re.compile(r"^\*\*Updated:\*\*\s*(.+?)\s*$")
_SESSION_RE = re.compile(r"^\*\*Session:\*\*\s*(.+?)\s*$")
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^-\s+(.*?)\s*$")


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 with trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_vault_root(vault_root: Path | None) -> Path:
    """Pick vault root: explicit arg > env var > default."""
    if vault_root is not None:
        return Path(vault_root).expanduser()
    raw = os.environ.get("MEMORY_ACTIVECONTEXT_VAULT")
    if raw:
        return Path(raw).expanduser()
    return DEFAULT_VAULT


def active_context_path(project: str, vault_root: Path | None = None) -> Path:
    """Absolute path to the activeContext.md for the given project."""
    if not project:
        raise ValueError("project required")
    root = _resolve_vault_root(vault_root)
    return root / project / "activeContext.md"


def _render_section(title: str, items: list[str]) -> str:
    """Render a markdown section with bullet items (empty list → '- _(none)_')."""
    clean = [s for s in (items or []) if s is not None and str(s).strip()]
    if not clean:
        return f"## {title}\n- _(none)_\n"
    lines = [f"## {title}"]
    for it in clean:
        lines.append(f"- {it}")
    return "\n".join(lines) + "\n"


def write_active_context(
    project: str,
    summary: str,
    next_steps: list[str],
    pitfalls: list[str],
    *,
    vault_root: Path | None = None,
    session_id: str | None = None,
) -> Path:
    """Write markdown live-doc. Overwrites existing file.

    Creates parent directories. Returns the path written.
    """
    if not project:
        raise ValueError("project required")
    if summary is None:
        summary = ""

    path = active_context_path(project, vault_root=vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    updated = _now_iso()
    sess = session_id or "n/a"

    # Normalize summary: keep multiline intact, strip trailing whitespace
    summary_body = (summary or "").rstrip()
    if not summary_body:
        summary_body = "_(none)_"

    parts = [
        f"# {project} — Active Context\n",
        f"\n**Updated:** {updated}\n",
        f"**Session:** {sess}\n",
        "\n## Summary\n",
        f"{summary_body}\n",
        "\n",
        _render_section("Next Steps", next_steps or []),
        "\n",
        _render_section("Pitfalls", pitfalls or []),
    ]
    path.write_text("".join(parts), encoding="utf-8")
    return path


def _parse_bullets(lines: list[str]) -> list[str]:
    """Extract bullet content. Filter the '(none)' placeholder."""
    out: list[str] = []
    for ln in lines:
        m = _BULLET_RE.match(ln)
        if not m:
            continue
        val = m.group(1).strip()
        if not val:
            continue
        # Drop placeholder from empty section
        if val in ("_(none)_", "*(none)*", "(none)"):
            continue
        out.append(val)
    return out


def read_active_context(
    project: str,
    vault_root: Path | None = None,
) -> dict[str, Any] | None:
    """Parse markdown back into a dict.

    Returns ``None`` when the file does not exist. Returns a dict with at
    least the keys ``summary`` / ``next_steps`` / ``pitfalls`` / ``updated_at``
    even when the file is partly malformed (best-effort).
    """
    path = active_context_path(project, vault_root=vault_root)
    if not path.exists():
        return None

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    if not text.strip():
        return None

    lines = text.splitlines()

    updated_at: str | None = None
    session_id: str | None = None
    sections: dict[str, list[str]] = {}

    current: str | None = None
    buf: list[str] = []

    def _flush() -> None:
        if current is not None:
            sections[current] = buf.copy()

    for raw in lines:
        m_upd = _UPDATED_RE.match(raw)
        if m_upd and updated_at is None:
            updated_at = m_upd.group(1).strip()
            continue
        m_sess = _SESSION_RE.match(raw)
        if m_sess and session_id is None:
            session_id = m_sess.group(1).strip()
            continue
        m_sec = _SECTION_RE.match(raw)
        if m_sec:
            _flush()
            current = m_sec.group(1).strip().lower()
            buf = []
            continue
        if current is not None:
            buf.append(raw)
    _flush()

    # Summary is free text; trim surrounding blank lines
    summary_lines = sections.get("summary", [])
    while summary_lines and not summary_lines[0].strip():
        summary_lines.pop(0)
    while summary_lines and not summary_lines[-1].strip():
        summary_lines.pop()
    summary_text = "\n".join(summary_lines).strip()
    if summary_text in ("_(none)_", "*(none)*"):
        summary_text = ""

    next_steps = _parse_bullets(sections.get("next steps", []))
    pitfalls = _parse_bullets(sections.get("pitfalls", []))

    if session_id in (None, "", "n/a"):
        session_id = None

    return {
        "summary": summary_text,
        "next_steps": next_steps,
        "pitfalls": pitfalls,
        "updated_at": updated_at,
        "session_id": session_id,
    }
