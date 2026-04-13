"""Tests for Graph Store CRUD and Graph Query traversal/analysis."""

import pytest


# ══════════════════════════════════════════════════════════
# GraphStore CRUD Tests
# ══════════════════════════════════════════════════════════


class TestGraphStoreNodes:
    def test_add_node_creates_node(self, graph_store):
        node_id = graph_store.add_node("concept", "auth", content="Authentication")
        assert node_id is not None
        node = graph_store.get_node(node_id)
        assert node is not None
        assert node["name"] == "auth"
        assert node["type"] == "concept"
        assert node["content"] == "Authentication"

    def test_add_node_idempotent(self, graph_store):
        id1 = graph_store.add_node("concept", "auth", content="v1")
        id2 = graph_store.add_node("concept", "auth", content="v2")
        assert id1 == id2
        node = graph_store.get_node(id1)
        assert node["content"] == "v2"
        assert node["mention_count"] == 2

    def test_get_node_by_name(self, graph_store):
        graph_store.add_node("concept", "billing")
        node = graph_store.get_node_by_name("billing", "concept")
        assert node is not None
        assert node["name"] == "billing"

    def test_get_node_by_name_not_found(self, graph_store):
        assert graph_store.get_node_by_name("nonexistent") is None

    def test_get_or_create_existing(self, graph_store):
        id1 = graph_store.add_node("concept", "go")
        id2 = graph_store.get_or_create("go", "concept")
        assert id1 == id2

    def test_get_or_create_new(self, graph_store):
        node_id = graph_store.get_or_create("python", "technology")
        assert node_id is not None
        node = graph_store.get_node(node_id)
        assert node["name"] == "python"
        assert node["type"] == "technology"

    def test_delete_node_cascades_edges(self, graph_store):
        a = graph_store.add_node("concept", "a")
        b = graph_store.add_node("concept", "b")
        graph_store.add_edge(a, b, "uses")

        assert graph_store.delete_node(a)
        assert graph_store.get_node(a) is None
        assert graph_store.get_edges(b) == []

    def test_delete_node_not_found(self, graph_store):
        assert graph_store.delete_node("nonexistent") is False

    def test_touch_node_increments(self, graph_store):
        node_id = graph_store.add_node("concept", "touch_test")
        node_before = graph_store.get_node(node_id)
        initial_count = node_before["mention_count"]

        graph_store.touch_node(node_id)
        node_after = graph_store.get_node(node_id)
        assert node_after["mention_count"] == initial_count + 1

    def test_update_node(self, graph_store):
        node_id = graph_store.add_node("concept", "updatable", content="old")
        result = graph_store.update_node(node_id, content="new", importance=0.9)
        assert result is True
        node = graph_store.get_node(node_id)
        assert node["content"] == "new"
        assert node["importance"] == 0.9


class TestGraphStoreEdges:
    def test_add_edge_creates_edge(self, graph_store):
        a = graph_store.add_node("concept", "a")
        b = graph_store.add_node("concept", "b")
        edge_id = graph_store.add_edge(a, b, "uses", weight=0.8)
        assert edge_id is not None

        edges = graph_store.get_edges(a, direction="outgoing")
        assert len(edges) == 1
        assert edges[0]["relation_type"] == "uses"
        assert edges[0]["weight"] == 0.8

    def test_add_edge_no_self_loops(self, graph_store):
        a = graph_store.add_node("concept", "self")
        with pytest.raises(ValueError, match="Self-loops"):
            graph_store.add_edge(a, a, "uses")

    def test_add_edge_reinforce_existing(self, graph_store):
        a = graph_store.add_node("concept", "a")
        b = graph_store.add_node("concept", "b")
        e1 = graph_store.add_edge(a, b, "uses", weight=0.5)
        e2 = graph_store.add_edge(a, b, "uses")
        assert e1 == e2

        edges = graph_store.get_edges(a, direction="outgoing")
        assert edges[0]["weight"] == 0.6  # 0.5 + 0.1
        assert edges[0]["reinforcement_count"] == 1

    def test_add_edge_nonexistent_node(self, graph_store):
        a = graph_store.add_node("concept", "exists")
        with pytest.raises(ValueError, match="does not exist"):
            graph_store.add_edge(a, "nonexistent_id", "uses")

    def test_get_edges_outgoing(self, graph_store, populated_graph):
        edges = graph_store.get_edges(populated_graph["saas"], direction="outgoing")
        assert len(edges) == 2
        targets = {e["target_id"] for e in edges}
        assert populated_graph["auth"] in targets
        assert populated_graph["billing"] in targets

    def test_get_edges_incoming(self, graph_store, populated_graph):
        edges = graph_store.get_edges(populated_graph["auth"], direction="incoming")
        assert len(edges) == 1
        assert edges[0]["source_id"] == populated_graph["saas"]

    def test_get_edges_both(self, graph_store, populated_graph):
        edges = graph_store.get_edges(populated_graph["auth"], direction="both")
        # Incoming from saas + outgoing to jwt + outgoing to go
        assert len(edges) == 3

    def test_reinforce_edge(self, graph_store):
        a = graph_store.add_node("concept", "a")
        b = graph_store.add_node("concept", "b")
        graph_store.add_edge(a, b, "uses", weight=1.0)

        graph_store.reinforce_edge(a, b, "uses", weight_delta=0.5)
        edges = graph_store.get_edges(a, direction="outgoing")
        assert edges[0]["weight"] == 1.5


