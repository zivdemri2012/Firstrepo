"""Normalized records that every collector produces.

Collectors translate each website's own format into these records; the rest
of the system (storage, processing, dashboard) only knows these shapes.
Fields that a source does not provide stay ``None`` — never invented.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class BehaviorKind(str, Enum):
    ABSENCE = "absence"     # היעדרות
    LATE = "late"           # איחור
    POSITIVE = "positive"   # חיזוק חיובי (ח"ח)
    NOTE = "note"           # אירוע / הערה


class TaskStatus(str, Enum):
    OPEN = "open"           # פתוחה
    SUBMITTED = "submitted" # הוגשה
    LATE = "late"           # באיחור (לא הוגשה ועבר המועד, או הוגשה באיחור)
    CANCELLED = "cancelled" # בוטלה / הוסרה מהמקור


class MessageCategory(str, Enum):
    HOMEWORK = "homework"   # שיעורי בית
    TRIP = "trip"           # טיולים
    ACTIVITY = "activity"   # פעילויות ואירועים
    TEACHER = "teacher"     # הודעות מורים
    GRADE = "grade"         # ציון חדש


@dataclass
class BehaviorEvent:
    external_id: str
    kind: BehaviorKind
    date: str                       # ISO date (YYYY-MM-DD)
    title: str                      # e.g. "איחור", "חיזוק חיובי"
    subject: str | None = None
    teacher: str | None = None
    lesson: str | None = None       # lesson number, if known
    details: str | None = None
    justified: bool | None = None


@dataclass
class Task:
    external_id: str
    title: str
    status: TaskStatus
    subject: str | None = None
    teacher: str | None = None
    due_at: str | None = None       # ISO datetime / date, local time
    url: str | None = None
    submitted_late: bool | None = None
    created_at: str | None = None


@dataclass
class Message:
    external_id: str
    category: MessageCategory
    title: str
    date: str | None = None         # ISO datetime / date
    sender: str | None = None
    subject: str | None = None
    body: str | None = None
    url: str | None = None
    grade: str | None = None        # only for MessageCategory.GRADE


@dataclass
class CollectorResult:
    """What a collector returns for one run.

    ``status`` is one of: ok, not_configured, needs_login, needs_calibration,
    error, skipped. Only ``ok`` results are stored/processed.

    ``complete_task_list``: True when ``tasks`` is the source's full list of
    current tasks, so a task that disappeared can be marked as cancelled.
    """
    source: str
    status: str
    message: str = ""
    behavior: list[BehaviorEvent] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    complete_task_list: bool = False
    provides_behavior: bool = False
    is_demo: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
