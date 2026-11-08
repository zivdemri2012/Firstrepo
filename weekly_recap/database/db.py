"""SQLite storage: deduplication, task change tracking, weekly history.

One database file per profile (``data/profiles/<profile>/weekly_recap.sqlite3``)
gives complete data separation between users.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from ..models import BehaviorEvent, CollectorResult, Message, Task, TaskStatus

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    week_start   TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS source_status (
    source          TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    message         TEXT NOT NULL DEFAULT '',
    last_attempt_at TEXT NOT NULL,
    last_success_at TEXT,
    provides_behavior INTEGER NOT NULL DEFAULT 0,
    is_demo         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS behavior_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source         TEXT NOT NULL,
    external_id    TEXT NOT NULL,
    kind           TEXT NOT NULL,
    date           TEXT NOT NULL,
    title          TEXT NOT NULL,
    subject        TEXT,
    teacher        TEXT,
    lesson         TEXT,
    details        TEXT,
    justified      INTEGER,
    first_seen_run INTEGER NOT NULL,
    last_seen_run  INTEGER NOT NULL,
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source         TEXT NOT NULL,
    external_id    TEXT NOT NULL,
    category       TEXT NOT NULL,
    title          TEXT NOT NULL,
    date           TEXT,
    sender         TEXT,
    subject        TEXT,
    body           TEXT,
    url            TEXT,
    grade          TEXT,
    first_seen_run INTEGER NOT NULL,
    first_seen_at  TEXT NOT NULL,
    read_at        TEXT,           -- dismissed in dashboard / shown already / baseline
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source            TEXT NOT NULL,
    external_id       TEXT NOT NULL,
    title             TEXT NOT NULL,
    subject           TEXT,
    teacher           TEXT,
    due_at            TEXT,
    url               TEXT,
    status            TEXT NOT NULL,
    submitted_late    INTEGER,
    created_at        TEXT,
    first_seen_run    INTEGER NOT NULL,
    first_seen_at     TEXT NOT NULL,
    last_seen_run     INTEGER NOT NULL,
    status_changed_at TEXT NOT NULL,
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS task_changes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER NOT NULL REFERENCES tasks(id),
    run_id     INTEGER NOT NULL,
    field      TEXT NOT NULL,      -- 'status' | 'due_at'
    old_value  TEXT,
    new_value  TEXT,
    changed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_snapshots (
    week_start         TEXT PRIMARY KEY,
    behavior_available INTEGER NOT NULL DEFAULT 0,
    absences           INTEGER,
    lates              INTEGER,
    positives          INTEGER,
    notes              INTEGER,
    tasks_available    INTEGER NOT NULL DEFAULT 0,
    open_tasks         INTEGER,
    late_tasks         INTEGER,
    submitted_tasks    INTEGER,
    carried_over       INTEGER,
    updated_at         TEXT NOT NULL,
    run_id             INTEGER NOT NULL
);
"""


