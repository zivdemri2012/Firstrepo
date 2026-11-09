"""Short, personal Hebrew weekly digest (the format the user chose).

Sections, each shown only when it has something to say:
⚠️ דחוף · 📅 בהמשך · ✅ מה היה טוב · 🔔 לשים לב · 📌 משימות ישנות · 💬 הודעות · בקיצור.
Built only from the report, so it never invents data a source did not provide.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .report import _join, _parse_dt

WEEKDAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]  # date.weekday() order


def _when(due: datetime | None, now: datetime) -> str:
    if due is None:
        return "בלי תאריך הגשה"
    days = (due.date() - now.date()).days
    hour = f"{due:%H:%M}"
    if days == 0:
        return f"**היום עד {hour}**"
    if days == 1:
        return f"**מחר עד {hour}**"
    return f"עד יום {WEEKDAYS[due.weekday()]} {due.day}.{due.month}"


def _task(t: dict) -> str:
    subj = f"{t['subject']}: " if t.get("subject") else ""
    return f"{subj}\"{t['title']}\""


def format_digest(report: dict[str, Any], now: datetime | None = None) -> str:
    now = now or datetime.now()
    beh, tasks, msgs = report["behavior"], report["tasks"], report["messages"]
    by_cat = msgs["by_category"]
    ok_sources = {s["source"] for s in report["sources"] if s["status"] == "ok"}
    lines: list[str] = ["## הסיכום השבועי שלך", ""]

    def section(title: str, items: list[str]) -> None:
        if items:
            lines.extend([f"**{title}**", *[f"- {i}" for i in items], ""])

    # ⚠️ urgent: open tasks due within 48h + recently-late tasks
    urgent_open = [t for t in tasks["open"] if t.get("urgency") == "urgent"]
    later_open = [t for t in tasks["open"] if t.get("urgency") != "urgent"]
    section("⚠️ דחוף:", [f"{_task(t)} — {_when(_parse_dt(t['due_at']), now)}, עוד לא סומנה כהוגשה."
                         for t in urgent_open])
    section("📅 בהמשך:", [f"{_task(t)} — {_when(_parse_dt(t['due_at']), now)}." for t in later_open])

    # ✅ good things
    good: list[str] = []
    attention: list[str] = []
    if beh["available"]:
        for e in beh["events"]:
            where = f" ב\"{e['subject']}\"" if e.get("subject") else ""
            kind_title = e["title"].replace("חיזוק חיובי - ", "")
            if e["kind"] == "positive":
                good.append(f"קיבלת **חיזוק חיובי** ({kind_title}){where}.")
            elif e["kind"] in ("absence", "late"):
                ok = " (מוצדק)" if e.get("justified") else ""
                attention.append(f"{e['title']}{where} ב-{date.fromisoformat(e['date']):%d.%m}{ok}.")
            else:
                attention.append(f"{e['title']}{where}.")
        c = beh["counts"]
        if not c["absences"] and not c["lates"]:
            good.append("אין חיסורים ואין איחורים השבוע.")
    grades = by_cat.get("grade", [])
    by_subj: dict[str, list[str]] = {}
    for g in grades:
        by_subj.setdefault(g.get("subject") or "ציון", []).append(str(g.get("grade")))
    for subj, gs in by_subj.items():
        good.append(f"ציונים חדשים ב{subj}: **{_join(gs)}**.")
    if "classit" in ok_sources and not any(
            t["source"] == "classit" for t in tasks["open"] + tasks["late"]):
        good.append("מתמטיקה (ClassIt): אין יחידות פתוחות, הכל הושלם.")
    section("✅ מה היה טוב:", good)
    section("🔔 לשים לב:", attention)

    # 📌 overdue, not marked submitted
    late = tasks["late"]
    old_n = tasks["old_late_count"]
    if late or old_n:
        examples = _join([f"\"{t['title']}\"" for t in late[:3]])
        n = len(late) + old_n
        text = f"{n} משימות שעבר להן התאריך ולא סומנו כהוגשו"
        text += f", למשל {examples}." if examples else "."
        section("📌 משימות ישנות שלא סומנו כהוגשו:",
                [text, "אם המורה לא דורשת אותן — אפשר להתעלם."])

    # 💬 messages
    notes: list[str] = []
    for cat, label in (("homework", "שיעורי בית"), ("trip", "טיול"), ("activity", "פעילות"),
                       ("teacher", "הודעה")):
        for m in by_cat.get(cat, [])[:3]:
            subj = f" ({m['subject']})" if m.get("subject") else ""
            notes.append(f"{label}{subj}: {m['title']}")
    if not notes and msgs["available"]:
        notes.append("אין הודעות חדשות ממורים, טיולים או שיעורי בית.")
    section("💬 הודעות:", notes)

    # bottom line
    if urgent_open:
        bottom = f"תטפל ב{_join([_task(t) for t in urgent_open])}. חוץ מזה"
        bottom += " המצב טוב 👍" if not attention else " — תעבור גם על \"לשים לב\"."
    elif attention:
        bottom = "אין משהו דחוף, אבל תעבור על \"לשים לב\"."
    else:
        bottom = "אין שום דבר דחוף — המצב מצוין 👍"
    lines.extend(["---", f"**בקיצור:** {bottom}"])

    missing = [s["display_name"] for s in report["sources"] if s["status"] != "ok"]
    if missing:
        lines.append(f"\n(לא עודכן הפעם: {', '.join(missing)})")
    return "\n".join(lines)
