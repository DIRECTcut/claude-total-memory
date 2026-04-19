# Changelog

All notable changes to total-agent-memory are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions use [Semantic Versioning](https://semver.org/).

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