def week_start_for(d: date) -> date:
    """Israeli school week starts on Sunday."""
    # Python: Monday=0 ... Sunday=6
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _iso_now(now: datetime | None = None) -> str:
    return (now or datetime.now()).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ------------------------------------------------------------------ runs
    def start_run(self, now: datetime | None = None) -> int:
        now = now or datetime.now()
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO runs(started_at, week_start) VALUES (?, ?)",
                (_iso_now(now), week_start_for(now.date()).isoformat()),
            )
            return int(cur.lastrowid)

    def finish_run(self, run_id: int, sources: dict[str, Any], now: datetime | None = None) -> None:
        with self.tx() as c:
            c.execute(
                "UPDATE runs SET finished_at = ?, sources_json = ? WHERE id = ?",
                (_iso_now(now), json.dumps(sources, ensure_ascii=False), run_id),
            )

    def latest_run(self) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()

    def previous_run(self, before_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM runs WHERE finished_at IS NOT NULL AND id < ? ORDER BY id DESC LIMIT 1",
            (before_id,),
        ).fetchone()

    # --------------------------------------------------------- source status
    def record_source(self, result: CollectorResult, now: datetime | None = None) -> None:
        ts = _iso_now(now)
        ok = result.status == "ok"
        with self.tx() as c:
            c.execute(
                """INSERT INTO source_status(source, status, message, last_attempt_at,
                                             last_success_at, provides_behavior, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(source) DO UPDATE SET
                     status = excluded.status,
                     message = excluded.message,
                     last_attempt_at = excluded.last_attempt_at,
                     last_success_at = COALESCE(excluded.last_success_at, source_status.last_success_at),
                     provides_behavior = MAX(source_status.provides_behavior, excluded.provides_behavior),
                     is_demo = excluded.is_demo""",
                (result.source, result.status, result.message, ts, ts if ok else None,
                 int(result.provides_behavior and ok), int(result.is_demo)),
            )

    def source_statuses(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM source_status ORDER BY source").fetchall()

    # ------------------------------------------------------------- ingest
    def ingest(self, run_id: int, result: CollectorResult, *,
               now: datetime | None = None, lookback_days: int = 14) -> dict[str, int]:
        """Store one successful collector result. Returns counters of what was new/changed."""
        now = now or datetime.now()
        ts = _iso_now(now)
        stats = {"behavior_new": 0, "messages_new": 0, "tasks_new": 0,
                 "tasks_changed": 0, "tasks_cancelled": 0}
        if result.status != "ok":
            return stats
        baseline_before = (now.date() - timedelta(days=lookback_days)).isoformat()
        with self.tx() as c:
            for ev in result.behavior:
                stats["behavior_new"] += self._upsert_behavior(c, run_id, result.source, ev)
            for msg in result.messages:
                stats["messages_new"] += self._upsert_message(
                    c, run_id, result.source, msg, ts, baseline_before)
            seen_ids: set[str] = set()
            for task in result.tasks:
                seen_ids.add(task.external_id)
                new, changed = self._upsert_task(c, run_id, result.source, task, ts)
                stats["tasks_new"] += new
                stats["tasks_changed"] += changed
            if result.complete_task_list:
                stats["tasks_cancelled"] = self._cancel_missing(c, run_id, result.source, seen_ids, ts)
        return stats

    @staticmethod
    def _upsert_behavior(c: sqlite3.Connection, run_id: int, source: str, ev: BehaviorEvent) -> int:
        row = c.execute("SELECT id FROM behavior_events WHERE source = ? AND external_id = ?",
                        (source, ev.external_id)).fetchone()
        justified = None if ev.justified is None else int(ev.justified)
        if row:
            c.execute(
                """UPDATE behavior_events SET kind=?, date=?, title=?, subject=?, teacher=?,
                       lesson=?, details=?, justified=?, last_seen_run=? WHERE id=?""",
                (ev.kind.value, ev.date, ev.title, ev.subject, ev.teacher, ev.lesson,
                 ev.details, justified, run_id, row["id"]),
            )
            return 0
        c.execute(
            """INSERT INTO behavior_events(source, external_id, kind, date, title, subject,
                   teacher, lesson, details, justified, first_seen_run, last_seen_run)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (source, ev.external_id, ev.kind.value, ev.date, ev.title, ev.subject, ev.teacher,
             ev.lesson, ev.details, justified, run_id, run_id),
        )
        return 1

    @staticmethod
    def _upsert_message(c: sqlite3.Connection, run_id: int, source: str, msg: Message,
                        ts: str, baseline_before: str) -> int:
        row = c.execute("SELECT id FROM messages WHERE source = ? AND external_id = ?",
                        (source, msg.external_id)).fetchone()
        if row:
            # Already known: never re-surface it. Refresh content only.
            c.execute(
                "UPDATE messages SET title=?, body=?, url=?, grade=? WHERE id=?",
                (msg.title, msg.body, msg.url, msg.grade, row["id"]),
            )
            return 0
        # Old items discovered on a first sync are recorded as a baseline, not "new".
        read_at = "baseline" if (msg.date and msg.date[:10] < baseline_before) else None
        c.execute(
            """INSERT INTO messages(source, external_id, category, title, date, sender, subject,
                   body, url, grade, first_seen_run, first_seen_at, read_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (source, msg.external_id, msg.category.value, msg.title, msg.date, msg.sender,
             msg.subject, msg.body, msg.url, msg.grade, run_id, ts, read_at),
        )
        return 0 if read_at else 1

    @staticmethod
    def _upsert_task(c: sqlite3.Connection, run_id: int, source: str, task: Task,
                     ts: str) -> tuple[int, int]:
        row = c.execute("SELECT * FROM tasks WHERE source = ? AND external_id = ?",
                        (source, task.external_id)).fetchone()
        late = None if task.submitted_late is None else int(task.submitted_late)
        if not row:
            c.execute(
                """INSERT INTO tasks(source, external_id, title, subject, teacher, due_at, url,
                       status, submitted_late, created_at, first_seen_run, first_seen_at,
                       last_seen_run, status_changed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (source, task.external_id, task.title, task.subject, task.teacher, task.due_at,
                 task.url, task.status.value, late, task.created_at, run_id, ts, run_id, ts),
            )
            return 1, 0
        changed = 0
        status_changed_at = row["status_changed_at"]
        for field, old, new in (("status", row["status"], task.status.value),
                                ("due_at", row["due_at"], task.due_at)):
            if old != new:
                changed = 1
                c.execute(
                    """INSERT INTO task_changes(task_id, run_id, field, old_value, new_value, changed_at)
                       VALUES (?,?,?,?,?,?)""",
                    (row["id"], run_id, field, old, new, ts),
                )
                if field == "status":
                    status_changed_at = ts
        c.execute(
            """UPDATE tasks SET title=?, subject=?, teacher=?, due_at=?, url=?, status=?,
                   submitted_late=?, created_at=COALESCE(?, created_at), last_seen_run=?,
                   status_changed_at=? WHERE id=?""",
            (task.title, task.subject, task.teacher, task.due_at, task.url, task.status.value,
             late, task.created_at, run_id, status_changed_at, row["id"]),
        )
        return 0, changed

    @staticmethod
    def _cancel_missing(c: sqlite3.Connection, run_id: int, source: str,
                        seen: set[str], ts: str) -> int:
        rows = c.execute(
            "SELECT id, external_id, status FROM tasks WHERE source = ? AND status IN ('open','late')",
            (source,),
        ).fetchall()
        n = 0
        for r in rows:
            if r["external_id"] in seen:
                continue
            c.execute("UPDATE tasks SET status='cancelled', status_changed_at=? WHERE id=?",
                      (ts, r["id"]))
            c.execute(
                """INSERT INTO task_changes(task_id, run_id, field, old_value, new_value, changed_at)
                   VALUES (?,?,?,?,?,?)""",
                (r["id"], run_id, "status", r["status"], TaskStatus.CANCELLED.value, ts),
            )
            n += 1
        return n

    # ------------------------------------------------------------ messages
    def mark_message_read(self, message_id: int, now: datetime | None = None) -> bool:
        with self.tx() as c:
            cur = c.execute("UPDATE messages SET read_at = ? WHERE id = ? AND read_at IS NULL",
                            (_iso_now(now), message_id))
            return cur.rowcount > 0

    def mark_shown_messages(self, before_run: int, now: datetime | None = None) -> int:
        """Messages that first appeared in an earlier run were already reported: retire them."""
        with self.tx() as c:
            cur = c.execute(
                "UPDATE messages SET read_at = ? WHERE read_at IS NULL AND first_seen_run < ?",
                ("shown:" + _iso_now(now), before_run),
            )
            return cur.rowcount

    # ----------------------------------------------------------- snapshots
    def save_snapshot(self, week_start: str, run_id: int, values: dict[str, Any],
                      now: datetime | None = None) -> None:
        """Upsert this week's snapshot. Behavior/task fields are only overwritten when available."""
        existing = self.get_snapshot(week_start)
        merged: dict[str, Any] = dict(existing) if existing else {
            "behavior_available": 0, "absences": None, "lates": None, "positives": None,
            "notes": None, "tasks_available": 0, "open_tasks": None, "late_tasks": None,
            "submitted_tasks": None, "carried_over": None,
        }
        if values.get("behavior_available"):
            for k in ("absences", "lates", "positives", "notes"):
                merged[k] = values.get(k)
            merged["behavior_available"] = 1
        if values.get("tasks_available"):
            for k in ("open_tasks", "late_tasks", "submitted_tasks", "carried_over"):
                merged[k] = values.get(k)
            merged["tasks_available"] = 1
        with self.tx() as c:
            c.execute(
                """INSERT INTO weekly_snapshots(week_start, behavior_available, absences, lates,
                       positives, notes, tasks_available, open_tasks, late_tasks, submitted_tasks,
                       carried_over, updated_at, run_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(week_start) DO UPDATE SET
                     behavior_available=excluded.behavior_available, absences=excluded.absences,
                     lates=excluded.lates, positives=excluded.positives, notes=excluded.notes,
                     tasks_available=excluded.tasks_available, open_tasks=excluded.open_tasks,
                     late_tasks=excluded.late_tasks, submitted_tasks=excluded.submitted_tasks,
                     carried_over=excluded.carried_over, updated_at=excluded.updated_at,
                     run_id=excluded.run_id""",
                (week_start, merged["behavior_available"], merged["absences"], merged["lates"],
                 merged["positives"], merged["notes"], merged["tasks_available"],
                 merged["open_tasks"], merged["late_tasks"], merged["submitted_tasks"],
                 merged["carried_over"], _iso_now(now), run_id),
            )

    def get_snapshot(self, week_start: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM weekly_snapshots WHERE week_start = ?",
                                 (week_start,)).fetchone()

    def snapshots(self, limit: int = 12) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM weekly_snapshots ORDER BY week_start DESC LIMIT ?", (limit,)
        ).fetchall()
