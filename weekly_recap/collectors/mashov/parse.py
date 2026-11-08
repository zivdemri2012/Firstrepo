"""Mashov JSON → normalized records.

Field names come from a calibration capture of the real student site
(``weekly recap --capture mashov``), not from guesses. Pure functions, so they
are unit-tested with synthetic fixtures (no real data in the repo).
"""
from __future__ import annotations

import html
import re
from typing import Any

from ...models import BehaviorEvent, BehaviorKind, Message, MessageCategory
from ...processing.classify import classify_message

MAILBOX_URL = "https://web.mashov.info/students/main/mailbox/folder/inbox"


def behavior_kind(name: str) -> BehaviorKind | None:
    """Map a Mashov behavior type name (achvaName) to a kind. None = not an event (attendance)."""
    n = (name or "").strip()
    if n.startswith("נוכחות"):            # "נוכחות", "נוכחות בפרטני", ... = was present
        return None
    if n.startswith("חיסור") or n.startswith("היעדרות"):
        return BehaviorKind.ABSENCE
    if n.startswith("איחור"):
        return BehaviorKind.LATE
    if n.startswith("חיזוק חיובי") or "חיזוק" in n:
        return BehaviorKind.POSITIVE
    return BehaviorKind.NOTE


def parse_behave(items: list[dict[str, Any]]) -> list[BehaviorEvent]:
    out: list[BehaviorEvent] = []
    for x in items or []:
        name = x.get("achvaName") or ""
        kind = behavior_kind(name)
        if kind is None or not x.get("lessonDate"):
            continue
        justified_code = x.get("justified")
        justified: bool | None
        if isinstance(justified_code, int) and justified_code > 0:
            justified = True
        elif kind == BehaviorKind.ABSENCE or kind == BehaviorKind.LATE:
            justified = False
        else:
            justified = None
        just_text = (x.get("justification") or "").strip()
        out.append(BehaviorEvent(
            external_id=f"{x.get('lessonId')}:{x.get('achvaCode')}",
            kind=kind,
            date=str(x["lessonDate"])[:10],
            title=name,
            subject=x.get("subject") or None,
            teacher=x.get("reporter") or None,
            lesson=str(x["lesson"]) if x.get("lesson") is not None else None,
            details=just_text if justified and just_text and just_text != "ללא הערות" else None,
            justified=justified,
        ))
    return out


def parse_grades(items: list[dict[str, Any]]) -> list[Message]:
    out: list[Message] = []
    for x in items or []:
        if x.get("grade") is None or x.get("id") is None:
            continue
        event = (x.get("gradingEvent") or "").strip()
        gtype = (x.get("gradeType") or "").strip()
        title = f"{gtype} – {event}" if gtype and event and gtype not in event else (event or gtype or "ציון")
        out.append(Message(
            external_id=f"grade:{x['id']}",
            category=MessageCategory.GRADE,
            title=title,
            # Entry time (timestamp) decides "new"; fall back to the event date.
            date=str(x.get("timestamp") or x.get("eventDate") or "")[:16] or None,
            sender=x.get("teacherName") or None,
            subject=x.get("subjectName") or None,
            grade=str(x["grade"]),
        ))
    return out


def _clean(text: str | None) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()


def parse_homework(items: list[dict[str, Any]]) -> list[Message]:
    out: list[Message] = []
    for x in items or []:
        text = _clean(x.get("homework"))
        if not text or x.get("lessonId") is None:
            continue
        remark = _clean(x.get("remark"))
        title = text if len(text) <= 140 else text[:137] + "…"
        body_parts = [text if len(text) > 140 else "", remark]
        body = " · ".join(p for p in body_parts if p) or None
        out.append(Message(
            external_id=f"hw:{x['lessonId']}",
            category=MessageCategory.HOMEWORK,
            title=title,
            date=str(x.get("lessonDate") or "")[:10] or None,
            subject=x.get("subjectName") or None,
            body=body,
        ))
    return out


def parse_conversations(items: list[dict[str, Any]]) -> list[Message]:
    out: list[Message] = []
    for c in items or []:
        cid = c.get("conversationId")
        subject = _clean(c.get("subject"))
        if not cid or not subject:
            continue
        msgs = c.get("messages") or []
        first = msgs[0] if msgs else {}
        sender = first.get("senderName") or None
        category = classify_message(subject, from_teacher=True)
        out.append(Message(
            external_id=f"mail:{cid}",
            category=category or MessageCategory.TEACHER,
            title=subject,
            date=str(c.get("sendTime") or first.get("sendTime") or "")[:16] or None,
            sender=sender,
            url=MAILBOX_URL,
        ))
    return out


def parse_message_board(items: list[dict[str, Any]]) -> list[Message]:
    out: list[Message] = []
    for x in items or []:
        text = _clean(x.get("eventtext"))
        if not text or x.get("eventid") is None:
            continue
        category = classify_message(text, from_teacher=True) or MessageCategory.TEACHER
        out.append(Message(
            external_id=f"board:{x['eventid']}",
            category=category,
            title=text if len(text) <= 160 else text[:157] + "…",
            body=text if len(text) > 160 else None,
            sender="לוח הודעות",
        ))
    return out
