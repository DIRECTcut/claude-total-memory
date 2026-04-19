"""
Task complexity classifier — v8.0.

Inspired by vanzan01/cursor-memory-bank. Classifies a task description into
one of four complexity levels and suggests the phases the workflow should
traverse (van → plan → creative → build → reflect → archive).

Levels:
    L1 — quick fix         (van → build → reflect → archive)
    L2 — small feature     (van → plan → build → reflect → archive)
    L3 — medium refactor   (van → plan → creative → build → reflect → archive)
    L4 — architecture      (van → plan → creative[extended] → build → reflect → archive)

If a `project` is supplied and the analogy engine is available, the
classifier looks up similar past solutions/lessons to boost confidence.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Iterable

# Canonical phase order — used to filter "suggested_phases" per level.
PHASES_ORDER: tuple[str, ...] = ("van", "plan", "creative", "build", "reflect", "archive")

LEVEL_PHASES: dict[int, list[str]] = {
    1: ["van", "build", "reflect", "archive"],
    2: ["van", "plan", "build", "reflect", "archive"],
    3: ["van", "plan", "creative", "build", "reflect", "archive"],
    4: ["van", "plan", "creative", "build", "reflect", "archive"],
}

LEVEL_TOKENS: dict[int, int] = {1: 2_000, 2: 8_000, 3: 25_000, 4: 80_000}

# Keyword → level mapping. Checked in order L4 > L3 > L2 > L1 so a more
# severe keyword wins when several match.
L4_KEYWORDS: tuple[str, ...] = (
    "architecture", "redesign", "multi-service", "multi service",
    "re-architect", "rearchitect", "microservice", "system overhaul",
    "platform redesign",
)
L3_KEYWORDS: tuple[str, ...] = (
    "refactor", "migrate", "migration", "implement feature",
    "new module", "rework", "restructure", "overhaul",
)
L2_KEYWORDS: tuple[str, ...] = (
    "add endpoint", "new page", "update docs", "add field",
    "add route", "new component", "extend api", "add method",
)
# Regex patterns for L2 — allow slashes/words between "add" and "endpoint" etc.
L2_REGEX: tuple[str, ...] = (
    r"\badd\b.{0,30}\bendpoint\b",
    r"\badd\b.{0,30}\broute\b",
    r"\bnew\b.{0,20}\b(page|component|endpoint|route)\b",
    r"\bextend\b.{0,20}\bapi\b",
)
L1_KEYWORDS: tuple[str, ...] = (
    "fix typo", "typo", "bump", "rename", "quick fix",
    "fix", "patch version", "update version",
)


def _contains_any(text: str, needles: Iterable[str]) -> str | None:
    """Return the first matching needle (lowercased) or None."""
    for n in needles:
        if n in text:
            return n
    return None


def _keyword_level(description: str) -> tuple[int | None, str | None]:
    """Detect a level purely from keywords. Returns (level, matched_keyword)."""
    text = description.lower()
    for lvl, kws in ((4, L4_KEYWORDS), (3, L3_KEYWORDS),
                     (2, L2_KEYWORDS), (1, L1_KEYWORDS)):
        hit = _contains_any(text, kws)
        if hit:
            return lvl, hit
        # L2 has extra regex patterns for expressions like "add /users endpoint"
        if lvl == 2:
            for pat in L2_REGEX:
                m = re.search(pat, text)
                if m:
                    return 2, m.group(0)
    return None, None


def _length_level(description: str) -> int:
    """Fallback classification by word count."""
    words = [w for w in re.split(r"\s+", description.strip()) if w]
    n = len(words)
    if n < 15:
        return 1
    if n <= 30:
        return 2
    if n <= 60:
        return 3
    return 4


def _boost_from_analogy(
    description: str,
    project: str,
    db: sqlite3.Connection | None,
) -> dict[str, Any] | None:
    """Look up similar past entries via AnalogyEngine. Returns summary or None."""
    if db is None:
        return None
    try:
        from analogy import AnalogyEngine  # local import — optional dep
    except Exception:
        return None
    try:
        ae = AnalogyEngine(db)
        hits = ae.find_analogies(
            text=description,
            exclude_project=None,  # include same project — we want history of THIS project
            limit=5,
            min_score=0.15,
        )
    except Exception:
        return None
    if not hits:
        return None
    # Score signal — average Jaccard of matched past items.
    avg = sum(h.get("analogy_score", 0.0) for h in hits) / len(hits)
    return {"count": len(hits), "avg_score": round(avg, 4)}


def classify_task(
    description: str,
    project: str | None = None,
    *,
    db: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Classify a task description and suggest workflow phases.

    Args:
        description: free-form task description from the user.
        project: optional project name; enables analogy lookup for a
            confidence boost.
        db: optional SQLite connection; required for analogy lookup.

    Returns:
        dict with keys: level, suggested_phases, estimated_tokens,
        rationale, confidence.
    """
    if not description or not description.strip():
        raise ValueError("description must be non-empty")

    kw_level, kw_match = _keyword_level(description)
    len_level = _length_level(description)

    if kw_level is not None:
        level = kw_level
        confidence = 1.0
        rationale = f"keyword match: '{kw_match}' → L{level}"
    else:
        level = len_level
        confidence = 0.5
        rationale = f"fallback by length ({len_level}) — no keyword match"

    # Optional: boost confidence slightly if analogy engine finds similar
    # past work in the given project. This does NOT change the level —
    # only signals that we have prior context to ground the estimate.
    analogy_info: dict[str, Any] | None = None
    if project and db is not None:
        analogy_info = _boost_from_analogy(description, project, db)
        if analogy_info and analogy_info.get("count", 0) > 0:
            confidence = min(1.0, confidence + 0.1 * min(analogy_info["count"], 3))
            rationale += f"; {analogy_info['count']} analogous past items (avg {analogy_info['avg_score']})"

    return {
        "level": level,
        "suggested_phases": list(LEVEL_PHASES[level]),
        "estimated_tokens": LEVEL_TOKENS[level],
        "rationale": rationale,
        "confidence": round(confidence, 4),
        "analogy": analogy_info,
    }
