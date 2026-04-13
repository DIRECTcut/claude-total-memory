"""Tests for Episode Store — episodic memory management."""

import pytest


class TestEpisodeStore:
    def test_save_episode(self, episode_store):
        eid = episode_store.save(
            session_id="sess-1",
            narrative="Fixed auth bug",
            outcome="breakthrough",
            project="myproject",
            impact_score=0.8,
        )
        assert eid is not None
        assert len(eid) == 32  # UUID hex

    def test_get_episode(self, episode_store):
        eid = episode_store.save(
            session_id="sess-1",
            narrative="Test narrative",
            outcome="routine",
        )
        ep = episode_store.get(eid)
        assert ep is not None
        assert ep["narrative"] == "Test narrative"
        assert ep["outcome"] == "routine"
        assert ep["session_id"] == "sess-1"

    def test_get_episode_not_found(self, episode_store):
        assert episode_store.get("nonexistent") is None

    def test_find_similar_by_concepts(self, episode_store):
        episode_store.save(
            session_id="s1", narrative="JWT auth",
            outcome="routine", concepts=["jwt", "auth"],
        )
        episode_store.save(
            session_id="s2", narrative="OAuth flow",
            outcome="routine", concepts=["oauth", "auth"],
        )
        episode_store.save(
            session_id="s3", narrative="DB migration",
            outcome="routine", concepts=["postgres", "migration"],
        )

        results = episode_store.find_similar(concepts=["auth", "jwt"])
        assert len(results) >= 1
        # The jwt+auth episode should rank first by concept overlap
        assert "auth" in str(results[0]["concepts"]).lower() or \
               "jwt" in str(results[0]["concepts"]).lower()

    def test_find_failures(self, episode_store):
        episode_store.save(
            session_id="s1", narrative="Deploy failed",
            outcome="failure", impact_score=0.9,
        )
        episode_store.save(
            session_id="s2", narrative="All good",
            outcome="routine", impact_score=0.3,
        )

        failures = episode_store.find_failures()
        assert len(failures) == 1
        assert failures[0]["outcome"] == "failure"

    def test_find_failures_min_impact(self, episode_store):
        episode_store.save(
            session_id="s1", narrative="Minor fail",
            outcome="failure", impact_score=0.3,
        )
        episode_store.save(
            session_id="s2", narrative="Major fail",
            outcome="failure", impact_score=0.8,
        )

        results = episode_store.find_failures(min_impact=0.5)
        assert len(results) == 1
        assert results[0]["impact_score"] >= 0.5

    def test_get_recent(self, episode_store):
        eid = episode_store.save(
            session_id="s1", narrative="Recent work",
            outcome="routine",
        )
        recent = episode_store.get_recent(days=1)
        assert len(recent) >= 1
        assert any(e["id"] == eid for e in recent)

    def test_episode_stats(self, episode_store):
        episode_store.save(session_id="s1", narrative="A", outcome="routine", impact_score=0.5)
        episode_store.save(session_id="s2", narrative="B", outcome="failure", impact_score=0.8)
        episode_store.save(session_id="s3", narrative="C", outcome="breakthrough", impact_score=0.9)

        stats = episode_store.stats()
        assert stats["total"] == 3
        assert stats["by_outcome"]["routine"] == 1
        assert stats["by_outcome"]["failure"] == 1
        assert stats["by_outcome"]["breakthrough"] == 1
        assert stats["avg_impact"] > 0

    def test_outcome_validation(self, episode_store):
        with pytest.raises(ValueError, match="Invalid outcome"):
            episode_store.save(
                session_id="s1", narrative="Bad", outcome="invalid_type"
            )

    def test_impact_score_clamped(self, episode_store):
        eid = episode_store.save(
            session_id="s1", narrative="Over limit",
            outcome="routine", impact_score=5.0,
        )
        ep = episode_store.get(eid)
        assert ep["impact_score"] <= 1.0

        eid2 = episode_store.save(
            session_id="s2", narrative="Under limit",
            outcome="routine", impact_score=-2.0,
        )
        ep2 = episode_store.get(eid2)
        assert ep2["impact_score"] >= 0.0

    def test_update_similar(self, episode_store):
        eid1 = episode_store.save(session_id="s1", narrative="A", outcome="routine")
        eid2 = episode_store.save(session_id="s2", narrative="B", outcome="routine")

        episode_store.update_similar(eid1, [eid2])
        ep = episode_store.get(eid1)
        assert eid2 in ep["similar_to"]

    def test_multiple_episodes_by_project(self, episode_store):
        episode_store.save(session_id="s1", narrative="P1 work", outcome="routine", project="proj1")
        episode_store.save(session_id="s2", narrative="P2 work", outcome="routine", project="proj2")
        episode_store.save(session_id="s3", narrative="P1 more", outcome="routine", project="proj1")

        stats_p1 = episode_store.stats(project="proj1")
        stats_p2 = episode_store.stats(project="proj2")
        assert stats_p1["total"] == 2
        assert stats_p2["total"] == 1

    def test_episode_with_all_fields(self, episode_store):
        eid = episode_store.save(
            session_id="s1",
            narrative="Full episode",
            outcome="discovery",
            project="test-project",
            impact_score=0.75,
            concepts=["go", "grpc", "microservices"],
            entities=["OrderService"],
            approaches_tried=["monolith", "microservice"],
            key_insight="gRPC is faster for inter-service communication",
            frustration_signals=2,
            user_corrections=["use proto3 not proto2"],
            tools_used=["protoc", "grpcurl"],
            duration_minutes=45,
        )
        ep = episode_store.get(eid)
        assert ep["outcome"] == "discovery"
        assert ep["project"] == "test-project"
        assert "go" in ep["concepts"]
        assert "monolith" in ep["approaches_tried"]
        assert ep["key_insight"] == "gRPC is faster for inter-service communication"
        assert ep["frustration_signals"] == 2
        assert ep["duration_minutes"] == 45
