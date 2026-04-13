"""Tests for Self Model — meta-cognitive memory management."""

import pytest


class TestCompetencies:
    def test_update_competency_breakthrough(self, self_model):
        self_model.update_competency("golang", "breakthrough")
        comp = self_model.get_competency("golang")
        assert comp is not None
        assert comp["level"] > 0.5  # 0.5 + 0.02
        assert comp["based_on"] == 1

    def test_update_competency_failure(self, self_model):
        self_model.update_competency("kubernetes", "failure")
        comp = self_model.get_competency("kubernetes")
        assert comp is not None
        assert comp["level"] < 0.5  # 0.5 - 0.01

    def test_update_competency_routine(self, self_model):
        self_model.update_competency("python", "routine")
        comp = self_model.get_competency("python")
        assert comp is not None
        assert comp["level"] == pytest.approx(0.505, abs=0.001)

    def test_competency_level_clamped(self, self_model):
        # Drive level to near 0 with many failures
        for _ in range(100):
            self_model.update_competency("bad_domain", "failure")
        comp = self_model.get_competency("bad_domain")
        assert comp["level"] >= 0.0

        # Drive level to near 1 with many breakthroughs
        for _ in range(100):
            self_model.update_competency("great_domain", "breakthrough")
        comp = self_model.get_competency("great_domain")
        assert comp["level"] <= 1.0

    def test_update_competency_increments_based_on(self, self_model):
        self_model.update_competency("rust", "routine")
        self_model.update_competency("rust", "breakthrough")
        self_model.update_competency("rust", "failure")
        comp = self_model.get_competency("rust")
        assert comp["based_on"] == 3

    def test_assess_single_domain(self, self_model):
        self_model.update_competency("go", "breakthrough")
        result = self_model.assess(["go"])
        assert result["level"] > 0.5
        assert result["confidence"] > 0

    def test_assess_multiple_domains(self, self_model):
        self_model.update_competency("go", "breakthrough")
        self_model.update_competency("docker", "failure")
        result = self_model.assess(["go", "docker"])
        # Average of (0.5+0.02) and (0.5-0.01)
        assert 0.49 < result["level"] < 0.52

    def test_assess_unknown_domain(self, self_model):
        result = self_model.assess(["totally_unknown"])
        assert result["level"] == 0.5
        assert result["confidence"] == 0.0
        assert "Unknown" in result["note"]


class TestBlindSpots:
    def test_add_blind_spot(self, self_model):
        bs_id = self_model.add_blind_spot(
            description="Struggles with async patterns",
            domains=["async", "concurrency"],
            evidence=["Failed 3 times"],
            severity=0.7,
        )
        assert bs_id is not None

        spots = self_model.get_blind_spots()
        assert len(spots) == 1
        assert spots[0]["description"] == "Struggles with async patterns"
        assert spots[0]["severity"] == 0.7

    def test_add_blind_spot_dedup(self, self_model):
        id1 = self_model.add_blind_spot(
            description="Struggles with async patterns in Go",
            domains=["async"],
            evidence=["Evidence 1"],
        )
        id2 = self_model.add_blind_spot(
            description="Struggles with async patterns in Go language",
            domains=["async"],
            evidence=["Evidence 2"],
        )
        # Should be deduplicated (similar description)
        assert id1 == id2

        spots = self_model.get_blind_spots()
        assert len(spots) == 1
        # Evidence should be merged
        assert len(spots[0]["evidence"]) == 2

    def test_resolve_blind_spot(self, self_model):
        bs_id = self_model.add_blind_spot(
            description="Cannot configure nginx",
            domains=["nginx"],
        )
        self_model.resolve_blind_spot(bs_id)

        active = self_model.get_blind_spots(status="active")
        resolved = self_model.get_blind_spots(status="resolved")
        assert len(active) == 0
        assert len(resolved) == 1

    def test_check_blind_spots(self, self_model):
        self_model.add_blind_spot(
            description="Issues with Docker networking",
            domains=["docker"],
            severity=0.8,
        )
        self_model.add_blind_spot(
            description="Problems with SQL joins",
            domains=["sql"],
            severity=0.5,
        )

        relevant = self_model.check_blind_spots(["docker"])
        assert len(relevant) == 1
        assert relevant[0]["domains"] == ["docker"]

    def test_frustration_creates_blind_spot(self, self_model):
        # frustration_signals > 3 should create a blind spot
        self_model.update_competency("css", "failure", frustration_signals=5)
        spots = self_model.get_blind_spots()
        assert len(spots) >= 1
        assert any("css" in str(s["domains"]) for s in spots)


class TestUserModel:
    def test_update_user_model(self, self_model):
        self_model.update_user_model("language", "Russian", confidence=0.9)
        model = self_model.get_user_model()
        assert "language" in model
        assert model["language"]["value"] == "Russian"
        assert model["language"]["confidence"] == 0.9
        assert model["language"]["evidence_count"] == 1

    def test_update_user_model_increments(self, self_model):
        self_model.update_user_model("editor", "VSCode")
        self_model.update_user_model("editor", "Cursor")
        model = self_model.get_user_model()
        assert model["editor"]["value"] == "Cursor"
        assert model["editor"]["evidence_count"] == 2

    def test_get_user_model(self, self_model):
        self_model.update_user_model("theme", "dark")
        self_model.update_user_model("os", "macOS")
        model = self_model.get_user_model()
        assert len(model) == 2
        assert "theme" in model
        assert "os" in model


class TestFullReport:
    def test_full_report(self, self_model):
        self_model.update_competency("go", "breakthrough")
        self_model.update_competency("python", "routine")
        self_model.add_blind_spot(
            description="Weak at CSS",
            domains=["css"],
        )
        self_model.update_user_model("style", "concise")

        report = self_model.full_report()
        assert report["competency_count"] == 2
        assert report["blind_spot_count"] == 1
        assert report["user_model_entries"] == 1
        assert report["avg_level"] > 0
        assert "competencies" in report
        assert "blind_spots" in report
