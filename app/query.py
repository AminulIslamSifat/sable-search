"""Query enhancement: entity extraction, filters, question detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedQuery:
    original: str
    cleaned: str
    site_filter: str | None = None
    time_hint: str | None = None
    is_question: bool = False
    entities: list[str] = field(default_factory=list)


_QUESTION_WORDS = {"who", "what", "where", "when", "why", "how", "which", "is", "are", "do", "does", "can", "will"}
_SITE_RE = re.compile(r"site:(\S+)")
_TIME_RE = re.compile(r"\b(past day|past week|past month|past year|today|this week)\b", re.IGNORECASE)


def parse_query(q: str) -> ParsedQuery:
    if not q or not q.strip():
        return ParsedQuery(original=q, cleaned="")

    raw = q.strip()
    cleaned = raw

    # Extract site: filter
    site_match = _SITE_RE.search(cleaned)
    site_filter = None
    if site_match:
        site_filter = site_match.group(1)
        cleaned = _SITE_RE.sub("", cleaned).strip()

    # Extract time hint
    time_match = _TIME_RE.search(cleaned)
    time_hint = None
    if time_match:
        raw_hint = time_match.group(1).lower()
        mapping = {
            "past day": "day",
            "today": "day",
            "past week": "week",
            "this week": "week",
            "past month": "month",
            "past year": "year",
        }
        time_hint = mapping.get(raw_hint, raw_hint)
        cleaned = _TIME_RE.sub("", cleaned).strip()

    # Detect question
    words = cleaned.lower().split()
    is_question = cleaned.endswith("?") or (len(words) > 0 and words[0] in _QUESTION_WORDS)

    # Simple entity extraction: capitalized multi-word phrases
    entities: list[str] = []
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", cleaned):
        entities.append(match.group(1))

    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return ParsedQuery(
        original=raw,
        cleaned=cleaned,
        site_filter=site_filter,
        time_hint=time_hint,
        is_question=is_question,
        entities=entities,
    )
