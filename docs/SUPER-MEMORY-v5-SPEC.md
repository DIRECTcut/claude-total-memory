# Claude Super Memory v5.0 — Full Specification

## Cognitive Architecture for a Self-Learning AI Agent

> **Vision:** Not a database with search. A BRAIN — where every piece of knowledge
> is connected to dozens of others, every new task triggers a wave of activation
> across the entire network, and the system gets smarter with every session.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Architecture Overview](#2-architecture-overview)
3. [Layer 1 — Unified Ingestion Gateway](#3-layer-1--unified-ingestion-gateway)
4. [Layer 2 — Processing Pipeline](#4-layer-2--processing-pipeline)
5. [Layer 3 — Vectorization](#5-layer-3--vectorization)
6. [Layer 4 — Triple Storage + Knowledge Graph](#6-layer-4--triple-storage--knowledge-graph)
7. [Layer 5 — Reflection Agent ("Sleep")](#7-layer-5--reflection-agent-sleep)
8. [Layer 6 — Smart Output](#8-layer-6--smart-output)
9. [Seven Memory Systems](#9-seven-memory-systems)
10. [Associative Memory Engine](#10-associative-memory-engine)
11. [Unified Knowledge Graph](#11-unified-knowledge-graph)
12. [Cognitive Engine — Always-On Thinking](#12-cognitive-engine--always-on-thinking)
13. [Feedback Loop](#13-feedback-loop)
14. [Learning Metrics](#14-learning-metrics)
15. [Database Schema](#15-database-schema)
16. [MCP Tools (API)](#16-mcp-tools-api)
17. [Implementation Plan](#17-implementation-plan)
18. [File Structure](#18-file-structure)

---

## 1. Problem Statement

### Current state (v3.0) — "notebook, not a brain"

| What we have | What's wrong |
|---|---|
| 1738 flat text records | 65% (1142) never recalled — dead weight |
| Keyword + semantic search | No associative thinking, no spreading activation |
| 1 rule learned in 364 sessions | Self-improvement pipeline barely works |
| Rules in CLAUDE.md (static text) | Not connected to memories, not part of thinking |
| 50+ skills (static files) | Not linked to knowledge graph, invoked only by command |
| Facts saved | No episodes (HOW things happened), no narrative |
| No procedural memory | Doesn't learn HOW to do things, only WHAT happened |
| No self-model | Doesn't know own strengths, weaknesses, blind spots |
| No prediction | Can't anticipate what user needs |
| memory_recall on demand only | Doesn't activate relevant knowledge automatically |

### Target state (v5.0) — "brain"

| Aspect | v3 | v5 |
|---|---|---|
| **Remembers** | Facts | Facts + episodes + skills + self-knowledge |
| **Learns** | Almost never | Continuously: every session → skills, rules |
| **Recalls** | When asked | Proactively — context assembles automatically |
| **Forgets** | By timer (90 days) | Intelligently — by value, impact, usage |
| **Analyzes** | Duplicates | Patterns, contradictions, trends, clusters |
| **Knows itself** | No | Competencies, blind spots, tendencies |
| **Predicts** | No | "User opened ImPatient at 23:00 → likely deploy" |
| **Input** | Text via MCP only | Text + files + screenshots + Telegram + URLs |
| **Thinking** | Isolated search | Unified graph activation across ALL knowledge |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CLAUDE SUPER MEMORY v5.0                          │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Layer 1: INGESTION GATEWAY                                    │   │
│  │ ┌──────┐ ┌──────────┐ ┌───────────┐ ┌────────┐ ┌──────────┐│   │
│  │ │Claude│ │Telegram  │ │File Watch │ │Web Hook│ │URL Fetch ││   │
│  │ │ MCP  │ │  Bot     │ │~/Inbox/   │ │  POST  │ │ scraper  ││   │
│  │ └──┬───┘ └────┬─────┘ └─────┬─────┘ └───┬────┘ └────┬─────┘│   │
│  │    └──────────┴─────────────┴────────────┴───────────┘      │   │
│  │                          │                                    │   │
│  │                    ┌─────▼──────┐                             │   │
│  │                    │ Ingest     │                             │   │
│  │                    │ Queue      │                             │   │
│  └────────────────────┴─────┬──────┴────────────────────────────┘   │
│                             │                                        │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │ Layer 2: PROCESSING PIPELINE                                  │   │
│  │ ┌──────────┐ ┌──────────┐ ┌───────┐ ┌──────────┐            │   │
│  │ │  Type    │ │ Chunker  │ │  OCR  │ │ Concept  │            │   │
│  │ │ Detect   │ │ Semantic │ │ Apple │ │ Extractor│            │   │
│  │ └────┬─────┘ └────┬─────┘ └───┬───┘ └────┬─────┘            │   │
│  │      └────────────┴───────────┴───────────┘                  │   │
│  │                          │                                    │   │
│  │                    ┌─────▼──────┐                             │   │
│  │                    │  Ollama    │                             │   │
│  │                    │ Summarizer │                             │   │
│  └────────────────────┴─────┬──────┴────────────────────────────┘   │
│                             │                                        │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │ Layer 3: VECTORIZATION                                        │   │
│  │ ┌───────────────────┐  ┌──────────────────────┐              │   │
│  │ │ nomic-embed-text  │  │ nomic-embed-vision   │              │   │
│  │ │ (768-dim, text)   │  │ (768-dim, images)    │              │   │
│  │ └────────┬──────────┘  └──────────┬───────────┘              │   │
│  │          └──────────┬─────────────┘                          │   │
│  │              Binary Quantization (96 bytes)                   │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │                                            │
│  ┌──────────────────────▼───────────────────────────────────────┐   │
│  │ Layer 4: TRIPLE STORAGE + UNIFIED KNOWLEDGE GRAPH             │   │
│  │                                                                │   │
│  │  ┌─────────────┐  ┌──────────────────────┐  ┌──────────────┐ │   │
│  │  │  Vector     │  │   Knowledge Graph     │  │   Blob       │ │   │
│  │  │  Store      │  │                       │  │   Store      │ │   │
│  │  │             │  │  nodes: ALL types      │  │              │ │   │
│  │  │ embeddings  │  │  (rules, skills,      │  │ ~/.claude-   │ │   │
│  │  │ + binary    │  │   memories, episodes,  │  │  memory/     │ │   │
│  │  │ ANN index   │  │   concepts, entities,  │  │  blobs/      │ │   │
│  │  │             │  │   patterns, repos...)  │  │              │ │   │
│  │  │ "find       │  │                       │  │ originals:   │ │   │
│  │  │  similar"   │  │  edges: 20+ relation   │  │ files, imgs, │ │   │
│  │  │             │  │  types with weights   │  │ PDFs, code   │ │   │
│  │  └─────────────┘  └──────────────────────┘  └──────────────┘ │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │                                            │
│  ┌──────────────────────▼───────────────────────────────────────┐   │
│  │ Layer 5: REFLECTION AGENT ("sleep")                           │   │
│  │                                                                │   │
│  │  Phase 1: DIGEST     Phase 2: SYNTHESIZE   Phase 3: EVOLVE   │   │
│  │  • dedup/merge       • cluster episodes    • skill refinement │   │
│  │  • resolve conflicts • cross-project       • rule generation  │   │
│  │  • intelligent decay • graph enrichment    • self-model update│   │
│  │  • archive unused    • generalization      • CLAUDE.md evolve │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │                                            │
│  ┌──────────────────────▼───────────────────────────────────────┐   │
│  │ Layer 6: SMART OUTPUT                                         │   │
│  │                                                                │   │
│  │  ┌───────────────────────┐  ┌────────────────────────────┐   │   │
│  │  │  Cognitive Engine     │  │  CLAUDE.md Auto-Updater    │   │   │
│  │  │  (always-on)          │  │                            │   │   │
│  │  │                       │  │  • rules from patterns     │   │   │
│  │  │  • spreading          │  │  • project summaries       │   │   │
│  │  │    activation         │  │  • stale rules removal     │   │   │
│  │  │  • composition        │  │  • show diff to user       │   │   │
│  │  │  • predictive         │  │                            │   │   │
│  │  │    context            │  │                            │   │   │
│  │  └───────────────────────┘  └────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ◄═══════════════ FEEDBACK LOOP ═══════════════════════════════►    │
│  Results → Episode capture → Outcome evaluation → Signal extraction │
│  → Graph update → Skill refinement → Self-model update → Better!    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Layer 1 — Unified Ingestion Gateway

All inputs — text, files, images, URLs, Telegram messages — enter through a single
pipeline. Everything is normalized into an `IngestItem` before processing.

### Input Sources

| Source | How | What |
|---|---|---|
| **Claude MCP** | `memory_save()` tool call | Text, decisions, solutions from sessions |
| **Claude Hooks** | `session-end.sh` → transcript extraction | Session narratives, auto-summaries |
| **Telegram Bot** | `aiogram` webhook on localhost | Quick thoughts, screenshots, files, links |
| **File Watcher** | `watchdog` monitors `~/MemoryInbox/` | Drop a file → auto-ingested |
| **Web Hook** | POST to `localhost:37738/ingest` | External integrations (Obsidian, n8n, Shortcuts) |
| **URL Fetch** | Explicit or auto (from Telegram links) | Articles, GitHub repos, documentation |

### IngestItem Schema

```python
@dataclass
class IngestItem:
    id: str                     # UUID v7
    source: str                 # "claude_mcp" | "telegram" | "file_watch" | "webhook" | "url"
    content_type: str           # "text" | "image" | "pdf" | "url" | "code" | "audio"
    raw_content: bytes          # original unchanged input
    text_content: str | None    # extracted text (after OCR/scraping/parsing)
    metadata: dict              # {
                                #   "project": str | None,
                                #   "timestamp": datetime,
                                #   "sender": str,
                                #   "source_url": str | None,
                                #   "file_path": str | None,
                                #   "language": str,
                                # }
    status: str                 # "pending" → "processing" → "stored" → "reflected"
    created_at: datetime
```

### Telegram Bot

```python
# telegram/bot.py
# Simple aiogram bot — sends everything to ingestion queue

async def on_message(message: Message):
    item = IngestItem(
        id=uuid7(),
        source="telegram",
        content_type=detect_type(message),
        raw_content=await extract_content(message),
        metadata={
            "sender": message.from_user.username,
            "timestamp": message.date,
            "chat_id": message.chat.id,
        },
        status="pending",
    )
    await ingest_queue.put(item)
    await message.reply("✓ Saved to memory")
```

### File Watcher

```python
# src/ingestion/file_watcher.py
class InboxWatcher(FileSystemEventHandler):
    WATCH_DIR = Path.home() / "MemoryInbox"
    
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        item = IngestItem(
            id=uuid7(),
            source="file_watch",
            content_type=detect_from_extension(path),
            raw_content=path.read_bytes(),
            metadata={"file_path": str(path), "file_name": path.name},
            status="pending",
        )
        ingest_queue.put_sync(item)
        # Move to processed/
        path.rename(self.WATCH_DIR / "processed" / path.name)
```

---

## 4. Layer 2 — Processing Pipeline

Every `IngestItem` goes through a processing pipeline that extracts text, chunks it,
generates summaries, extracts metadata and concepts.

### Pipeline Steps

```
IngestItem → TypeDetector → ProcessorRouter → Chunker → 
             Summarizer → ConceptExtractor → MetadataEnricher → 
             [Chunk1, Chunk2, ...] ready for vectorization
```

### Processors

| Processor | Input | Output |
|---|---|---|
| **TextChunker** | Plain text, code | Semantic chunks (by topic/paragraph change) |
| **OCR** | Images, screenshots | Extracted text + visual description |
| **PDFParser** | PDF files | Text per page, structured extraction |
| **URLScraper** | URLs | Clean article text (trafilatura + readability) |
| **CodeAnalyzer** | Source code files | Structured code: functions, classes, imports |

### Semantic Chunking

Not fixed-size splitting. Intelligent chunking by topic boundaries:

```python
class SemanticChunker:
    """Split text by semantic boundaries, not character count"""
    
    MAX_CHUNK_TOKENS = 500
    MIN_CHUNK_TOKENS = 50
    OVERLAP_TOKENS = 50
    
    def chunk(self, text: str) -> list[Chunk]:
        # Short text (< 500 tokens) → single chunk
        if count_tokens(text) < self.MAX_CHUNK_TOKENS:
            return [Chunk(content=text, index=0)]
        
        # Split by paragraphs first
        paragraphs = text.split("\n\n")
        
        # Merge small paragraphs, split large ones
        chunks = []
        current = ""
        for para in paragraphs:
            if count_tokens(current + para) > self.MAX_CHUNK_TOKENS:
                if current:
                    chunks.append(current.strip())
                current = para
            else:
                current += "\n\n" + para
        if current:
            chunks.append(current.strip())
        
        return [Chunk(content=c, index=i) for i, c in enumerate(chunks)]
```

### OCR (Apple Vision Framework)

```python
# src/ingestion/ocr.py
import objc
from Vision import VNRecognizeTextRequest, VNImageRequestHandler

def ocr_image(image_path: str) -> str:
    """Free, fast, local OCR using macOS Vision framework"""
    handler = VNImageRequestHandler.alloc().initWithURL_options_(
        NSURL.fileURLWithPath_(image_path), {}
    )
    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(1)  # accurate
    request.setRecognitionLanguages_(["en", "ru"])
    handler.performRequests_error_([request], None)
    
    results = request.results()
    return "\n".join(r.text() for r in results)
```

### Ollama Summarizer

Every chunk gets a 1-2 sentence summary for fast recall:

```python
async def summarize(chunk: str) -> str:
    response = await ollama.generate(
        model="qwen2.5-coder:32b",
        prompt=f"Summarize in 1-2 sentences (same language as input):\n\n{chunk}",
    )
    return response.strip()
```

### Concept Extractor (Critical!)

Automatically extracts concepts, capabilities, and composability from every chunk:

```python
class ConceptExtractor:
    PROMPT = """Analyze this content and extract structured information.
Return JSON only, no explanation.

{
  "concepts": [
    {"name": "concept_name", "category": "domain|pattern|technology", "strength": 0.0-1.0}
  ],
  "capabilities": ["what this code/solution CAN DO"],
  "composable_with": ["what other systems this needs or works with"],
  "entities": [
    {"name": "entity_name", "type": "person|project|company|technology"}
  ],
  "relations": [
    {"source": "entity_a", "target": "entity_b", "type": "relation_type"}
  ],
  "quality": "production-ready|prototype|educational|reference",
  "key_patterns": ["architectural patterns used"]
}

Content:
{content}"""

    async def extract(self, content: str) -> ExtractionResult:
        response = await ollama.generate(
            model="qwen2.5-coder:32b",
            prompt=self.PROMPT.format(content=content),
            format="json",
        )
        return ExtractionResult.parse(response)
```

### Chunk Schema

```python
@dataclass
class Chunk:
    id: str                     # UUID v7
    parent_id: str              # reference to IngestItem
    content: str                # chunk text
    summary: str                # Ollama-generated 1-2 sentence summary
    chunk_index: int            # order in document
    
    # Extracted by ConceptExtractor
    concepts: list[ConceptLink] # [{concept_id, strength, role}]
    capabilities: list[str]     # what this can do
    composable_with: list[str]  # what this works with
    entities: list[EntityRef]   # extracted entities
    relations: list[Relation]   # extracted relations
    
    # Metadata
    metadata: dict              # project, language, source, etc.
    embedding: bytes | None     # filled in Layer 3
    binary_vector: bytes | None # filled in Layer 3
```

---

## 5. Layer 3 — Vectorization

### Embedding Models

| Model | Dimensions | Use | Speed |
|---|---|---|---|
| `nomic-embed-text` | 768 | Text content | ~670ms/record |
| `nomic-embed-vision` | 768 | Images (compatible space!) | ~800ms/record |
| Binary quantization | 96 bytes | Fast pre-filter (Hamming) | 6.4ms search |

### Late Chunking Enhancement

Embed each chunk WITH document context for better retrieval:

```python
async def embed_chunk(chunk: Chunk, parent_summary: str) -> bytes:
    # Prepend document summary for context-aware embedding
    text = f"Document: {parent_summary}\n\nChunk: {chunk.content}"
    return await ollama.embed(model="nomic-embed-text", input=text)
```

### Two-Level ANN (Already Implemented)

```
Query → binary Hamming pre-filter (top-50) → cosine re-rank on float32 → top-10
```

- Binary vectors: 96 bytes per record (768-dim → packbits)
- Float32 vectors: 3072 bytes per record
- Total for 2000 records: ~6 MB (vs 19.2 MB ChromaDB)
- Search time: 6.4ms full pipeline

---

## 6. Layer 4 — Triple Storage + Knowledge Graph

Three storage systems working together:

### 6.1 Vector Store (Semantic Search)
Already implemented: SQLite `embeddings` table with binary quantization.
Purpose: "find something SIMILAR to this query"

### 6.2 Blob Store (Original Files)
```
~/.claude-memory/blobs/
├── {uuid7}.png          # screenshots
├── {uuid7}.pdf          # documents
├── {uuid7}.json         # structured data
└── {uuid7}.txt          # raw text
```
Purpose: "show me the ORIGINAL file/image"

### 6.3 Knowledge Graph (The Brain)

This is where EVERYTHING lives as connected nodes. Rules, skills, memories,
episodes, concepts, entities, patterns — all in ONE graph.

See [Section 11: Unified Knowledge Graph](#11-unified-knowledge-graph) for full details.

---

## 7. Layer 5 — Reflection Agent ("Sleep")

Background process that runs periodically to consolidate, synthesize, and evolve
knowledge. Like sleep for the brain — transfers short-term to long-term memory,
finds patterns, creates generalizations.

### Trigger Schedule

| Trigger | When | What runs |
|---|---|---|
| `after_session` | Every session end | Quick digest (dedup, decay) |
| `periodic` | Every 6 hours | Full synthesis + evolution |
| `weekly` | Sunday midnight | Weekly digest + major consolidation |
| `manual` | `memory_reflect_now()` | Full pipeline on demand |

### Phase 1: DIGEST (Cleanup)

```python
class DigestPhase:
    """Clean up, deduplicate, decay — prepare for synthesis"""
    
    def run(self):
        # 1. Merge semantic duplicates
        self.merge_similar(threshold=0.85)
        # Uses Jaccard + fuzzy matching (already exists)
        # Enhanced: also merge if same concepts + same capabilities
        
        # 2. Resolve contradictions
        contradictions = self.find_contradictions()
        for old, new in contradictions:
            if new.confidence > old.confidence:
                old.status = "superseded"
                old.superseded_by = new.id
                self.graph.add_edge(new, old, "supersedes")
                # Keep link — "we used to think X, now we know Y"
        
        # 3. Intelligent Decay (not just time-based)
        for node in self.get_all_active():
            decay = self.calculate_intelligent_decay(node)
            if decay > 0.9:
                self.archive(node)
        
        # 4. Clean dead nodes in graph
        self.graph.remove_orphans()
        self.graph.remove_weak_edges(min_weight=0.1)
    
    def calculate_intelligent_decay(self, node) -> float:
        """Different decay strategies by node type"""
        
        if node.type == "episode" and node.impact_score > 0.7:
            return 0.0  # FAILURES NEVER DECAY — pain is remembered forever
        
        if node.type in ("rule", "prohibition"):
            return 0.0  # rules don't decay
        
        if node.type == "skill":
            # skills decay by USAGE, not time
            if node.last_used_days_ago < 30:
                return 0.0
            return min(1.0, (node.last_used_days_ago - 30) / 180)
        
        if node.type == "episode":
            # episodes: impact-based decay
            base_decay = node.age_days / (self.half_life * 2)  # slower than facts
            return base_decay * (1.0 - node.impact_score)
        
        # facts, solutions: standard time-based with recall reinforcement
        base_decay = node.age_days / self.half_life
        recall_factor = 1.0 / (1.0 + node.recall_count * 0.5)
        return min(1.0, base_decay * recall_factor)
```

### Phase 2: SYNTHESIZE (Create New Knowledge)

```python
class SynthesizePhase:
    """Find patterns, create generalizations, enrich graph"""
    
    def run(self):
        # 1. Cluster recent episodes by theme
        recent = self.get_recent_episodes(days=7)
        clusters = self.cluster_by_concepts(recent)
        
        for cluster in clusters:
            if len(cluster) >= 3:
                # 3+ similar episodes → this is a PATTERN
                pattern = self.create_generalization(cluster)
                self.graph.add_node(pattern, type="pattern")
                for episode in cluster:
                    self.graph.add_edge(pattern, episode, "generalizes")
                
                # Pattern might become a skill
                if cluster.has_common_procedure():
                    self.propose_skill(cluster)
        
        # 2. Cross-project pattern detection
        # "retry pattern used in ImPatient, Strata, JobFlow → universal"
        cross_patterns = self.find_cross_project_patterns()
        for pattern in cross_patterns:
            self.promote_to_reusable(pattern)
        
        # 3. Graph enrichment
        self.strengthen_cooccurrence_edges()  # entities mentioned together
        self.compute_entity_importance()       # PageRank-like scoring
        self.detect_communities()              # topic clusters
        self.infer_transitive_relations()      # A→B, B→C → maybe A→C
        
        # 4. Contradiction detection across entire graph
        self.find_and_flag_contradictions()
        
        # 5. Gap detection
        # "We have auth and billing but no notification system in JobFlow"
        self.detect_capability_gaps()
```

### Phase 3: EVOLVE (Get Smarter)

```python
class EvolvePhase:
    """Refine skills, generate rules, update self-model, evolve CLAUDE.md"""
    
    def run(self):
        # 1. Skill refinement
        for skill in self.get_all_skills():
            recent_uses = self.get_skill_uses(skill, days=30)
            if recent_uses:
                successes = [u for u in recent_uses if u.success]
                failures = [u for u in recent_uses if not u.success]
                
                skill.success_rate = len(successes) / len(recent_uses)
                skill.times_used += len(recent_uses)
                
                # Learn from failures — add anti-patterns
                for f in failures:
                    skill.anti_patterns.append(f.what_went_wrong)
                
                # Learn from successes — refine steps
                for s in successes:
                    if s.had_novel_step:
                        skill.steps = self.merge_steps(skill.steps, s.steps)
                
                skill.version += 1
                skill.last_refined = now()
        
        # 2. Rule generation from mature patterns
        mature = self.get_insights(min_evidence=3, min_importance=5)
        for insight in mature:
            if insight.confidence >= 0.8:
                rule = self.propose_rule(insight)
                # NOT auto-applied — queued for user approval
                self.pending_rules.append(rule)
        
        # 3. Self-model update
        self.update_competencies()
        self.detect_blind_spots()
        self.update_user_model()
        self.update_work_patterns()
        
        # 4. CLAUDE.md evolution proposals
        new_rules = self.get_pending_rules(min_confidence=0.9)
        stale_rules = self.find_stale_claude_md_rules()
        if new_rules or stale_rules:
            diff = self.generate_claude_md_diff(new_rules, stale_rules)
            self.save_proposed_changes(diff)
            # Show to user at next session start
        
        # 5. Generate reflection report
        report = ReflectionReport(
            period=self.period,
            new_knowledge=self.stats.new_nodes,
            patterns_found=self.stats.patterns,
            skills_refined=self.stats.skills_updated,
            rules_proposed=len(self.pending_rules),
            contradictions_resolved=self.stats.contradictions,
            blind_spots_found=self.stats.blind_spots,
            decay_archived=self.stats.archived,
        )
        self.save_report(report)
```

### Scheduler

```python
# src/reflection/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# After every session
@scheduler.scheduled_job("interval", hours=6)
async def periodic_reflection():
    agent = ReflectionAgent()
    await agent.run_full()

# Weekly deep reflection  
@scheduler.scheduled_job("cron", day_of_week="sun", hour=0)
async def weekly_reflection():
    agent = ReflectionAgent()
    await agent.run_weekly_digest()
```

---

## 8. Layer 6 — Smart Output

### Context Builder

Assembles optimal context before every query, combining all storage layers:

```python
class ContextBuilder:
    MAX_TOKENS = 4000
    
    async def build(self, query: str, project: str | None) -> ContextBundle:
        # 1. Extract concepts from query
        concepts = await self.extractor.extract_concepts(query)
        
        # 2. Spreading activation (see Section 10)
        activated = self.associative.spread(concepts, depth=2)
        
        # 3. Gather from all sources
        semantic_results = await self.vector_store.search(query, top_k=20)
        graph_results = self.graph.traverse(activated, depth=2)
        episode_results = self.episode_store.find_similar(query)
        skill_results = self.skill_store.match_trigger(query)
        
        # 4. Merge and deduplicate
        all_results = self.merge(semantic_results, graph_results, 
                                 episode_results, skill_results)
        
        # 5. Rank by: relevance × recency × importance × activation_score
        ranked = self.rank(all_results, weights={
            "relevance": 0.3,
            "recency": 0.2, 
            "importance": 0.2,
            "activation": 0.3,
        })
        
        # 6. Fit into token budget
        selected = self.fit_to_budget(ranked, self.MAX_TOKENS)
        
        # 7. Competency check
        competency = self.self_model.assess(concepts)
        
        return ContextBundle(
            knowledge=selected,
            competency=competency,
            blind_spots=self.self_model.relevant_blind_spots(concepts),
            predicted_needs=self.predictor.predict(query, project),
        )
```

### CLAUDE.md Auto-Updater

```python
class ClaudeMdUpdater:
    """Proposes CLAUDE.md changes based on learned patterns"""
    
    def generate_proposals(self) -> list[Proposal]:
        proposals = []
        
        # 1. New rules from reflection
        for rule in self.reflection.pending_rules:
            proposals.append(Proposal(
                action="add",
                section=rule.target_section,
                content=rule.text,
                evidence=rule.evidence_count,
                confidence=rule.confidence,
            ))
        
        # 2. Stale rules (never triggered, or low success rate)
        for rule in self.find_stale_rules():
            proposals.append(Proposal(
                action="review",
                section=rule.section,
                reason=f"Never triggered in {rule.age_days} days",
            ))
        
        # 3. Project summaries update
        for project in self.get_active_projects():
            current = self.get_claude_md_section(project)
            actual = self.generate_project_summary(project)
            if self.differs_significantly(current, actual):
                proposals.append(Proposal(
                    action="update",
                    section=f"Project: {project}",
                    content=actual,
                ))
        
        return proposals
    
    def present_to_user(self, proposals: list[Proposal]):
        """Show diff at next session start — user approves/rejects"""
        diff = self.generate_diff(proposals)
        # Saved to ~/.claude-memory/pending-claude-md-update.md
        # Session start hook detects and shows to user
```

---

## 9. Seven Memory Systems

Human brain has multiple memory systems. So should Claude:

```
Human Brain                         Claude Super Memory v5.0
═══════════════                     ════════════════════════

Sensory Memory          ──────────► Ingestion Buffer
(milliseconds)                      (raw input, unprocessed IngestItems)

Working Memory           ──────────► Session Context
(7±2 items, current task)           (current conversation, CLAUDE.md, active rules)

Short-term Memory        ──────────► Session Memory
(minutes-hours)                     (current session facts, not yet consolidated)

      ┌── Episodic ───────────────► Episode Store
      │   (WHAT happened)           narratives, outcomes, impact scores
      │
Long- │── Semantic ───────────────► Knowledge Graph  
term  │   (WHAT I know)            facts, entities, relations, concepts
Memory│
      │── Procedural ─────────────► Skill Store
      │   (HOW I do things)        step-by-step procedures, success rates
      │
      └── Meta-cognitive ─────────► Self Model
          (what I know ABOUT ME)    competencies, blind spots, trends

Emotional Tagging        ──────────► Impact Score
(important = remembered better)     failure/breakthrough = high impact = never decayed

Sleep Consolidation      ──────────► Reflection Agent
(short→long term transfer)          background synthesis every 6 hours

Forgetting              ──────────► Intelligent Decay
(noise removal)                     by value, not by time

Intuition               ──────────► Predictive Context
(patterns → gut feeling)            "user likely needs X, prepare Y"
```

### 9.1 Episode Store

Episodic memory — not WHAT happened, but HOW. The narrative, the journey, the
outcome. Currently completely missing.

```python
@dataclass
class Episode:
    id: str
    session_id: str
    timestamp: datetime
    
    # Narrative — HOW things happened, not just the result
    narrative: str
    # "Started with approach X, it failed because Y, 
    #  switched to Z — that worked. Key insight was..."
    
    # Emotional tagging
    outcome: str                # "breakthrough" | "failure" | "routine" | "discovery"
    impact_score: float         # 0.0-1.0
    frustration_signals: int    # how many times user corrected/re-asked
    
    # Context
    project: str
    concepts: list[str]         # abstract concepts involved
    entities: list[str]         # people, technologies, tools
    tools_used: list[str]       # what tools were used
    duration_minutes: int
    
    # Connections
    similar_to: list[str]       # similar past episodes
    led_to: str | None          # "this episode led to solution X"
    contradicts: str | None     # "this contradicts what we thought in episode Y"
    
    # Extracted from transcript
    approaches_tried: list[str] # what was tried (including failures)
    key_insight: str | None     # the aha moment
    user_corrections: list[str] # what user corrected (learning signal!)
```

**How episodes are captured:**

```python
# In session-end.sh hook → auto_episode_capture.py

async def capture_episode(transcript_path: str) -> Episode:
    # 1. Parse transcript (already have extract_transcript.py)
    messages = parse_transcript(transcript_path)
    
    # 2. Ollama generates narrative from messages
    narrative = await ollama.generate(
        model="qwen2.5-coder:32b",
        prompt=f"""Analyze this coding session transcript and create a brief narrative.
Focus on: what was attempted, what failed, what worked, key insights.

Format:
- narrative: 2-3 sentences of what happened
- outcome: breakthrough | failure | routine | discovery
- impact: 0.0-1.0 (how significant was this)
- approaches_tried: list of approaches
- key_insight: the main learning (or null)
- frustration_signals: count of user corrections/re-asks

Transcript:
{messages[:5000]}"""  # truncate for token budget
    )
    
    return Episode.from_ollama(narrative)
```

### 9.2 Knowledge Graph

See [Section 11](#11-unified-knowledge-graph).

### 9.3 Skill Store

Procedural memory — not WHAT I know, but HOW I do things. Step-by-step procedures
that improve with each use.

```python
@dataclass
class Skill:
    id: str
    name: str                   # "debug_go_compilation_error"
    trigger: str                # "when Go code doesn't compile"
    
    # Step-by-step procedure
    steps: list[str]
    # [
    #   "1. Read the full error message",
    #   "2. Check type signatures",
    #   "3. Check imports",
    #   "4. If interface — verify all methods implemented",
    # ]
    
    # Effectiveness metrics
    times_used: int
    success_rate: float         # percentage of successful uses
    avg_steps_to_solve: float   # usually solves in N steps
    
    # Evolution
    version: int                # skill improves over time
    learned_from: list[str]     # which episodes led to this skill
    last_refined: datetime
    
    # Applicability
    projects: list[str]         # which projects this applies to
    stack: list[str]            # ["go", "postgresql"]
    
    # Anti-patterns (learned from failures)
    anti_patterns: list[str]
    # ["DON'T: immediately change types without understanding the error"]
    
    # Composability
    related_skills: list[str]   # skills often used together
    prerequisite_of: list[str]  # skills that need this one first
```

**How skills form:**

```
Episode → Episode → Episode (3+ similar)
    ↓
Pattern Detector finds common procedure
    ↓
Reflection Agent formulates Skill (draft, v1)
    ↓
Next application → evaluate (success/fail)
    ↓
Skill refined (steps added/removed, v2)
    ↓
After 10+ successful uses → "mastered skill"
```

**Example skills that should already exist (from 364 sessions):**

```yaml
- name: "parallel_agent_orchestration"
  trigger: "task with 3+ independent subtasks"
  steps:
    - "Decompose into independent parts"
    - "Launch agents in parallel (NOT sequential!)"
    - "Give each agent FULL context, not references"
    - "Collect results, check for conflicts"
  success_rate: 0.92
  learned_from: ["episode_loyalti_refactor", "episode_cortex_tools"]
  anti_patterns: ["don't launch >8 agents — coordination degrades"]

- name: "docker_project_setup"
  trigger: "new project with docker-compose"
  steps:
    - "docker compose up -d"
    - "check health: docker compose ps"
    - "ALL commands via docker compose exec"
    - "NEVER npm/composer on host"
  learned_from: ["15 sessions where forgot about docker"]

- name: "webhook_implementation"
  trigger: "implement webhook handler"
  steps:
    - "Save raw body BEFORE parsing"
    - "Verify signature (HMAC SHA256, timing-safe)"
    - "Idempotency key in separate table"
    - "Process async via queue, not inline"
    - "Structured logging with all fields"
  anti_patterns: ["returning 500 without mapping → causes retries → duplicates"]
  learned_from: ["episode_strata_payment_bug", "episode_vitamin_tinkoff"]
```

### 9.4 Self Model

Meta-cognition — knowing what I know and don't know about myself.

```python
@dataclass
class SelfModel:
    # Competencies — objective assessment by domain
    competencies: dict[str, CompetencyScore]
    # {
    #   "go_backend":        CompetencyScore(level=0.9, confidence=0.85, based_on=47),
    #   "vue_frontend":      CompetencyScore(level=0.7, confidence=0.6,  based_on=12),
    #   "css_styling":       CompetencyScore(level=0.3, confidence=0.8,  based_on=8),
    #   "docker_ops":        CompetencyScore(level=0.85,confidence=0.75, based_on=30),
    #   "postgresql_tuning": CompetencyScore(level=0.8, confidence=0.7,  based_on=15),
    #   "debugging":         CompetencyScore(level=0.75,confidence=0.65, based_on=25),
    # }
    
    # Trends
    trends: dict[str, str]
    # {
    #   "go_backend": "improving",
    #   "css_styling": "stable_low",
    #   "parallel_agents": "improving",
    # }
    
    # Blind spots — what I DON'T KNOW that I don't know
    blind_spots: list[BlindSpot]
    # [
    #   BlindSpot("Tends to suggest Go for everything, even when PHP fits better"),
    #   BlindSpot("Underestimates time for CSS/design tasks"),
    #   BlindSpot("Forgets to check edge cases in time zones"),
    #   BlindSpot("Often forgets to wrap errors with context"),
    # ]
    
    # User model (learned, not prescribed!)
    user_model: UserModel
    # {
    #   communication_style: "brief, no fluff, Russian",
    #   decision_speed: "fast — doesn't like long discussions",
    #   autonomy_preference: "high — don't ask about small things",
    #   quality_bar: "production-grade, not prototypes",
    #   work_patterns: {
    #     peak_hours: "19:00-02:00",
    #     session_length: "avg 45 min",
    #     projects_per_week: "2-3",
    #   }
    # }

    def assess(self, concepts: list[str]) -> CompetencyAssessment:
        """How competent am I for this task?"""
        relevant = [self.competencies.get(c) for c in concepts if c in self.competencies]
        if not relevant:
            return CompetencyAssessment(level=0.5, confidence=0.3, note="Unknown domain")
        
        avg_level = sum(c.level for c in relevant) / len(relevant)
        avg_conf = sum(c.confidence for c in relevant) / len(relevant)
        
        blind_spot_matches = [b for b in self.blind_spots 
                              if any(c in b.domains for c in concepts)]
        
        return CompetencyAssessment(
            level=avg_level,
            confidence=avg_conf,
            blind_spots=blind_spot_matches,
            note="Strong" if avg_level > 0.8 else "Moderate" if avg_level > 0.5 else "Weak — be cautious",
        )
```

**How Self Model updates:**

```python
# After every session
def update_from_episode(self, episode: Episode):
    for concept in episode.concepts:
        comp = self.competencies.get(concept)
        if not comp:
            comp = CompetencyScore(level=0.5, confidence=0.3, based_on=0)
            self.competencies[concept] = comp
        
        comp.based_on += 1
        
        if episode.outcome == "breakthrough":
            comp.level = min(1.0, comp.level + 0.02)
            comp.confidence = min(1.0, comp.confidence + 0.05)
        
        elif episode.outcome == "failure":
            comp.level = max(0.0, comp.level - 0.01)
            # DON'T reduce confidence on failure — we LEARNED something
            comp.confidence = min(1.0, comp.confidence + 0.03)
        
        if episode.frustration_signals > 3:
            # User corrected me a lot → blind spot?
            self.add_blind_spot_candidate(concept, episode)
    
    # User model update
    if episode.user_corrections:
        self.analyze_corrections(episode.user_corrections)
```

---

## 10. Associative Memory Engine

The core innovation: spreading activation instead of keyword search.

### How Human Associative Memory Works

```
Brain does NOT search by keywords.
Brain works through SPREADING ACTIVATION:

    "SaaS" activates →
        → "subscriptions" → "Stripe" → "We looked at repo B!"
        → "multi-tenant" → "data isolation" → "Repo C did this!"
        → "auth" → "OAuth" → "PKCE" → "Repo A!"
        
Three independent memories SIMULTANEOUSLY activated
through a network of connections. Not search — RESONANCE.
```

### Spreading Activation Algorithm

```python
class AssociativeRecall:
    # Activation decay per hop
    HOP_DECAY = [1.0, 0.7, 0.4, 0.2]  # direct, 1-hop, 2-hop, 3-hop
    
    # Minimum activation to consider
    ACTIVATION_THRESHOLD = 0.3
    
    # Bonus for multi-path activation
    MULTI_PATH_BONUS = {2: 1.2, 3: 1.5, 4: 1.8}
    
    def spread(self, seed_concepts: list[str], depth: int = 2) -> dict[str, float]:
        """Spreading activation from seed concepts through the graph"""
        
        activation_map: dict[str, float] = {}
        activation_paths: dict[str, int] = {}  # count of activation paths
        
        for concept in seed_concepts:
            self._activate(concept, 1.0, 0, depth, activation_map, activation_paths)
        
        # Multi-path bonus
        for node_id, path_count in activation_paths.items():
            if path_count in self.MULTI_PATH_BONUS:
                activation_map[node_id] *= self.MULTI_PATH_BONUS[path_count]
        
        # Filter below threshold
        return {k: v for k, v in activation_map.items() if v >= self.ACTIVATION_THRESHOLD}
    
    def _activate(self, node_id: str, strength: float, current_depth: int,
                  max_depth: int, activation_map: dict, path_count: dict):
        """Recursive activation spread"""
        
        if current_depth > max_depth or strength < 0.1:
            return
        
        # Update activation (keep max)
        current = activation_map.get(node_id, 0)
        if strength > current:
            activation_map[node_id] = strength
        
        # Count paths
        path_count[node_id] = path_count.get(node_id, 0) + 1
        
        # Spread to neighbors
        neighbors = self.graph.get_neighbors(node_id)
        for neighbor_id, edge_weight in neighbors:
            next_strength = strength * self.HOP_DECAY[min(current_depth + 1, 3)] * edge_weight
            self._activate(neighbor_id, next_strength, current_depth + 1,
                          max_depth, activation_map, path_count)
    
    def recall(self, query: str, context: dict = None) -> AssociationResult:
        """Full associative recall pipeline"""
        
        # Step 1: Extract concepts from query
        concepts = self.extractor.extract_concepts(query)
        
        # Step 2: Spreading activation
        activation_map = self.spread(concepts, depth=2)
        
        # Step 3: Find memories through activated concepts
        activated_memories: dict[str, float] = {}
        for concept_id, activation in activation_map.items():
            memories = self.graph.get_memories_for_node(concept_id)
            for memory, link_strength in memories:
                score = activated_memories.get(memory.id, 0)
                activated_memories[memory.id] = score + activation * link_strength
        
        # Step 4: Rank by total activation
        ranked = sorted(activated_memories.items(), key=lambda x: x[1], reverse=True)
        top_memories = [self.get_memory(mid) for mid, score in ranked[:20]]
        
        # Step 5: Composition analysis
        composition = self.composition_engine.compose(concepts, top_memories)
        
        return AssociationResult(
            query_concepts=concepts,
            activated_nodes=len(activation_map),
            memories=top_memories,
            composition=composition,
        )
```

### Composition Engine

Not just "found similar" — but "here's how to COMBINE pieces into a solution":

```python
class CompositionEngine:
    def compose(self, needed_concepts: list[str], 
                available: list[Memory]) -> Composition:
        
        # 1. Coverage matrix
        matrix = {}
        for mem in available:
            matrix[mem.id] = {
                c.name: c.strength 
                for c in mem.concepts 
                if c.name in needed_concepts
            }
        
        # 2. Greedy set cover — minimum set covering all concepts
        selected = []
        uncovered = set(needed_concepts)
        candidates = list(available)
        
        while uncovered and candidates:
            # Pick memory that covers most uncovered concepts
            best = max(candidates, key=lambda m: len(
                set(matrix[m.id].keys()) & uncovered
            ))
            covered_by_best = set(matrix[best.id].keys()) & uncovered
            if not covered_by_best:
                break
            selected.append(best)
            uncovered -= covered_by_best
            candidates.remove(best)
        
        # 3. Conflict detection
        conflicts = self.detect_conflicts(selected)
        
        # 4. Integration plan
        integration = self.plan_integration(selected, needed_concepts)
        
        # 5. Gaps
        covered = set()
        for mem in selected:
            covered.update(c for c, s in matrix[mem.id].items() if s > 0.5)
        gaps = set(needed_concepts) - covered
        
        return Composition(
            sources=selected,
            coverage_percent=len(covered) / max(len(needed_concepts), 1) * 100,
            conflicts=conflicts,
            integration_plan=integration,
            gaps=list(gaps),
        )
    
    def detect_conflicts(self, memories: list[Memory]) -> list[Conflict]:
        """Find conflicting approaches between selected memories"""
        conflicts = []
        for i, a in enumerate(memories):
            for b in memories[i+1:]:
                # Same concept, different implementation?
                shared = set(a.concept_names) & set(b.concept_names)
                for concept in shared:
                    if a.get_approach(concept) != b.get_approach(concept):
                        conflicts.append(Conflict(
                            concept=concept,
                            approach_a=a.get_approach(concept),
                            approach_b=b.get_approach(concept),
                            recommendation=self.recommend_resolution(a, b, concept),
                        ))
        return conflicts
```

---

## 11. Unified Knowledge Graph

**The brain of the system.** Everything — rules, skills, memories, episodes,
concepts, entities, patterns, repos — lives as nodes in ONE graph.

### Node Types (18 types)

```python
class NodeType(Enum):
    # === From CLAUDE.md (rules & conventions) ===
    RULE = "rule"                   # "thin handler ≤15 lines"
    CONVENTION = "convention"       # "UUID v7 for PKs"
    PROHIBITION = "prohibition"     # "NEVER git push"
    
    # === From Skills (procedures) ===
    SKILL = "skill"                 # "developing-go", "managing-docker"
    PROCEDURE = "procedure"         # step-by-step process within skill
    
    # === From Memory (experience) ===
    EPISODE = "episode"             # "session where we debugged for 3 hours"
    FACT = "fact"                   # "Redis 7 supports ACL per key"
    SOLUTION = "solution"           # "retry with exponential backoff"
    DECISION = "decision"           # "chose Go over Rust"
    LESSON = "lesson"               # "never mock DB in integration tests"
    
    # === Abstractions ===
    CONCEPT = "concept"             # "authentication", "caching"
    PATTERN = "pattern"             # "repository pattern", "CQRS"
    TECHNOLOGY = "technology"       # "PostgreSQL 18", "Go 1.25"
    
    # === External sources ===
    REPO = "repo"                   # GitHub repo we looked at
    ARTICLE = "article"             # article we read
    DOCUMENTATION = "doc"           # docs we studied
    
    # === Real-world entities ===
    PERSON = "person"               # "Vitalii", "colleague Ivan"
    PROJECT = "project"             # "JobFlow", "ImPatient"
    COMPANY = "company"             # "Alfapair", "Stripe"
    
    # === Meta-cognition ===
    BLINDSPOT = "blindspot"         # "poor at estimating CSS time"
    COMPETENCY = "competency"       # "Go backend: 0.9"
    PREFERENCE = "preference"       # "user prefers brevity"
```

### Relation Types (25 types)

```python
RELATION_TYPES = {
    # Semantic relations
    "is_a",             # cat is_a animal
    "part_of",          # auth part_of saas
    "has_part",         # saas has_part billing
    
    # People & projects
    "works_at",         # Vitalii works_at Alfapair
    "works_on",         # Vitalii works_on JobFlow
    "owns",             # Vitalii owns ImPatient
    
    # Technology relations
    "uses",             # JobFlow uses Go
    "depends_on",       # billing depends_on auth
    "alternative_to",   # Redis alternative_to Memcached
    "integrates_with",  # Stripe integrates_with webhook
    "replaced_by",      # old_auth replaced_by new_auth
    
    # Knowledge relations
    "provides",         # repo_A provides OAuth2
    "requires",         # billing requires auth
    "composable_with",  # auth composable_with tenancy
    "solves",           # retry_solution solves timeout_problem
    "causes",           # missing_idempotency causes duplicate_payments
    "contradicts",      # fact_A contradicts fact_B
    "supersedes",       # new_fact supersedes old_fact
    "generalizes",      # retry_pattern generalizes specific_retries
    "example_of",       # impatient_retry example_of retry_pattern
    
    # Governance
    "governs",          # rule governs concept
    "enforced_by",      # rule enforced_by skill
    "applies_to",       # convention applies_to technology
    
    # Temporal
    "led_to",           # episode_A led_to solution_B
    "preceded_by",      # task_B preceded_by task_A
    
    # Cognitive
    "struggles_with",   # Vitalii struggles_with CSS
    "prefers",          # Vitalii prefers Go
    "mentioned_with",   # auth mentioned_with billing (co-occurrence)
}
```

### How CLAUDE.md Rules Become Graph Nodes

```python
class ClaudeMdParser:
    """Parse CLAUDE.md and create graph nodes + edges"""
    
    def ingest(self, claude_md_path: str):
        content = Path(claude_md_path).read_text()
        sections = self.parse_sections(content)
        
        for section in sections:
            rules = self.extract_rules(section)
            for rule_text in rules:
                # Create node
                node = self.graph.add_node(
                    type=self.classify_rule(rule_text),  # rule | convention | prohibition
                    content=rule_text,
                    source="claude_md",
                    section=section.title,
                )
                
                # Auto-link to technologies
                techs = self.detect_technologies(rule_text)
                for tech in techs:
                    tech_node = self.graph.get_or_create(tech, type="technology")
                    self.graph.add_edge(node, tech_node, "applies_to")
                
                # Auto-link to concepts
                concepts = self.extractor.extract_concepts(rule_text)
                for concept in concepts:
                    concept_node = self.graph.get_or_create(concept.name, type="concept")
                    self.graph.add_edge(node, concept_node, "governs", weight=concept.strength)
                
                # Auto-link to skills
                skills = self.find_related_skills(rule_text)
                for skill in skills:
                    self.graph.add_edge(node, skill, "enforced_by")
```

### How Skills Become Graph Nodes

```python
class SkillIndexer:
    """Index all skills as graph nodes with connections"""
    
    def index_all(self, skills_dir: str = "~/.claude/skills/"):
        for skill_file in Path(skills_dir).glob("**/*.md"):
            skill = self.parse_skill(skill_file)
            
            node = self.graph.add_node(
                type="skill",
                name=skill.name,
                content=skill.description,
                triggers=skill.triggers,
                capabilities=skill.capabilities,
            )
            
            # Link to technologies
            for tech in skill.technologies:
                self.graph.add_edge(node, tech, "implements")
            
            # Link to rules it enforces
            for rule in self.find_enforced_rules(skill):
                self.graph.add_edge(node, rule, "enforces")
            
            # Link to concepts it covers
            for concept in skill.concepts:
                self.graph.add_edge(node, concept, "covers")
            
            # Link to related skills
            for dep in skill.dependencies:
                self.graph.add_edge(node, dep, "depends_on")
            
            # Link to projects where this skill was used
            episodes = self.find_skill_episodes(skill)
            for episode in episodes:
                self.graph.add_edge(node, episode.project, "used_in")
```

### Graph Queries

```python
class GraphQuery:
    """Query the unified knowledge graph"""
    
    def neighborhood(self, node_id: str, depth: int = 2, 
                     types: list[str] = None) -> Subgraph:
        """Get everything within N hops of a node"""
        visited = set()
        result = Subgraph()
        self._traverse(node_id, 0, depth, types, visited, result)
        return result
    
    def shortest_path(self, from_id: str, to_id: str) -> list[Edge]:
        """Find how two nodes are connected"""
        # BFS shortest path
        return self._bfs_path(from_id, to_id)
    
    def common_ancestors(self, node_ids: list[str]) -> list[Node]:
        """Find concepts shared between multiple nodes"""
        ancestor_sets = [self._get_ancestors(nid) for nid in node_ids]
        return set.intersection(*ancestor_sets)
    
    def find_composition(self, required_concepts: list[str]) -> list[Node]:
        """Find minimum set of nodes that covers all required concepts"""
        return self.composition_engine.compose(required_concepts, 
                                                self.get_all_providing_nodes())
    
    def pagerank(self) -> dict[str, float]:
        """Rank nodes by importance (connectivity)"""
        # Simplified PageRank for importance scoring
        scores = {n.id: 1.0 for n in self.get_all_nodes()}
        for _ in range(20):  # 20 iterations
            new_scores = {}
            for node in self.get_all_nodes():
                incoming = self.get_incoming_edges(node.id)
                score = 0.15  # damping
                for edge in incoming:
                    source_out_degree = len(self.get_outgoing_edges(edge.source_id))
                    score += 0.85 * scores[edge.source_id] / source_out_degree
                new_scores[node.id] = score
            scores = new_scores
        return scores
```

---

## 12. Cognitive Engine — Always-On Thinking

The Cognitive Engine is NOT invoked by user. It runs AUTOMATICALLY on every
message, every action, every result. It's the "thinking" layer.

```python
class CognitiveEngine:
    """Always-on thinking — activates on every event"""
    
    # ═══ TRIGGER 1: Session start ═══
    async def on_session_start(self, project: str):
        # 1. Activate everything related to this project
        project_context = self.graph.neighborhood(
            project, depth=3,
            types=["rule", "convention", "lesson", "skill", "blindspot", "episode"]
        )
        
        # 2. What was left unfinished?
        open_tasks = self.get_unfinished_tasks(project)
        
        # 3. Any pending reflection proposals?
        proposals = self.reflection.get_pending_proposals()
        
        # 4. Predict what user will likely do
        prediction = self.predictor.predict(project, current_time())
        
        # 5. Assemble session context
        return SessionContext(
            project_knowledge=project_context,
            open_tasks=open_tasks,
            proposals=proposals,
            prediction=prediction,
        )
    
    # ═══ TRIGGER 2: Every user message ═══
    async def on_user_message(self, message: str, project: str):
        # Extract concepts
        concepts = await self.extractor.extract_concepts(message)
        
        # Spreading activation through ENTIRE graph
        activated = self.associative.spread(concepts, depth=2)
        
        # Filter: only genuinely helpful results
        relevant = {k: v for k, v in activated.items() if v > 0.5}
        
        # Build context bundle
        context = await self.context_builder.build_from_activation(relevant)
        
        # Inject into Claude's thinking (not shown to user)
        return context
    
    # ═══ TRIGGER 3: Before every action ═══
    async def before_action(self, action_type: str, target: str):
        # What RULES apply to this action?
        rules = self.graph.query(
            f"nodes(type='rule') → edges(type='governs') → "
            f"nodes(name LIKE '%{target}%')"
        )
        
        # Were there FAILURES with similar actions?
        failures = self.episode_store.find(
            outcome="failure",
            concepts_overlap=self.extractor.extract_concepts(f"{action_type} {target}"),
            min_impact=0.5,
        )
        
        # Is there a READY solution?
        solutions = self.graph.query(
            f"nodes(type='solution') → edges(type='solves') → "
            f"nodes(name LIKE '%{target}%')"
        )
        
        # Which SKILL applies?
        skill = self.skill_store.match_trigger(f"{action_type} {target}")
        
        # Competency check
        competency = self.self_model.assess(
            self.extractor.extract_concepts(f"{action_type} {target}")
        )
        
        return ActionContext(
            rules=rules,
            past_failures=failures,
            available_solutions=solutions,
            applicable_skill=skill,
            competency=competency,
        )
    
    # ═══ TRIGGER 4: After every result ═══
    async def after_result(self, result: ActionResult):
        if result.is_failure:
            # Similar failures in the past?
            similar = self.episode_store.find_similar_failures(result)
            if similar:
                # "This happened before! Last time X helped."
                return Suggestion(
                    source="past_failure",
                    episodes=similar,
                    recommended_fix=similar[0].fix,
                )
            
            # Update self-model
            self.self_model.record_failure(result.domain)
        
        if result.is_success:
            # Update skill stats
            if result.used_skill:
                self.skill_store.record_use(result.used_skill, success=True)
            
            # Is this reusable?
            if self.is_reusable(result):
                await self.save_reusable_solution(result)
    
    # ═══ TRIGGER 5: Project switch ═══
    async def on_project_switch(self, from_project: str, to_project: str):
        # What's shared between projects?
        shared = self.graph.common_ancestors([from_project, to_project])
        
        # Transferable solutions?
        transferable = self.find_transferable(from_project, to_project)
        
        return ProjectSwitchContext(
            shared_concepts=shared,
            transferable_solutions=transferable,
        )
```

---

## 13. Feedback Loop

Every session result feeds back into the system, making it smarter.

```
┌──────────────────────────────────────────────────────────────┐
│                     FEEDBACK LOOP                             │
│                                                               │
│   Session ──────┐                                            │
│                 │                                             │
│                 ▼                                             │
│   ┌──────────────────────┐                                   │
│   │  Episode Capture     │ ← Auto from transcript            │
│   │  (what happened)     │                                   │
│   └─────────┬────────────┘                                   │
│             │                                                 │
│             ▼                                                 │
│   ┌──────────────────────┐                                   │
│   │  Signal Extraction   │                                   │
│   │                      │                                   │
│   │  ✓ correction_count  │ ← how many times user corrected  │
│   │  ✓ retry_count       │ ← how many retries needed        │
│   │  ✓ time_to_solve     │ ← how long it took               │
│   │  ✓ tools_efficiency  │ ← right tools used?              │
│   │  ✓ user_satisfaction │ ← "thanks!" vs "no, not that"    │
│   │  ✓ first_attempt_ok  │ ← solved on first try?           │
│   └─────────┬────────────┘                                   │
│             │                                                 │
│             ├──────────► Episode Store (experience)           │
│             ├──────────► Skill refinement (procedures)       │
│             ├──────────► Self Model update (meta-cognition)  │
│             ├──────────► Rule voting (upvote/downvote)       │
│             ├──────────► Graph edge strengthening             │
│             └──────────► Concept co-occurrence update         │
│                                                               │
│          Reflection Agent (every 6h)                          │
│                 │                                             │
│                 ▼                                             │
│          ┌──────────────┐                                    │
│          │  Synthesis   │                                     │
│          │  + Evolution │                                     │
│          └──────┬───────┘                                    │
│                 │                                             │
│                 ▼                                             │
│          ┌──────────────────┐                                │
│          │  Better Next     │                                 │
│          │  Session!        │ ← skills, rules, context       │
│          └──────────────────┘                                │
└──────────────────────────────────────────────────────────────┘
```

### Signal Extraction from Transcript

```python
class SignalExtractor:
    """Extract learning signals from session transcript"""
    
    async def extract(self, transcript: list[Message]) -> SessionSignals:
        corrections = 0
        retries = 0
        positive_signals = 0
        
        for i, msg in enumerate(transcript):
            if msg.role == "user":
                # Negative signals
                if self.is_correction(msg.text):
                    corrections += 1
                if self.is_retry_request(msg.text):
                    retries += 1
                
                # Positive signals
                if self.is_approval(msg.text):
                    positive_signals += 1
        
        return SessionSignals(
            correction_count=corrections,
            retry_count=retries,
            positive_count=positive_signals,
            total_messages=len(transcript),
            satisfaction_score=positive_signals / max(corrections + positive_signals, 1),
        )
    
    def is_correction(self, text: str) -> bool:
        patterns = [
            r"нет,?\s+(не\s+)?т(ак|о)", r"не\s+правильно", r"не\s+то",
            r"я\s+говор(ю|ил)", r"не\s+нужно", r"убери", r"верни",
            r"wrong", r"not what I", r"undo", r"revert",
        ]
        return any(re.search(p, text, re.I) for p in patterns)
    
    def is_approval(self, text: str) -> bool:
        patterns = [
            r"спасибо", r"отлично", r"супер", r"да,?\s+именно",
            r"правильно", r"хорошо", r"perfect", r"great", r"thanks",
        ]
        return any(re.search(p, text, re.I) for p in patterns)
```

---

## 14. Learning Metrics

How fast is the system getting smarter?

```python
@dataclass
class LearningMetrics:
    # Learning velocity
    skills_per_month: int           # new skills formed per month
    rules_per_month: int            # new rules generated per month
    corrections_trend: str          # "decreasing" = good!
    
    # Memory quality
    recall_precision: float         # % of recalled records that actually helped
    never_recalled_ratio: float     # % of useless records (currently 65%!)
    contradiction_count: int        # contradictions in knowledge base
    
    # Self-improvement
    blind_spots_found: int          # blind spots discovered
    blind_spots_resolved: int       # blind spots closed
    competency_growth: dict         # trends by domain
    
    # User satisfaction
    corrections_per_session: float  # trend should DECREASE
    first_attempt_success: float    # trend should INCREASE
    
    # Graph health
    total_nodes: int
    total_edges: int
    avg_connectivity: float         # edges per node
    orphan_nodes: int               # nodes with no connections
    strongest_clusters: list[str]   # top concept clusters

# Targets:
# Now:       1 rule / 364 sessions, 65% never recalled, no skills
# 3 months:  20+ skills, 10+ rules, never_recalled < 30%
# 6 months:  Predict user needs 50%+ of the time, corrections ↓50%
```

### Dashboard v5.0

Extends existing dashboard (port 37737) with new tabs:

```
┌─────────────────────────────────────────────────────────────┐
│  CLAUDE SUPER MEMORY v5.0 DASHBOARD                          │
│                                                               │
│  [Overview] [Graph] [Episodes] [Skills] [Self] [Reflection]  │
│                                                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ 1738 nodes  │ │ 12 skills   │ │ 87% recall  │            │
│  │ 4521 edges  │ │ rate: 0.82  │ │ precision   │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
│                                                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ 3 blind     │ │ corrections │ │ competency  │            │
│  │ spots       │ │ ↓ 23%/mo    │ │ Go: 0.90 ↑  │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
│                                                               │
│  [Graph Visualization — D3.js force-directed]                │
│  Interactive concept map with clickable nodes                │
│                                                               │
│  [Weekly Digest — latest reflection report]                  │
│  Focus areas, new skills, resolved blind spots               │
└─────────────────────────────────────────────────────────────┘
```

---

## 15. Database Schema

All in SQLite (single file, same as current `~/.claude-memory/memory.db`).

### New Tables (additions to existing schema)

```sql
-- ══════════════════════════════════════════
-- KNOWLEDGE GRAPH
-- ══════════════════════════════════════════

-- Graph nodes (concepts, entities, patterns, technologies)
CREATE TABLE graph_nodes (
    id TEXT PRIMARY KEY,                -- UUID v7
    type TEXT NOT NULL,                 -- NodeType enum value
    name TEXT NOT NULL,                 -- human-readable name
    content TEXT,                       -- full content/description
    properties JSON,                    -- flexible attributes
    source TEXT,                        -- "claude_md" | "skill" | "memory" | "auto"
    importance REAL DEFAULT 0.5,        -- PageRank-computed importance
    first_seen_at TEXT NOT NULL,        -- ISO 8601
    last_seen_at TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active'        -- active | archived
);

CREATE INDEX idx_graph_nodes_type ON graph_nodes(type);
CREATE INDEX idx_graph_nodes_name ON graph_nodes(name);
CREATE INDEX idx_graph_nodes_status ON graph_nodes(status);

-- Graph edges (relations between any nodes)
CREATE TABLE graph_edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES graph_nodes(id),
    target_id TEXT NOT NULL REFERENCES graph_nodes(id),
    relation_type TEXT NOT NULL,        -- from RELATION_TYPES
    weight REAL DEFAULT 1.0,            -- strengthened by co-occurrence
    context TEXT,                       -- why this relation exists
    created_at TEXT NOT NULL,
    last_reinforced_at TEXT,
    reinforcement_count INTEGER DEFAULT 0,
    UNIQUE(source_id, target_id, relation_type)
);

CREATE INDEX idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX idx_graph_edges_target ON graph_edges(target_id);
CREATE INDEX idx_graph_edges_type ON graph_edges(relation_type);

-- Link existing knowledge records to graph nodes
CREATE TABLE knowledge_nodes (
    knowledge_id INTEGER REFERENCES knowledge(id),
    node_id TEXT REFERENCES graph_nodes(id),
    role TEXT DEFAULT 'related',        -- provides | requires | mentions | governs
    strength REAL DEFAULT 1.0,
    PRIMARY KEY (knowledge_id, node_id)
);

-- ══════════════════════════════════════════
-- EPISODE STORE
-- ══════════════════════════════════════════

CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    project TEXT,
    timestamp TEXT NOT NULL,
    
    -- Narrative
    narrative TEXT NOT NULL,            -- 2-3 sentence story of what happened
    approaches_tried JSON,             -- ["approach A", "approach B"]
    key_insight TEXT,                   -- the aha moment
    
    -- Outcome
    outcome TEXT NOT NULL,              -- breakthrough | failure | routine | discovery
    impact_score REAL DEFAULT 0.5,     -- 0.0-1.0
    frustration_signals INTEGER DEFAULT 0,
    user_corrections JSON,             -- ["correction 1", "correction 2"]
    
    -- Context
    concepts JSON,                     -- ["auth", "webhook", "go"]
    entities JSON,                     -- ["ImPatient", "Stripe"]
    tools_used JSON,                   -- ["Bash", "Edit", "Agent"]
    duration_minutes INTEGER,
    
    -- Relations
    similar_to JSON,                   -- [episode_id, ...]
    led_to TEXT,                       -- solution/decision id
    contradicts TEXT,                   -- episode_id
    
    -- Metadata
    created_at TEXT NOT NULL,
    embedding_id TEXT                   -- reference to embeddings table
);

CREATE INDEX idx_episodes_project ON episodes(project);
CREATE INDEX idx_episodes_outcome ON episodes(outcome);
CREATE INDEX idx_episodes_impact ON episodes(impact_score);

-- ══════════════════════════════════════════
-- SKILL STORE
-- ══════════════════════════════════════════

CREATE TABLE skills (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,          -- "debug_go_compilation_error"
    trigger_pattern TEXT NOT NULL,      -- when this skill activates
    
    -- Procedure
    steps JSON NOT NULL,               -- ["step 1", "step 2", ...]
    anti_patterns JSON,                -- ["DON'T do X", "DON'T do Y"]
    
    -- Metrics
    times_used INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    avg_steps_to_solve REAL,
    
    -- Evolution
    version INTEGER DEFAULT 1,
    learned_from JSON,                 -- [episode_id, ...]
    last_refined_at TEXT,
    
    -- Context
    projects JSON,                     -- ["ImPatient", "JobFlow"]
    stack JSON,                        -- ["go", "postgresql"]
    related_skills JSON,               -- [skill_id, ...]
    
    -- Status
    status TEXT DEFAULT 'draft',       -- draft | active | mastered | deprecated
    created_at TEXT NOT NULL
);

CREATE INDEX idx_skills_status ON skills(status);
CREATE INDEX idx_skills_name ON skills(name);

-- Skill usage log (for tracking effectiveness)
CREATE TABLE skill_uses (
    id TEXT PRIMARY KEY,
    skill_id TEXT REFERENCES skills(id),
    episode_id TEXT REFERENCES episodes(id),
    success BOOLEAN NOT NULL,
    steps_used INTEGER,
    notes TEXT,
    used_at TEXT NOT NULL
);

-- ══════════════════════════════════════════
-- SELF MODEL
-- ══════════════════════════════════════════

CREATE TABLE competencies (
    domain TEXT PRIMARY KEY,            -- "go_backend", "css_styling"
    level REAL DEFAULT 0.5,            -- 0.0-1.0
    confidence REAL DEFAULT 0.3,       -- how sure about the assessment
    based_on INTEGER DEFAULT 0,        -- number of data points
    trend TEXT DEFAULT 'unknown',      -- improving | stable | declining
    last_updated TEXT NOT NULL
);

CREATE TABLE blind_spots (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    domains JSON,                      -- affected domains
    evidence JSON,                     -- episode_ids that show this
    severity REAL DEFAULT 0.5,         -- 0.0-1.0
    status TEXT DEFAULT 'active',      -- active | resolved | monitoring
    discovered_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE user_model (
    key TEXT PRIMARY KEY,               -- "communication_style", "peak_hours"
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 1,
    last_updated TEXT NOT NULL
);

-- ══════════════════════════════════════════
-- INGESTION QUEUE
-- ══════════════════════════════════════════

CREATE TABLE ingest_queue (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,               -- telegram | file_watch | webhook | url
    content_type TEXT NOT NULL,         -- text | image | pdf | url | code
    raw_content BLOB,
    text_content TEXT,
    metadata JSON,
    status TEXT DEFAULT 'pending',      -- pending | processing | stored | error
    error_message TEXT,
    created_at TEXT NOT NULL,
    processed_at TEXT
);

CREATE INDEX idx_ingest_status ON ingest_queue(status);

-- ══════════════════════════════════════════
-- REFLECTION
-- ══════════════════════════════════════════

CREATE TABLE reflection_reports (
    id TEXT PRIMARY KEY,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    type TEXT NOT NULL,                 -- session | periodic | weekly
    
    -- Stats
    new_nodes INTEGER DEFAULT 0,
    patterns_found INTEGER DEFAULT 0,
    skills_refined INTEGER DEFAULT 0,
    rules_proposed INTEGER DEFAULT 0,
    contradictions INTEGER DEFAULT 0,
    archived INTEGER DEFAULT 0,
    
    -- Content
    focus_areas JSON,
    key_findings JSON,
    proposed_changes JSON,
    
    created_at TEXT NOT NULL
);

CREATE TABLE pending_proposals (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                 -- rule | skill | claude_md_update
    content TEXT NOT NULL,
    evidence JSON,
    confidence REAL,
    status TEXT DEFAULT 'pending',      -- pending | approved | rejected
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);
```

---

## 16. MCP Tools (API)

### Existing tools (keep all 19):
`memory_recall`, `memory_save`, `memory_update`, `memory_delete`, `memory_forget`,
`memory_timeline`, `memory_stats`, `memory_consolidate`, `memory_export`,
`memory_observe`, `memory_relate`, `memory_history`, `memory_search_by_tag`,
`memory_extract_session`, `self_error_log`, `self_insight`, `self_rules`,
`self_patterns`, `self_reflect`, `self_rules_context`

### New tools (+12):

```python
# ═══ Associative Memory ═══

memory_associate(
    query: str,                     # "need SaaS with billing and auth"
    mode: str = "recall",           # "recall" | "composition"
    max_sources: int = 5,
    min_coverage: float = 0.7,
) -> AssociationResult
# Returns: activated nodes, ranked memories, composition (sources + gaps + conflicts)

memory_graph(
    node: str,                      # node name or ID
    depth: int = 2,
    relation_types: list[str] = None,
    include_types: list[str] = None,
) -> Subgraph
# Returns: neighborhood of a node in the graph

memory_concepts(
    query: str = None,              # search concepts
    list_all: bool = False,
    include_memories: bool = False,
) -> list[Concept]
# Returns: concepts matching query with linked memories

# ═══ Episodes ═══

memory_episode_save(
    narrative: str,
    outcome: str,                   # "breakthrough" | "failure" | "routine" | "discovery"
    impact_score: float,
    project: str,
    concepts: list[str],
    approaches_tried: list[str] = None,
    key_insight: str = None,
) -> Episode

memory_episode_recall(
    query: str = None,
    project: str = None,
    outcome: str = None,            # filter by outcome type
    min_impact: float = 0.0,
) -> list[Episode]

# ═══ Skills ═══

memory_skill_get(
    trigger: str,                   # natural language trigger to match
) -> Skill | None

memory_skill_update(
    skill_id: str,
    success: bool,
    notes: str = None,
    new_steps: list[str] = None,
    new_anti_pattern: str = None,
) -> Skill

# ═══ Self Model ═══

memory_self_assess(
    concepts: list[str],            # domains to assess
) -> CompetencyAssessment
# Returns: level, confidence, blind spots, recommendation

memory_self_blindspots(
    domain: str = None,             # filter by domain
) -> list[BlindSpot]

# ═══ Context & Reflection ═══

memory_context_build(
    query: str,
    project: str = None,
    max_tokens: int = 4000,
) -> ContextBundle
# Smart context: activation + graph + episodes + skills + self-model

memory_reflect_now(
    scope: str = "full",            # "quick" | "full" | "weekly"
) -> ReflectionReport
```

---

## 17. Implementation Plan

### Phase 0: Foundation (Week 1)
- [ ] Database schema migration (add new tables)
- [ ] Graph node/edge CRUD operations
- [ ] ConceptExtractor (Ollama-based)
- [ ] CLAUDE.md parser → graph nodes
- [ ] Skills indexer → graph nodes
- [ ] Tests for graph operations

### Phase 1: Associative Core (Week 2)  
- [ ] Spreading activation algorithm
- [ ] `memory_associate()` MCP tool
- [ ] `memory_graph()` MCP tool
- [ ] `memory_concepts()` MCP tool
- [ ] Integration with existing `memory_recall()` (add activation as 5th search tier)
- [ ] Auto-concept extraction on `memory_save()`

### Phase 2: Episodes & Skills (Week 3)
- [ ] Episode Store (save, recall, search)
- [ ] Auto episode capture from session transcripts
- [ ] Skill Store (create, match, update)
- [ ] `memory_episode_save/recall()` tools
- [ ] `memory_skill_get/update()` tools
- [ ] Hook: session-end → auto episode capture

### Phase 3: Self Model (Week 4)
- [ ] Competency tracking
- [ ] Blind spot detection
- [ ] User model (learned preferences)
- [ ] `memory_self_assess()` tool
- [ ] `memory_self_blindspots()` tool
- [ ] Signal extraction from transcripts

### Phase 4: Reflection Agent (Week 5)
- [ ] Digest phase (dedup, decay, contradictions)
- [ ] Synthesize phase (clustering, patterns, graph enrichment)
- [ ] Evolve phase (skill refinement, rule generation, self-model update)
- [ ] APScheduler integration
- [ ] `memory_reflect_now()` tool
- [ ] Weekly digest generation

### Phase 5: Smart Output (Week 6)
- [ ] Context Builder (activation + ranking + token budget)
- [ ] `memory_context_build()` tool
- [ ] Cognitive Engine hooks (session start, message, action, result)
- [ ] CLAUDE.md Auto-Updater
- [ ] Predictive Context

### Phase 6: Ingestion Gateway (Week 7)
- [ ] Telegram Bot (aiogram)
- [ ] File Watcher (watchdog)
- [ ] Web Hook endpoint
- [ ] OCR (Apple Vision)
- [ ] URL scraper (trafilatura)
- [ ] Semantic chunking

### Phase 7: Dashboard & Polish (Week 8)
- [ ] Dashboard v5.0 (new tabs: Graph, Episodes, Skills, Self)
- [ ] D3.js graph visualization
- [ ] Learning metrics display
- [ ] Reflection reports view
- [ ] Performance optimization
- [ ] Full test coverage

---

## 18. File Structure

```
~/claude-memory-server/
├── src/
│   ├── server.py                  # MCP server (extend with new tools)
│   ├── models.py                  # All dataclasses: Episode, Skill, SelfModel, etc.
│   ├── cache.py                   # LRU cache (existing)
│   ├── reembed.py                 # Re-embedding script (existing)
│   ├── reranker.py                # HyDE + reranker (existing)
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── store.py               # GraphStore: CRUD for nodes and edges
│   │   ├── query.py               # GraphQuery: neighborhood, path, pagerank
│   │   ├── indexer.py             # Index CLAUDE.md + Skills into graph
│   │   └── enricher.py            # Co-occurrence, PageRank, communities
│   │
│   ├── associative/
│   │   ├── __init__.py
│   │   ├── activation.py          # Spreading activation algorithm
│   │   ├── composition.py         # Composition engine (set cover + conflicts)
│   │   └── recall.py              # AssociativeRecall (full pipeline)
│   │
│   ├── cognitive/
│   │   ├── __init__.py
│   │   ├── engine.py              # CognitiveEngine (always-on triggers)
│   │   ├── context_builder.py     # Smart context assembly
│   │   ├── predictor.py           # Predictive context
│   │   └── claude_md.py           # CLAUDE.md auto-updater
│   │
│   ├── memory_systems/
│   │   ├── __init__.py
│   │   ├── episode_store.py       # Episodic memory
│   │   ├── skill_store.py         # Procedural memory
│   │   ├── self_model.py          # Meta-cognitive memory
│   │   └── signals.py             # Signal extraction from transcripts
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── gateway.py             # Unified ingestion gateway
│   │   ├── chunker.py             # Semantic chunking
│   │   ├── ocr.py                 # Apple Vision OCR
│   │   ├── scraper.py             # URL scraping (trafilatura)
│   │   ├── enricher.py            # Metadata + concept extraction
│   │   └── extractor.py           # ConceptExtractor (Ollama)
│   │
│   ├── reflection/
│   │   ├── __init__.py
│   │   ├── agent.py               # Main reflection loop
│   │   ├── digest.py              # Phase 1: cleanup
│   │   ├── synthesize.py          # Phase 2: patterns & generalization
│   │   ├── evolve.py              # Phase 3: skills, rules, self-model
│   │   └── scheduler.py           # APScheduler cron
│   │
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── learning.py            # Learning velocity metrics
│   │   └── dashboard.py           # Dashboard v5.0 (extend existing)
│   │
│   ├── extract_transcript.py      # Existing transcript parser
│   ├── auto_session_save.py       # Existing auto-save
│   └── auto_extract_active.py     # Existing active extraction
│
├── telegram/
│   ├── bot.py                     # Telegram bot (aiogram)
│   └── handlers.py                # Message handlers
│
├── ollama/
│   ├── rag_chat.py                # Existing RAG chat
│   ├── lookup_memory.sh           # Existing lookup script
│   ├── export_knowledge.py        # Existing export
│   └── sync_to_ollama.sh          # Existing sync
│
├── tests/
│   ├── test_graph.py
│   ├── test_activation.py
│   ├── test_composition.py
│   ├── test_episodes.py
│   ├── test_skills.py
│   ├── test_self_model.py
│   ├── test_reflection.py
│   ├── test_context_builder.py
│   ├── test_ingestion.py
│   └── test_concept_extractor.py
│
├── docs/
│   ├── SUPER-MEMORY-v5-SPEC.md    # THIS FILE
│   └── ARCHITECTURE.md            # Architecture diagrams
│
├── migrations/
│   └── 001_v5_schema.sql          # Database migration script
│
├── pyproject.toml                 # Existing
├── README.md                      # Existing (update)
├── SYSTEM-OVERVIEW.md             # Existing (update)
└── CLAUDE.md                      # Project-level instructions
```

---

## Summary: What Makes This "Super"

1. **Unified Graph** — Rules, skills, memories, episodes, concepts, entities —
   ALL in ONE connected network. Not separate systems, ONE brain.

2. **Associative Recall** — Spreading activation, not keyword search. A wave of
   activation through the entire graph, finding connections humans would miss.

3. **Composition** — Not just "found similar", but "here's how to COMBINE 3
   different pieces into a complete solution, with conflicts and gaps identified".

4. **Episodes** — Remembers HOW things happened (narrative, failures, insights),
   not just WHAT was decided. Failures remembered longer than successes.

5. **Skills** — Learns HOW to do things (procedures), not just WHAT happened.
   Skills improve with each use, anti-patterns from failures.

6. **Self-Knowledge** — Knows own strengths, weaknesses, blind spots. Adjusts
   behavior based on self-assessment. Honest about uncertainty.

7. **Reflection ("Sleep")** — Background process that consolidates, generalizes,
   finds patterns, creates new knowledge. Gets smarter while you sleep.

8. **Predictive Context** — Anticipates needs based on patterns. "User opened
   project X at 23:00 → likely debugging → prepare relevant episodes and skills."

9. **Always-On Cognitive Engine** — Not invoked by command. Runs on EVERY message,
   EVERY action. Rules + skills + episodes + lessons = ONE unified response.

10. **Continuous Learning** — Every session → episode → patterns → skills → rules.
    Every correction → blind spot detection → self-improvement.
    Target: corrections ↓50% in 6 months.

---

*Version: 5.0-spec*
*Created: 2026-04-07*
*Status: Design specification — ready for implementation*
