"""Tests for Skill Store — procedural memory management."""

import pytest


class TestSkillStore:
    def test_create_skill(self, skill_store):
        sid = skill_store.create(
            name="deploy_docker",
            trigger_pattern="deploy docker container kubernetes",
            steps=["Build image", "Push to registry", "Apply k8s manifest"],
            stack=["docker", "kubernetes"],
        )
        assert sid is not None
        assert len(sid) == 32

    def test_get_by_name(self, skill_store):
        skill_store.create(
            name="setup_grpc",
            trigger_pattern="grpc protobuf service",
            steps=["Define proto", "Generate code", "Implement server"],
        )
        skill = skill_store.get_by_name("setup_grpc")
        assert skill is not None
        assert skill["name"] == "setup_grpc"
        assert skill["status"] == "draft"
        assert skill["version"] == 1
        assert len(skill["steps"]) == 3

    def test_get_by_name_not_found(self, skill_store):
        assert skill_store.get_by_name("nonexistent") is None

    def test_match_trigger_exact(self, skill_store):
        skill_store.create(
            name="jwt_auth",
            trigger_pattern="jwt authentication token validation",
            steps=["Parse token", "Validate signature", "Extract claims"],
        )
        matches = skill_store.match_trigger("jwt authentication")
        assert len(matches) >= 1
        assert matches[0]["name"] == "jwt_auth"

    def test_match_trigger_partial(self, skill_store):
        skill_store.create(
            name="db_migration",
            trigger_pattern="database migration postgresql schema",
            steps=["Create migration file", "Write SQL", "Apply"],
        )
        matches = skill_store.match_trigger("postgresql migration")
        assert len(matches) >= 1

    def test_match_trigger_no_match(self, skill_store):
        skill_store.create(
            name="unrelated",
            trigger_pattern="quantum physics particle accelerator",
            steps=["Step 1"],
        )
        matches = skill_store.match_trigger("docker kubernetes deploy")
        assert len(matches) == 0

    def test_record_use_updates_metrics(self, skill_store):
        sid = skill_store.create(
            name="test_skill",
            trigger_pattern="test trigger",
            steps=["Step 1"],
        )
        skill_store.record_use(sid, success=True, steps_used=3)
        skill = skill_store.get(sid)
        assert skill["times_used"] == 1
        assert skill["success_rate"] == 1.0

        skill_store.record_use(sid, success=False)
        skill = skill_store.get(sid)
        assert skill["times_used"] == 2
        assert skill["success_rate"] == 0.5

    def test_record_use_auto_promote(self, skill_store):
        sid = skill_store.create(
            name="promote_test",
            trigger_pattern="promote trigger",
            steps=["Step 1"],
        )
        # Draft -> active after 3+ uses
        for _ in range(3):
            skill_store.record_use(sid, success=True)
        skill = skill_store.get(sid)
        assert skill["status"] == "active"

        # Active -> mastered after 10+ uses with 80%+ success
        for _ in range(7):
            skill_store.record_use(sid, success=True)
        skill = skill_store.get(sid)
        assert skill["status"] == "mastered"

    def test_refine_adds_steps(self, skill_store):
        sid = skill_store.create(
            name="refinable",
            trigger_pattern="refine trigger",
            steps=["Old step 1"],
        )
        skill_store.refine(sid, new_steps=["New step 1", "New step 2"])
        skill = skill_store.get(sid)
        assert len(skill["steps"]) == 2
        assert skill["steps"][0] == "New step 1"
        assert skill["version"] == 2

    def test_refine_adds_anti_pattern(self, skill_store):
        sid = skill_store.create(
            name="anti_test",
            trigger_pattern="anti trigger",
            steps=["Step 1"],
        )
        skill_store.refine(sid, new_anti_pattern="Never use global state")
        skill = skill_store.get(sid)
        assert "Never use global state" in skill["anti_patterns"]

    def test_refine_increments_version(self, skill_store):
        sid = skill_store.create(
            name="version_test",
            trigger_pattern="version trigger",
            steps=["Step 1"],
        )
        skill_store.refine(sid, new_steps=["Updated"])
        skill_store.refine(sid, new_anti_pattern="Bad pattern")
        skill = skill_store.get(sid)
        assert skill["version"] == 3

    def test_refine_nonexistent_raises(self, skill_store):
        with pytest.raises(ValueError, match="not found"):
            skill_store.refine("nonexistent_id", new_steps=["X"])

    def test_deprecate(self, skill_store):
        sid = skill_store.create(
            name="deprecatable",
            trigger_pattern="deprecate trigger",
            steps=["Step 1"],
        )
        skill_store.deprecate(sid)
        skill = skill_store.get(sid)
        assert skill["status"] == "deprecated"

        # Deprecated skills should not match triggers
        matches = skill_store.match_trigger("deprecate trigger")
        assert len(matches) == 0

    def test_skill_stats(self, skill_store):
        skill_store.create(name="s1", trigger_pattern="t1", steps=["a"])
        skill_store.create(name="s2", trigger_pattern="t2", steps=["b"])

        stats = skill_store.stats()
        assert stats["total"] == 2
        assert stats["by_status"]["draft"] == 2
        assert stats["total_uses"] == 0
