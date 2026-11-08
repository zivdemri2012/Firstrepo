"""Core tests: dedup, task tracking, weekly history, no-invented-data, server, RTL."""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from weekly_recap.collectors.base import Collector
from weekly_recap.collectors.classroom.collector import due_datetime, map_task
from weekly_recap.collectors.demo.collector import DemoCollector
from weekly_recap.config import PROJECT_ROOT, load_settings
from weekly_recap.database.db import Database, week_start_for
from weekly_recap.models import (BehaviorEvent, BehaviorKind, CollectorResult, Message,
                                 MessageCategory, Task, TaskStatus)
from weekly_recap.pipeline import make_collector, run_recap
from weekly_recap.processing.classify import classify_behavior, classify_message
from weekly_recap.server.app import create_app

NOW = datetime(2026, 11, 10, 18, 0)  # Tuesday


def settings_for(tmp_path: Path, profile: str = "demo"):
    s = load_settings(profile)
    s.data_dir = tmp_path
    s.env = {**s.env, "WR_LOOKBACK_DAYS": "14"}
    return s


class FakeCollector(Collector):
    """Scripted collector for tests (stands in for a real site)."""
    name = "fake"
    display_name = "fake"
    provides_behavior = True

    def __init__(self, settings, result: CollectorResult):
        super().__init__(settings, log=lambda *_: None)
        self._result = result

    def is_configured(self):
        return True, ""

    def collect(self):
        return self._result


def quiet(*_a, **_k):
    pass


# ---------------------------------------------------------------- dedup
def test_messages_are_not_shown_twice(tmp_path):
    s = settings_for(tmp_path)
    demo = DemoCollector(s, log=quiet, now=NOW)
    r1, _ = run_recap(s, [demo], now=NOW, log=quiet)
    first = r1["messages"]["count"]
    assert first == 6

    r2, _ = run_recap(s, [DemoCollector(s, log=quiet, now=NOW)], now=NOW + timedelta(hours=1), log=quiet)
    assert r2["messages"]["count"] == 0, "already-reported messages must not reappear"

    r3, _ = run_recap(s, [DemoCollector(s, log=quiet, now=NOW, variant=1)],
                      now=NOW + timedelta(hours=2), log=quiet)
    assert r3["messages"]["count"] == 1  # only the genuinely new grade
    assert r3["messages"]["by_category"]["grade"][0]["grade"] == "91"


def test_old_messages_on_first_sync_are_baseline(tmp_path):
    s = settings_for(tmp_path, "default")
    old = Message("m-old", MessageCategory.TEACHER, "ישנה", (NOW - timedelta(days=60)).isoformat())
    new = Message("m-new", MessageCategory.TEACHER, "חדשה", (NOW - timedelta(days=1)).isoformat())
    res = CollectorResult("fake", "ok", messages=[old, new])
    r, _ = run_recap(s, [FakeCollector(s, res)], now=NOW, log=quiet)
    titles = [m["title"] for m in r["messages"]["by_category"]["teacher"]]
    assert titles == ["חדשה"]


def test_mark_message_read_via_api(tmp_path):
    s = settings_for(tmp_path)
    run_recap(s, [DemoCollector(s, log=quiet, now=NOW)], now=NOW, log=quiet)
    client = TestClient(create_app(data_dir=tmp_path), base_url="http://localhost")
    rep = client.get("/api/report?profile=demo").json()
    mid = rep["messages"]["by_category"]["trip"][0]["id"]
    assert client.post(f"/api/messages/{mid}/read?profile=demo").json() == {"ok": True}
    rep2 = client.get("/api/report?profile=demo").json()
    assert rep2["messages"]["count"] == rep["messages"]["count"] - 1


