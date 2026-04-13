"""
Composition Engine — combines multiple memory sources into unified solutions.

When no single memory record answers a query completely, the composition engine
finds the minimum set of records that covers all needed concepts, detects
conflicts between sources, and produces an integration plan.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from typing import Any

LOG = lambda msg: sys.stderr.write(f"[memory-composition] {msg}\n")


class CompositionEngine:
    """Combines multiple memory sources into a unified solution."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def compose(
        self,
        needed_concepts: list[str],
        candidate_memories: list[dict[str, Any]],
        max_sources: int = 5,
    ) -> dict[str, Any]:
        """Find minimum set of memories that covers all needed concepts.

        Uses a greedy set cover algorithm to select the fewest memories
        that together address all the concepts in the query.

        Args:
            needed_concepts: List of concept names that need to be covered.
            candidate_memories: List of memory dicts from the knowledge table.
            max_sources: Maximum number of source memories in the composition.

        Returns:
            Dict with keys:
                sources: list of {memory: dict, covers: list[str]}
                coverage_percent: float (0.0 to 100.0)
                covered: list of concept names covered
                gaps: list of concept names not covered
                conflicts: list of conflict dicts
                integration_plan: str or None
        """
        if not needed_concepts or not candidate_memories:
            return {
                "sources": [],
                "coverage_percent": 0.0,
                "covered": [],
                "gaps": list(needed_concepts),
                "conflicts": [],
                "integration_plan": None,
            }

        # Build coverage matrix: which concepts does each memory provide?
        memory_lookup = {m["id"]: m for m in candidate_memories}
        coverage_matrix = self._build_coverage_matrix(
            candidate_memories, needed_concepts
        )

        if not coverage_matrix:
            LOG("compose: no coverage found for any candidate memory")
            return {
                "sources": [],
                "coverage_percent": 0.0,
                "covered": [],
                "gaps": list(needed_concepts),
                "conflicts": [],
                "integration_plan": None,
            }

        # Greedy set cover
        universe = set(needed_concepts)
        selected_ids = self._greedy_set_cover(coverage_matrix, universe, max_sources)

        # Build result sources
        sources: list[dict[str, Any]] = []
        all_covered: set[str] = set()
        selected_memories: list[dict[str, Any]] = []

        for mid in selected_ids:
            memory = memory_lookup.get(mid)
            if memory is None:
                continue
            covers = sorted(coverage_matrix.get(mid, set()))
            all_covered.update(covers)
            sources.append({"memory": memory, "covers": covers})
            selected_memories.append(memory)

        covered_list = sorted(all_covered)
        gaps = sorted(universe - all_covered)
        coverage_pct = (
            round(len(all_covered) / len(universe) * 100, 1) if universe else 0.0
        )

        # Detect conflicts
        conflicts = self._detect_conflicts(selected_memories, coverage_matrix)

        # Generate integration plan if multiple sources selected
        integration_plan = None
        if len(sources) > 1:
            integration_plan = self._generate_integration_plan(
                sources, conflicts, gaps
            )

        LOG(
            f"compose: {len(candidate_memories)} candidates -> "
            f"{len(sources)} selected, {coverage_pct}% coverage, "
            f"{len(gaps)} gaps, {len(conflicts)} conflicts"
        )

        return {
            "sources": sources,
            "coverage_percent": coverage_pct,
            "covered": covered_list,
            "gaps": gaps,
            "conflicts": conflicts,
            "integration_plan": integration_plan,
        }

    def _build_coverage_matrix(
        self,
        memories: list[dict[str, Any]],
        concepts: list[str],
    ) -> dict[int, set[str]]:
        """Build matrix: memory_id -> set of concept names it provides.

        Queries knowledge_nodes + graph_nodes to find which concepts each
        memory is linked to. Also does text-based matching as a fallback
        for memories not linked via the graph.

        Args:
            memories: List of memory dicts (must have 'id' key).
            concepts: List of concept names to check coverage for.

        Returns:
            Dict mapping memory_id to set of covered concept names.
        """
        matrix: dict[int, set[str]] = defaultdict(set)
        concept_set_lower = {c.lower() for c in concepts}
        concept_by_lower = {c.lower(): c for c in concepts}

        memory_ids = [m["id"] for m in memories]
        if not memory_ids:
            return matrix

        # Strategy 1: Graph-based coverage via knowledge_nodes -> graph_nodes
        placeholders = ",".join("?" * len(memory_ids))
        rows = self.db.execute(
            f"""SELECT kn.knowledge_id, LOWER(gn.name) as node_name
                FROM knowledge_nodes kn
                JOIN graph_nodes gn ON kn.node_id = gn.id
                WHERE kn.knowledge_id IN ({placeholders})
                  AND gn.status = 'active'""",
            memory_ids,
        ).fetchall()

        for row in rows:
            kid = row[0]
            node_name = row[1]
            if node_name in concept_set_lower:
                original = concept_by_lower[node_name]
                matrix[kid].add(original)

        # Strategy 2: Text-based fallback — check if concept name appears
        # in memory content (for memories not linked via graph)
        for memory in memories:
            mid = memory["id"]
            if mid in matrix and matrix[mid]:
                continue  # already has graph-based coverage

            content_lower = (memory.get("content") or "").lower()
            context_lower = (memory.get("context") or "").lower()
            text = f"{content_lower} {context_lower}"

            for concept in concepts:
                if concept.lower() in text:
                    matrix[mid].add(concept)

        return dict(matrix)

    def _detect_conflicts(
        self,
        selected: list[dict[str, Any]],
        coverage: dict[int, set[str]],
    ) -> list[dict[str, Any]]:
        """Find concepts covered by multiple sources (potential conflicts).

        A conflict exists when two or more selected memories provide
        information about the same concept, potentially with different
        or contradictory approaches.

        Args:
            selected: List of selected memory dicts.
            coverage: Coverage matrix (memory_id -> concepts).

        Returns:
            List of conflict dicts with keys: concept, sources, recommendation.
        """
        # Build reverse index: concept -> list of memory IDs covering it
        concept_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for memory in selected:
            mid = memory["id"]
            concepts = coverage.get(mid, set())
            for concept in concepts:
                concept_sources[concept].append(memory)

        conflicts: list[dict[str, Any]] = []
        for concept, sources in concept_sources.items():
            if len(sources) < 2:
                continue

            # Determine recommendation based on source types and confidence
            source_types = {s.get("type", "unknown") for s in sources}
            confidences = [s.get("confidence", 1.0) for s in sources]

            if len(source_types) > 1:
                recommendation = (
                    f"Multiple source types ({', '.join(sorted(source_types))}) — "
                    f"prefer the most specific/recent one"
                )
            elif max(confidences) - min(confidences) > 0.3:
                recommendation = "Prefer the source with higher confidence"
            else:
                recommendation = "Sources likely complementary; merge information"

            conflicts.append(
                {
                    "concept": concept,
                    "sources": [
                        {
                            "id": s["id"],
                            "type": s.get("type", "unknown"),
                            "confidence": s.get("confidence", 1.0),
                            "preview": (s.get("content") or "")[:100],
                        }
                        for s in sources
                    ],
                    "recommendation": recommendation,
                }
            )

        return conflicts

    def _greedy_set_cover(
        self,
        matrix: dict[int, set[str]],
        universe: set[str],
        max_sets: int = 5,
    ) -> list[int]:
        """Classic greedy set cover algorithm.

        At each step, picks the memory that covers the most uncovered
        concepts. Stops when all concepts are covered or max_sets reached.

        Args:
            matrix: Dict mapping memory_id to set of concepts it covers.
            universe: Full set of concepts to cover.
            max_sets: Maximum number of sets (memories) to select.

        Returns:
            List of selected memory IDs in selection order.
        """
        remaining = set(universe)
        selected: list[int] = []
        used: set[int] = set()

        for _ in range(max_sets):
            if not remaining:
                break

            # Find the memory that covers the most remaining concepts
            best_id: int | None = None
            best_count = 0

            for mid, concepts in matrix.items():
                if mid in used:
                    continue
                overlap = len(concepts & remaining)
                if overlap > best_count:
                    best_count = overlap
                    best_id = mid

            if best_id is None or best_count == 0:
                break

            selected.append(best_id)
            used.add(best_id)
            remaining -= matrix[best_id]

        return selected

    def _generate_integration_plan(
        self,
        sources: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
        gaps: list[str],
    ) -> str:
        """Generate a human-readable integration plan for composed sources.

        Args:
            sources: List of source dicts with 'memory' and 'covers' keys.
            conflicts: List of conflict dicts.
            gaps: List of uncovered concept names.

        Returns:
            Multi-line string describing how to combine the sources.
        """
        lines: list[str] = []
        lines.append(f"Integration plan ({len(sources)} sources):")

        for i, src in enumerate(sources, 1):
            memory = src["memory"]
            covers = src["covers"]
            mtype = memory.get("type", "unknown")
            lines.append(
                f"  {i}. [{mtype}] id={memory['id']} — covers: {', '.join(covers)}"
            )

        if conflicts:
            lines.append(f"\nConflicts ({len(conflicts)}):")
            for conflict in conflicts:
                lines.append(
                    f"  - '{conflict['concept']}': {conflict['recommendation']}"
                )

        if gaps:
            lines.append(f"\nGaps (not covered): {', '.join(gaps)}")
            lines.append("  -> These concepts need manual research or new memories")

        return "\n".join(lines)
