"""
Reflection Synthesize Phase -- pattern finding, generalization, graph enrichment.

Phase 2 of the reflection pipeline. Clusters recent episodes,
discovers cross-project patterns, strengthens co-occurrence edges,
proposes new skills, and generates weekly digests.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta

LOG = lambda msg: sys.stderr.write(f"[memory-reflection] {msg}\n")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return uuid.uuid4().hex


def _parse_json(val: str | None, default: list | dict | None = None) -> list | dict:
    """Safely parse a JSON string, returning default on failure."""
    if val is None:
        return default if default is not None else []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def _concept_overlap(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two concept sets."""
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union) if union else 0.0


class SynthesizePhase:
    """Phase 2: Find patterns, create generalizations, enrich graph."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def run(self, days: int = 7) -> dict:
        """Run synthesis on recent data. Returns stats."""
        stats: dict = {
            "clusters_found": 0,
            "cross_project_patterns": 0,
            "edges_strengthened": 0,
            "skills_proposed": 0,
        }

        try:
            clusters = self.cluster_recent_episodes(days=days)
            stats["clusters_found"] = len(clusters)

            if clusters:
                proposals = self.propose_skills(clusters)
                stats["skills_proposed"] = len(proposals)
        except Exception as e:
            LOG(f"cluster/propose error: {e}")

        try:
            patterns = self.find_cross_project_patterns()
            stats["cross_project_patterns"] = len(patterns)
        except Exception as e:
            LOG(f"cross_project_patterns error: {e}")

        try:
            stats["edges_strengthened"] = self.strengthen_cooccurrences(
                days=max(days, 30)
            )
        except Exception as e:
            LOG(f"strengthen_cooccurrences error: {e}")

        LOG(f"Synthesis complete: {stats}")
        return stats

    def cluster_recent_episodes(
        self, days: int = 7, min_cluster_size: int = 3
    ) -> list[list[dict]]:
        """
        Cluster recent episodes by concept overlap.
        Two episodes are similar if they share 50%+ concepts (Jaccard).
        Returns list of clusters (each cluster = list of episode dicts).
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        rows = self.db.execute(
            """SELECT id, session_id, project, narrative, outcome,
                      impact_score, concepts, key_insight, timestamp
               FROM episodes
               WHERE timestamp >= ?
               ORDER BY timestamp DESC""",
            (cutoff,),
        ).fetchall()

        if len(rows) < min_cluster_size:
            return []

        # Parse concepts for each episode
        episodes: list[dict] = []
        for row in rows:
            ep = dict(row)
            ep["concept_set"] = set(_parse_json(ep.get("concepts")))
            episodes.append(ep)

        # Simple greedy clustering: assign each episode to the first
        # cluster with >= 50% concept overlap, or create a new cluster
        clusters: list[list[dict]] = []

        for ep in episodes:
            placed = False
            for cluster in clusters:
                # Check overlap with the cluster's combined concept set
                cluster_concepts: set[str] = set()
                for member in cluster:
                    cluster_concepts |= member["concept_set"]

                if _concept_overlap(ep["concept_set"], cluster_concepts) >= 0.5:
                    cluster.append(ep)
                    placed = True
                    break

            if not placed:
                clusters.append([ep])

        # Filter by minimum size
        result = [c for c in clusters if len(c) >= min_cluster_size]

        LOG(f"Clustered {len(rows)} episodes into {len(result)} clusters "
            f"(min_size={min_cluster_size})")
        return result

    def find_cross_project_patterns(self, min_projects: int = 2) -> list[dict]:
        """
        Find solutions/patterns used across multiple projects.
        Looks at knowledge records of type 'solution' or 'pattern' that
        share concepts across different projects.
        Returns list of {pattern, projects, count, concept_names}.
        """
        # Find concepts that appear in knowledge across multiple projects
        rows = self.db.execute(
            """SELECT gn.name AS concept_name,
                      GROUP_CONCAT(DISTINCT k.project) AS projects,
                      COUNT(DISTINCT k.project) AS project_count,
                      COUNT(DISTINCT k.id) AS knowledge_count
               FROM knowledge_nodes kn
               JOIN graph_nodes gn ON kn.node_id = gn.id
               JOIN knowledge k ON kn.knowledge_id = k.id
               WHERE k.status = 'active'
                 AND k.type IN ('solution', 'pattern', 'lesson')
                 AND gn.status = 'active'
               GROUP BY gn.name
               HAVING project_count >= ?
               ORDER BY project_count DESC, knowledge_count DESC
               LIMIT 50""",
            (min_projects,),
        ).fetchall()

        patterns: list[dict] = []
        for row in rows:
            projects = (row["projects"] or "").split(",")
            patterns.append({
                "pattern": row["concept_name"],
                "projects": projects,
                "count": row["knowledge_count"],
            })

        LOG(f"Found {len(patterns)} cross-project patterns")
        return patterns

    def strengthen_cooccurrences(
        self, days: int = 30, min_count: int = 3
    ) -> int:
        """
        Find concepts that co-occur in knowledge records.
        Create or strengthen 'mentioned_with' edges in the graph.
        Returns number of edges created/strengthened.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Find co-occurring node pairs in recent knowledge
        rows = self.db.execute(
            """SELECT kn1.node_id AS node_a, kn2.node_id AS node_b,
                      COUNT(*) AS cnt
               FROM knowledge_nodes kn1
               JOIN knowledge_nodes kn2
                 ON kn1.knowledge_id = kn2.knowledge_id
                 AND kn1.node_id < kn2.node_id
               JOIN knowledge k ON kn1.knowledge_id = k.id
               WHERE k.created_at >= ?
                 AND k.status = 'active'
               GROUP BY kn1.node_id, kn2.node_id
               HAVING cnt >= ?
               ORDER BY cnt DESC""",
            (cutoff, min_count),
        ).fetchall()

        edges_modified = 0
        for row in rows:
            node_a = row["node_a"]
            node_b = row["node_b"]
            count = row["cnt"]

            # Check if edge already exists
            existing = self.db.execute(
                """SELECT id, weight FROM graph_edges
                   WHERE source_id = ? AND target_id = ?
                     AND relation_type = 'mentioned_with'""",
                (node_a, node_b),
            ).fetchone()

            if existing:
                # Strengthen: add weight proportional to co-occurrence count
                new_weight = min(existing["weight"] + 0.05 * count, 10.0)
                self.db.execute(
                    """UPDATE graph_edges
                       SET weight = ?,
                           last_reinforced_at = ?,
                           reinforcement_count = reinforcement_count + 1
                       WHERE id = ?""",
                    (new_weight, _now(), existing["id"]),
                )
            else:
                # Create new edge with weight based on count
                initial_weight = min(0.3 + 0.1 * count, 3.0)
                self.db.execute(
                    """INSERT INTO graph_edges
                       (id, source_id, target_id, relation_type, weight, context, created_at)
                       VALUES (?, ?, ?, 'mentioned_with', ?, ?, ?)""",
                    (
                        _new_id(),
                        node_a,
                        node_b,
                        initial_weight,
                        f"Co-occurred in {count} knowledge records",
                        _now(),
                    ),
                )
            edges_modified += 1

        if edges_modified > 0:
            self.db.commit()
            LOG(f"Strengthened/created {edges_modified} co-occurrence edges")

        return edges_modified

    def propose_skills(self, clusters: list[list[dict]]) -> list[dict]:
        """
        For each cluster of 3+ similar episodes, propose a skill.
        Analyzes the cluster for common patterns and generates
        a skill definition.
        Returns list of proposed skills as dicts.
        Saves to pending_proposals table.
        """
        proposals: list[dict] = []

        for cluster in clusters:
            if len(cluster) < 3:
                continue

            # Extract common concepts from the cluster
            concept_sets = [ep["concept_set"] for ep in cluster]
            common_concepts = concept_sets[0].copy()
            for cs in concept_sets[1:]:
                common_concepts &= cs

            if not common_concepts:
                # Fall back to most frequent concepts
                concept_freq: dict[str, int] = defaultdict(int)
                for cs in concept_sets:
                    for c in cs:
                        concept_freq[c] += 1
                threshold = len(cluster) * 0.6
                common_concepts = {
                    c for c, freq in concept_freq.items() if freq >= threshold
                }

            if not common_concepts:
                continue

            # Determine success rate from outcomes
            outcomes = [ep.get("outcome", "routine") for ep in cluster]
            success_count = sum(
                1 for o in outcomes if o in ("breakthrough", "routine")
            )
            success_rate = success_count / len(outcomes)

            # Collect key insights
            insights = [
                ep["key_insight"]
                for ep in cluster
                if ep.get("key_insight")
            ]

            # Collect projects
            projects = list({ep.get("project", "general") for ep in cluster})

            # Build trigger pattern from common concepts
            trigger = " AND ".join(sorted(common_concepts)[:5])

            # Build steps from insights
            steps = []
            if insights:
                for idx, insight in enumerate(insights[:5], 1):
                    steps.append(f"Step {idx}: {insight}")
            else:
                steps.append("Apply known approach for: " + ", ".join(sorted(common_concepts)[:3]))

            skill_name = "skill_" + "_".join(
                sorted(common_concepts)[:3]
            ).replace(" ", "_").lower()[:50]

            # Check if skill already exists
            existing = self.db.execute(
                "SELECT id FROM skills WHERE name = ?", (skill_name,)
            ).fetchone()
            if existing:
                continue

            proposal = {
                "type": "skill",
                "skill_name": skill_name,
                "trigger_pattern": trigger,
                "steps": steps,
                "common_concepts": sorted(common_concepts),
                "projects": projects,
                "success_rate": round(success_rate, 2),
                "based_on_episodes": len(cluster),
                "episode_ids": [ep["id"] for ep in cluster],
            }

            # Save to pending_proposals
            proposal_id = _new_id()
            self.db.execute(
                """INSERT INTO pending_proposals
                   (id, type, content, evidence, confidence, status, created_at)
                   VALUES (?, 'skill', ?, ?, ?, 'pending', ?)""",
                (
                    proposal_id,
                    json.dumps(proposal),
                    json.dumps({"episode_count": len(cluster), "success_rate": success_rate}),
                    min(0.5 + 0.1 * len(cluster), 0.95),
                    _now(),
                ),
            )

            proposal["id"] = proposal_id
            proposals.append(proposal)

        if proposals:
            self.db.commit()
            LOG(f"Proposed {len(proposals)} new skills")

        return proposals

    def generate_weekly_digest(self) -> dict:
        """
        Generate weekly digest with stats and focus areas.
        """
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        period_start = week_ago.strftime("%Y-%m-%dT%H:%M:%SZ")
        period_end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Sessions count
        sessions_count = self.db.execute(
            """SELECT COUNT(*) FROM sessions
               WHERE started_at >= ?""",
            (period_start,),
        ).fetchone()[0]

        # Memories created
        memories_created = self.db.execute(
            """SELECT COUNT(*) FROM knowledge
               WHERE created_at >= ?""",
            (period_start,),
        ).fetchone()[0]

        # Focus areas: top projects by knowledge count
        focus_rows = self.db.execute(
            """SELECT project, COUNT(*) as cnt
               FROM knowledge
               WHERE created_at >= ? AND status = 'active'
               GROUP BY project
               ORDER BY cnt DESC
               LIMIT 5""",
            (period_start,),
        ).fetchall()
        focus_areas = [row["project"] for row in focus_rows]

        # Skills refined
        skills_refined = self.db.execute(
            """SELECT COUNT(*) FROM skills
               WHERE last_refined_at >= ?""",
            (period_start,),
        ).fetchone()[0]

        # Episode counts by outcome
        episode_rows = self.db.execute(
            """SELECT outcome, COUNT(*) as cnt
               FROM episodes
               WHERE timestamp >= ?
               GROUP BY outcome""",
            (period_start,),
        ).fetchall()
        episodes_by_outcome: dict[str, int] = {}
        for row in episode_rows:
            episodes_by_outcome[row["outcome"]] = row["cnt"]

        # Top concepts by mention count (from graph nodes linked to recent knowledge)
        concept_rows = self.db.execute(
            """SELECT gn.name, COUNT(*) as mentions
               FROM knowledge_nodes kn
               JOIN graph_nodes gn ON kn.node_id = gn.id
               JOIN knowledge k ON kn.knowledge_id = k.id
               WHERE k.created_at >= ? AND k.status = 'active'
               GROUP BY gn.name
               ORDER BY mentions DESC
               LIMIT 10""",
            (period_start,),
        ).fetchall()
        top_concepts = [
            {"name": row["name"], "mentions": row["mentions"]}
            for row in concept_rows
        ]

        # Active blind spots
        blind_spots_active = self.db.execute(
            "SELECT COUNT(*) FROM blind_spots WHERE status = 'active'"
        ).fetchone()[0]

        digest = {
            "period": f"{week_ago.strftime('%Y-%m-%d')} -- {now.strftime('%Y-%m-%d')}",
            "sessions_count": sessions_count,
            "memories_created": memories_created,
            "focus_areas": focus_areas,
            "skills_refined": skills_refined,
            "episodes": episodes_by_outcome,
            "top_concepts": top_concepts,
            "blind_spots_active": blind_spots_active,
        }

        LOG(f"Weekly digest: {sessions_count} sessions, "
            f"{memories_created} memories, "
            f"{len(focus_areas)} focus areas")

        return digest