# ---------------------------------------------------------------- tasks
def test_open_tasks_persist_and_changes_tracked(tmp_path):
    s = settings_for(tmp_path)
    r1, _ = run_recap(s, [DemoCollector(s, log=quiet, now=NOW)], now=NOW, log=quiet)
    open_ids = {t["external_id"] for t in r1["tasks"]["open"]}
    assert {"demo-t1", "demo-t2", "demo-t5"} <= open_ids
    assert [t["external_id"] for t in r1["tasks"]["late"]] == ["demo-t4"]

    later = NOW + timedelta(hours=3)
    r2, _ = run_recap(s, [DemoCollector(s, log=quiet, now=NOW, variant=1)], now=later, log=quiet)
    open2 = {t["external_id"] for t in r2["tasks"]["open"]}
    assert "demo-t1" not in open2 and "demo-t6" in open2
    assert "demo-t2" in open2, "open task keeps showing on every run until completed"
    assert "demo-t1" in {t["external_id"] for t in r2["tasks"]["submitted"]}
    fields = {(c["title"], c["field"]) for c in r2["tasks"]["changes"]}
    assert ("דף עבודה – משוואות ריבועיות", "status") in fields
    assert ("חיבור: הדמות הראשית בסיפור", "due_at") in fields
    new_flags = {t["external_id"]: t["is_new"] for t in r2["tasks"]["open"]}
    assert new_flags["demo-t6"] is True and new_flags["demo-t2"] is False


def test_missing_task_is_cancelled_and_carried_over_flag(tmp_path):
    s = settings_for(tmp_path, "default")
    t = Task("x1", "עבודה", TaskStatus.OPEN, "מתמטיקה", due_at=(NOW + timedelta(days=20)).isoformat())
    last_week = NOW - timedelta(days=7)
    run_recap(s, [FakeCollector(s, CollectorResult("fake", "ok", tasks=[t], complete_task_list=True))],
              now=last_week, log=quiet)
    r, _ = run_recap(s, [FakeCollector(s, CollectorResult("fake", "ok", tasks=[t], complete_task_list=True))],
                     now=NOW, log=quiet)
    assert r["tasks"]["open"][0]["carried_over"] is True
    assert any("הועברה" in x for x in r["summary"]["todo"])
    r2, _ = run_recap(s, [FakeCollector(s, CollectorResult("fake", "ok", tasks=[], complete_task_list=True))],
                      now=NOW + timedelta(hours=1), log=quiet)
    assert r2["tasks"]["open"] == [] and r2["tasks"]["cancelled"][0]["external_id"] == "x1"


# ---------------------------------------------------------------- history
def test_weekly_history_and_comparison(tmp_path):
    s = settings_for(tmp_path, "default")
    prev_week = NOW - timedelta(days=7)
    ev_prev = [BehaviorEvent(f"p{i}", BehaviorKind.LATE, (week_start_for(prev_week.date()) + timedelta(days=i)).isoformat(), "איחור") for i in range(3)]
    run_recap(s, [FakeCollector(s, CollectorResult("fake", "ok", behavior=ev_prev, provides_behavior=True))],
              now=prev_week, log=quiet)
    ev_now = ev_prev + [BehaviorEvent("n1", BehaviorKind.LATE, NOW.date().isoformat(), "איחור"),
                        BehaviorEvent("n2", BehaviorKind.POSITIVE, NOW.date().isoformat(), "חיזוק חיובי")]
    r, _ = run_recap(s, [FakeCollector(s, CollectorResult("fake", "ok", behavior=ev_now, provides_behavior=True))],
                     now=NOW, log=quiet)
    b = r["behavior"]
    assert b["counts"]["lates"] == 1 and b["counts"]["positives"] == 1
    assert b["previous"]["lates"] == 3 and b["delta"]["lates"] == -2
    assert "מספר האיחורים ירד מ-3 ל-1." in r["summary"]["behavior_change"]
    weeks = [h["week_start"] for h in r["history"]]
    assert weeks == [week_start_for(NOW.date()).isoformat(), week_start_for(prev_week.date()).isoformat()]
    db = Database(s.db_path)
    assert db.get_snapshot(week_start_for(prev_week.date()).isoformat())["lates"] == 3
    db.close()


# ------------------------------------------------------- no invented data
def test_unconfigured_sources_show_no_numbers(tmp_path):
    s = settings_for(tmp_path, "default")
    s.env = {k: v for k, v in s.env.items() if not k.startswith(("MASHOV", "GALIM", "CLASSROOM"))}
    cols = [make_collector(s, n, log=quiet) for n in ("mashov", "classroom", "galim")]
    r, results = run_recap(s, cols, now=NOW, log=quiet)
    assert {x.status for x in results.values()} == {"not_configured"}
    assert r["behavior"]["available"] is False and r["behavior"]["counts"] is None
    assert r["tasks"]["available"] is False and r["messages"]["available"] is False
    assert r["is_demo"] is False
    snap = r["history"][0]
    assert snap["behavior_available"] == 0 and snap["absences"] is None and snap["open_tasks"] is None


