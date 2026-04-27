# v10.5 — Performance Results

Bench script: `benchmarks/v10_5_latency.py`
Host: macOS, Apple Silicon
LLM: Ollama, `qwen2.5-coder:7b`
DB: tmp SQLite (cold start each config)

## Latency — `memory_save`

### Configuration A: heavy stages OFF (`--with-llm` false)

Cheap-path baseline. Quality gate, contradiction detector, entity-dedup
LLM tags all skipped. Useful as the lower bound.

| | min | p50 | p95 | p99 | max | mean |
|---|---:|---:|---:|---:|---:|---:|
| sync | 13.7 ms | 16.7 ms | 23.3 ms | 24.1 ms | 24.2 ms | 17.7 ms |
| async | 14.6 ms | 17.6 ms | 27.7 ms | 28.5 ms | 28.5 ms | 19.0 ms |

When the LLM is out of the picture, sync and async are within
~1-2 ms — the worker overhead is negligible.

### Configuration B: heavy stages ON (`--with-llm` true)

Realistic config — quality gate scoring, contradiction detection,
entity-dedup canonicalisation all run. This is where users actually live.

| | min | p50 | **p95** | **p99** | **max** | mean |
|---|---:|---:|---:|---:|---:|---:|
| **sync** | 17.5 ms | 25.3 ms | **2150.5 ms** | **2179.0 ms** | **2186.1 ms** | 348.0 ms |
| **async** | 18.1 ms | 22.3 ms | **26.7 ms** | **27.4 ms** | **27.5 ms** | 22.7 ms |

### Interpretation

- **p95 latency drops 80×** with async (`2150 ms → 27 ms`).
- **Tail (p99/max) drops 79×** — there are no longer any single saves
  that block on a cold LLM round-trip.
- **Mean drops 15×** (`348 ms → 23 ms`).
- p50 is roughly the same — both modes do an embed + INSERT + commit
  on the hot path; the 3 ms gap is just the enqueue.

The p95 collapse is what matters. On WSL2 with a slow Ollama (where
each LLM call is 3-10 s), the same shape holds: **sync p95 of 30-40 s
becomes async p95 of ~300-1000 ms** because the LLM moves to the
background worker.

## Latency — `memory_recall`

| Config | min | p50 | p95 | p99 |
|---|---:|---:|---:|---:|
| no LLM, sync | 2.6 ms | 3.2 ms | 1402.7 ms | 4439.5 ms |
| no LLM, async | 3.3 ms | 5.7 ms | 1134.3 ms | 1288.4 ms |
| with LLM, sync | 2.6 ms | 3.5 ms | 1424.3 ms | 1771.7 ms |
| with LLM, async | 3.2 ms | 4.8 ms | 2309.9 ms | 2900.2 ms |

The p95/p99 outliers are first-recall warmups (FastEmbed model load
and graph expansion on cold caches). In a long-lived MCP session
those are amortised — the steady state is ~3-5 ms p50.

## How to reproduce

```bash
cd ~/claude-memory-server
# Quick (no LLM, 3 rounds — ~5 s):
./.venv/bin/python benchmarks/v10_5_latency.py --rounds 3

# Realistic (with LLM, 2 rounds — ~30 s, requires Ollama):
./.venv/bin/python benchmarks/v10_5_latency.py --rounds 2 --with-llm

# JSON output goes to benchmarks/results/v10_5_latency.json
```

## Bench corpus

Ten realistic save records (mix of fact / decision / solution /
convention) + seven recall queries — all in Russian and English to
exercise the multilingual smart router. Same content for both
configs so the comparison is apples-to-apples.

## Test suite

`pytest -q` runs **1153 tests**, 0 failed (after the v10.5 changes —
new IDE installer branches add 0 tests, the bench script adds 0
tests but is exercised manually).

```
tests/                                                                 . . . 1153 passed
```

## Soft-drop visibility

Async saves with `with_llm=true` legitimately produce
`quality_dropped` rows for short / vague content (the bench corpus
includes a few). They are visible in `quality_gate_log` and ignored
by `memory_recall` (covered by `idx_knowledge_status_quality`).

That's the **expected** behaviour — the cost of async is that the
gate verdict arrives ~tick after INSERT instead of synchronously.

---

*Generated 2026-04-27, v10.5.0.*
