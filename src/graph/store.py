"""
Graph Store — CRUD operations for the knowledge graph.

Manages nodes, edges, and knowledge-node links in SQLite.
All IDs are UUID hex strings. Timestamps are ISO 8601 with Z suffix.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

LOG = lambda msg: sys.stderr.write(f"[memory-graph] {msg}\n")


def _now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    """Generate a new UUID hex string."""
    return uuid.uuid4().hex


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert a sqlite3.Row to a plain dict, parsing JSON fields."""
    if row is None:
        return None
    d = dict(row)
    if "properties" in d and isinstance(d["properties"], str):
        try:
            d["properties"] = json.loads(d["properties"])
        except (json.JSONDecodeError, TypeError):
            d["properties"] = {}
    return d


class GraphStore:
    """CRUD operations for graph_nodes, graph_edges, and knowledge_nodes."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    # ──────────────────────────────────────────────
    # Node CRUD
    # ──────────────────────────────────────────────

    def add_node(
        self,
        type: str,
        name: str,
        content: str | None = None,
        properties: dict | None = None,
        source: str = "auto",
    ) -> str:
        """Create or update a node. If a node with the same name+type exists, update it.

        Returns the node_id (existing or newly created).
        """
        existing = self.get_node_by_name(name, type)
        if existing:
            node_id = existing["id"]
            updates: dict[str, Any] = {
                "last_seen_at": _now(),
            }
            if content is not None:
                updates["content"] = content
            if properties is not None:
                updates["properties"] = json.dumps(properties)
            if source != "auto":
                updates["source"] = source

            # Increment mention_count
            self.db.execute(
                "UPDATE graph_nodes SET mention_count = mention_count + 1 WHERE id = ?",
                (node_id,),
            )

            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                values = list(updates.values()) + [node_id]
                self.db.execute(
                    f"UPDATE graph_nodes SET {set_clause} WHERE id = ?", values
                )

            self.db.commit()
            LOG(f"Node updated: {name} ({type}) -> {node_id}")
            return node_id

        node_id = _new_id()
        now = _now()
        self.db.execute(
            """INSERT INTO graph_nodes
               (id, type, name, content, properties, source, first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node_id,
                type,
                name,
                content,
                json.dumps(properties) if properties else None,
                source,
                now,
                now,
            ),
        )
        self.db.commit()
        LOG(f"Node created: {name} ({type}) -> {node_id}")
        return node_id

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Get a node by its ID."""
        row = self.db.execute(
            "SELECT * FROM graph_nodes WHERE id = ?", (node_id,)
        ).fetchone()
        return _row_to_dict(row)

    def get_node_by_name(self, name: str, type: str | None = None) -> dict[str, Any] | None:
        """Get a node by name, optionally filtered by type."""
        if type is not None:
            row = self.db.execute(
                "SELECT * FROM graph_nodes WHERE name = ? AND type = ?",
                (name, type),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT * FROM graph_nodes WHERE name = ?", (name,)
            ).fetchone()
        return _row_to_dict(row)

    def get_or_create(self, name: str, type: str, **kwargs: Any) -> str:
        """Get existing node by name+type or create a new one. Returns node_id."""
        existing = self.get_node_by_name(name, type)
        if existing:
            self.touch_node(existing["id"])
            return existing["id"]
        return self.add_node(type=type, name=name, **kwargs)

    def update_node(self, node_id: str, **kwargs: Any) -> bool:
        """Update node fields. Accepts: name, type, content, properties, source,
        importance, status. Returns True if the node was found and updated.
        """
        node = self.get_node(node_id)
        if node is None:
            LOG(f"update_node: node {node_id} not found")
            return False

        allowed = {"name", "type", "content", "properties", "source", "importance", "status"}
        updates = {}
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k == "properties":
                updates[k] = json.dumps(v) if isinstance(v, dict) else v
            else:
                updates[k] = v

        if not updates:
            return True  # nothing to update, but node exists

        updates["last_seen_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [node_id]
        self.db.execute(f"UPDATE graph_nodes SET {set_clause} WHERE id = ?", values)
        self.db.commit()
        return True

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its edges and knowledge links.

        Returns True if the node existed and was deleted.
        """
        node = self.get_node(node_id)
        if node is None:
            return False

        # CASCADE should handle edges, but be explicit for safety
        self.db.execute(
            "DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        )
        self.db.execute(
            "DELETE FROM knowledge_nodes WHERE node_id = ?", (node_id,)
        )
        self.db.execute("DELETE FROM graph_nodes WHERE id = ?", (node_id,))
        self.db.commit()
        LOG(f"Node deleted: {node_id}")
        return True

    def touch_node(self, node_id: str) -> None:
        """Update last_seen_at and increment mention_count."""
        self.db.execute(
            """UPDATE graph_nodes
               SET last_seen_at = ?, mention_count = mention_count + 1
               WHERE id = ?""",
            (_now(), node_id),
        )
        self.db.commit()

    # ──────────────────────────────────────────────
    # Edge CRUD
    # ──────────────────────────────────────────────

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
        context: str | None = None,
    ) -> str:
        """Create an edge or reinforce an existing one. Returns edge_id.

        Prevents self-loops. If edge already exists (same source, target, relation),
        reinforces it instead of creating a duplicate.
        """
        if source_id == target_id:
            LOG(f"add_edge: self-loop rejected ({source_id})")
            raise ValueError("Self-loops are not allowed")

        # Verify both nodes exist
        for nid in (source_id, target_id):
            if self.get_node(nid) is None:
                raise ValueError(f"Node {nid} does not exist")

        # Check for existing edge
        existing = self.db.execute(
            """SELECT id, weight, reinforcement_count FROM graph_edges
               WHERE source_id = ? AND target_id = ? AND relation_type = ?""",
            (source_id, target_id, relation_type),
        ).fetchone()

        if existing:
            edge_id = existing["id"]
            new_weight = min(existing["weight"] + 0.1, 10.0)
            self.db.execute(
                """UPDATE graph_edges
                   SET weight = ?, last_reinforced_at = ?,
                       reinforcement_count = reinforcement_count + 1,
                       context = COALESCE(?, context)
                   WHERE id = ?""",
                (new_weight, _now(), context, edge_id),
            )
            self.db.commit()
            LOG(f"Edge reinforced: {source_id} -[{relation_type}]-> {target_id} (w={new_weight:.2f})")
            return edge_id

        edge_id = _new_id()
        self.db.execute(
            """INSERT INTO graph_edges
               (id, source_id, target_id, relation_type, weight, context, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (edge_id, source_id, target_id, relation_type, weight, context, _now()),
        )
        self.db.commit()
        LOG(f"Edge created: {source_id} -[{relation_type}]-> {target_id}")
        return edge_id

    def get_edges(
        self,
        node_id: str,
        direction: str = "both",
        relation_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get edges for a node.

        Args:
            node_id: The node to query edges for.
            direction: 'outgoing', 'incoming', or 'both'.
            relation_types: Optional filter by relation types.

        Returns:
            List of edge dicts.
        """
        conditions: list[str] = []
        params: list[Any] = []

        if direction == "outgoing":
            conditions.append("source_id = ?")
            params.append(node_id)
        elif direction == "incoming":
            conditions.append("target_id = ?")
            params.append(node_id)
        else:  # both
            conditions.append("(source_id = ? OR target_id = ?)")
            params.extend([node_id, node_id])

        if relation_types:
            placeholders = ",".join("?" * len(relation_types))
            conditions.append(f"relation_type IN ({placeholders})")
            params.extend(relation_types)

        where = " AND ".join(conditions)
        rows = self.db.execute(
            f"SELECT * FROM graph_edges WHERE {where} ORDER BY weight DESC", params
        ).fetchall()
        return [dict(r) for r in rows]

    def reinforce_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight_delta: float = 0.1,
    ) -> None:
        """Strengthen an existing edge by adding to its weight."""
        self.db.execute(
            """UPDATE graph_edges
               SET weight = MIN(weight + ?, 10.0),
                   last_reinforced_at = ?,
                   reinforcement_count = reinforcement_count + 1
               WHERE source_id = ? AND target_id = ? AND relation_type = ?""",
            (weight_delta, _now(), source_id, target_id, relation_type),
        )
        self.db.commit()

    def weaken_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        factor: float = 0.5,
    ) -> None:
        """Weaken an existing edge by multiplying its weight by factor (0 < factor < 1)."""
        if not 0.0 < factor < 1.0:
            raise ValueError("factor must be between 0 and 1 (exclusive)")
        self.db.execute(
            """UPDATE graph_edges
               SET weight = weight * ?
               WHERE source_id = ? AND target_id = ? AND relation_type = ?""",
            (factor, source_id, target_id, relation_type),
        )
        self.db.commit()

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge by its ID. Returns True if it existed."""
        cursor = self.db.execute("DELETE FROM graph_edges WHERE id = ?", (edge_id,))
        self.db.commit()
        return cursor.rowcount > 0

    # ──────────────────────────────────────────────
    # Knowledge <-> Node linking
    # ──────────────────────────────────────────────

    def link_knowledge(
        self,
        knowledge_id: int,
        node_id: str,
        role: str = "related",
        strength: float = 1.0,
    ) -> None:
        """Link a knowledge record to a graph node.

        Uses INSERT OR REPLACE to handle duplicates — if the link exists,
        it will be updated with the new role and strength.
        """
        self.db.execute(
            """INSERT OR REPLACE INTO knowledge_nodes
               (knowledge_id, node_id, role, strength)
               VALUES (?, ?, ?, ?)""",
            (knowledge_id, node_id, role, strength),
        )
        self.db.commit()

    def get_knowledge_nodes(self, knowledge_id: int) -> list[dict[str, Any]]:
        """Get all graph nodes linked to a knowledge record."""
        rows = self.db.execute(
            """SELECT kn.role, kn.strength, gn.*
               FROM knowledge_nodes kn
               JOIN graph_nodes gn ON kn.node_id = gn.id
               WHERE kn.knowledge_id = ?
               ORDER BY kn.strength DESC""",
            (knowledge_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_node_knowledge(self, node_id: str) -> list[dict[str, Any]]:
        """Get all knowledge records linked to a graph node."""
        rows = self.db.execute(
            """SELECT kn.role, kn.strength, k.*
               FROM knowledge_nodes kn
               JOIN knowledge k ON kn.knowledge_id = k.id
               WHERE kn.node_id = ? AND k.status = 'active'
               ORDER BY kn.strength DESC""",
            (node_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────
    # Bulk operations
    # ──────────────────────────────────────────────

    def get_nodes(
        self,
        type: str | None = None,
        status: str = "active",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get nodes with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if type:
            conditions.append("type = ?")
            params.append(type)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.db.execute(
            f"""SELECT * FROM graph_nodes {where}
                ORDER BY importance DESC, last_seen_at DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def search_nodes(
        self, query: str, type: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Simple LIKE search on name and content fields."""
        pattern = f"%{query}%"
        conditions = ["(name LIKE ? OR content LIKE ?)"]
        params: list[Any] = [pattern, pattern]

        if type:
            conditions.append("type = ?")
            params.append(type)

        conditions.append("status = 'active'")
        where = " AND ".join(conditions)

        rows = self.db.execute(
            f"""SELECT * FROM graph_nodes WHERE {where}
                ORDER BY importance DESC, mention_count DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_neighbors(
        self, node_id: str, depth: int = 1
    ) -> list[tuple[str, float]]:
        """Get neighbor node_ids with edge weights via BFS.

        Returns list of (node_id, max_weight) tuples for all nodes
        reachable within the given depth. Includes both edge directions.
        """
        visited: dict[str, float] = {}
        frontier = {node_id}

        for _ in range(depth):
            if not frontier:
                break
            next_frontier: set[str] = set()
            for nid in frontier:
                edges = self.get_edges(nid, direction="both")
                for edge in edges:
                    neighbor = (
                        edge["target_id"]
                        if edge["source_id"] == nid
                        else edge["source_id"]
                    )
                    if neighbor == node_id:
                        continue  # skip origin
                    w = edge["weight"]
                    if neighbor not in visited or visited[neighbor] < w:
                        visited[neighbor] = w
                    if neighbor not in visited or neighbor in next_frontier:
                        next_frontier.add(neighbor)
            frontier = next_frontier - {node_id}

        return sorted(visited.items(), key=lambda x: x[1], reverse=True)

    def remove_orphans(self) -> int:
        """Remove nodes with no edges and no knowledge links.

        Returns the number of nodes removed.
        """
        cursor = self.db.execute(
            """DELETE FROM graph_nodes
               WHERE id NOT IN (
                   SELECT DISTINCT source_id FROM graph_edges
                   UNION
                   SELECT DISTINCT target_id FROM graph_edges
               )
               AND id NOT IN (
                   SELECT DISTINCT node_id FROM knowledge_nodes
               )"""
        )
        self.db.commit()
        count = cursor.rowcount
        if count > 0:
            LOG(f"Removed {count} orphan nodes")
        return count

    def remove_weak_edges(self, min_weight: float = 0.1) -> int:
        """Remove edges below the minimum weight threshold.

        Returns the number of edges removed.
        """
        cursor = self.db.execute(
            "DELETE FROM graph_edges WHERE weight < ?", (min_weight,)
        )
        self.db.commit()
        count = cursor.rowcount
        if count > 0:
            LOG(f"Removed {count} weak edges (weight < {min_weight})")
        return count

    def stats(self) -> dict[str, Any]:
        """Return graph statistics: node/edge counts by type, totals."""
        node_counts = {}
        for row in self.db.execute(
            "SELECT type, COUNT(*) as cnt FROM graph_nodes WHERE status = 'active' GROUP BY type"
        ).fetchall():
            node_counts[row["type"]] = row["cnt"]

        edge_counts = {}
        for row in self.db.execute(
            "SELECT relation_type, COUNT(*) as cnt FROM graph_edges GROUP BY relation_type"
        ).fetchall():
            edge_counts[row["relation_type"]] = row["cnt"]

        total_nodes = self.db.execute(
            "SELECT COUNT(*) FROM graph_nodes WHERE status = 'active'"
        ).fetchone()[0]
        total_edges = self.db.execute(
            "SELECT COUNT(*) FROM graph_edges"
        ).fetchone()[0]
        total_links = self.db.execute(
            "SELECT COUNT(*) FROM knowledge_nodes"
        ).fetchone()[0]

        avg_weight = self.db.execute(
            "SELECT AVG(weight) FROM graph_edges"
        ).fetchone()[0]

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_knowledge_links": total_links,
            "nodes_by_type": node_counts,
            "edges_by_type": edge_counts,
            "avg_edge_weight": round(avg_weight, 3) if avg_weight else 0.0,
        }
