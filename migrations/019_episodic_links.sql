-- v10.0.0 — Episodic links (Entity → Event → Fact).
--
-- Beever Atlas's persister builds an Entity → Event → Fact chain in
-- Neo4j: every saved fact spawns an Event node, the entities mentioned
-- in the fact link to the Event via MENTIONED_IN edges, and the Event
-- references the Fact. This unlocks queries like "show me every save
-- where Bob and Postgres were mentioned together" via a single graph
-- traversal — pure vector RAG can't do that without a re-embed loop.
--
-- We piggy-back on the existing graph: Event becomes a new
-- `graph_nodes.type='event'`, MENTIONED_IN becomes a graph_edges
-- relation_type, and the Event ↔ Knowledge link goes through the
-- existing `knowledge_nodes` table with `role='represents'`.
--
-- This migration adds indexes that keep those queries fast as the
-- volume of event nodes grows (one per save_knowledge call).

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_role ON knowledge_nodes(role);

-- Composite index: "give me all events that involve this entity" hits
-- (target=entity_id, relation_type='mentioned_in') a lot.
CREATE INDEX IF NOT EXISTS idx_graph_edges_target_type
    ON graph_edges(target_id, relation_type);

-- Co-mention queries scan source_id by relation_type.
CREATE INDEX IF NOT EXISTS idx_graph_edges_source_type
    ON graph_edges(source_id, relation_type);
