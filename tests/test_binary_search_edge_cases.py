"""Regression tests for Store._binary_search candidate-pool edge cases.

Bug 2026-04-27: when the active embedding pool was equal to or smaller
than `n_candidates`, `np.argpartition(hamming, kth=n_cand)` raised
``ValueError: kth(=N) out of bounds (N)`` because argpartition needs
``kth STRICTLY < array length``. The save-path swallowed the exception
in a generic ``except Exception``, so v10 ``contradiction_log`` silently
stopped recording. Tiny test-projects (≤ n_candidates active rows) were
the natural trigger.

These tests pin three pool sizes against n_candidates=3:
  pool < n_candidates  → return everything
  pool == n_candidates → return everything (the regressed case)
  pool > n_candidates  → take top-n via argpartition
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def store(monkeypatch, tmp_path):
    """Spin up a real Store on a tmp SQLite, no MCP/outbox side effects."""
    monkeypatch.setenv("MEMORY_QUALITY_GATE_ENABLED", "false")
    monkeypatch.setenv("MEMORY_CONTRADICTION_DETECT_ENABLED", "false")
    monkeypatch.setenv("MEMORY_OUTBOX_ENABLED", "false")
    monkeypatch.setenv("MEMORY_EPISODIC_ENABLED", "false")

    import server as srv
    # MEMORY_DIR is resolved at import time, so patch the module attribute.
    monkeypatch.setattr(srv, "MEMORY_DIR", tmp_path)
    s = srv.Store()
    yield s
    try:
        s.db.close()
    except Exception:
        pass


def _seed_embeddings(store, vectors: dict[int, np.ndarray], project: str = "p"):
    """Insert (knowledge, embeddings) rows for the given knowledge_id → vector map."""
    now = "2026-04-27T00:00:00Z"
    for kid, vec in vectors.items():
        store.db.execute(
            """INSERT INTO knowledge (id, session_id, type, content, project, status, created_at)
                   VALUES (?, 's', 'fact', ?, ?, 'active', ?)""",
            (kid, f"row-{kid}", project, now),
        )
        store._upsert_embedding(kid, vec.tolist(), "test-model")
    store.db.commit()


def _rand_vec(rng: np.random.Generator, dim: int = 32) -> np.ndarray:
    return rng.standard_normal(dim).astype(np.float32)


def test_binary_search_pool_smaller_than_n_candidates(store):
    """pool=2, n_candidates=3 → all 2 returned, no argpartition call."""
    rng = np.random.default_rng(0)
    vecs = {1: _rand_vec(rng), 2: _rand_vec(rng)}
    _seed_embeddings(store, vecs)

    query = _rand_vec(rng)
    results = store._binary_search(query.tolist(), n_candidates=3, project="p")

    assert {kid for kid, _score in results} == {1, 2}
    # Cosine similarity is bounded in [-1, 1].
    assert all(-1.0 <= score <= 1.0 for _kid, score in results)


def test_binary_search_pool_equal_to_n_candidates_does_not_raise(store):
    """pool=3, n_candidates=3 → the exact case that used to raise ValueError."""
    rng = np.random.default_rng(1)
    vecs = {kid: _rand_vec(rng) for kid in (10, 11, 12)}
    _seed_embeddings(store, vecs)

    query = _rand_vec(rng)
    # Must NOT raise — this is the regression we are pinning.
    results = store._binary_search(query.tolist(), n_candidates=3, project="p")

    assert {kid for kid, _score in results} == {10, 11, 12}


def test_binary_search_pool_larger_than_n_candidates_truncates(store):
    """pool=5, n_candidates=3 → at most 3 candidates flow to cosine re-rank.

    n_results default is 10 so we cannot assert cardinality from the return
    value alone, but we can assert it does not exceed n_candidates.
    """
    rng = np.random.default_rng(2)
    vecs = {kid: _rand_vec(rng) for kid in range(20, 25)}
    _seed_embeddings(store, vecs)

    query = _rand_vec(rng)
    results = store._binary_search(query.tolist(), n_candidates=3, project="p")

    assert len(results) <= 3
    seen_kids = {kid for kid, _score in results}
    assert seen_kids.issubset({20, 21, 22, 23, 24})


def test_binary_search_empty_pool_returns_empty(store):
    """Sanity: zero embeddings → empty result, no NumPy ops attempted."""
    rng = np.random.default_rng(3)
    query = _rand_vec(rng)
    assert store._binary_search(query.tolist(), n_candidates=3, project="p") == []
