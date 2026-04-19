"""End-to-end integration smoke test for v7.1 + v8.0 features.

Exercises the real user journey in a single flow:
  privacy redaction → classify_task → task_create → phase_transition →
  save_decision (structured) → memory_recall mode=index → memory_get →
  memory_recall decisions_only → phase advance → complete_task (workflow
  outcome tracking) → session_end (markdown projection) → session_init →
  save_intent → list_intents → dashboard /api/knowledge/{id} payload.

Two additional micro-tests guard the cloud provider smoke path and the
PR5 timeout config helpers.

No real network is touched; the cloud-provider smoke test monkeypatches
`make_provider` to a mock.
"""

from __future__ import annotations

import asyncio
import json
import sys
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# Make src/ importable everywhere below.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_vault(tmp_path, monkeypatch):
    """Redirect activeContext markdown writes to a per-test tmp vault."""
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MEMORY_ACTIVECONTEXT_VAULT", str(vault))
    return vault


@pytest.fixture
def srv(monkeypatch, tmp_path, tmp_vault):
    """MCP server wired to an ephemeral Store + fresh memory.db.

    LLM is explicitly disabled so no network probes happen. All migrations
    the Store applies get a clean slate.
    """
    # Keep LLM dormant — tests that need provider paths mock explicitly.
    monkeypatch.setenv("MEMORY_LLM_ENABLED", "false")

    (tmp_path / "blobs").mkdir(exist_ok=True)
    (tmp_path / "chroma").mkdir(exist_ok=True)

    import server
    import config

    config._cache_clear()
    monkeypatch.setattr(server, "MEMORY_DIR", tmp_path)

    s = server.Store()
    server.store = s
    server.recall = server.Recall(s)
    server.SID = "sess-e2e-v8"
    server.BRANCH = ""

    s.db.execute(
        "INSERT OR IGNORE INTO sessions (id, started_at, project, status) "
        "VALUES (?, ?, ?, ?)",
        (server.SID, "2026-04-19T00:00:00Z", "e2e", "open"),
    )
    s.db.commit()

    yield server
    try:
        s.db.close()
    except Exception:
        pass


def _call(server_mod, name, args):
    """Invoke the private MCP dispatcher and return decoded JSON."""
    raw = asyncio.run(server_mod._do(name, args))
    return json.loads(raw)


# ──────────────────────────────────────────────────────────────────────
# Main scenario — 16-step user journey
# ──────────────────────────────────────────────────────────────────────


