"""Tests for provider-aware config.has_llm().

Legacy behavior (Ollama only) must stay intact; new behavior is that when
MEMORY_LLM_PROVIDER (or MEMORY_<PHASE>_PROVIDER) points at a cloud provider,
``has_llm()`` consults that provider's ``available()`` instead of Ollama.

All network traffic is mocked — no real HTTP.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def _clear_caches(monkeypatch):
    """Clear both config and provider availability caches between tests."""
    import config
    import llm_provider

    # Reset mode to auto so MEMORY_LLM_ENABLED=false from a prior test can't
    # short-circuit.
    monkeypatch.delenv("MEMORY_LLM_ENABLED", raising=False)
    config._cache_clear()
    llm_provider._clear_available_cache()
    yield
    config._cache_clear()
    llm_provider._clear_available_cache()


# ──────────────────────────────────────────────
# Ollama path (backward compat)
# ──────────────────────────────────────────────


def test_has_llm_ollama_path_backward_compat(monkeypatch):
    """Default provider is Ollama; when detect + model pass → True."""
    import config

    monkeypatch.delenv("MEMORY_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(config, "detect_ollama", lambda: True)
    monkeypatch.setattr(config, "has_model", lambda name: True)

    assert config.has_llm() is True


def test_has_llm_ollama_unreachable_returns_false(monkeypatch):
    import config

    monkeypatch.delenv("MEMORY_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(config, "detect_ollama", lambda: False)
    # has_model shouldn't even be called — guard with assertion.
    monkeypatch.setattr(
        config, "has_model",
        lambda name: (_ for _ in ()).throw(AssertionError("should not reach")),
    )

    assert config.has_llm() is False


# ──────────────────────────────────────────────
# OpenAI provider path
# ──────────────────────────────────────────────


def test_has_llm_openai_with_key_returns_true(monkeypatch):
    import config
    import llm_provider

    monkeypatch.setenv("MEMORY_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    # Must not consult Ollama — if it does, fail loudly.
    monkeypatch.setattr(
        config, "detect_ollama",
        lambda: (_ for _ in ()).throw(AssertionError("ollama probed")),
    )
    monkeypatch.setattr(llm_provider.OpenAIProvider, "available", lambda self: True)

    assert config.has_llm() is True


def test_has_llm_openai_without_key_returns_false(monkeypatch):
    import config
    import llm_provider

    monkeypatch.setenv("MEMORY_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_LLM_API_KEY", raising=False)
    # Force the real .available() which should short-circuit without a key.
    monkeypatch.setattr(
        config, "detect_ollama",
        lambda: (_ for _ in ()).throw(AssertionError("ollama probed")),
    )

    assert config.has_llm() is False


# ──────────────────────────────────────────────
# Per-phase override
# ──────────────────────────────────────────────


def test_has_llm_phase_override(monkeypatch):
    """MEMORY_TRIPLE_PROVIDER=anthropic: has_llm('triple') asks Anthropic."""
    import config
    import llm_provider

    monkeypatch.delenv("MEMORY_LLM_PROVIDER", raising=False)  # global stays ollama
    monkeypatch.setenv("MEMORY_TRIPLE_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")

    # Global has_llm() (no phase) must still go through Ollama path.
    monkeypatch.setattr(config, "detect_ollama", lambda: False)

    calls: list[str] = []

    def fake_available(self):
        calls.append(self.name)
        return True

    monkeypatch.setattr(llm_provider.AnthropicProvider, "available", fake_available)

    # Default (global) falls to Ollama → unavailable.
    assert config.has_llm() is False
    # Phase "triple" talks to Anthropic instead.
    assert config.has_llm("triple") is True
    assert calls == ["anthropic"]


# ──────────────────────────────────────────────
# Cache semantics
# ──────────────────────────────────────────────


def test_has_llm_cache_ttl_respects(monkeypatch):
    """Repeated has_llm() calls for a cloud provider don't re-probe each time."""
    import config
    import llm_provider

    monkeypatch.setenv("MEMORY_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1")
    monkeypatch.setattr(config, "detect_ollama", lambda: True)  # not used

    probe_calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        probe_calls["n"] += 1

        class _FakeResp:
            status = 200

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return b"{}"

        return _FakeResp()

    monkeypatch.setattr(llm_provider.urllib.request, "urlopen", fake_urlopen)

    # Three back-to-back calls should probe at most once thanks to the cache.
    assert config.has_llm() is True
    assert config.has_llm() is True
    assert config.has_llm() is True
    assert probe_calls["n"] == 1


def test_has_llm_no_infinite_recursion(monkeypatch):
    """Provider factory throwing must degrade to False, not crash."""
    import config
    import llm_provider

    monkeypatch.setenv("MEMORY_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1")

    def boom(name, **kwargs):
        raise RuntimeError("provider blew up")

    monkeypatch.setattr(llm_provider, "make_provider", boom)

    assert config.has_llm() is False
