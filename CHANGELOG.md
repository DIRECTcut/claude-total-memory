# Changelog

All notable changes to total-agent-memory are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions use [Semantic Versioning](https://semver.org/).

## [10.5.0] — 2026-04-27

Universal skill, 9-IDE installer, cross-platform hardening, sub-agent protocol, and a fresh latency benchmark proving the v10.1 async worker delivers an **80× p95 reduction** on `memory_save`.

### Added
- **Universal `memory-protocol` skill** (`skills/memory-protocol/`) — single SKILL.md (`v10.5.0`) + 4 references (`tool-cheatsheet.md` covering all 60+ MCP tools, `workflow-recipes.md` with 15 production-tested recipes, `hooks-explained.md`, `ide-setup.md`, `subagent-protocol.md`) + 4 templates (`claude-code-settings.json`, `codex-config.toml`, `cursor-rules.mdc`, `cline-rules.md`, `codex-AGENTS-block.md`). Same canonical content for every IDE; only the wiring differs.
- **`install.sh --ide` extended from 5 to 9 IDEs**: claude-code, codex, cursor, **cline**, **continue**, **aider**, **windsurf**, gemini-cli, opencode. New helpers: `register_mcp_cline`, `register_mcp_continue`, `register_mcp_aider`, `register_mcp_windsurf`, plus `_json_merge_mcp_nested` for the dotted-key case (`cline.mcpServers`).
- **Auto-install of `skills/memory-protocol/`** on every `install.sh --ide <X>` run that targets an IDE with a skill API (claude-code / codex / opencode); IDEs without a skill API get a rules-file copy via their respective register function.
- **Sub-agent memory protocol** — universal header for any sub-agent (`php-pro`, `golang-pro`, `vue-expert`, `code-reviewer`, etc.). Documented in `skills/memory-protocol/references/subagent-protocol.md`.
- **`benchmarks/v10_5_latency.py`** — apples-to-apples sync vs async micro-bench. `--rounds N`, `--with-llm`, JSON output to `benchmarks/results/v10_5_latency.json`. Markdown report `benchmarks/v10_5_results.md`.

### Performance
- `memory_save` p95 with LLM stages on: **2150 ms (sync) → 27 ms (async)**, **80× reduction**.
- `memory_save` p99: **2179 ms → 27 ms**.
- `memory_save` mean: **348 ms → 23 ms** (15×).
- `memory_recall` p50 steady state: **3-5 ms** in both modes.
- On WSL2 with slow Ollama the same shape holds — sync p95 of 30-40 s becomes async p95 of ~300-1000 ms.

### Fixed
- **`update.sh` bash 3.2 incompatibility** — `${var,,}` (lowercase parameter expansion) replaced with `tr '[:upper:]' '[:lower:]'`. macOS default shell now parses cleanly.
- **Cross-platform shellcheck pass** — all production `.sh` scripts (`install*.sh`, `update.sh`, `setup.sh`, `hooks/*.sh`, `ollama/*.sh`) syntax-check under `/bin/bash 3.2.x` (macOS), `bash 5.x` (Linux / WSL2). Zero blocker findings; only style/info notes remain.

### Changed
- README badges: `version 10.5.0`, `tests 1153 passing`, `IDEs 9 supported`.
- README: new **IDE matrix** table after Install, updated **Performance Tuning** numbers, new **v10.5 Roadmap** entry.
- `install.sh` USAGE: documents all 9 IDEs.
- `pyproject.toml`: bumped to `10.5.0`.

### Test suite
- 1153 passing (no new tests this version — the additions are docs / installer / bench code that is exercised by smoke runs in the bench tool).

## [10.1.0] — 2026-04-27

Inbox/outbox async pipeline, two production bugfixes, and dashboard observability for the worker. Backwards compatible: all new behaviour is opt-in.

### Added
- **Async enrichment worker** (`src/enrichment_worker.py`, migration `020_async_enrichment.sql`). Opt-in via `MEMORY_ASYNC_ENRICHMENT=true`. Moves the heavy LLM-bound stages of `save_knowledge` (quality gate, entity-dedup audit, contradiction detector, episodic event linking, wiki refresh) to a background daemon thread that consumes `enrichment_queue`. Drops `memory_save` p99 latency from ~2.5 s to ~460 ms on macOS, and from 30–40 s to ~300–1000 ms on WSL2 with a slow Ollama. Soft-drop semantic: a `quality_gate` `drop` verdict marks the row `status='quality_dropped'` after the INSERT (instead of blocking it).
- **Stale-processing recovery** in `enrichment_worker`. Rows stuck in `status='processing'` longer than `MEMORY_ENRICH_STALE_AFTER_SEC` (default 60 s) flip back to `pending` automatically. Covers worker process kills mid-stage.
- **Dashboard panel `⚡ v10.1 enrichment worker`** — depth, throughput per minute, p50/p95 ms per task, oldest pending age (color-coded by SLO band), and last 5 failures with their error message. New endpoint `GET /api/v10/enrichment-queue`.
- **5 new env knobs** for the worker: `MEMORY_ASYNC_ENRICHMENT`, `MEMORY_ENRICH_TICK_SEC`, `MEMORY_ENRICH_BATCH`, `MEMORY_ENRICH_MAX_ATTEMPTS`, `MEMORY_ENRICH_STALE_AFTER_SEC`.
- **`Performance tuning` README section** with sync-vs-async benchmark and tuning guidance for slow-LLM hosts.
- **17 regression tests**: 15 for the worker (enqueue/claim/idempotency/retry/soft-drop/daemon/stale-recovery), 4 for `_binary_search` edge cases, 1 for coref RU→EN guard.

### Fixed
- **`Store._binary_search` `ValueError: kth(=N) out of bounds (N)` on small candidate pools.** `np.argpartition` requires `kth STRICTLY < N`; tiny test projects (≤ 50 active embeddings) used to silently break `contradiction_log` because the save-path swallowed the exception in a generic `except`. Hot path now takes the whole pool when `n_candidates >= len(pool)`.
- **`coref_resolver` translating Russian → English.** `qwen2.5-coder:7b` (and Llama 3.x) interpreted the rewrite prompt as an instruction to switch language. Prompt now pins output language explicitly (`Do NOT translate. Do NOT switch language even partially.`) and tests assert the guard remains in the prompt.
- **`embed_provider` test fixtures** rejecting the `context=` kwarg passed by certifi-aware production callers (Python 3.13 macOS). Fixture `_capture_urlopen.fake()` now accepts forward-compatible kwargs.

### Changed
- `sqlite3.connect(check_same_thread=False)` for the `Store` connection so the enrichment worker thread can share it. Safe under WAL + busy_timeout=5000.
- Test suite: 1124 → 1153 passing (+29).
- Bumped version to `10.1.0`; `pyproject.toml` aligned.

## [10.0.0] — 2026-04-27

Beever-Atlas-inspired feature wave: 10 new pipeline stages, 5 new migrations, 153 new tests.

### Added
- **Quality gate (Beever 6-Month Test)** — synchronous LLM scorer (specificity / actionability / verifiability) with threshold 0.5, fail-open. Blocks low-signal records before INSERT. `MEMORY_QUALITY_GATE_ENABLED`, `MEMORY_QUALITY_THRESHOLD`.
- **Importance boost** — `critical / high / medium / low` field on knowledge rows; multiplies recall RRF score (×1.5 / ×1.2 / ×1.0 / ×0.8). Reserved for migration-blocking decisions and security incidents.
- **Canonical tag vocabulary** — 86 topics in `vocabularies/canonical_topics.txt`, normalised on save via embedding cosine + Levenshtein. Aliases under length 3 ignored.
- **Coref resolver** (opt-in via `MEMORY_COREF_ENABLED=true` or `coref=True` per save). Expands pronouns/deictics using last 20 records from the same session before INSERT.
- **Auto contradiction detector** — same-type/project semantic neighbours scored by LLM; `≥0.8` confidence → automatic supersession, `0.5–0.8` → flagged. Audit trail in `contradiction_log`.
- **Outbox / write-intent journal** — every `save_knowledge` call writes an intent row before any side-effects, allowing crash recovery on restart. `_reconcile_outbox_at_startup` replays committed intents.
- **Embedding-based entity dedup** — non-canonical tags get a second-chance lookup against active `graph_nodes` via cosine ≥ 0.85. Audit log in `entity_dedup_log`.
- **Episodic save events** — every save spawns an `event` node in `graph_nodes` with `MENTIONED_IN` edges to entity nodes. Enables queries like "show me saves where Postgres and Bob were mentioned together".
- **Smart query router** — bilingual (EN+RU) heuristic classifier on `memory_recall`; relational queries (wh-words / connectors / multiple entities) get a graph_search pass with a +1.3× RRF boost.
- **Per-project Markdown wiki digest** (`memory_wiki_generate(project)`) — Top Decisions / Active Solutions / Conventions / Recent Changes. Files land in `<MEMORY_DIR>/wikis/<project>.md`.

### Migrations
- `015_quality_importance.sql`, `016_contradictions.sql`, `017_outbox.sql`, `018_entity_dedup.sql`, `019_episodic_links.sql` — applied automatically by `_apply_sql_migrations` at startup.

### Changed
- `save_knowledge` returns a 5-tuple `(rid, was_dedup, was_redacted, private_sections, quality_meta)` — was 4-tuple in v9.

## [8.0.0] — 2026-04-19

Major feature wave: task workflow phases, structured decisions, cloud providers, activeContext live-doc, and many other quality-of-life improvements.

### Added
- **Cloud LLM providers** — `MEMORY_LLM_PROVIDER=openai|anthropic|ollama`. OpenAI-compat for OpenRouter, Together, Groq, DeepSeek, LM Studio, llama.cpp server. Per-phase routing: `MEMORY_TRIPLE_PROVIDER`, `MEMORY_ENRICH_PROVIDER`, `MEMORY_REPR_PROVIDER` with independent models.
- **Cloud embeddings** — `MEMORY_EMBED_PROVIDER=fastembed|openai|cohere` with dimension-mismatch safety gate that blocks catastrophic re-embed accidents.
- **`<private>...</private>` inline-tag** for automatic secret redaction in `save_knowledge`.
- **Session auto-compression** — `session_end(auto_compress=True)` generates summary/next_steps/pitfalls via LLM provider.
- **Progressive disclosure 3-layer workflow** — `memory_recall(mode="index")` returns compact ID+title+score, `memory_get(ids=[...])` batched full-content fetch. ~83% token saving vs default full recall.
- **Task complexity classifier** — `classify_task(description)` returns {level: 1-4, suggested_phases, estimated_tokens}.
- **Task phases state machine** — `task_create` / `phase_transition` / `task_phases_list` / `complete_task` with L1-L4 routing (van→plan→creative→build→reflect→archive). Migration 012_task_phases.sql.
- **Structured `save_decision`** — title + options + criteria_matrix + selected + rationale + discarded + auto multi-representation indexing. `memory_recall(decisions_only=True)` filter.
- **`activeContext.md` live-doc** — Obsidian markdown projection of session_init/end for human-readable session state. `MEMORY_ACTIVECONTEXT_VAULT` env override.
- **Phase-scoped rules** — `self_rules_context(project, phase="build")` with `phase:X` tag filter (zero migration). `rule_set_phase` MCP tool.
- **HTTP citation endpoints** — `/api/knowledge/{id}`, `/api/session/{id}` with related-graph expansion. HTML views at `/knowledge/{id}` and `/session/{id}`.
- **UserPromptSubmit hook** — captures user prompts into `intents` table (migration 013). `save_intent` / `list_intents` / `search_intents` MCP tools.
- **PostToolUse capture hook** — opt-in (`MEMORY_POST_TOOL_CAPTURE=1`) tool observation capture via deferred reflection queue.
- **Unified installer** — `install.sh --ide {claude-code|cursor|gemini-cli|opencode|codex}`. `install-codex.sh` is now a 3-line backward-compat shim.
- **15+ new MCP tools** — total count now 60+.
- **9 new src modules** — privacy_filter, llm_provider, embed_provider, task_classifier, task_phases, decisions, active_context, intents, recall_modes.
- **3 new migrations** — 011 privacy_counters, 012 task_phases, 013 intents.
- **2 new hooks** — user-prompt-submit.sh, post-tool-use.sh.
- **Donation link** updated to PayPal.Me/vbcherepanov.

### Fixed
- **Regression restore** — commit 2976ca1 ("docs(v7.0): sync README, install.sh, src refresh", 2026-04-17) accidentally reverted merged PR #5 (timeout config functions). Restored `get_triple_timeout_sec`, `get_enrich_timeout_sec`, `get_repr_timeout_sec`, `get_triple_max_predict` and related callers.
- **`has_llm()` phase-aware** — now consults provider.available() for cloud providers instead of only probing local Ollama. Previously `MEMORY_LLM_PROVIDER=openai` with Ollama offline would early-return False from all callers.

### Changed
- **Test suite** — 501 → 749 passing tests (+248).
- **Dashboard bind** — already on 127.0.0.1 (no change, maintaining security baseline).

## [7.0.0] — 2026-04-15

See git history for previous releases.
