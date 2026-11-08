"""Turns stored data into the dashboard report (JSON) + a short Hebrew summary.

Golden rule: a number is shown only if the source that provides it actually
succeeded at least once. Otherwise the value is ``None`` and the dashboard
says "אין נתונים" — it never shows a made-up zero.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from ..database.db import Database, week_start_for
from ..models import MessageCategory

STATUS_LABELS = {
    "ok": "עודכן",
    "not_configured": "לא מוגדר",
    "needs_login": "נדרשת התחברות",
    "needs_calibration": "ממתין למיפוי",
    "error": "שגיאה",
    "skipped": "דולג",
}

DISPLAY_NAMES = {"mashov": "משוב", "classroom": "Google Classroom", "galim": "גלים פרו", "cet": "לשון והבעה (מט\"ח)", "classit": "ClassIt (מתמטיקה)",
                 "demo": "נתוני דמה"}

OLD_LATE_DAYS = 30
URGENT_HOURS = 48


# ----------------------------------------------------------------- Hebrew
def plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else f"{n} {many}"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    if len(value) <= 10:  # date only → end of day
        dt = dt.replace(hour=23, minute=59)
    return dt


def _row(r) -> dict[str, Any]:
    return dict(r) if r is not None else {}


# ----------------------------------------------------------------- build
def build_report(db: Database, now: datetime | None = None, is_demo: bool = False,
                 profile: str = "default") -> dict[str, Any]:
    now = now or datetime.now()
    run = db.latest_run()
    ws = week_start_for(now.date())
    we = ws + timedelta(days=6)
    report: dict[str, Any] = {
        "generated_at": now.replace(microsecond=0).isoformat(),
        "profile": profile,
        "is_demo": is_demo,
        "has_run": run is not None,
        "run": _row(run) if run else None,
        "previous_run_at": None,
        "week": {"start": ws.isoformat(), "end": we.isoformat()},
    }
    if run:
        prev = db.previous_run(run["id"])
        report["previous_run_at"] = prev["finished_at"] if prev else None

    statuses = [dict(s) for s in db.source_statuses()]
    for s in statuses:
        s["display_name"] = DISPLAY_NAMES.get(s["source"], s["source"])
        s["status_label"] = STATUS_LABELS.get(s["status"], s["status"])
    report["sources"] = statuses
    report["is_demo"] = is_demo or any(s["is_demo"] for s in statuses)

    report["behavior"] = _behavior(db, statuses, ws, we)
    report["tasks"] = _tasks(db, statuses, run, now, ws)
    report["messages"] = _messages(db, statuses, run)
    report["history"] = [dict(r) for r in db.snapshots(12)]
    report["summary"] = build_summary(report, now)
    return report


def behavior_counts(db: Database, ws: date, we: date) -> dict[str, int]:
    rows = db.conn.execute(
        "SELECT kind, COUNT(*) n FROM behavior_events WHERE date BETWEEN ? AND ? GROUP BY kind",
        (ws.isoformat(), we.isoformat()),
    ).fetchall()
    by = {r["kind"]: r["n"] for r in rows}
    return {"absences": by.get("absence", 0), "lates": by.get("late", 0),
            "positives": by.get("positive", 0), "notes": by.get("note", 0)}


def _behavior(db: Database, statuses: list[dict], ws: date, we: date) -> dict[str, Any]:
    providers = [s for s in statuses if s["provides_behavior"] and s["last_success_at"]]
    out: dict[str, Any] = {"available": bool(providers), "as_of": None, "counts": None,
                           "previous": None, "delta": None, "events": []}
    if not providers:
        return out
    out["as_of"] = max(s["last_success_at"] for s in providers)
    out["stale"] = any(s["status"] != "ok" for s in providers)
    out["counts"] = behavior_counts(db, ws, we)
    prev = db.get_snapshot((ws - timedelta(days=7)).isoformat())
    if prev and prev["behavior_available"]:
        out["previous"] = {k: prev[k] for k in ("absences", "lates", "positives", "notes")}
        out["delta"] = {k: out["counts"][k] - prev[k] for k in out["previous"]
                        if prev[k] is not None}
    out["events"] = [dict(r) for r in db.conn.execute(
        """SELECT id, source, kind, date, title, subject, teacher, lesson, details, justified
           FROM behavior_events WHERE date BETWEEN ? AND ? ORDER BY date DESC, id DESC""",
        (ws.isoformat(), we.isoformat()),
    ).fetchall()]
    return out


def _tasks(db: Database, statuses: list[dict], run, now: datetime, ws: date) -> dict[str, Any]:
    task_sources = {r["source"] for r in db.conn.execute("SELECT DISTINCT source FROM tasks")}
    ok_sources = {s["source"] for s in statuses if s["last_success_at"]}
    out: dict[str, Any] = {"available": bool(task_sources & ok_sources), "open": [], "late": [],
                           "submitted": [], "old_late_count": 0, "cancelled": [], "changes": []}
    if not run:
        return out
    run_id = run["id"]
    ws_dt = datetime.combine(ws, datetime.min.time())
    changes_by_task: dict[int, list[dict]] = {}
    for c in db.conn.execute(
        "SELECT task_id, field, old_value, new_value, changed_at FROM task_changes WHERE run_id = ?",
        (run_id,),
    ):
        changes_by_task.setdefault(c["task_id"], []).append(dict(c))

    for r in db.conn.execute("SELECT * FROM tasks ORDER BY due_at IS NULL, due_at"):
        t = dict(r)
        due = _parse_dt(t["due_at"])
        status = t["status"]
        if status == "open" and due and due < now:
            status = "late"  # due passed since the source last reported it
        t["effective_status"] = status
        t["source_name"] = DISPLAY_NAMES.get(t["source"], t["source"])
        t["is_new"] = t["first_seen_run"] == run_id
        t["carried_over"] = status in ("open", "late") and _parse_dt(t["first_seen_at"]) < ws_dt
        t["changes"] = changes_by_task.get(t["id"], [])
        hours_left = (due - now).total_seconds() / 3600 if due else None
        t["hours_left"] = round(hours_left, 1) if hours_left is not None else None
        if status == "late":
            t["urgency"] = "urgent"
        elif hours_left is not None and hours_left <= URGENT_HOURS:
            t["urgency"] = "urgent"
        elif hours_left is not None and hours_left <= 24 * 5:
            t["urgency"] = "soon"
        else:
            t["urgency"] = "normal"

        if status == "open":
            out["open"].append(t)
        elif status == "late":
            if due and due < now - timedelta(days=OLD_LATE_DAYS):
                out["old_late_count"] += 1
            else:
                out["late"].append(t)
        elif status == "submitted":
            changed = _parse_dt(t["status_changed_at"])
            if (changed and changed >= ws_dt and not t["is_new"]) or (due and due >= ws_dt):
                out["submitted"].append(t)
        elif status == "cancelled" and t["changes"]:
            out["cancelled"].append(t)
        for ch in t["changes"]:
            if t["is_new"]:
                continue
            out["changes"].append({**ch, "task_id": t["id"], "title": t["title"],
                                   "subject": t["subject"]})
    return out


def _messages(db: Database, statuses: list[dict], run) -> dict[str, Any]:
    msg_sources = {r["source"] for r in db.conn.execute("SELECT DISTINCT source FROM messages")}
    ok_sources = {s["source"] for s in statuses if s["last_success_at"]}
    out: dict[str, Any] = {"available": bool(msg_sources & ok_sources),
                           "by_category": {c.value: [] for c in MessageCategory}, "count": 0}
    if not run:
        return out
    for r in db.conn.execute(
        """SELECT id, source, category, title, date, sender, subject, body, url, grade
           FROM messages WHERE read_at IS NULL ORDER BY date DESC, id DESC"""
    ):
        m = dict(r)
        m["source_name"] = DISPLAY_NAMES.get(m["source"], m["source"])
        out["by_category"].setdefault(m["category"], []).append(m)
        out["count"] += 1
    return out


# ---------------------------------------------------------------- summary
_TEST_WORDS = ("מבחן", "בוחן", "מבדק", "בגרות")

_DELTA_WORDS = {
    "absences": ("ההיעדרויות", "היעדרויות"),
    "lates": ("האיחורים", "איחורים"),
    "positives": ("החיזוקים החיוביים", "חיזוקים חיוביים"),
    "notes": ("האירועים וההערות", "אירועים והערות"),
}


def build_summary(report: dict[str, Any], now: datetime) -> dict[str, list[str]]:
    beh, tasks, msgs = report["behavior"], report["tasks"], report["messages"]
    ws = date.fromisoformat(report["week"]["start"])
    next_ws, next_we = ws + timedelta(days=7), ws + timedelta(days=13)
    happened: list[str] = []
    todo: list[str] = []
    next_week: list[str] = []
    behavior_change: list[str] = []

    # --- what happened
    if beh["available"]:
        c = beh["counts"]
        parts = []
        if c["absences"]:
            parts.append(plural(c["absences"], "היעדרות אחת", "היעדרויות"))
        if c["lates"]:
            parts.append(plural(c["lates"], "איחור אחד", "איחורים"))
        if c["positives"]:
            parts.append(plural(c["positives"], "חיזוק חיובי אחד", "חיזוקים חיוביים"))
        if c["notes"]:
            parts.append(plural(c["notes"], "אירוע או הערה אחת", "אירועים והערות"))
        if parts:
            happened.append("השבוע נרשמו " + _join(parts) + ".")
        else:
            happened.append("השבוע לא נרשמו היעדרויות, איחורים או הערות.")
    grades = msgs["by_category"].get("grade", [])
    if grades:
        g = [f"{m['grade']} ב{m['subject']}" if m.get("subject") and m.get("grade")
             else m["title"] for m in grades[:4]]
        happened.append(f"התקבלו {plural(len(grades), 'ציון חדש אחד', 'ציונים חדשים')}: "
                        + _join(g) + ".")
    if tasks["submitted"]:
        happened.append(f"הוגשו {plural(len(tasks['submitted']), 'משימה אחת', 'משימות')}.")
    if not happened:
        happened.append("אין עדיין נתונים ממקורות מחוברים לשבוע הזה.")

    # --- what needs completing
    if tasks["late"]:
        names = _join([_task_name(t) for t in tasks["late"][:3]])
        more = f" ועוד {len(tasks['late']) - 3}" if len(tasks["late"]) > 3 else ""
        todo.append(f"באיחור: {names}{more}.")
    this_week_open = [t for t in tasks["open"]
                      if (d := _parse_dt(t["due_at"])) and d.date() < next_ws]
    if this_week_open:
        todo.append(f"להגשה עד סוף השבוע: {_join([_task_name(t) for t in this_week_open[:4]])}.")
    if tasks["old_late_count"]:
        todo.append(f"יש גם {plural(tasks['old_late_count'], 'משימה ישנה אחת', 'משימות ישנות')}"
                    f" (מעל {OLD_LATE_DAYS} יום) שלא סומנו כהוגשו.")
    carried = [t for t in tasks["open"] + tasks["late"] if t["carried_over"]]
    if carried:
        todo.append(f"{plural(len(carried), 'משימה אחת הועברה', 'משימות הועברו')} משבוע קודם.")
    if not todo:
        todo.append("אין משימות פתוחות שידוע עליהן." if tasks["available"]
                    else "אין עדיין מקור משימות מחובר.")

    # --- next week
    nxt = [t for t in tasks["open"]
           if (d := _parse_dt(t["due_at"])) and next_ws <= d.date() <= next_we]
    if nxt:
        next_week.append(f"להגשה בשבוע הבא: {_join([_task_name(t) for t in nxt[:4]])}.")
    for m in msgs["by_category"].get("trip", [])[:2]:
        next_week.append(f"טיול: {m['title']}.")
    for m in msgs["by_category"].get("activity", [])[:2]:
        next_week.append(f"פעילות: {m['title']}.")
    for m in msgs["by_category"].get("teacher", []):
        if any(w in (m["title"] + " " + (m.get("body") or "")) for w in _TEST_WORDS):
            next_week.append(f"שימו לב: {m['title']}.")
    if not next_week:
        next_week.append("לא ידוע על משימות או אירועים מיוחדים לשבוע הבא.")

    # --- behavior change
    if beh["available"] and beh["delta"] is not None:
        for key, (def_word, word) in _DELTA_WORDS.items():
            prev, cur = beh["previous"].get(key), beh["counts"][key]
            if prev is None or prev == cur:
                continue
            direction = "עלה" if cur > prev else "ירד"
            behavior_change.append(f"מספר {def_word} {direction} מ-{prev} ל-{cur}.")
        if not behavior_change:
            behavior_change.append("אין שינוי משמעותי לעומת השבוע הקודם.")
    elif beh["available"]:
        behavior_change.append("אין עדיין נתונים משבוע קודם להשוואה.")
    else:
        behavior_change.append("אין נתוני התנהגות — משוב עוד לא מחובר.")

    return {"happened": happened, "todo": todo, "next_week": next_week,
            "behavior_change": behavior_change}


def _task_name(t: dict) -> str:
    return f"{t['title']} ({t['subject']})" if t.get("subject") else t["title"]


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    last = items[-1]
    vav = "ו־" if last[:1].isdigit() or last[:1].isascii() else "ו"
    return ", ".join(items[:-1]) + " " + vav + last


# ------------------------------------------------------------- snapshots
def snapshot_values(report: dict[str, Any], behavior_ok_this_run: bool,
                    tasks_ok_this_run: bool) -> dict[str, Any]:
    beh, tasks = report["behavior"], report["tasks"]
    vals: dict[str, Any] = {"behavior_available": 0, "tasks_available": 0}
    if behavior_ok_this_run and beh["counts"] is not None:
        vals.update(beh["counts"], behavior_available=1)
    if tasks_ok_this_run:
        vals.update(
            tasks_available=1,
            open_tasks=len(tasks["open"]),
            late_tasks=len(tasks["late"]) + tasks["old_late_count"],
            submitted_tasks=len(tasks["submitted"]),
            carried_over=sum(1 for t in tasks["open"] + tasks["late"] if t["carried_over"]),
        )
    return vals
