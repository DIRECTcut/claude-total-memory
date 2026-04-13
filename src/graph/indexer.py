"""
Graph Indexer — Parse CLAUDE.md rules, skills, and conventions into the knowledge graph.

Reads markdown files (CLAUDE.md, rules/*.md, skills/*/SKILL.md) and creates
structured graph nodes (rule, convention, prohibition, skill, technology, concept)
with edges linking them together.

All node IDs are UUID hex strings. Timestamps are ISO 8601 with Z suffix.
Source field marks origin: 'claude_md', 'skill', 'rule_file'.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG = lambda msg: sys.stderr.write(f"[memory-indexer] {msg}\n")

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

TECHNOLOGIES: set[str] = {
    "go", "golang", "php", "symfony", "python", "javascript", "typescript",
    "vue", "nuxt", "react", "docker", "postgresql", "postgres", "redis",
    "rabbitmq", "grpc", "rest", "graphql", "nginx", "git", "linux",
    "kubernetes", "terraform", "aws", "stripe", "telegram", "sqlite",
    "chromadb", "ollama", "tailwind", "pinia", "laravel", "django",
    "fastapi", "flask", "celery", "protobuf", "prometheus", "monolog",
    "doctrine", "alembic", "sqlalchemy", "pydantic", "pytest", "phpunit",
    "phpstan", "eslint", "ruff", "mypy", "slog", "chi", "pgx",
    "bitrix", "bitrix24", "makefile", "compose",
}

PROHIBITION_MARKERS: list[str] = [
    "ЗАПРЕЩЕНО", "НИКОГДА", "NEVER", "КАТЕГОРИЧЕСКИ",
    "forbidden", "DO NOT", "don't", "NEVER",
    "НЕ ИСПОЛЬЗОВАТЬ", "НЕ ДЕЛАТЬ", "АБСОЛЮТНЫЙ ЗАПРЕТ",
]

CONVENTION_MARKERS: list[str] = [
    "ВСЕГДА", "ALWAYS", "ОБЯЗАТЕЛЬНО", "ДОЛЖЕН", "MUST",
    "ОБЯЗАН", "предпочтительно", "preferred", "recommended",
    "по умолчанию", "default", "convention",
]

# Default paths
DEFAULT_CLAUDE_MD: str = str(Path.home() / ".claude" / "CLAUDE.md")
DEFAULT_SKILLS_DIR: str = str(Path.home() / ".claude" / "skills")
DEFAULT_RULES_DIR: str = str(Path.home() / ".claude" / "rules")


def _now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    """Generate a new UUID hex string."""
    return uuid.uuid4().hex


class GraphIndexer:
    """Index CLAUDE.md rules, skills, and conventions into the knowledge graph."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self.db.row_factory = sqlite3.Row

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def index_claude_md(self, path: str | None = None) -> dict[str, int]:
        """Parse CLAUDE.md and create graph nodes for each rule/convention/prohibition.

        Default paths checked:
        - ~/.claude/CLAUDE.md (global)

        Returns: {"nodes_created": int, "edges_created": int, "sections_parsed": int}
        """
        md_path = Path(path) if path else Path(DEFAULT_CLAUDE_MD)

        if not md_path.exists():
            LOG(f"CLAUDE.md not found at {md_path}")
            return {"nodes_created": 0, "edges_created": 0, "sections_parsed": 0}

        content = md_path.read_text(encoding="utf-8")
        if not content.strip():
            LOG(f"CLAUDE.md is empty: {md_path}")
            return {"nodes_created": 0, "edges_created": 0, "sections_parsed": 0}

        rules = self._parse_claude_md(content)
        LOG(f"Parsed {len(rules)} rules from {md_path}")

        nodes_created = 0
        edges_created = 0
        sections_seen: set[str] = set()

        # Create a root node for CLAUDE.md itself
        root_id = self._get_or_create_node(
            name="CLAUDE.md",
            type="doc",
            content="Global Claude Code Rules",
            source="claude_md",
        )

        for rule in rules:
            sections_seen.add(rule["section"])

            # Create the rule node
            rule_id = self._get_or_create_node(
                name=self._make_rule_name(rule["text"], rule["section"]),
                type=rule["type"],
                content=rule["text"],
                source="claude_md",
                properties={"section": rule["section"]},
            )
            nodes_created += 1

            # Link rule -> CLAUDE.md
            self._add_edge(rule_id, root_id, "part_of", weight=0.8,
                           context=f"Section: {rule['section']}")
            edges_created += 1

            # Link rule -> technologies
            for tech in rule["technologies"]:
                tech_id = self._get_or_create_node(
                    name=tech, type="technology", source="claude_md",
                )
                self._add_edge(rule_id, tech_id, "applies_to", weight=0.7,
                               context=rule["section"])
                edges_created += 1

            # Create section node and link
            section_id = self._get_or_create_node(
                name=rule["section"],
                type="concept",
                source="claude_md",
            )
            self._add_edge(rule_id, section_id, "part_of", weight=0.5)
            edges_created += 1

        LOG(f"Indexed CLAUDE.md: {nodes_created} nodes, {edges_created} edges, "
            f"{len(sections_seen)} sections")

        return {
            "nodes_created": nodes_created,
            "edges_created": edges_created,
            "sections_parsed": len(sections_seen),
        }

    def index_skills(self, skills_dir: str | None = None) -> dict[str, int]:
        """Parse all skill SKILL.md files and create graph nodes.

        For each skill:
        - Create node (type='skill')
        - Link to technologies it covers
        - Link to concepts it mentions

        Returns: {"skills_indexed": int, "nodes_created": int, "edges_created": int}
        """
        sdir = Path(skills_dir) if skills_dir else Path(DEFAULT_SKILLS_DIR)

        if not sdir.exists():
            LOG(f"Skills directory not found: {sdir}")
            return {"skills_indexed": 0, "nodes_created": 0, "edges_created": 0}

        skills_indexed = 0
        nodes_created = 0
        edges_created = 0

        for skill_dir in sorted(sdir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            parsed = self._parse_skill(skill_md)
            if parsed is None:
                continue

            # Create skill node
            skill_id = self._get_or_create_node(
                name=parsed["name"],
                type="skill",
                content=parsed["description"],
                source="skill",
                properties={
                    "triggers": parsed["triggers"],
                    "path": str(skill_md),
                },
            )
            nodes_created += 1
            skills_indexed += 1

            # Link to technologies
            for tech in parsed["technologies"]:
                tech_id = self._get_or_create_node(
                    name=tech, type="technology", source="skill",
                )
                self._add_edge(skill_id, tech_id, "uses", weight=0.9,
                               context=f"Skill: {parsed['name']}")
                edges_created += 1
                nodes_created += 1

            # Link to concepts
            for concept in parsed["concepts"]:
                concept_id = self._get_or_create_node(
                    name=concept, type="concept", source="skill",
                )
                self._add_edge(skill_id, concept_id, "provides", weight=0.7,
                               context=f"Skill: {parsed['name']}")
                edges_created += 1
                nodes_created += 1

        LOG(f"Indexed {skills_indexed} skills: {nodes_created} nodes, {edges_created} edges")

        return {
            "skills_indexed": skills_indexed,
            "nodes_created": nodes_created,
            "edges_created": edges_created,
        }

    def index_rules_dir(self, rules_dir: str | None = None) -> dict[str, int]:
        """Parse ~/.claude/rules/*.md files (go.md, php.md, etc.)

        Returns: {"rules_indexed": int, "nodes_created": int, "edges_created": int}
        """
        rdir = Path(rules_dir) if rules_dir else Path(DEFAULT_RULES_DIR)

        if not rdir.exists():
            LOG(f"Rules directory not found: {rdir}")
            return {"rules_indexed": 0, "nodes_created": 0, "edges_created": 0}

        rules_indexed = 0
        nodes_created = 0
        edges_created = 0

        for md_file in sorted(rdir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            if not content.strip():
                continue

            file_stem = md_file.stem  # e.g., "go", "php", "docker"
            file_label = f"rules/{md_file.name}"

            # Create doc node for the rules file
            doc_id = self._get_or_create_node(
                name=file_label,
                type="doc",
                content=f"Language/domain rules: {file_stem}",
                source="rule_file",
                properties={"path": str(md_file)},
            )

            # Parse rules from the file content
            parsed_rules = self._parse_claude_md(content)

            for rule in parsed_rules:
                rule_id = self._get_or_create_node(
                    name=self._make_rule_name(rule["text"], f"{file_stem}/{rule['section']}"),
                    type=rule["type"],
                    content=rule["text"],
                    source="rule_file",
                    properties={"section": rule["section"], "file": file_label},
                )
                nodes_created += 1

                # Link rule -> doc
                self._add_edge(rule_id, doc_id, "part_of", weight=0.8)
                edges_created += 1

                # Link to technologies
                for tech in rule["technologies"]:
                    tech_id = self._get_or_create_node(
                        name=tech, type="technology", source="rule_file",
                    )
                    self._add_edge(rule_id, tech_id, "applies_to", weight=0.7)
                    edges_created += 1

            rules_indexed += 1
            LOG(f"Indexed {md_file.name}: {len(parsed_rules)} rules")

        LOG(f"Indexed {rules_indexed} rule files: {nodes_created} nodes, {edges_created} edges")

        return {
            "rules_indexed": rules_indexed,
            "nodes_created": nodes_created,
            "edges_created": edges_created,
        }

    def reindex_all(self) -> dict[str, Any]:
        """Full reindex: CLAUDE.md + skills + rules. Clears old indexed nodes first."""
        LOG("Starting full reindex...")

        # Delete nodes from previous indexing (by source)
        deleted = self._clear_indexed_nodes()
        LOG(f"Cleared {deleted} previously indexed nodes")

        claude_stats = self.index_claude_md()
        skills_stats = self.index_skills()
        rules_stats = self.index_rules_dir()

        total = {
            "cleared_old_nodes": deleted,
            "claude_md": claude_stats,
            "skills": skills_stats,
            "rules": rules_stats,
            "total_nodes": (claude_stats["nodes_created"]
                           + skills_stats["nodes_created"]
                           + rules_stats["nodes_created"]),
            "total_edges": (claude_stats["edges_created"]
                           + skills_stats["edges_created"]
                           + rules_stats["edges_created"]),
        }

        LOG(f"Reindex complete: {total['total_nodes']} nodes, {total['total_edges']} edges")
        return total

    # ──────────────────────────────────────────────
    # Parsing
    # ──────────────────────────────────────────────

    def _parse_claude_md(self, content: str) -> list[dict[str, Any]]:
        """Parse CLAUDE.md-style markdown into structured rules.

        Returns list of:
        {
            "text": str,           # rule text
            "section": str,        # parent section title
            "type": str,           # "rule" | "convention" | "prohibition"
            "technologies": [str], # auto-detected technologies
        }
        """
        rules: list[dict[str, Any]] = []
        sections = self._split_sections(content)

        for section_title, section_body in sections:
            # Extract bullet points, numbered items, standalone lines
            items = self._extract_items(section_body)

            for item_text in items:
                text = item_text.strip()
                if len(text) < 10:
                    continue  # skip too-short fragments

                rule_type = self._classify_rule(text)
                technologies = self._detect_technologies(text)

                rules.append({
                    "text": text,
                    "section": section_title,
                    "type": rule_type,
                    "technologies": technologies,
                })

        return rules

    def _split_sections(self, content: str) -> list[tuple[str, str]]:
        """Split markdown into (title, body) tuples by ## headers.

        Also handles ### headers as subsections within the parent ## section.
        Returns the parent title for subsections as "Parent / Subsection".
        """
        sections: list[tuple[str, str]] = []

        # Match ## and ### headers
        header_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
        matches = list(header_pattern.finditer(content))

        if not matches:
            # No headers found — treat entire content as one section
            stripped = content.strip()
            if stripped:
                sections.append(("Root", stripped))
            return sections

        parent_title = "Root"

        for i, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()

            # Determine section body: from end of this header to start of next
            body_start = match.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[body_start:body_end].strip()

            if level == 2:
                parent_title = title
                section_name = title
            else:  # level == 3
                section_name = f"{parent_title} / {title}"

            if body:
                sections.append((section_name, body))

        return sections

    def _extract_items(self, text: str) -> list[str]:
        """Extract individual rule items from a section body.

        Handles:
        - Bullet points (-, *, +)
        - Numbered lists (1., 2.)
        - Bold/highlighted lines (starting with **)
        - Non-code standalone lines that look like rules
        """
        items: list[str] = []
        in_code_block = False
        current_item: list[str] = []

        for line in text.split("\n"):
            stripped = line.strip()

            # Track code blocks — skip their content
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                # If we were building an item, flush it before code block
                if current_item:
                    items.append(" ".join(current_item))
                    current_item = []
                continue

            if in_code_block:
                continue

            # Skip empty lines (flush current item)
            if not stripped:
                if current_item:
                    items.append(" ".join(current_item))
                    current_item = []
                continue

            # Skip table rows and horizontal rules
            if stripped.startswith("|") or stripped.startswith("---"):
                continue

            # Bullet points: -, *, +
            bullet_match = re.match(r"^[-*+]\s+(.+)$", stripped)
            if bullet_match:
                if current_item:
                    items.append(" ".join(current_item))
                    current_item = []
                current_item.append(bullet_match.group(1))
                continue

            # Numbered lists: 1., 2.
            number_match = re.match(r"^\d+\.\s+(.+)$", stripped)
            if number_match:
                if current_item:
                    items.append(" ".join(current_item))
                    current_item = []
                current_item.append(number_match.group(1))
                continue

            # Continuation of a bullet/numbered item (indented)
            if line.startswith("  ") and current_item:
                current_item.append(stripped)
                continue

            # Standalone meaningful line (bold headers, key statements)
            if stripped.startswith("**") or stripped.startswith("#"):
                if current_item:
                    items.append(" ".join(current_item))
                    current_item = []
                # Clean up markdown bold markers for node content
                clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
                clean = re.sub(r"^#+\s*", "", clean)
                if len(clean) >= 10:
                    current_item.append(clean)
                continue

            # Other lines — if they look like a rule (contain key words)
            if self._looks_like_rule(stripped):
                if current_item:
                    items.append(" ".join(current_item))
                    current_item = []
                current_item.append(stripped)

        # Flush remaining
        if current_item:
            items.append(" ".join(current_item))

        return items

    def _parse_skill(self, path: Path) -> dict[str, Any] | None:
        """Parse a skill SKILL.md file.

        Returns:
        {
            "name": str,
            "description": str,
            "technologies": [str],
            "concepts": [str],
            "triggers": [str],
        }
        """
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            LOG(f"Failed to read skill: {path}: {e}")
            return None

        if not content.strip():
            return None

        name = path.parent.name  # directory name is the skill name

        # Extract frontmatter
        description = ""
        triggers: list[str] = []

        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if frontmatter_match:
            fm = frontmatter_match.group(1)
            # Extract name from frontmatter
            name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
            if name_match:
                name = name_match.group(1).strip().strip('"').strip("'")

            # Extract description
            desc_match = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', fm,
                                   re.MULTILINE | re.DOTALL)
            if desc_match:
                description = desc_match.group(1).strip().strip('"').strip("'")

            # Extract triggers from description (phrases after "when")
            if description:
                trigger_match = re.search(
                    r"(?:Use when|when the user|when)\s+(.+?)(?:\.|$)",
                    description, re.IGNORECASE,
                )
                if trigger_match:
                    trigger_text = trigger_match.group(1)
                    # Split on commas and "or"
                    parts = re.split(r",\s*|\s+or\s+", trigger_text)
                    triggers = [p.strip() for p in parts if len(p.strip()) > 5]

        # Detect technologies from full content
        technologies = self._detect_technologies(content)

        # Detect concepts from headings and key terms
        concepts = self._detect_concepts(content)

        # If no description from frontmatter, use first paragraph after first heading
        if not description:
            body = content
            if frontmatter_match:
                body = content[frontmatter_match.end():]
            first_para = re.search(r"^[^#\n].{20,}", body, re.MULTILINE)
            if first_para:
                description = first_para.group(0)[:200]

        return {
            "name": name,
            "description": description,
            "technologies": technologies,
            "concepts": concepts,
            "triggers": triggers,
        }

    # ──────────────────────────────────────────────
    # Classification & Detection
    # ──────────────────────────────────────────────

    def _classify_rule(self, text: str) -> str:
        """Classify rule text as 'rule', 'convention', or 'prohibition'."""
        upper = text.upper()

        # Check prohibition first (stronger signal)
        for marker in PROHIBITION_MARKERS:
            if marker.upper() in upper:
                return "prohibition"

        # Check convention markers
        for marker in CONVENTION_MARKERS:
            if marker.upper() in upper:
                return "convention"

        return "rule"

    def _detect_technologies(self, text: str) -> list[str]:
        """Find technology keywords in text (case-insensitive)."""
        lower = text.lower()
        found: list[str] = []

        for tech in TECHNOLOGIES:
            # Word boundary match to avoid partial matches
            # e.g., "go" shouldn't match "going"
            pattern = rf"\b{re.escape(tech)}\b"
            if re.search(pattern, lower):
                found.append(tech)

        # Normalize aliases
        normalized: list[str] = []
        seen: set[str] = set()
        for t in found:
            canonical = self._normalize_tech(t)
            if canonical not in seen:
                seen.add(canonical)
                normalized.append(canonical)

        return normalized

    def _detect_concepts(self, text: str) -> list[str]:
        """Extract concept-like phrases from text.

        Looks for:
        - Markdown headings (## / ###)
        - Bold terms (**term**)
        - Technical compound terms (e.g., "error handling", "dependency injection")
        """
        concepts: set[str] = set()

        # Extract headings
        for match in re.finditer(r"^#{1,4}\s+(.+)$", text, re.MULTILINE):
            heading = match.group(1).strip()
            # Clean markdown formatting
            heading = re.sub(r"[*_`]", "", heading)
            heading = re.sub(r"\s*[-—]\s*.+$", "", heading)  # remove dash suffixes
            if 3 <= len(heading) <= 60:
                concepts.add(heading.lower())

        # Extract bold terms
        for match in re.finditer(r"\*\*([^*]{3,40})\*\*", text):
            term = match.group(1).strip().lower()
            # Skip if it's just a technology name (already handled)
            if term not in TECHNOLOGIES and len(term) > 3:
                concepts.add(term)

        # Common architecture/development concepts
        known_concepts = [
            "dependency injection", "constructor injection", "service locator",
            "middleware", "interceptor", "error handling", "logging",
            "testing", "metrics", "observability", "caching", "pagination",
            "authentication", "authorization", "validation", "serialization",
            "migration", "deployment", "ci/cd", "code review",
            "single responsibility", "contract first", "facade pattern",
            "structured logging", "health check", "rate limiting",
            "event sourcing", "message queue", "connection pooling",
            "thin controller", "domain driven", "repository pattern",
        ]
        lower = text.lower()
        for concept in known_concepts:
            if concept in lower:
                concepts.add(concept)

        return sorted(concepts)

    def _looks_like_rule(self, text: str) -> bool:
        """Check if a standalone line looks like a rule statement."""
        # Must be meaningful length
        if len(text) < 15:
            return False

        # Check for rule-like patterns
        patterns = [
            r"(?i)^(ВСЕГДА|НИКОГДА|ALWAYS|NEVER|MUST|SHOULD|ОБЯЗАТЕЛЬНО|ЗАПРЕЩЕНО)",
            r"(?i)(правило|rule|convention|принцип|standard):",
            r"(?i)^(использовать|не использовать|применять)",
            r"(?i)^(все|каждый|любой)\s+",
        ]
        for p in patterns:
            if re.search(p, text):
                return True

        return False

    @staticmethod
    def _normalize_tech(tech: str) -> str:
        """Normalize technology name aliases to canonical form."""
        aliases: dict[str, str] = {
            "golang": "go",
            "postgres": "postgresql",
            "compose": "docker",
        }
        return aliases.get(tech, tech)

    @staticmethod
    def _make_rule_name(text: str, section: str) -> str:
        """Create a short, unique-ish name for a rule node.

        Format: "section: first_N_words" (max 80 chars).
        """
        # Clean text for naming
        clean = re.sub(r"[*_`#\[\]]", "", text)
        clean = re.sub(r"\s+", " ", clean).strip()

        # Take first ~60 chars, break at word boundary
        if len(clean) > 60:
            clean = clean[:60].rsplit(" ", 1)[0] + "..."

        # Truncate section too
        short_section = section[:30] if len(section) > 30 else section

        name = f"{short_section}: {clean}"
        return name[:80]

    # ──────────────────────────────────────────────
    # Graph Operations (thin wrappers)
    # ──────────────────────────────────────────────

    def _get_or_create_node(
        self,
        name: str,
        type: str,
        content: str | None = None,
        source: str = "auto",
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Get existing node by name+type or create new. Returns node_id."""
        row = self.db.execute(
            "SELECT id FROM graph_nodes WHERE name = ? AND type = ?",
            (name, type),
        ).fetchone()

        if row:
            node_id = row["id"]
            # Update last_seen and mention_count
            self.db.execute(
                """UPDATE graph_nodes
                   SET last_seen_at = ?, mention_count = mention_count + 1
                   WHERE id = ?""",
                (_now(), node_id),
            )
            self.db.commit()
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
        return node_id

    def _add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
        context: str | None = None,
    ) -> str:
        """Add edge, reinforcing weight if it already exists. Returns edge_id."""
        if source_id == target_id:
            return ""

        # Check for existing edge
        row = self.db.execute(
            """SELECT id, weight FROM graph_edges
               WHERE source_id = ? AND target_id = ? AND relation_type = ?""",
            (source_id, target_id, relation_type),
        ).fetchone()

        if row:
            edge_id = row["id"]
            new_weight = min(row["weight"] + 0.1, 10.0)
            self.db.execute(
                """UPDATE graph_edges
                   SET weight = ?, last_reinforced_at = ?,
                       reinforcement_count = reinforcement_count + 1,
                       context = COALESCE(?, context)
                   WHERE id = ?""",
                (new_weight, _now(), context, edge_id),
            )
            self.db.commit()
            return edge_id

        edge_id = _new_id()
        self.db.execute(
            """INSERT INTO graph_edges
               (id, source_id, target_id, relation_type, weight, context, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (edge_id, source_id, target_id, relation_type, weight, context, _now()),
        )
        self.db.commit()
        return edge_id

    def _clear_indexed_nodes(self) -> int:
        """Delete all nodes previously created by indexing (source in claude_md, skill, rule_file).

        Also cleans up orphaned edges via CASCADE.
        Returns count of deleted nodes.
        """
        # First delete edges pointing to/from these nodes
        self.db.execute(
            """DELETE FROM graph_edges
               WHERE source_id IN (
                   SELECT id FROM graph_nodes WHERE source IN ('claude_md', 'skill', 'rule_file')
               )
               OR target_id IN (
                   SELECT id FROM graph_nodes WHERE source IN ('claude_md', 'skill', 'rule_file')
               )"""
        )

        # Delete knowledge_nodes links
        self.db.execute(
            """DELETE FROM knowledge_nodes
               WHERE node_id IN (
                   SELECT id FROM graph_nodes WHERE source IN ('claude_md', 'skill', 'rule_file')
               )"""
        )

        # Delete the nodes
        cursor = self.db.execute(
            "DELETE FROM graph_nodes WHERE source IN ('claude_md', 'skill', 'rule_file')"
        )
        self.db.commit()

        return cursor.rowcount


# ──────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────

def main() -> None:
    """Run indexer from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Index CLAUDE.md rules into knowledge graph")
    parser.add_argument("--db", default=str(Path.home() / ".claude-memory" / "memory.db"),
                        help="Path to SQLite database")
    parser.add_argument("--claude-md", default=None, help="Path to CLAUDE.md")
    parser.add_argument("--skills-dir", default=None, help="Path to skills directory")
    parser.add_argument("--rules-dir", default=None, help="Path to rules directory")
    parser.add_argument("--reindex", action="store_true", help="Full reindex (clear + index)")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")

    indexer = GraphIndexer(db)

    if args.reindex:
        result = indexer.reindex_all()
    else:
        result = {}
        result["claude_md"] = indexer.index_claude_md(args.claude_md)
        result["skills"] = indexer.index_skills(args.skills_dir)
        result["rules"] = indexer.index_rules_dir(args.rules_dir)

    import json
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
