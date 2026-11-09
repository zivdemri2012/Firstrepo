"""CET (מט"ח) TreeLMS JSON → normalized records.

Field names come from a calibration capture of the real student site
(``weekly recap --capture cet``), not from guesses:

* ``GetUserAudiences``         → the student's classes; the title tells לשון from הבעה.
* ``GetAllEnvironmentTasks``   → every task in a class (TaskId, TaskTitle, TaskType,
                                 StartTime/EndTime in UTC, IsScheduled, IsHidden).
* ``GetStudentScores``         → only the tasks the student already submitted, with
                                 State ("submitted"/"evaluated"), SubmittedTime (epoch)
                                 and Scores.FinalScore.

A past-due task with no submission record is skipped, not shown as late: the student
confirmed that such tasks were not actually late (the הבעה class returns no scores at all).
Unscheduled "SelfLearning" items are the course's optional library, not assignments,
so they are skipped. Pure functions → unit-tested with synthetic fixtures.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from ...models import Message, MessageCategory, Task, TaskStatus

SUBMITTED_STATES = {"submitted", "evaluated"}


def subject_of(audience_title: str) -> str:
    """Every CET task must be tagged לשון or הבעה (the course holds both)."""
    t = audience_title or ""
    if "הבעה" in t:
        return "הבעה"
    if "לשון" in t:
        return "לשון"
    return "לשון והבעה"


def _utc(value: Any) -> datetime | None:
    """CET sends either ISO strings in UTC (no zone) or epoch seconds."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    s = str(value).rstrip("Z")
    if "." in s:
        s = s.split(".")[0]
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _local_iso(dt: datetime | None, tz: str) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(ZoneInfo(tz)).replace(tzinfo=None).isoformat(timespec="minutes")


def scores_by_task(scores: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {s["TaskId"]: s for s in scores or [] if s.get("TaskId")}


def _is_submitted(score: dict[str, Any] | None) -> bool:
    info = (score or {}).get("StudentLmsInfo") or {}
    return info.get("State") in SUBMITTED_STATES or bool(info.get("SubmittedTime"))


def map_tasks(tasks: list[dict[str, Any]], scores: list[dict[str, Any]], subject: str,
              url: str | None, now: datetime, tz: str) -> list[Task]:
    by_task = scores_by_task(scores)
    out: list[Task] = []
    for x in tasks or []:
        if not x.get("TaskId") or x.get("IsHidden"):
            continue
        if not x.get("IsScheduled"):          # optional self-learning library, not an assignment
            continue
        due = _utc(x.get("EndTime"))
        score = by_task.get(x["TaskId"])
        submitted = _is_submitted(score)
        submitted_late = None
        if submitted:
            status = TaskStatus.SUBMITTED
            sub_at = _utc(((score or {}).get("StudentLmsInfo") or {}).get("SubmittedTime"))
            submitted_late = bool(sub_at and due and sub_at > due)
        elif due is not None and due < now:
            # No submission record and the date passed. CET has no score record for every
            # class (e.g. הבעה returned none at all), so "late" can't be known. Don't guess it.
            continue
        else:
            status = TaskStatus.OPEN
        out.append(Task(
            external_id=f"cet:{x['TaskId']}",
            title=(x.get("TaskTitle") or "(ללא כותרת)").strip(),
            status=status,
            subject=subject,
            due_at=_local_iso(due, tz),
            url=url,
            submitted_late=submitted_late,
            created_at=_local_iso(_utc(x.get("StartTime")), tz),
        ))
    return out


def map_grades(scores: list[dict[str, Any]], subject: str, url: str | None, tz: str) -> list[Message]:
    out: list[Message] = []
    for s in scores or []:
        info = s.get("StudentLmsInfo") or {}
        final = (info.get("Scores") or {}).get("FinalScore")
        if (not s.get("TaskId") or info.get("State") != "evaluated" or final is None
                or info.get("HideScoreFromStudents") or s.get("HideGrade")):
            continue
        out.append(Message(
            external_id=f"cetgrade:{s['TaskId']}",
            category=MessageCategory.GRADE,
            title=(s.get("Title") or "משימה").strip(),
            date=_local_iso(_utc(info.get("SubmittedTime")), tz),
            sender='מט"ח',
            subject=subject,
            url=url,
            grade=f"{final:g}" if isinstance(final, (int, float)) else str(final),
        ))
    return out
