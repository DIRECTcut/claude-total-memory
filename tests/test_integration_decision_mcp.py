"""Integration tests: MCP wiring for `save_decision` + decisions_only recall."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


# Ensure src/ is importable.
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def srv(monkeypatch, tmp_path):
    """Real MCP server with temp storage; LLM disabled so tests stay offline."""
    monkeypatch.setenv("MEMORY_LLM_ENABLED", "false")

    (tmp_path / "blobs").mkdir(exist_ok=True)
    (tmp_path / "chroma").mkdir(exist_ok=True)

    import server, config
    config._cache_clear()
    monkeypatch.setattr(server, "MEMORY_DIR", tmp_path)

    s = server.Store()
    server.store = s
    server.recall = server.Recall(s)
    server.SID = "sess-decision-mcp"
    s.db.execute(
        "INSERT OR IGNORE INTO sessions (id, started_at, project, status) "
        "VALUES (?, ?, ?, ?)",
        (server.SID, "2026-04-19T00:00:00Z", "demo", "open"),
    )
    s.db.commit()

    yield server
    try:
        s.db.close()
    except Exception:
        pass


def _call(server_mod, name, args):
    raw = asyncio.run(server_mod._do(name, args))
    return json.loads(raw)


def _sample_args(**overrides):
    base = {
        "title": "Pick web framework",
        "options": [
            {
                "name": "FastAPI",
                "pros": ["async", "pydantic"],
                "cons": ["fewer batteries"],
                "unknowns": ["HTTP2"],
            },
            {
                "name": "Django",
                "pros": ["admin", "ORM"],
                "cons": ["sync"],
            },
        ],
        "criteria_matrix": {
            "performance": {"FastAPI": 5, "Django": 3},
            "ecosystem": {"FastAPI": 3, "Django": 5},
            "type-safety": {"FastAPI": 5, "Django": 3},
        },
        "selected": "FastAPI",
        "rationale": "Async I/O and type-safety outweigh ecosystem gap.",
        "discarded": ["Django"],
        "project": "demo",
        "tags": ["web", "python"],
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────
# Tool discovery
# ─────────────────────────────────────────────────────────────


def test_save_decision_tool_registered(srv):
    tools = asyncio.run(srv.list_tools())
    names = {t.name for t in tools}
    assert "save_decision" in names


# ─────────────────────────────────────────────────────────────
# Roundtrip
# ─────────────────────────────────────────────────────────────


def test_mcp_save_decision_roundtrip(srv):
    result = _call(srv, "save_decision", _sample_args())
    assert result["saved"] is True
    assert result["structured"] is True
    assert isinstance(result["id"], int)

    rid = result["id"]
    row = srv.store.db.execute(
        "SELECT type, content, context, tags, project FROM knowledge WHERE id=?",
        (rid,),
    ).fetchone()
    assert row["type"] == "decision"
    assert row["project"] == "demo"
    assert "SELECTED: FastAPI" in row["content"]

    payload = json.loads(row["context"])
    assert payload["schema"] == "decision/v1"
    assert payload["selected"] == "FastAPI"
    assert payload["criteria_matrix"]["performance"]["FastAPI"] == 5.0

    tags = json.loads(row["tags"])
    assert "structured" in tags
    assert "web" in tags


# ─────────────────────────────────────────────────────────────
# Validation — bad args return a structured error, no insert.
# ─────────────────────────────────────────────────────────────


def test_mcp_save_decision_validates_args(srv):
    bad = _sample_args(selected="Flask")  # not in options
    out = _call(srv, "save_decision", bad)
    assert out["saved"] is False
    assert "invalid decision" in out["error"].lower()

    # Nothing landed in knowledge.
    count = srv.store.db.execute(
        "SELECT COUNT(*) FROM knowledge WHERE type='decision'"
    ).fetchone()[0]
    assert count == 0


def test_mcp_save_decision_rejects_rating_out_of_range(srv):
    bad = _sample_args(criteria_matrix={"perf": {"FastAPI": 9, "Django": 1}})
    out = _call(srv, "save_decision", bad)
    assert out["saved"] is False
    assert "0..5" in out["error"] or "outside" in out["error"]


def test_mcp_save_decision_missing_required_arg(srv):
    bad = _sample_args()
    bad.pop("rationale")
    out = _call(srv, "save_decision", bad)
    assert out["saved"] is False


# ─────────────────────────────────────────────────────────────
# memory_recall decisions_only
# ─────────────────────────────────────────────────────────────


def test_recall_decisions_only_filter_returns_structured(srv):
    # Insert one structured decision …
    saved = _call(srv, "save_decision", _sample_args())
    assert saved["saved"] is True

    # … and one legacy free-form decision (memory_save type=decision).
    legacy = _call(srv, "memory_save", {
        "type": "decision",
        "content": "DECISION: Pick web framework — legacy note without schema",
        "project": "demo",
        "tags": ["web"],
        "context": "WHY: just a note",
    })
    assert legacy["saved"] is True

    # Recall WITHOUT decisions_only — both are eligible (content has shared terms).
    unfiltered = _call(srv, "memory_recall", {
        "query": "web framework",
        "project": "demo",
        "type": "decision",
    })
    unfiltered_ids = {
        item["id"]
        for group in unfiltered.get("results", {}).values()
        for item in group
        if isinstance(item.get("id"), int)
    }
    assert saved["id"] in unfiltered_ids
    assert legacy["id"] in unfiltered_ids

    # Recall WITH decisions_only — legacy row is filtered out, structured one
    # survives and carries the parsed `decision` payload.
    filtered = _call(srv, "memory_recall", {
        "query": "web framework",
        "project": "demo",
        "type": "decision",
        "decisions_only": True,
    })
    assert filtered.get("decisions_only") is True

    surviving = [
        item
        for group in filtered.get("results", {}).values()
        for item in group
    ]
    surviving_ids = {item["id"] for item in surviving}
    assert saved["id"] in surviving_ids
    assert legacy["id"] not in surviving_ids

    for item in surviving:
        assert "decision" in item, f"structured item missing parsed payload: {item}"
        assert item["decision"]["schema"] == "decision/v1"
        assert item["decision"]["selected"] == "FastAPI"
