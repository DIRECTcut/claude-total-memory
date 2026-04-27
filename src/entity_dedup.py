"""Pre-write entity dedup — v10 P1.7.

Beever Atlas computes Jina embeddings for incoming entity names and
runs cosine against known entity vectors before its CrossBatchValidator
LLM step, so "Atlas" matches to canonical "Beever Atlas" instead of
splintering into a new graph node. We do the equivalent for the tag
list that arrives at `save_knowledge`: any tag that didn't resolve to
a canonical topic gets a second chance against existing entity nodes
in `graph_nodes`.

Resolution:

  1. Take input tags that are NOT already a canonical topic
     (canonical_tags has first crack — runs before this).
  2. Filter graph_nodes to entity-flavoured types (technology, project,
     company, person, concept) with status='active'. Optionally scope
     to nodes that have been mentioned in the same project.
  3. Embed candidate names + the input tag through embed_provider.
  4. Best cosine ≥ MEMORY_ENTITY_DEDUP_THRESHOLD (default 0.85) → rewrite
     the tag to the canonical entity name; log to entity_dedup_log.
  5. Otherwise leave the tag intact and log as `no_match` (sampled).

The module is **dependency-injected**: callers pass `embed_fn` and
`candidates_fn`, which keeps tests free of FastEmbed / Ollama / Store.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

LOG = lambda msg: sys.stderr.write(f"[entity-dedup] {msg}\n")

_DEFAULT_THRESHOLD = 0.85
_DEFAULT_MAX_CANDIDATES = 200          # cap on graph_nodes pulled per call
_DEFAULT_TOP_K_PER_TAG = 3
_DEFAULT_ENTITY_TYPES = (
    "technology", "project", "company", "person", "concept",
    "tool", "doc", "article", "repo",
)


# ──────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────


@dataclass
class EntityCandidate:
    node_id: str
    name: str
    type: str
    embedding: list[float] | None = None


@dataclass
class DedupDecision:
    input_tag: str
    decision: str            # 'merged' | 'considered' | 'no_match' | 'error'
    matched_node_id: str | None
    canonical_name: str | None
    similarity: float
    threshold: float
    reason: str


# ──────────────────────────────────────────────
# Env
# ──────────────────────────────────────────────


def _enabled() -> bool:
    return os.environ.get("MEMORY_ENTITY_DEDUP_ENABLED", "auto").strip().lower() not in (
        "0", "false", "off", "no",
    )


def _threshold() -> float:
    raw = os.environ.get("MEMORY_ENTITY_DEDUP_THRESHOLD")
    if not raw:
        return _DEFAULT_THRESHOLD
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return _DEFAULT_THRESHOLD


def _max_candidates() -> int:
    raw = os.environ.get("MEMORY_ENTITY_DEDUP_MAX_CANDIDATES")
    if not raw:
        return _DEFAULT_MAX_CANDIDATES
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_MAX_CANDIDATES


def _entity_types() -> tuple[str, ...]:
    raw = os.environ.get("MEMORY_ENTITY_DEDUP_TYPES")
    if not raw:
        return _DEFAULT_ENTITY_TYPES
    return tuple(t.strip().lower() for t in raw.split(",") if t.strip())


def _log_no_matches() -> bool:
    return os.environ.get("MEMORY_ENTITY_DEDUP_LOG_ALL", "0").strip() == "1"


# ──────────────────────────────────────────────
# Cosine helper (no numpy dep — tags are tiny vectors otherwise)
# ──────────────────────────────────────────────


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ──────────────────────────────────────────────
# Production candidate fetcher (graph_nodes lookup)
# ──────────────────────────────────────────────


def production_candidates_query(db, *, project: str | None = None) -> list[EntityCandidate]:
    """Pull active entity-typed graph_nodes ordered by mention_count desc.

    Project scoping is best-effort: graph_nodes.properties contains a JSON
    blob that *may* include a `project` field. We don't reject candidates
    when the field is missing — global entities (Postgres, Go, Python)
    legitimately span projects.
    """
    types = _entity_types()
    placeholders = ",".join("?" * len(types))
    try:
        rows = db.execute(
            f"""SELECT id, name, type, properties FROM graph_nodes
                WHERE status='active' AND type IN ({placeholders})
                ORDER BY mention_count DESC, importance DESC
                LIMIT ?""",
            (*types, _max_candidates()),
        ).fetchall()
    except Exception as exc:
        LOG(f"candidates query failed: {exc}")
        return []
    return [
        EntityCandidate(
            node_id=r[0] if not hasattr(r, "keys") else r["id"],
            name=r[1] if not hasattr(r, "keys") else r["name"],
            type=r[2] if not hasattr(r, "keys") else r["type"],
        )
        for r in rows
    ]


def production_embed_call(texts: list[str]) -> list[list[float]] | None:
    """Default embed_fn — uses the embed_provider abstraction."""
    try:
        import embed_provider
    except Exception:
        return None
    try:
        provider = embed_provider.get_provider()
    except Exception:
        return None
    if provider is None or not getattr(provider, "available", lambda: True)():
        return None
    try:
        return provider.embed(texts)
    except Exception as exc:
        LOG(f"embed call failed: {exc}")
        return None


# ──────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────


def find_dedup_candidates(
    tag: str,
    *,
    candidates: list[EntityCandidate],
    embed_fn: Callable[[list[str]], list[list[float]] | None],
    threshold: float | None = None,
    top_k: int | None = None,
) -> list[tuple[EntityCandidate, float]]:
    """Return up to `top_k` (candidate, cosine) pairs above `threshold`.

    Embeds the input tag and any candidate that hasn't been embedded yet
    in a single call so the embedder batches efficiently.
    """
    if not tag or not candidates:
        return []
    thr = _threshold() if threshold is None else threshold
    k = _DEFAULT_TOP_K_PER_TAG if top_k is None else top_k

    # Ensure every candidate has an embedding. Embedding the canonical
    # *name* (rather than `name + properties`) keeps the query short and
    # focused — the surrounding context lives outside the dedup decision.
    missing_idx = [i for i, c in enumerate(candidates) if c.embedding is None]
    to_embed: list[str] = [tag]
    if missing_idx:
        to_embed.extend(candidates[i].name for i in missing_idx)

    embs = embed_fn(to_embed)
    if not embs or not embs[0]:
        return []

    tag_vec = embs[0]
    if missing_idx:
        for slot, idx in enumerate(missing_idx):
            cand_vec = embs[1 + slot] if 1 + slot < len(embs) else None
            if cand_vec:
                candidates[idx].embedding = cand_vec

    scored: list[tuple[EntityCandidate, float]] = []
    for cand in candidates:
        if not cand.embedding:
            continue
        score = cosine(tag_vec, cand.embedding)
        if score >= thr:
            scored.append((cand, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:k]


def canonicalize_entity_tags(
    tags: Iterable[str],
    *,
    candidates: list[EntityCandidate],
    embed_fn: Callable[[list[str]], list[list[float]] | None],
    threshold: float | None = None,
) -> tuple[list[str], list[DedupDecision]]:
    """Walk `tags`, swap each one to a canonical entity name when the top
    cosine match crosses `threshold`. Returns the rewritten tag list AND
    the audit decisions (one per tag that produced any consideration —
    `no_match` decisions are returned only when MEMORY_ENTITY_DEDUP_LOG_ALL=1).

    Originals that did NOT match are kept verbatim. Ordering is preserved.
    """
    if not tags:
        return [], []
    thr = _threshold() if threshold is None else threshold

    if not _enabled():
        return list(tags), []

    out: list[str] = []
    decisions: list[DedupDecision] = []
    seen: set[str] = set()

    def _add(name: str):
        norm = (name or "").strip().lower()
        if not norm or norm in seen:
            return
        seen.add(norm)
        out.append(norm)

    for raw in tags:
        if not isinstance(raw, str):
            continue
        tag = raw.strip()
        if not tag:
            continue
        try:
            matches = find_dedup_candidates(
                tag, candidates=candidates, embed_fn=embed_fn,
                threshold=thr,
            )
        except Exception as exc:
            LOG(f"dedup error for tag {tag!r}: {exc}")
            decisions.append(DedupDecision(
                input_tag=tag, decision="error",
                matched_node_id=None, canonical_name=None,
                similarity=0.0, threshold=thr,
                reason=str(exc)[:240],
            ))
            _add(tag)
            continue

        if not matches:
            if _log_no_matches():
                decisions.append(DedupDecision(
                    input_tag=tag, decision="no_match",
                    matched_node_id=None, canonical_name=None,
                    similarity=0.0, threshold=thr,
                    reason="no candidate above threshold",
                ))
            _add(tag)
            continue

        best_cand, best_score = matches[0]
        _add(best_cand.name)
        # Preserve the original verbatim too — a future recall using the
        # legacy synonym still works, mirroring the canonical_tags policy.
        if best_cand.name.lower() != tag.lower():
            _add(tag)

        decisions.append(DedupDecision(
            input_tag=tag,
            decision="merged",
            matched_node_id=best_cand.node_id,
            canonical_name=best_cand.name,
            similarity=best_score,
            threshold=thr,
            reason=f"cosine={best_score:.3f}",
        ))

    return out, decisions


# ──────────────────────────────────────────────
# Audit log persistence
# ──────────────────────────────────────────────


def log_decisions(
    db,
    decisions: list[DedupDecision],
    *,
    knowledge_id: int | None,
    project: str | None,
) -> None:
    if not decisions:
        return
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        for d in decisions:
            db.execute(
                """INSERT INTO entity_dedup_log (
                    created_at, knowledge_id, project, input_tag,
                    matched_node_id, canonical_name, similarity,
                    threshold, decision, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now, knowledge_id, project, d.input_tag,
                    d.matched_node_id, d.canonical_name, d.similarity,
                    d.threshold, d.decision, d.reason,
                ),
            )
        db.commit()
    except Exception as exc:
        LOG(f"log_decisions insert failed: {exc}")
