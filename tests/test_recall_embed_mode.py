from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def store(monkeypatch, tmp_path):
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    (tmp_path / "blobs").mkdir(exist_ok=True)
    (tmp_path / "chroma").mkdir(exist_ok=True)

    import server

    monkeypatch.setattr(server, "MEMORY_DIR", tmp_path)
    s = server.Store()
    yield s
    try:
        s.db.close()
    except Exception:
        pass


def test_recall_does_not_touch_sentence_transformer_when_ollama_mode_active(store, monkeypatch):
    import server as _srv

    store.db.execute(
        "INSERT INTO sessions (id, started_at, project, status) VALUES ('s1', '2026-04-14T00:00:00Z', 'demo', 'open')"
    )
    store.db.commit()
    store.save_knowledge(
        sid="s1",
        content="directcut memory recall performance diagnostics",
        ktype="fact",
        project="demo",
    )

    store._embed_mode = "ollama"
    store._fastembed_model = False
    store.chroma = None

    monkeypatch.setattr(_srv.Store, "fastembed", property(lambda self: None))
    monkeypatch.setattr(
        _srv.Store,
        "embedder",
        property(lambda self: (_ for _ in ()).throw(AssertionError("SentenceTransformer touched"))),
    )
    monkeypatch.setattr(_srv.Store, "_check_ollama", lambda self: True)
    monkeypatch.setattr(_srv.Store, "_check_binary_search", lambda self: False)

    result = _srv.Recall(store).search(
        query="memory recall performance",
        project="demo",
        limit=5,
        detail="summary",
    )

    items = [item for group in result["results"].values() for item in group]
    assert any("performance" in (item.get("content", "") or "").lower() for item in items)
