"""Inline <private>...</private> tag redaction (P0.1)."""

from __future__ import annotations

import re

# Non-greedy, multiline, case-insensitive; flat (non-nested) semantics
PRIVATE_RE = re.compile(r"<private>(.*?)</private>", re.DOTALL | re.IGNORECASE)


def redact_private_sections(content: str) -> tuple[str, int]:
    # Returns (cleaned_content, redactions_count). Idempotent.
    if not content:
        return content, 0
    matches = PRIVATE_RE.findall(content)
    if not matches:
        return content, 0
    cleaned = PRIVATE_RE.sub("", content)
    return cleaned, len(matches)