def test_failed_source_keeps_last_real_snapshot(tmp_path):
    s = settings_for(tmp_path, "default")
    ev = [BehaviorEvent("a", BehaviorKind.ABSENCE, NOW.date().isoformat(), "חיסור")]
    run_recap(s, [FakeCollector(s, CollectorResult("fake", "ok", behavior=ev, provides_behavior=True))],
              now=NOW, log=quiet)
    r, _ = run_recap(s, [FakeCollector(s, CollectorResult("fake", "error", "boom"))],
                     now=NOW + timedelta(hours=1), log=quiet)
    assert r["behavior"]["available"] and r["behavior"]["stale"] is True
    assert r["history"][0]["absences"] == 1


def test_demo_is_flagged_and_isolated(tmp_path):
    demo = settings_for(tmp_path, "demo")
    real = settings_for(tmp_path, "default")
    r, _ = run_recap(demo, [DemoCollector(demo, log=quiet, now=NOW)], now=NOW, log=quiet)
    assert r["is_demo"] is True
    assert demo.db_path != real.db_path and not real.db_path.exists()
    assert DemoCollector(real, log=quiet).run().status == "not_configured"


# ---------------------------------------------------------------- parsers
def test_classroom_mapping_utc_and_status():
    course = {"id": "c1", "name": "מתמטיקה"}
    work = {"id": "w1", "title": "תרגיל", "state": "PUBLISHED", "alternateLink": "https://classroom.google.com/x",
            "dueDate": {"year": 2026, "month": 11, "day": 12}, "dueTime": {"hours": 21, "minutes": 59}}
    due = due_datetime(work, "Asia/Jerusalem")
    assert (due.hour, due.minute, due.day) == (23, 59, 12)  # UTC+2 in November
    now = datetime(2026, 11, 10, tzinfo=due.tzinfo)
    assert map_task(course, work, None, "המורה", now, "Asia/Jerusalem").status == TaskStatus.OPEN
    assert map_task(course, work, {"state": "TURNED_IN", "late": True}, None, now, "Asia/Jerusalem").submitted_late
    late_now = datetime(2026, 11, 13, tzinfo=due.tzinfo)
    assert map_task(course, work, {"state": "CREATED"}, None, late_now, "Asia/Jerusalem").status == TaskStatus.LATE
    assert map_task(course, {**work, "state": "DRAFT"}, None, None, now, "Asia/Jerusalem") is None


def test_hebrew_classification():
    assert classify_behavior("איחור לשיעור") == BehaviorKind.LATE
    assert classify_behavior("חיסור") == BehaviorKind.ABSENCE
    assert classify_behavior('ח"ח על השתתפות') == BehaviorKind.POSITIVE
    assert classify_behavior("הפרעה בשיעור") == BehaviorKind.NOTE
    assert classify_message("טיול שנתי") == MessageCategory.TRIP
    assert classify_message("שיעורי בית לשבוע") == MessageCategory.HOMEWORK
    assert classify_message("טקס סיום") == MessageCategory.ACTIVITY
    assert classify_message("כללי", from_teacher=False) is None


# ---------------------------------------------------------------- server / RTL
def test_server_serves_rtl_dashboard_and_blocks_foreign_hosts(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path), base_url="http://localhost")
    html = client.get("/").text
    assert 'lang="he"' in html and 'dir="rtl"' in html and "הסיכום השבועי" in html
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/api/health").json()["app"] == "weekly-recap"
    assert client.get("/api/report").json()["has_run"] is False
    evil = TestClient(create_app(data_dir=tmp_path), base_url="http://evil.example")
    assert evil.get("/api/report").status_code == 403
    assert client.get("/api/report?profile=../etc").status_code == 400


def test_css_is_rtl():
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
    assert "direction: rtl" in css
    js = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert ".innerHTML" not in js  # all content inserted as text


# ---------------------------------------------------------------- git hygiene
def test_gitignore_covers_secrets():
    gi = (PROJECT_ROOT / ".gitignore").read_text()
    for pat in (".env", "data/", "*.sqlite3", "sessions/", "secrets/", "captures/", "*cookies*"):
        assert pat in gi
    if (PROJECT_ROOT / ".git").exists():
        tracked = subprocess.run(["git", "ls-files"], cwd=PROJECT_ROOT, capture_output=True,
                                 text=True).stdout.split()
        bad = [f for f in tracked if f == ".env" or f.startswith("data/") or f.endswith(".sqlite3")]
        assert not bad, bad