def test_v8_full_workflow_end_to_end(srv, tmp_vault, monkeypatch):
    """Exercise every touched surface from save_knowledge to dashboard citation."""
    store = srv.store

    # Step 1 — Store already set up by fixture (tmp_path memory.db, migrations).

    # Step 2 — privacy redaction on save_knowledge
    save_result = _call(srv, "memory_save", {
        "type": "fact",
        "content": (
            "PublicAPI: /users\n"
            "<private>SECRET_KEY=abc</private>\n"
            "Functional spec for cursor pagination..."
        ),
        "project": "e2e",
        "tags": ["spec", "users"],
    })
    assert save_result["saved"] is True
    assert save_result.get("privacy_redacted_sections") == 1
    kid_fact = save_result["id"]

    row = store.db.execute(
        "SELECT content FROM knowledge WHERE id=?", (kid_fact,)
    ).fetchone()
    assert "SECRET_KEY" not in row["content"]
    assert "abc" not in row["content"]
    # Public parts survive.
    assert "PublicAPI" in row["content"]
    assert "pagination" in row["content"]

    # Step 3 — classify_task
    cls = _call(srv, "classify_task", {
        "description": "refactor users endpoint to support cursor pagination"
    })
    assert cls["level"] in (2, 3), f"unexpected level: {cls['level']}"
    assert "build" in cls["suggested_phases"]

    # Step 4 — task_create → van phase
    created = _call(srv, "task_create", {
        "task_id": "e2e-task-1",
        "description": "refactor users endpoint to support cursor pagination",
    })
    assert created["phase"] == "van"

    # Step 5 — phase_transition van → plan
    moved = _call(srv, "phase_transition", {
        "task_id": "e2e-task-1",
        "new_phase": "plan",
        "notes": "gathering prior art",
    })
    assert moved["from_phase"] == "van"
    assert moved["to_phase"] == "plan"
    assert "rules_preview" in moved

    listed = _call(srv, "task_phases_list", {"task_id": "e2e-task-1"})
    phases = listed["phases"]
    assert [p["phase"] for p in phases] == ["van", "plan"]
    # van is closed (has exited_at), plan is open.
    assert phases[0]["exited_at"] is not None
    assert phases[1]["exited_at"] is None

    # Step 6 — save_decision (structured)
    dec = _call(srv, "save_decision", {
        "title": "Pagination strategy",
        "options": [
            {"name": "offset", "pros": ["simple"], "cons": ["unstable"]},
            {"name": "cursor", "pros": ["stable"], "cons": ["no skip"]},
        ],
        "criteria_matrix": {
            "stability": {"offset": 2, "cursor": 5},
            "simplicity": {"offset": 5, "cursor": 3},
        },
        "selected": "cursor",
        "rationale": "Stable under writes",
        "project": "e2e",
    })
    assert dec["saved"] is True
    assert dec["structured"] is True
    kid_decision = dec["id"]

    row = store.db.execute(
        "SELECT type, tags FROM knowledge WHERE id=?", (kid_decision,)
    ).fetchone()
    assert row["type"] == "decision"
    assert "structured" in json.loads(row["tags"])

    # Step 7 — memory_recall mode=index (no content leakage)
    idx = _call(srv, "memory_recall", {
        "query": "pagination",
        "project": "e2e",
        "mode": "index",
        "limit": 10,
    })
    assert idx["mode"] == "index"
    entries = idx.get("results") or []
    assert entries, "index recall returned no results"
    for entry in entries:
        assert "content" not in entry
        assert "context" not in entry
        # Required meta keys
        assert set(entry.keys()) >= {"id", "title", "score", "type", "project", "created_at"}

    first_two_ids = [e["id"] for e in entries[:2]]
    assert len(first_two_ids) >= 1

    # Step 8 — memory_get full fetch
    got = _call(srv, "memory_get", {"ids": first_two_ids, "detail": "full"})
    assert got["total"] == len(first_two_ids)
    for item in got["results"]:
        assert "content" in item
        assert "context" in item
        assert item["id"] in first_two_ids

    # Step 9 — memory_recall decisions_only → parsed schema
    dec_only = _call(srv, "memory_recall", {
        "query": "pagination",
        "project": "e2e",
        "type": "decision",
        "decisions_only": True,
    })
    assert dec_only.get("decisions_only") is True
    surviving = [
        item
        for group in dec_only.get("results", {}).values()
        for item in group
    ]
    assert any(it["id"] == kid_decision for it in surviving), (
        "structured decision missing from decisions_only recall"
    )
    found = next(it for it in surviving if it["id"] == kid_decision)
    assert found["decision"]["schema"] == "decision/v1"
    assert found["decision"]["selected"] == "cursor"
    # criteria_matrix preserved with parsed floats.
    assert found["decision"]["criteria_matrix"]["stability"]["cursor"] == 5.0

    # Step 10 — advance through remaining phases → archive, seed a workflow,
    # monkeypatch procedural.track_outcome, ensure complete_task fires it.
    # Order depends on classified level (L3 requires creative, L2 skips it).
    remaining = [p for p in cls["suggested_phases"] if p not in ("van", "plan")]
    for phase in remaining:
        _call(srv, "phase_transition", {
            "task_id": "e2e-task-1",
            "new_phase": phase,
        })

    # Seed a workflow row keyed by the task_id so complete_task → track_outcome fires.
    from procedural import ProceduralMemory
    pm = ProceduralMemory(store.db)
    pm.learn_workflow(
        name="refactor users endpoint",
        steps=["read code", "write tests", "refactor", "verify"],
        project="e2e",
    )
    # get_workflow looks up by id — rewrite the row id to match task_id.
    store.db.execute(
        "UPDATE workflows SET id=? WHERE name=? AND project=?",
        ("e2e-task-1", "refactor users endpoint", "e2e"),
    )
    store.db.commit()

    track_calls: list[dict] = []
    original_track = ProceduralMemory.track_outcome

    def spy_track(self, workflow_id, outcome, **kw):
        track_calls.append({"workflow_id": workflow_id, "outcome": outcome})
        return original_track(self, workflow_id, outcome, **kw)

    monkeypatch.setattr(ProceduralMemory, "track_outcome", spy_track)

    # complete_task is not an MCP tool — invoke directly via TaskPhases.
    from task_phases import TaskPhases
    tp = TaskPhases(store.db)
    completion = tp.complete_task("e2e-task-1", outcome="success")
    assert completion["outcome"] == "success"
    assert completion["tracked"]["workflow_id"] == "e2e-task-1"
    assert len(track_calls) == 1
    assert track_calls[0]["outcome"] == "success"

    # Step 11 — session_end (auto_compress=False: no provider call needed).
    end_result = _call(srv, "session_end", {
        "session_id": "s1",
        "project": "e2e",
        "summary": "done",
        "next_steps": ["write tests"],
        "pitfalls": ["watch ratelimits"],
    })
    assert end_result["summary_len"] == len("done")
    assert end_result["next_steps_count"] == 1
    assert "active_context_path" in end_result

    # Step 12 — activeContext.md is written into the tmp vault
    md_path = tmp_vault / "e2e" / "activeContext.md"
    assert md_path.exists(), f"expected {md_path} to be written"
    md = md_path.read_text(encoding="utf-8")
    assert "done" in md
    assert "write tests" in md
    assert "watch ratelimits" in md

    # Step 13 — session_init on a fresh project read returns the summary
    init_out = _call(srv, "session_init", {"project": "e2e"})
    assert init_out.get("summary") == "done"
    assert "write tests" in (init_out.get("next_steps") or [])
    # active_context projection round-trips
    assert init_out.get("active_context", {}).get("summary") == "done"

    # Step 14 — save_intent
    intent_res = _call(srv, "save_intent", {
        "prompt": "check why pagination broke",
        "session_id": "s2",
        "project": "e2e",
    })
    assert intent_res["saved"] is True
    assert intent_res["id"] > 0

    rows = store.db.execute(
        "SELECT COUNT(*) FROM intents WHERE session_id='s2' AND project='e2e'"
    ).fetchone()
    assert rows[0] == 1

    # Step 15 — list_intents surfaces the saved row
    lst = _call(srv, "list_intents", {"project": "e2e"})
    assert lst["count"] >= 1
    prompts = [r["prompt"] for r in lst["items"]]
    assert "check why pagination broke" in prompts

    # Step 16 — dashboard /api/knowledge/{id} citation payload
    import dashboard
    payload = dashboard.api_knowledge_citation(store.db, kid_decision)
    assert payload is not None
    assert payload["id"] == kid_decision
    assert payload["type"] == "decision"
    assert isinstance(payload["tags"], list)
    assert "related" in payload
    assert isinstance(payload["related"], list)


