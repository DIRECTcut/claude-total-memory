"""
Signal Extraction — detects learning signals from session messages.

Analyzes conversation messages for:
- User corrections (Russian + English patterns)
- Approval / positive feedback
- Retry attempts
- Overall satisfaction score

Used to estimate episode outcomes and impact scores automatically.
"""

from __future__ import annotations

import re
import sys
from typing import Any

LOG = lambda msg: sys.stderr.write(f"[memory-signals] {msg}\n")


class SignalExtractor:
    """Extract learning signals from session messages."""

    # Correction patterns (Russian + English)
    CORRECTION_PATTERNS = [
        r"нет,?\s+(не\s+)?т(ак|о)",
        r"не\s+правильно",
        r"не\s+то",
        r"я\s+говор(ю|ил)",
        r"не\s+нужно",
        r"убери",
        r"верни",
        r"wrong",
        r"not what I",
        r"undo",
        r"revert",
        r"не надо",
        r"отмени",
        r"откати",
        r"не так\b",
        r"заново",
        r"переделай",
    ]

    # Approval patterns
    APPROVAL_PATTERNS = [
        r"спасибо",
        r"отлично",
        r"супер",
        r"да,?\s+именно",
        r"правильно",
        r"хорошо",
        r"perfect",
        r"great",
        r"thanks",
        r"круто",
        r"класс",
        r"молодец",
        r"замечательно",
        r"exactly",
        r"awesome",
        r"nice",
        r"👍",
        r"то что нужно",
        r"в точку",
    ]

    # Retry / reattempt patterns (indicate struggle)
    RETRY_PATTERNS = [
        r"попробуй\s+(ещё|еще|снова|опять)",
        r"try\s+again",
        r"ещё раз",
        r"еще раз",
        r"заново",
        r"retry",
        r"давай\s+снова",
        r"не\s+работает",
        r"doesn'?t\s+work",
        r"still\s+(broken|failing|wrong)",
        r"опять\s+(не|ошибка)",
    ]

    def __init__(self) -> None:
        # Compile all patterns once for performance
        self._correction_re = [
            re.compile(p, re.IGNORECASE | re.UNICODE)
            for p in self.CORRECTION_PATTERNS
        ]
        self._approval_re = [
            re.compile(p, re.IGNORECASE | re.UNICODE)
            for p in self.APPROVAL_PATTERNS
        ]
        self._retry_re = [
            re.compile(p, re.IGNORECASE | re.UNICODE)
            for p in self.RETRY_PATTERNS
        ]

    def is_correction(self, text: str) -> bool:
        """Check if text contains a correction signal."""
        return any(rx.search(text) for rx in self._correction_re)

    def is_approval(self, text: str) -> bool:
        """Check if text contains an approval signal."""
        return any(rx.search(text) for rx in self._approval_re)

    def _is_retry(self, text: str) -> bool:
        """Check if text contains a retry signal."""
        return any(rx.search(text) for rx in self._retry_re)

    def extract(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """
        Extract signals from a list of {role, text} messages.

        Only analyzes user messages (role == "user") since corrections
        and approvals come from the user.

        Returns:
            correction_count: number of correction signals detected
            retry_count: number of retry/reattempt signals
            positive_count: number of approval signals
            total_messages: total message count
            satisfaction_score: float 0.0-1.0 (higher = more satisfied)
            corrections: list of actual correction message texts
        """
        correction_count = 0
        retry_count = 0
        positive_count = 0
        corrections: list[str] = []

        user_messages = [
            m for m in messages
            if m.get("role") == "user" and m.get("text")
        ]

        for msg in user_messages:
            text = msg["text"]

            if self.is_correction(text):
                correction_count += 1
                corrections.append(text)

            if self._is_retry(text):
                retry_count += 1

            if self.is_approval(text):
                positive_count += 1

        total = len(messages)
        user_total = len(user_messages)

        # Satisfaction score: ratio of positive to negative signals
        negative = correction_count + retry_count
        if positive_count + negative == 0:
            satisfaction = 0.5  # neutral — no signals
        else:
            satisfaction = positive_count / (positive_count + negative)

        return {
            "correction_count": correction_count,
            "retry_count": retry_count,
            "positive_count": positive_count,
            "total_messages": total,
            "user_messages": user_total,
            "satisfaction_score": round(satisfaction, 3),
            "corrections": corrections,
        }

    def estimate_outcome(self, signals: dict[str, Any]) -> str:
        """
        Estimate episode outcome from extracted signals.

        Returns: 'breakthrough' | 'failure' | 'routine' | 'discovery'

        Heuristics:
          - Many corrections + retries + low satisfaction -> failure
          - High satisfaction + some corrections (recovered) -> breakthrough
          - High satisfaction + no corrections -> routine (or discovery if long)
          - Mixed signals -> routine
        """
        corrections = signals.get("correction_count", 0)
        retries = signals.get("retry_count", 0)
        positives = signals.get("positive_count", 0)
        satisfaction = signals.get("satisfaction_score", 0.5)

        negative = corrections + retries

        # Failure: significant negative signals, low satisfaction
        if negative >= 3 and satisfaction < 0.3:
            return "failure"

        # Breakthrough: had struggles but recovered with positive outcome
        if negative >= 2 and positives >= 2 and satisfaction >= 0.5:
            return "breakthrough"

        # Discovery: strong positives, no struggle, possibly insightful
        if positives >= 3 and negative == 0 and satisfaction > 0.8:
            return "discovery"

        # Default: routine
        return "routine"

    def estimate_impact(
        self,
        signals: dict[str, Any],
        duration_minutes: int | None = None,
    ) -> float:
        """
        Estimate impact score 0.0-1.0 from signals.

        Factors:
          - Higher satisfaction -> higher impact
          - Breakthroughs after struggle -> high impact
          - Longer sessions tend to be more impactful
          - Pure routine with no signals -> low impact
        """
        satisfaction = signals.get("satisfaction_score", 0.5)
        corrections = signals.get("correction_count", 0)
        positives = signals.get("positive_count", 0)
        total = signals.get("total_messages", 0)

        # Base: satisfaction score
        impact = satisfaction * 0.6

        # Struggle-then-success bonus
        if corrections >= 2 and positives >= 2:
            impact += 0.2

        # Activity bonus (more messages = more content)
        if total > 20:
            impact += 0.1
        elif total > 10:
            impact += 0.05

        # Duration bonus
        if duration_minutes is not None:
            if duration_minutes > 60:
                impact += 0.1
            elif duration_minutes > 30:
                impact += 0.05

        # No signals at all -> slightly below neutral
        if positives == 0 and corrections == 0:
            impact = 0.3

        return round(max(0.0, min(1.0, impact)), 3)
