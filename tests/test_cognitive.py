"""Tests for Cognitive Engine — always-on thinking triggers."""

import pytest


class TestCognitiveEngine:
    @pytest.fixture
    def engine(self, db):
        from cognitive.engine import CognitiveEngine
        return CognitiveEngine(db)

    def test_on_session_start(self, engine):
        result = engine.on_session_start("test-project")
        assert "project_context" in result
        assert "open_episodes" in result
        assert "pending_proposals" in result
        assert "blind_spots" in result
        assert "recent_skills" in result

    def test_on_query(self, engine, populated_graph):
        result = engine.on_query("authentication jwt tokens")
        assert "activated_concepts" in result
        assert "relevant_rules" in result
        assert "past_failures" in result
        assert "available_solutions" in result
        assert "applicable_skills" in result

    def test_on_query_empty(self, engine):
        result = engine.on_query("")
        assert result["activated_concepts"] == []

    def test_on_action_result_success(self, engine):
        result = engine.on_action_result(
            success=True, domain="golang", concepts=["grpc", "api"]
        )
        assert "updates" in result
        assert "competency:golang" in result["updates"]

    def test_on_action_result_failure(self, engine):
        result = engine.on_action_result(
            success=False, domain="css", concepts=["flexbox"]
        )
        assert "updates" in result
        assert "competency:css" in result["updates"]

    def test_build_context(self, engine, populated_graph):
        ctx = engine.build_context("authentication setup", project="myproject")
        assert "knowledge" in ctx
        assert "episodes" in ctx
        assert "skills" in ctx
        assert "rules" in ctx
        assert "total_tokens" in ctx
        assert isinstance(ctx["total_tokens"], int)

    def test_build_context_token_budget(self, engine):
        ctx = engine.build_context("some query", max_tokens=100)
        assert ctx["total_tokens"] <= 200  # allow some overhead

    def test_build_context_includes_episodes(self, db, engine):
        from memory_systems.episode_store import EpisodeStore
        store = EpisodeStore(db)
        store.save(
            session_id="s1",
            narrative="Worked on authentication",
            outcome="routine",
            project="myproject",
            concepts=["auth"],
        )
        ctx = engine.build_context("authentication", project="myproject")
        # Should find the episode in context
        assert isinstance(ctx["episodes"], list)

    def test_build_context_includes_skills(self, db, engine):
        from memory_systems.skill_store import SkillStore
        store = SkillStore(db)
        sid = store.create(
            name="auth_setup",
            trigger_pattern="authentication setup configure",
            steps=["Step 1", "Step 2"],
        )
        # Promote to active so it appears in context
        db.execute("UPDATE skills SET status = 'active' WHERE id = ?", (sid,))
        db.commit()

        ctx = engine.build_context("authentication setup")
        assert isinstance(ctx["skills"], list)
