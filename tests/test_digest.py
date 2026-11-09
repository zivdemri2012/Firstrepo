"""Digest format tests — synthetic report (no real data)."""
from datetime import datetime

from weekly_recap.processing.digest import format_digest

NOW = datetime(2026, 11, 9, 10, 0)


def report(open_tasks=(), late=(), events=(), grades=(), sources=("mashov", "cet", "classit")):
    return {
        "sources": [{"source": s, "status": "ok", "display_name": s} for s in sources],
        "behavior": {"available": True, "events": list(events),
                     "counts": {"absences": sum(e["kind"] == "absence" for e in events),
                                "lates": 0, "positives": 0, "notes": 0}},
        "tasks": {"open": list(open_tasks), "late": list(late), "old_late_count": 0, "available": True},
        "messages": {"available": True, "by_category": {"grade": list(grades)}},
    }


def test_urgent_and_bottom_line():
    t = {"source": "cet", "subject": "הבעה", "title": "חיבור", "due_at": "2026-11-09T23:59", "urgency": "urgent"}
    n = {"source": "cet", "subject": "לשון", "title": "תרגול", "due_at": "2026-11-15T23:59", "urgency": "normal"}
    out = format_digest(report(open_tasks=[t, n]), NOW)
    assert "⚠️ דחוף" in out and "**היום עד 23:59**" in out
    assert "עד יום ראשון 15.11" in out
    assert "**בקיצור:** תטפל בהבעה: \"חיבור\"" in out
    assert "מתמטיקה (ClassIt): אין יחידות פתוחות" in out


def test_nothing_urgent_with_absence():
    ev = {"kind": "absence", "title": "חיסור", "subject": "היסטוריה", "date": "2026-11-08", "justified": False}
    out = format_digest(report(events=[ev], grades=[{"subject": "לשון", "grade": "95"}]), NOW)
    assert "⚠️ דחוף" not in out and "🔔 לשים לב" in out and "חיסור ב\"היסטוריה\" ב-08.11" in out
    assert "ציונים חדשים בלשון: **95**" in out
    assert "אין שום דבר דחוף" not in out
