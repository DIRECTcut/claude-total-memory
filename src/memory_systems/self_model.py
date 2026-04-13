"""
Meta-Cognitive Memory — self-assessment of competencies, blind spots, and user model.

Tracks:
- Competency levels per domain (updated from episode outcomes)
- Blind spots (recurring failure patterns or frustration areas)
- User model (preferences, communication style, expertise areas)
"""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

LOG = lambda msg: sys.stderr.write(f"[memory-self] {msg}\n")

_TREND_VALUES = {"improving", "stable", "declining", "stable_low", "unknown"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _json_loads(text: str | None, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class SelfModel:
    """Manages meta-cognitive memory: competencies, blind spots, user model."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Competencies
    # ------------------------------------------------------------------

    def update_competency(
        self,
        domain: str,
        outcome: str,
        frustration_signals: int = 0,
    ) -> None:
        """
        Update competency based on episode outcome.

        Adjustments:
          - 'breakthrough' -> level +0.02, confidence +0.05
          - 'discovery'    -> level +0.01, confidence +0.03
          - 'routine'      -> level +0.005, confidence +0.02
          - 'failure'      -> level -0.01, confidence +0.03 (we learned something)

        If frustration_signals > 3, log as candidate blind spot.
        """
        adjustments = {
            "breakthrough": (0.02, 0.05),
            "discovery": (0.01, 0.03),
            "routine": (0.005, 0.02),
            "failure": (-0.01, 0.03),
        }
        level_delta, conf_delta = adjustments.get(outcome, (0.0, 0.01))
        now = _now_iso()

        # Try to get existing competency
        cur = self.db.execute(
            "SELECT level, confidence, based_on FROM competencies WHERE domain = ?",
            (domain,),
        )
        row = cur.fetchone()

        if row:
            new_level = _clamp(float(row[0]) + level_delta)
            new_conf = _clamp(float(row[1]) + conf_delta)
            new_based_on = int(row[2]) + 1

            self.db.execute(
                """UPDATE competencies
                SET level = ?, confidence = ?, based_on = ?, last_updated = ?
                WHERE domain = ?""",
                (round(new_level, 4), round(new_conf, 4), new_based_on, now, domain),
            )
        else:
            # Initial competency: start at 0.5
            new_level = _clamp(0.5 + level_delta)
            new_conf = _clamp(0.3 + conf_delta)

            self.db.execute(
                """INSERT INTO competencies (domain, level, confidence, based_on, trend, last_updated)
                VALUES (?, ?, ?, 1, 'unknown', ?)""",
                (domain, round(new_level, 4), round(new_conf, 4), now),
            )

        self.db.commit()
        LOG(f"competency '{domain}' updated: outcome={outcome}, delta={level_delta:+.3f}")

        # Detect candidate blind spot from high frustration
        if frustration_signals > 3:
            self.add_blind_spot(
                description=f"High frustration ({frustration_signals} signals) in domain '{domain}'",
                domains=[domain],
                evidence=[f"frustration_signals={frustration_signals}, outcome={outcome}"],
                severity=min(1.0, frustration_signals * 0.1),
            )

    def get_competency(self, domain: str) -> dict[str, Any] | None:
        """Get competency for a specific domain."""
        cur = self.db.execute(
            "SELECT domain, level, confidence, based_on, trend, last_updated "
            "FROM competencies WHERE domain = ?",
            (domain,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "domain": row[0],
            "level": float(row[1]),
            "confidence": float(row[2]),
            "based_on": int(row[3]),
            "trend": row[4],
            "last_updated": row[5],
        }

    def assess(self, concepts: list[str]) -> dict[str, Any]:
        """
        Assess competency for a set of concepts.
        Returns aggregated level, confidence, related blind spots, and advisory note.
        """
        if not concepts:
            return {
                "level": 0.5,
                "confidence": 0.0,
                "blind_spots": [],
                "note": "No concepts provided",
            }

        levels: list[float] = []
        confidences: list[float] = []
        found_domains: list[str] = []

        for concept in concepts:
            comp = self.get_competency(concept)
            if comp:
                levels.append(comp["level"])
                confidences.append(comp["confidence"])
                found_domains.append(concept)

        if not levels:
            # No data for any concept
            blind_spots = self.check_blind_spots(concepts)
            return {
                "level": 0.5,
                "confidence": 0.0,
                "blind_spots": blind_spots,
                "note": "Unknown — no prior data for these concepts",
            }

        avg_level = sum(levels) / len(levels)
        avg_conf = sum(confidences) / len(confidences)
        blind_spots = self.check_blind_spots(concepts)

        if avg_level > 0.8:
            note = "Strong"
        elif avg_level > 0.5:
            note = "Moderate"
        else:
            note = "Weak — be cautious"

        if blind_spots:
            note += f" (but {len(blind_spots)} active blind spot(s))"

        return {
            "level": round(avg_level, 3),
            "confidence": round(avg_conf, 3),
            "blind_spots": blind_spots,
            "note": note,
            "domains_found": found_domains,
        }

    def get_all_competencies(self) -> list[dict[str, Any]]:
        """Get all competency records."""
        cur = self.db.execute(
            "SELECT domain, level, confidence, based_on, trend, last_updated "
            "FROM competencies ORDER BY level DESC"
        )
        return [
            {
                "domain": row[0],
                "level": float(row[1]),
                "confidence": float(row[2]),
                "based_on": int(row[3]),
                "trend": row[4],
                "last_updated": row[5],
            }
            for row in cur.fetchall()
        ]

    def update_trends(self) -> None:
        """
        Analyze recent competency changes and update trend fields.

        Heuristic: compare current level against a baseline.
        With limited history (no separate history table), we use
        based_on count and current level as proxies:
          - level > 0.7 and based_on >= 5 -> 'improving'
          - level > 0.5 and based_on >= 5 -> 'stable'
          - level <= 0.3 and based_on >= 3 -> 'declining'
          - level <= 0.5 and based_on >= 5 -> 'stable_low'
          - else -> 'unknown'
        """
        cur = self.db.execute(
            "SELECT domain, level, based_on FROM competencies"
        )
        rows = cur.fetchall()

        for domain, level, based_on in rows:
            level = float(level)
            based_on = int(based_on)

            if based_on < 3:
                trend = "unknown"
            elif level > 0.7 and based_on >= 5:
                trend = "improving"
            elif level <= 0.3:
                trend = "declining"
            elif level <= 0.5:
                trend = "stable_low"
            else:
                trend = "stable"

            self.db.execute(
                "UPDATE competencies SET trend = ? WHERE domain = ?",
                (trend, domain),
            )

        self.db.commit()
        LOG(f"updated trends for {len(rows)} competencies")

    # ------------------------------------------------------------------
    # Blind Spots
    # ------------------------------------------------------------------

    def add_blind_spot(
        self,
        description: str,
        domains: list[str],
        evidence: list[str] | None = None,
        severity: float = 0.5,
    ) -> str:
        """
        Add a blind spot. Deduplicates by fuzzy matching on description
        (SequenceMatcher ratio > 0.75). If similar exists, appends evidence instead.
        Returns blind_spot_id.
        """
        # Check for existing similar blind spots
        cur = self.db.execute(
            "SELECT id, description, evidence FROM blind_spots WHERE status = 'active'"
        )
        for row in cur.fetchall():
            existing_desc = row[1]
            ratio = SequenceMatcher(None, description.lower(), existing_desc.lower()).ratio()
            if ratio > 0.75:
                # Append evidence to existing
                existing_evidence = _json_loads(row[2], [])
                new_evidence = existing_evidence + (evidence or [])
                self.db.execute(
                    "UPDATE blind_spots SET evidence = ?, severity = MAX(severity, ?) WHERE id = ?",
                    (_json_dumps(new_evidence), severity, row[0]),
                )
                self.db.commit()
                LOG(f"blind spot dedup: merged into {row[0]} (ratio={ratio:.2f})")
                return row[0]

        # No duplicate found, create new
        bs_id = uuid.uuid4().hex
        now = _now_iso()

        self.db.execute(
            """INSERT INTO blind_spots (id, description, domains, evidence, severity, status, discovered_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?)""",
            (
                bs_id, description,
                _json_dumps(domains),
                _json_dumps(evidence or []),
                _clamp(severity),
                now,
            ),
        )
        self.db.commit()
        LOG(f"added blind spot {bs_id}: {description[:60]}")
        return bs_id

    def resolve_blind_spot(self, blind_spot_id: str) -> None:
        """Mark a blind spot as resolved."""
        now = _now_iso()
        self.db.execute(
            "UPDATE blind_spots SET status = 'resolved', resolved_at = ? WHERE id = ?",
            (now, blind_spot_id),
        )
        self.db.commit()
        LOG(f"resolved blind spot {blind_spot_id}")

    def get_blind_spots(
        self,
        domain: str | None = None,
        status: str = "active",
    ) -> list[dict[str, Any]]:
        """Get blind spots, optionally filtered by domain and status."""
        conditions = ["status = ?"]
        params: list[Any] = [status]

        if domain:
            conditions.append("domains LIKE ?")
            params.append(f'%"{domain}"%')

        where = " AND ".join(conditions)
        cur = self.db.execute(
            f"""SELECT id, description, domains, evidence, severity, status, discovered_at, resolved_at
            FROM blind_spots WHERE {where} ORDER BY severity DESC""",
            params,
        )
        return [
            {
                "id": row[0],
                "description": row[1],
                "domains": _json_loads(row[2], []),
                "evidence": _json_loads(row[3], []),
                "severity": float(row[4]),
                "status": row[5],
                "discovered_at": row[6],
                "resolved_at": row[7],
            }
            for row in cur.fetchall()
        ]

    def check_blind_spots(self, concepts: list[str]) -> list[dict[str, Any]]:
        """Find active blind spots relevant to given concepts."""
        if not concepts:
            return []

        # Build OR conditions for domain matching
        conditions = " OR ".join(["domains LIKE ?" for _ in concepts])
        params = [f'%"{c}"%' for c in concepts]

        cur = self.db.execute(
            f"""SELECT id, description, domains, evidence, severity, status, discovered_at, resolved_at
            FROM blind_spots WHERE status = 'active' AND ({conditions})
            ORDER BY severity DESC""",
            params,
        )
        return [
            {
                "id": row[0],
                "description": row[1],
                "domains": _json_loads(row[2], []),
                "evidence": _json_loads(row[3], []),
                "severity": float(row[4]),
                "status": row[5],
                "discovered_at": row[6],
                "resolved_at": row[7],
            }
            for row in cur.fetchall()
        ]

    # ------------------------------------------------------------------
    # User Model
    # ------------------------------------------------------------------

    def update_user_model(
        self,
        key: str,
        value: str,
        confidence: float = 0.5,
    ) -> None:
        """Update or create user model entry. Increments evidence_count if exists."""
        now = _now_iso()

        cur = self.db.execute(
            "SELECT evidence_count FROM user_model WHERE key = ?",
            (key,),
        )
        row = cur.fetchone()

        if row:
            new_count = int(row[0]) + 1
            self.db.execute(
                """UPDATE user_model
                SET value = ?, confidence = ?, evidence_count = ?, last_updated = ?
                WHERE key = ?""",
                (value, _clamp(confidence), new_count, now, key),
            )
        else:
            self.db.execute(
                """INSERT INTO user_model (key, value, confidence, evidence_count, last_updated)
                VALUES (?, ?, ?, 1, ?)""",
                (key, value, _clamp(confidence), now),
            )

        self.db.commit()
        LOG(f"user model '{key}' updated")

    def get_user_model(self) -> dict[str, dict[str, Any]]:
        """Return full user model as {key: {value, confidence, evidence_count}}."""
        cur = self.db.execute(
            "SELECT key, value, confidence, evidence_count, last_updated FROM user_model"
        )
        return {
            row[0]: {
                "value": row[1],
                "confidence": float(row[2]),
                "evidence_count": int(row[3]),
                "last_updated": row[4],
            }
            for row in cur.fetchall()
        }

    def get_user_preference(self, key: str) -> str | None:
        """Get a single user model value by key."""
        cur = self.db.execute(
            "SELECT value FROM user_model WHERE key = ?",
            (key,),
        )
        row = cur.fetchone()
        return row[0] if row else None

    # ------------------------------------------------------------------
    # Full Report
    # ------------------------------------------------------------------

    def full_report(self) -> dict[str, Any]:
        """Complete self-model report: competencies, blind spots, user model, trends."""
        self.update_trends()

        competencies = self.get_all_competencies()
        blind_spots = self.get_blind_spots(status="active")
        user_model = self.get_user_model()

        # Summary stats
        levels = [c["level"] for c in competencies]
        avg_level = sum(levels) / len(levels) if levels else 0.5

        trend_counts: dict[str, int] = {}
        for c in competencies:
            t = c.get("trend", "unknown")
            trend_counts[t] = trend_counts.get(t, 0) + 1

        return {
            "competencies": competencies,
            "competency_count": len(competencies),
            "avg_level": round(avg_level, 3),
            "trend_summary": trend_counts,
            "blind_spots": blind_spots,
            "blind_spot_count": len(blind_spots),
            "user_model": user_model,
            "user_model_entries": len(user_model),
        }