# ──────────────────────────────────────────────────────────────────────
# Cloud provider smoke — no network, provider injected via monkeypatch
# ──────────────────────────────────────────────────────────────────────


def test_e2e_cloud_provider_smoke(monkeypatch):
    """When MEMORY_LLM_PROVIDER=openai, deep_enricher._llm_complete routes
    through make_provider → provider.complete().

    We mock make_provider so no real HTTP leaves the process.
    """
    monkeypatch.setenv("MEMORY_LLM_PROVIDER", "openai")
    monkeypatch.setenv("MEMORY_ENRICH_PROVIDER", "openai")
    monkeypatch.setenv("MEMORY_LLM_API_KEY", "sk-test-smoke")
    monkeypatch.setenv("MEMORY_ENRICH_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("MEMORY_LLM_ENABLED", "force")

    import config
    import deep_enricher

    # Reset cached resolution so env changes take effect.
    config._cache_clear()
    deep_enricher._provider_cache.clear()

    mock_provider = MagicMock()
    mock_provider.name = "openai"
    mock_provider.available.return_value = True
    mock_provider.complete.return_value = '{"topics": ["auth", "pagination"]}'

    def fake_make_provider(name, **kwargs):
        return mock_provider

    # Patch at the import site used by deep_enricher._get_phase_provider.
    monkeypatch.setattr("llm_provider.make_provider", fake_make_provider)

    out = deep_enricher._llm_complete("analyze me", num_predict=80)
    assert out == '{"topics": ["auth", "pagination"]}'

    mock_provider.complete.assert_called_once()
    args, kwargs = mock_provider.complete.call_args
    # Provider gets the prompt as positional arg plus completion knobs.
    assert args[0] == "analyze me"
    assert kwargs.get("max_tokens") == 80
    # Model routes to the configured gpt-4o-mini.
    assert kwargs.get("model") == "gpt-4o-mini"
    # Temperature is enrich-phase default (0.1).
    assert kwargs.get("temperature") == pytest.approx(0.1)


# ──────────────────────────────────────────────────────────────────────
# Regression — PR5 timeout helpers must remain importable + callable
# ──────────────────────────────────────────────────────────────────────


def test_e2e_regression_pr5_functions_present(monkeypatch):
    """Guard against accidental reversal of PR5 (commit 2976ca1).

    The three phase-timeout helpers must be public and return floats with
    documented defaults when no override env is set.
    """
    # Scrub any env so we see pure defaults.
    for var in (
        "MEMORY_TRIPLE_TIMEOUT_SEC",
        "MEMORY_ENRICH_TIMEOUT_SEC",
        "MEMORY_REPR_TIMEOUT_SEC",
        "MEMORY_LLM_TIMEOUT_SEC",
    ):
        monkeypatch.delenv(var, raising=False)

    from config import (
        get_triple_timeout_sec,
        get_enrich_timeout_sec,
        get_repr_timeout_sec,
    )

    assert callable(get_triple_timeout_sec)
    assert callable(get_enrich_timeout_sec)
    assert callable(get_repr_timeout_sec)

    # Documented defaults
    assert get_triple_timeout_sec() == 30.0
    assert get_enrich_timeout_sec() == 45.0
    assert get_repr_timeout_sec() == 60.0

    # Per-phase env override wins
    monkeypatch.setenv("MEMORY_TRIPLE_TIMEOUT_SEC", "12.5")
    assert get_triple_timeout_sec() == 12.5
