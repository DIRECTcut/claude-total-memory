"""Tests for src/active_context.py — live-doc markdown projection."""

from __future__ import annotations

from pathlib import Path

import pytest

from active_context import (
    active_context_path,
    read_active_context,
    write_active_context,
)


# ──────────────────────────────────────────────
# Path resolution
# ──────────────────────────────────────────────


def test_active_context_path_uses_vault_root(tmp_path: Path) -> None:
    p = active_context_path("myproj", vault_root=tmp_path)
    assert p == tmp_path / "myproj" / "activeContext.md"


def test_active_context_path_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_ACTIVECONTEXT_VAULT", str(tmp_path))
    p = active_context_path("other")
    assert p == tmp_path / "other" / "activeContext.md"


def test_active_context_path_requires_project() -> None:
    with pytest.raises(ValueError):
        active_context_path("", vault_root=Path("/tmp"))


# ──────────────────────────────────────────────
# write_active_context
# ──────────────────────────────────────────────


def test_write_active_context_creates_parent_dirs(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    # Parent directory does not exist yet
    assert not vault.exists()
    path = write_active_context(
        "proj",
        "hello",
        ["step 1"],
        ["watch out"],
        vault_root=vault,
        session_id="sess_abc",
    )
    assert path.exists()
    assert path == vault / "proj" / "activeContext.md"
    assert path.parent.is_dir()


def test_write_active_context_overwrites_existing(tmp_path: Path) -> None:
    write_active_context("p", "first", [], [], vault_root=tmp_path)
    path = write_active_context("p", "second", [], [], vault_root=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "second" in text
    assert "first" not in text


def test_write_active_context_contains_header_fields(tmp_path: Path) -> None:
    path = write_active_context(
        "proj",
        "summary text",
        ["s1"],
        ["p1"],
        vault_root=tmp_path,
        session_id="sess_42",
    )
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# proj — Active Context")
    assert "**Updated:**" in text
    assert "**Session:** sess_42" in text
    assert "## Summary" in text
    assert "## Next Steps" in text
    assert "## Pitfalls" in text
    assert "- s1" in text
    assert "- p1" in text


def test_write_active_context_handles_no_session_id(tmp_path: Path) -> None:
    path = write_active_context("p", "sum", [], [], vault_root=tmp_path)
    assert "**Session:** n/a" in path.read_text(encoding="utf-8")


# ──────────────────────────────────────────────
# read_active_context
# ──────────────────────────────────────────────


def test_read_missing_file_returns_none(tmp_path: Path) -> None:
    assert read_active_context("nope", vault_root=tmp_path) is None


def test_write_read_roundtrip(tmp_path: Path) -> None:
    write_active_context(
        "proj",
        "Working on feature X",
        ["Run tests", "Ship PR"],
        ["Don't forget migration"],
        vault_root=tmp_path,
        session_id="s123",
    )
    doc = read_active_context("proj", vault_root=tmp_path)
    assert doc is not None
    assert doc["summary"] == "Working on feature X"
    assert doc["next_steps"] == ["Run tests", "Ship PR"]
    assert doc["pitfalls"] == ["Don't forget migration"]
    assert doc["session_id"] == "s123"
    assert doc["updated_at"] is not None


def test_roundtrip_empty_lists(tmp_path: Path) -> None:
    write_active_context("p", "sum", [], [], vault_root=tmp_path)
    doc = read_active_context("p", vault_root=tmp_path)
    assert doc is not None
    assert doc["next_steps"] == []
    assert doc["pitfalls"] == []
    assert doc["summary"] == "sum"


def test_read_malformed_markdown_returns_partial(tmp_path: Path) -> None:
    path = tmp_path / "badproj" / "activeContext.md"
    path.parent.mkdir(parents=True)
    # Missing standard headers, random content
    path.write_text("random garbage\nno headers at all\n", encoding="utf-8")
    doc = read_active_context("badproj", vault_root=tmp_path)
    assert doc is not None  # best-effort parse, not None
    assert doc["summary"] == ""
    assert doc["next_steps"] == []
    assert doc["pitfalls"] == []
    assert doc["updated_at"] is None


def test_read_empty_file_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "p" / "activeContext.md"
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    assert read_active_context("p", vault_root=tmp_path) is None


def test_multiline_summary_survives_roundtrip(tmp_path: Path) -> None:
    multiline = "Line one.\nLine two with detail.\nLine three."
    write_active_context("proj", multiline, ["step"], [], vault_root=tmp_path)
    doc = read_active_context("proj", vault_root=tmp_path)
    assert doc is not None
    assert doc["summary"] == multiline
    assert doc["next_steps"] == ["step"]


def test_bullet_with_dash_in_content_survives(tmp_path: Path) -> None:
    write_active_context(
        "p",
        "sum",
        ["fix bug - race condition in queue"],
        [],
        vault_root=tmp_path,
    )
    doc = read_active_context("p", vault_root=tmp_path)
    assert doc is not None
    assert doc["next_steps"] == ["fix bug - race condition in queue"]


def test_none_placeholder_is_filtered(tmp_path: Path) -> None:
    # Empty sections are written with "_(none)_" placeholder; reader must drop.
    write_active_context("p", "sum", [], [], vault_root=tmp_path)
    raw = (tmp_path / "p" / "activeContext.md").read_text(encoding="utf-8")
    assert "_(none)_" in raw
    doc = read_active_context("p", vault_root=tmp_path)
    assert doc is not None
    assert doc["next_steps"] == []
    assert doc["pitfalls"] == []
