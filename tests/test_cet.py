"""CET parser tests — synthetic fixtures shaped like the real TreeLMS API (no real data)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from weekly_recap.collectors.cet import parse
from weekly_recap.models import MessageCategory, TaskStatus

TZ = "Asia/Jerusalem"
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=ZoneInfo(TZ))


def task(tid, title, end, ttype="EvalWork", scheduled=True, hidden=False):
    return {"TaskId": tid, "TaskTitle": title, "TaskType": ttype, "IsScheduled": scheduled,
            "IsHidden": hidden, "StartTime": "2026-10-18T09:29:00.943", "EndTime": end}


def score(tid, state="evaluated", submitted=1793181943, final=100.0, hide=False):
    return {"TaskId": tid, "Title": f"משימה {tid}", "HideGrade": None,
            "StudentLmsInfo": {"State": state, "SubmittedTime": submitted,
                               "HideScoreFromStudents": hide,
                               "Scores": {"FinalScore": final}}}


def test_subject_tagging():
    assert parse.subject_of("מפל- לשון") == "לשון"
    assert parse.subject_of("ט מפל - שפה הבעה") == "הבעה"


def test_task_statuses_and_filters():
    tasks = [task("a", "הוגשה", "2026-10-31T20:59:59"),
             task("b", "פתוחה", "2026-11-20T21:59:59"),
             task("c", "באיחור", "2026-11-01T21:59:59"),
             task("d", "ספרייה", "2027-07-31T23:59:59", ttype="SelfLearning", scheduled=False),
             task("e", "מוסתרת", "2026-11-20T21:59:59", hidden=True)]
    out = parse.map_tasks(tasks, [score("a")], "לשון", "https://x", NOW, TZ)
    assert [t.external_id for t in out] == ["cet:a", "cet:b", "cet:c"]
    assert [t.status for t in out] == [TaskStatus.SUBMITTED, TaskStatus.OPEN, TaskStatus.LATE]
    assert out[0].submitted_late is False and out[1].submitted_late is None
    # UTC → Israel time (winter, UTC+2); created_at drops fractional seconds.
    assert out[1].due_at == "2026-11-20T23:59" and out[0].created_at == "2026-10-18T12:29"
    assert all(t.subject == "לשון" for t in out)


def test_learning_work_submitted_without_score():
    out = parse.map_tasks([task("l", "למידה", "2026-09-14T20:59:59", ttype="LearningWork")],
                          [score("l", state="submitted", final=None)], "לשון", None, NOW, TZ)
    assert out[0].status == TaskStatus.SUBMITTED


def test_grades():
    g = parse.map_grades([score("a", final=98.0), score("b", state="submitted"),
                          score("c", hide=True)], "הבעה", None, TZ)
    assert len(g) == 1
    assert (g[0].category, g[0].grade, g[0].subject, g[0].external_id) == (
        MessageCategory.GRADE, "98", "הבעה", "cetgrade:a")
