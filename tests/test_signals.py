"""Tests for Signal Extraction — learning signal detection from messages."""

import pytest
from memory_systems.signals import SignalExtractor


@pytest.fixture
def extractor():
    return SignalExtractor()


class TestSignalDetection:
    def test_detect_correction_russian(self, extractor):
        assert extractor.is_correction("нет, не так нужно делать")
        assert extractor.is_correction("убери это")
        assert extractor.is_correction("переделай заново")
        assert extractor.is_correction("не правильно, верни как было")

    def test_detect_correction_english(self, extractor):
        assert extractor.is_correction("that's wrong, undo it")
        assert extractor.is_correction("revert the changes")
        assert extractor.is_correction("not what I asked for")

    def test_detect_approval_russian(self, extractor):
        assert extractor.is_approval("спасибо, отлично получилось")
        assert extractor.is_approval("супер, именно то что нужно")
        assert extractor.is_approval("круто, молодец")

    def test_detect_approval_english(self, extractor):
        assert extractor.is_approval("perfect, thanks!")
        assert extractor.is_approval("great work, awesome")
        assert extractor.is_approval("nice, exactly what I needed")

    def test_no_false_positive(self, extractor):
        neutral = "Please add a new function to handle user authentication"
        assert not extractor.is_correction(neutral)
        # "not" alone shouldn't match correction patterns
        assert not extractor.is_correction("I do not have the file yet")

    def test_extract_signals_mixed(self, extractor):
        messages = [
            {"role": "user", "text": "Add JWT auth"},
            {"role": "assistant", "text": "Done, here is the code"},
            {"role": "user", "text": "нет, не так, переделай"},
            {"role": "assistant", "text": "Fixed it"},
            {"role": "user", "text": "отлично, спасибо!"},
        ]
        signals = extractor.extract(messages)
        assert signals["correction_count"] >= 1
        assert signals["positive_count"] >= 1
        assert signals["total_messages"] == 5
        assert signals["user_messages"] == 3

    def test_satisfaction_score(self, extractor):
        # All positive
        positive_msgs = [
            {"role": "user", "text": "спасибо, отлично"},
            {"role": "user", "text": "perfect, great"},
        ]
        signals = extractor.extract(positive_msgs)
        assert signals["satisfaction_score"] > 0.5

        # All negative
        negative_msgs = [
            {"role": "user", "text": "нет, не так, переделай"},
            {"role": "user", "text": "wrong, revert it"},
            {"role": "user", "text": "try again, doesn't work"},
        ]
        signals = extractor.extract(negative_msgs)
        assert signals["satisfaction_score"] < 0.5

    def test_satisfaction_neutral(self, extractor):
        # No signals at all
        msgs = [
            {"role": "user", "text": "Add function X"},
            {"role": "assistant", "text": "Done"},
        ]
        signals = extractor.extract(msgs)
        assert signals["satisfaction_score"] == 0.5


class TestOutcomeEstimation:
    def test_estimate_outcome_failure(self, extractor):
        signals = {
            "correction_count": 4,
            "retry_count": 2,
            "positive_count": 0,
            "satisfaction_score": 0.1,
        }
        assert extractor.estimate_outcome(signals) == "failure"

    def test_estimate_outcome_breakthrough(self, extractor):
        signals = {
            "correction_count": 3,
            "retry_count": 0,
            "positive_count": 3,
            "satisfaction_score": 0.6,
        }
        assert extractor.estimate_outcome(signals) == "breakthrough"

    def test_estimate_outcome_routine(self, extractor):
        signals = {
            "correction_count": 0,
            "retry_count": 0,
            "positive_count": 1,
            "satisfaction_score": 0.7,
        }
        assert extractor.estimate_outcome(signals) == "routine"

    def test_estimate_outcome_discovery(self, extractor):
        signals = {
            "correction_count": 0,
            "retry_count": 0,
            "positive_count": 5,
            "satisfaction_score": 0.9,
        }
        assert extractor.estimate_outcome(signals) == "discovery"


class TestImpactEstimation:
    def test_estimate_impact(self, extractor):
        signals = {
            "correction_count": 0,
            "retry_count": 0,
            "positive_count": 3,
            "satisfaction_score": 0.8,
            "total_messages": 15,
        }
        impact = extractor.estimate_impact(signals)
        assert 0.0 <= impact <= 1.0
        assert impact > 0.4  # positive signals should yield moderate-high impact

    def test_estimate_impact_no_signals(self, extractor):
        signals = {
            "correction_count": 0,
            "retry_count": 0,
            "positive_count": 0,
            "satisfaction_score": 0.5,
            "total_messages": 5,
        }
        impact = extractor.estimate_impact(signals)
        assert impact == 0.3  # no signals -> below neutral

    def test_estimate_impact_long_session(self, extractor):
        signals = {
            "correction_count": 2,
            "retry_count": 0,
            "positive_count": 4,
            "satisfaction_score": 0.7,
            "total_messages": 25,
        }
        impact_short = extractor.estimate_impact(signals, duration_minutes=10)
        impact_long = extractor.estimate_impact(signals, duration_minutes=90)
        assert impact_long > impact_short  # longer sessions get duration bonus
