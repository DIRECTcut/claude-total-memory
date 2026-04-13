"""
Reflection Agent -- background process for knowledge consolidation.

Like sleep for the brain: transfers short-term to long-term memory,
consolidates patterns, resolves contradictions, and evolves the knowledge graph.

Orchestrates DigestPhase (cleanup) and SynthesizePhase (pattern finding).
Runs in three modes: quick (post-session), full (periodic), weekly (deep analysis).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Relative imports via sys.path for flat project structure
_src = str(Path(__file__).parent.parent)
if _src not in sys.path:
    sys.path.insert(0, _src)

from reflection.digest import DigestPhase
from reflection.synthesize import SynthesizePhase

LOG = lambda msg: sys.stderr.write(f"[memory-reflection] {msg}\n")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return uuid.uuid4().hex


class ReflectionAgent:
    """Background process that consolidates, synthesizes, and evolves knowledge.

    Like sleep for the brain -- transfers short-term to long-term memory.
    Orchestrates two phases:
      1. Digest: cleanup, dedup, decay, contradiction resolution
      2. Synthesize: pattern finding, clustering, skill proposals
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self.digest = DigestPhase(db)
        self.synthesize = SynthesizePhase(db)

    async def run(self, scope: str = "full") -> dict:
        """
        Run reflection pipeline.

        Args:
            scope: 'quick' (digest only), 'full' (digest + synthesize),
                   'weekly' (full + deep analysis + digest generation)

        Returns:
            ReflectionReport as dict.
        """
        if scope == "quick":
            return await self.run_quick()
        elif scope == "weekly":
            return await self.run_weekly()
        else:
            return await self.run_full()

    async def run_quick(self) -> dict:
        """Quick reflection: dedup + decay only. Runs after each session."""
        LOG("Starting quick reflection...")
        started_at = _now()

        # Run synchronously — SQLite connections are not thread-safe
        digest_stats = self._run_digest_quick()

        report = {
            "id": _new_id(),
            "type": "session",
            "scope": "quick",
            "started_at": started_at,
            "completed_at": _now(),
            "digest": digest_stats,
            "synthesis": None,
            "weekly_digest": None,
        }

        self._save_report(report)
        LOG(f"Quick reflection complete: {digest_stats}")
        return report

    async def run_full(self) -> dict:
        """Full reflection: digest + synthesize + evolve. Runs every 6 hours."""
        LOG("Starting full reflection...")
        started_at = _now()

        # Run synchronously — SQLite connections are not thread-safe
        # Phase 1: Digest
        digest_stats = self.digest.run()

        # Phase 2: Synthesize (depends on clean data from digest)
        synthesis_stats = self.synthesize.run(days=7)

        report = {
            "id": _new_id(),
            "type": "periodic",
            "scope": "full",
            "started_at": started_at,
            "completed_at": _now(),
            "digest": digest_stats,
            "synthesis": synthesis_stats,
            "weekly_digest": None,
        }

        self._save_report(report)
        LOG(f"Full reflection complete: digest={digest_stats}, synthesis={synthesis_stats}")
        return report

    async def run_weekly(self) -> dict:
        """Weekly deep reflection with digest generation."""
        LOG("Starting weekly reflection...")
        started_at = _now()

        # Run synchronously — SQLite connections are not thread-safe
        # Phase 1: Full digest
        digest_stats = self.digest.run()

        # Phase 2: Extended synthesis (30 days lookback)
        synthesis_stats = self.synthesize.run(days=30)

        # Phase 3: Generate weekly digest report
        weekly_digest = self.synthesize.generate_weekly_digest()

        # Phase 4: Update graph importance via PageRank
        try:
            self._update_graph_importance()
        except Exception as e:
            LOG(f"PageRank update error: {e}")

        report = {
            "id": _new_id(),
            "type": "weekly",
            "scope": "weekly",
            "started_at": started_at,
            "completed_at": _now(),
            "digest": digest_stats,
            "synthesis": synthesis_stats,
            "weekly_digest": weekly_digest,
        }

        self._save_report(report)
        LOG(f"Weekly reflection complete")
        return report

    def _run_digest_quick(self) -> dict:
        """Run a lightweight digest: only dedup and decay, skip contradiction analysis."""
        stats: dict = {
            "duplicates_merged": 0,
            "decay": {"checked": 0, "archived": 0, "kept": 0},
        }

        try:
            stats["duplicates_merged"] = self.digest.merge_duplicates()
        except Exception as e:
            LOG(f"quick merge_duplicates error: {e}")

        try:
            stats["decay"] = self.digest.apply_intelligent_decay()
        except Exception as e:
            LOG(f"quick apply_intelligent_decay error: {e}")

        return stats

    def _update_graph_importance(self) -> None:
        """Update graph node importance via PageRank."""
        try:
            from graph.query import GraphQuery
            from graph.store import GraphStore

            store = GraphStore(self.db)
            query = GraphQuery(store)
            query.update_importance()
            LOG("Graph importance updated via PageRank")
        except ImportError:
            LOG("graph.query not available, skipping PageRank update")
        except Exception as e:
            LOG(f"PageRank update failed: {e}")

    def _save_report(self, report: dict) -> str:
        """Save reflection report to DB. Returns report ID."""
        report_id = report.get("id", _new_id())
        report_type = report.get("type", "periodic")

        # Calculate period from report timing
        now = datetime.now(timezone.utc)
        if report_type == "weekly":
            period_start = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif report_type == "periodic":
            period_start = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            period_start = report.get("started_at", _now())
        period_end = report.get("completed_at", _now())

        # Extract stats for report fields
        digest = report.get("digest") or {}
        synthesis = report.get("synthesis") or {}

        try:
            self.db.execute(
                """INSERT INTO reflection_reports
                   (id, period_start, period_end, type,
                    new_nodes, patterns_found, skills_refined,
                    rules_proposed, contradictions, archived,
                    focus_areas, key_findings, proposed_changes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    report_id,
                    period_start,
                    period_end,
                    report_type,
                    synthesis.get("edges_strengthened", 0),
                    synthesis.get("clusters_found", 0),
                    synthesis.get("skills_proposed", 0),
                    0,  # rules_proposed
                    digest.get("contradictions_found", 0),
                    digest.get("decay", {}).get("archived", 0),
                    json.dumps((report.get("weekly_digest") or {}).get("focus_areas", [])),
                    json.dumps((report.get("weekly_digest") or {}).get("top_concepts", [])),
                    json.dumps(synthesis),
                    _now(),
                ),
            )
            self.db.commit()
            LOG(f"Saved reflection report: {report_id} ({report_type})")
        except Exception as e:
            LOG(f"Failed to save reflection report: {e}")

        return report_id

    def _get_pending_proposals(self) -> list[dict]:
        """Get pending proposals for user review."""
        rows = self.db.execute(
            """SELECT id, type, content, evidence, confidence, created_at
               FROM pending_proposals
               WHERE status = 'pending'
               ORDER BY confidence DESC, created_at DESC"""
        ).fetchall()

        proposals: list[dict] = []
        for row in rows:
            proposal = dict(row)
            # Parse JSON fields
            if isinstance(proposal.get("content"), str):
                try:
                    proposal["content"] = json.loads(proposal["content"])
                except (json.JSONDecodeError, TypeError):
                    pass
            if isinstance(proposal.get("evidence"), str):
                try:
                    proposal["evidence"] = json.loads(proposal["evidence"])
                except (json.JSONDecodeError, TypeError):
                    pass
            proposals.append(proposal)

        return proposals

    def approve_proposal(self, proposal_id: str) -> bool:
        """Mark proposal as approved and apply it.

        For skill proposals: creates the skill in the skills table.
        Returns True if proposal was found and approved.
        """
        row = self.db.execute(
            "SELECT id, type, content, status FROM pending_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()

        if not row:
            LOG(f"Proposal {proposal_id} not found")
            return False

        if row["status"] != "pending":
            LOG(f"Proposal {proposal_id} already {row['status']}")
            return False

        # Parse content
        content = row["content"]
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                content = {}

        proposal_type = row["type"]

        # Apply the proposal
        if proposal_type == "skill" and isinstance(content, dict):
            self._apply_skill_proposal(content)

        # Mark as approved
        self.db.execute(
            """UPDATE pending_proposals
               SET status = 'approved', reviewed_at = ?
               WHERE id = ?""",
            (_now(), proposal_id),
        )
        self.db.commit()
        LOG(f"Approved proposal {proposal_id} ({proposal_type})")
        return True

    def reject_proposal(self, proposal_id: str) -> bool:
        """Mark proposal as rejected."""
        row = self.db.execute(
            "SELECT id, status FROM pending_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()

        if not row:
            LOG(f"Proposal {proposal_id} not found")
            return False

        if row["status"] != "pending":
            LOG(f"Proposal {proposal_id} already {row['status']}")
            return False

        self.db.execute(
            """UPDATE pending_proposals
               SET status = 'rejected', reviewed_at = ?
               WHERE id = ?""",
            (_now(), proposal_id),
        )
        self.db.commit()
        LOG(f"Rejected proposal {proposal_id}")
        return True

    def _apply_skill_proposal(self, content: dict) -> None:
        """Create a skill from an approved proposal."""
        skill_id = _new_id()
        name = content.get("skill_name", f"skill_{skill_id[:8]}")
        trigger = content.get("trigger_pattern", "")
        steps = content.get("steps", [])
        projects = content.get("projects", [])
        episode_ids = content.get("episode_ids", [])

        try:
            self.db.execute(
                """INSERT INTO skills
                   (id, name, trigger_pattern, steps, anti_patterns,
                    times_used, success_rate, projects, stack,
                    related_skills, learned_from, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 'draft', ?)""",
                (
                    skill_id,
                    name,
                    trigger,
                    json.dumps(steps),
                    json.dumps([]),
                    content.get("success_rate", 0.0),
                    json.dumps(projects),
                    json.dumps([]),
                    json.dumps([]),
                    json.dumps(episode_ids),
                    _now(),
                ),
            )
            LOG(f"Created skill from proposal: {name} ({skill_id})")
        except sqlite3.IntegrityError:
            LOG(f"Skill {name} already exists, skipping")
