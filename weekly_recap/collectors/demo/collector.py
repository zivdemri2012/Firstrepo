"""⚠️ נתוני דמה — DEMO DATA ONLY.

Fictional data used to test the dashboard design. It is only ever loaded into
the separate ``demo`` profile (its own database), and every report built from
it is flagged ``is_demo`` so the dashboard shows a clear "נתוני דמה" banner.
Nothing here comes from a real account.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ...database.db import week_start_for
from ...models import (BehaviorEvent, BehaviorKind, CollectorResult, Message, MessageCategory,
                       Task, TaskStatus)
from ..base import Collector, register


def _d(base: datetime, days: int, hour: int = 8, minute: int = 0) -> datetime:
    return (base + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)


@register
class DemoCollector(Collector):
    name = "demo"
    display_name = "נתוני דמה"
    provides_behavior = True

    def __init__(self, *a, now: datetime | None = None, variant: int = 0, **kw):
        super().__init__(*a, **kw)
        self.now = now or datetime.now()
        self.variant = variant  # lets tests simulate a second run with changes

    def is_configured(self) -> tuple[bool, str]:
        if not self.settings.is_demo:
            return False, "נתוני דמה זמינים רק בפרופיל demo"
        return True, ""

    def collect(self) -> CollectorResult:
        now = self.now
        ws = datetime.combine(week_start_for(now.date()), datetime.min.time())
        day = lambda n: (ws + timedelta(days=n)).date().isoformat()  # noqa: E731

        behavior = [
            BehaviorEvent("demo-b1", BehaviorKind.LATE, day(0), "איחור", "מתמטיקה", "[דמה] רונית כהן", "1"),
            BehaviorEvent("demo-b2", BehaviorKind.POSITIVE, day(1), "חיזוק חיובי", "אנגלית",
                          "[דמה] דוד לוי", "3", "השתתפות פעילה ועזרה לחברים"),
            BehaviorEvent("demo-b3", BehaviorKind.ABSENCE, day(2), "חיסור", "היסטוריה",
                          "[דמה] מיכל אברהם", "5", justified=True),
            BehaviorEvent("demo-b4", BehaviorKind.POSITIVE, day(2), "חיזוק חיובי", "מדעים",
                          "[דמה] יוסי פרץ", "2", "עבודה מצוינת בפרויקט"),
            BehaviorEvent("demo-b5", BehaviorKind.NOTE, day(3), "אי הכנת שיעורי בית", "מתמטיקה",
                          "[דמה] רונית כהן", "1"),
            # Previous week — appears in history, not in this week's counts.
            BehaviorEvent("demo-b0", BehaviorKind.LATE, (ws - timedelta(days=4)).date().isoformat(),
                          "איחור", "ספרות", "[דמה] נועה שמש", "1"),
        ]
        tasks = [
            Task("demo-t1", "דף עבודה – משוואות ריבועיות", TaskStatus.OPEN, "מתמטיקה",
                 "[דמה] רונית כהן", _d(now, 2, 23, 59).isoformat(timespec="minutes"),
                 "https://example.com/demo/task1"),
            Task("demo-t2", "חיבור: הדמות הראשית בסיפור", TaskStatus.OPEN, "ספרות",
                 "[דמה] נועה שמש", _d(now, 5, 20).isoformat(timespec="minutes"),
                 "https://example.com/demo/task2"),
            Task("demo-t3", "Reading Comprehension Unit 4", TaskStatus.SUBMITTED, "אנגלית",
                 "[דמה] דוד לוי", _d(now, 1, 22).isoformat(timespec="minutes"),
                 "https://example.com/demo/task3", submitted_late=False),
            Task("demo-t4", "דו\"ח מעבדה – תאים", TaskStatus.LATE, "מדעים", "[דמה] יוסי פרץ",
                 _d(now, -3, 23, 59).isoformat(timespec="minutes"), "https://example.com/demo/task4"),
            Task("demo-t5", "תרגול גלים: שברים עשרוניים", TaskStatus.OPEN, "מתמטיקה", None,
                 _d(now, 1, 18).isoformat(timespec="minutes"), "https://example.com/demo/task5"),
        ]
        if self.variant >= 1:
            # Second simulated run: one task submitted, one due date moved, one new task.
            tasks[0].status = TaskStatus.SUBMITTED
            tasks[1].due_at = _d(now, 7, 20).isoformat(timespec="minutes")
            tasks.append(Task("demo-t6", "מצגת – מהפכה תעשייתית", TaskStatus.OPEN, "היסטוריה",
                              "[דמה] מיכל אברהם", _d(now, 9, 8).isoformat(timespec="minutes"),
                              "https://example.com/demo/task6"))
        messages = [
            Message("demo-m1", MessageCategory.HOMEWORK, "שיעורי בית במתמטיקה: עמ' 54, תרגילים 1-8",
                    _d(now, -1, 14).isoformat(timespec="minutes"), "[דמה] רונית כהן", "מתמטיקה"),
            Message("demo-m2", MessageCategory.TRIP, "טיול שנתי לגליל – יש להחזיר אישור הורים",
                    _d(now, -2, 10).isoformat(timespec="minutes"), "[דמה] רכזת השכבה", None,
                    "הטיול יתקיים בעוד שבועיים. יש להחזיר טופס חתום עד יום חמישי."),
            Message("demo-m3", MessageCategory.ACTIVITY, "טקס יום הזיכרון ליצחק רבין – לבוש חגיגי",
                    _d(now, -1, 9).isoformat(timespec="minutes"), "[דמה] הנהלת בית הספר"),
            Message("demo-m4", MessageCategory.TEACHER, "מבחן באנגלית יתקיים ביום שלישי הבא",
                    _d(now, -3, 16).isoformat(timespec="minutes"), "[דמה] דוד לוי", "אנגלית"),
            Message("demo-m5", MessageCategory.GRADE, "בוחן – אלגברה", _d(now, -2, 12).isoformat(timespec="minutes"),
                    "[דמה] רונית כהן", "מתמטיקה", grade="88"),
            Message("demo-m6", MessageCategory.GRADE, "עבודה – מערכת העיכול", _d(now, -1, 13).isoformat(timespec="minutes"),
                    "[דמה] יוסי פרץ", "מדעים", grade="95"),
        ]
        if self.variant >= 1:
            messages.append(Message("demo-m7", MessageCategory.GRADE, "מבחן – Unit 3",
                                    now.replace(microsecond=0).isoformat(timespec="minutes"),
                                    "[דמה] דוד לוי", "אנגלית", grade="91"))
        return self.result("ok", "נתוני דמה (לא אמיתיים)", behavior=behavior, tasks=tasks,
                           messages=messages, complete_task_list=True, is_demo=True)

    @staticmethod
    def previous_week_snapshot() -> dict:
        """Fictional previous-week numbers so the week-over-week comparison can be previewed."""
        return {"behavior_available": 1, "absences": 0, "lates": 3, "positives": 1, "notes": 2,
                "tasks_available": 1, "open_tasks": 4, "late_tasks": 2, "submitted_tasks": 3,
                "carried_over": 1}