class TestGraphStoreBulk:
    def test_link_knowledge(self, db, graph_store):
        node_id = graph_store.add_node("concept", "auth")
        # Insert a knowledge record first
        db.execute(
            "INSERT INTO knowledge (id, type, content, created_at) VALUES (1, 'solution', 'Auth solution', '2025-01-01')"
        )
        db.commit()

        graph_store.link_knowledge(1, node_id, role="provides", strength=0.9)
        links = graph_store.get_knowledge_nodes(1)
        assert len(links) == 1
        assert links[0]["name"] == "auth"

    def test_search_nodes(self, graph_store, populated_graph):
        results = graph_store.search_nodes("auth")
        assert len(results) >= 1
        assert any(n["name"] == "authentication" for n in results)

    def test_search_nodes_by_type(self, graph_store, populated_graph):
        results = graph_store.search_nodes("go", type="technology")
        assert len(results) == 1
        assert results[0]["name"] == "go"

    def test_get_neighbors(self, graph_store, populated_graph):
        neighbors = graph_store.get_neighbors(populated_graph["auth"])
        neighbor_ids = {nid for nid, _ in neighbors}
        assert populated_graph["saas"] in neighbor_ids
        assert populated_graph["jwt"] in neighbor_ids
        assert populated_graph["go"] in neighbor_ids

    def test_remove_orphans(self, graph_store):
        orphan = graph_store.add_node("concept", "orphan_node")
        removed = graph_store.remove_orphans()
        assert removed >= 1
        assert graph_store.get_node(orphan) is None

    def test_remove_weak_edges(self, graph_store):
        a = graph_store.add_node("concept", "a")
        b = graph_store.add_node("concept", "b")
        graph_store.add_edge(a, b, "weak", weight=0.05)
        removed = graph_store.remove_weak_edges(min_weight=0.1)
        assert removed == 1
        assert graph_store.get_edges(a) == []

    def test_stats(self, graph_store, populated_graph):
        stats = graph_store.stats()
        assert stats["total_nodes"] == 6
        assert stats["total_edges"] == 6
        assert stats["nodes_by_type"]["concept"] == 5
        assert stats["nodes_by_type"]["technology"] == 1
        assert stats["avg_edge_weight"] > 0


# ══════════════════════════════════════════════════════════
# GraphQuery Tests
# ══════════════════════════════════════════════════════════


class TestGraphQueryTraversal:
    def test_neighborhood_depth_1(self, graph_query, populated_graph):
        result = graph_query.neighborhood(populated_graph["auth"], depth=1)
        node_names = {n["name"] for n in result["nodes"]}
        assert "authentication" in node_names
        assert "jwt" in node_names
        assert "go" in node_names
        assert "saas" in node_names

    def test_neighborhood_depth_2(self, graph_query, populated_graph):
        result = graph_query.neighborhood(populated_graph["jwt"], depth=2)
        node_names = {n["name"] for n in result["nodes"]}
        assert "jwt" in node_names
        assert "authentication" in node_names
        # depth 2 should reach saas via jwt->auth->saas
        assert "saas" in node_names

    def test_neighborhood_type_filter(self, graph_query, populated_graph):
        result = graph_query.neighborhood(
            populated_graph["saas"], depth=2, types=["technology"]
        )
        # Only technology nodes should be included (besides origin)
        non_origin_nodes = [
            n for n in result["nodes"] if n["id"] != populated_graph["saas"]
        ]
        for n in non_origin_nodes:
            assert n["type"] == "technology"

    def test_neighborhood_nonexistent(self, graph_query):
        result = graph_query.neighborhood("nonexistent")
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_shortest_path(self, graph_query, populated_graph):
        path = graph_query.shortest_path(
            populated_graph["jwt"], populated_graph["billing"]
        )
        assert path is not None
        assert len(path) >= 2  # jwt->auth->saas->billing or jwt->auth, auth->saas->billing

    def test_shortest_path_same_node(self, graph_query, populated_graph):
        path = graph_query.shortest_path(
            populated_graph["auth"], populated_graph["auth"]
        )
        assert path == []

    def test_shortest_path_no_path(self, graph_query, graph_store):
        a = graph_store.add_node("concept", "isolated_a")
        b = graph_store.add_node("concept", "isolated_b")
        path = graph_query.shortest_path(a, b)
        assert path is None


class TestGraphQueryAnalysis:
    def test_pagerank(self, graph_query, populated_graph):
        scores = graph_query.pagerank()
        assert len(scores) == 6
        total = sum(scores.values())
        assert abs(total - 1.0) < 0.01  # normalized to 1.0

        # auth and go should have high scores (many connections)
        auth_score = scores[populated_graph["auth"]]
        jwt_score = scores[populated_graph["jwt"]]
        assert auth_score > jwt_score

    def test_pagerank_empty_graph(self, db):
        from graph.store import GraphStore
        from graph.query import GraphQuery
        store = GraphStore(db)
        query = GraphQuery(store)
        assert query.pagerank() == {}

    def test_communities(self, graph_query, populated_graph):
        # All 6 nodes are connected, so expect 1 community with min_size=3
        communities = graph_query.find_communities(min_size=3)
        assert len(communities) >= 1
        assert len(communities[0]) == 6

    def test_communities_min_size_filter(self, graph_query, populated_graph):
        # With min_size=7, no community should pass
        communities = graph_query.find_communities(min_size=7)
        assert len(communities) == 0
