"""Hebrew keyword classification, shared by site parsers.

Parsers should prefer explicit type fields from the site; these helpers are a
fallback for free-text titles. Returning ``None`` means "not relevant" — the
item is dropped rather than shown under a made-up category.
"""
from __future__ import annotations

import re

from ..models import BehaviorKind, MessageCategory

_BEHAVIOR_RULES: list[tuple[BehaviorKind, tuple[str, ...]]] = [
    (BehaviorKind.LATE, ("איחור", "איחר", "איחרה")),
    (BehaviorKind.ABSENCE, ("חיסור", "היעדרות", "העדרות", "נעדר", "נעדרה", "לא נכח")),
    (BehaviorKind.POSITIVE, ("חיזוק", 'ח"ח', "ח``ח", "שבח", "מצוין", "מצוינת", "הצטיינות",
                             "כל הכבוד", "מחמאה", "התנהגות טובה")),
]

_MESSAGE_RULES: list[tuple[MessageCategory, tuple[str, ...]]] = [
    (MessageCategory.TRIP, ("טיול", "סיור", "גיחה", "מחנה")),
    (MessageCategory.HOMEWORK, ("שיעורי בית", 'ש"ב', "שיעורי-בית", "להגיש", "הגשה", "תרגילים")),
    (MessageCategory.ACTIVITY, ("טקס", "פעילות", "אירוע", "הצגה", "מסיבה", "יום ספורט",
                                "כנס", "הרצאה", "ערב הורים", "אסיפה", "חגיגה")),
]


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).replace("״", '"').strip()


def classify_behavior(text: str | None) -> BehaviorKind:
    """Free-text behavior title → kind. Anything unrecognized is a note/event."""
    t = _norm(text)
    for kind, words in _BEHAVIOR_RULES:
        if any(w in t for w in words):
            return kind
    return BehaviorKind.NOTE


def classify_message(text: str | None, from_teacher: bool = True) -> MessageCategory | None:
    """Message subject/body → category, or None when it is not one of the wanted kinds."""
    t = _norm(text)
    for cat, words in _MESSAGE_RULES:
        if any(w in t for w in words):
            return cat
    return MessageCategory.TEACHER if from_teacher else None
