"""Mashov parser tests — synthetic fixtures shaped like the real API (no real data)."""
from weekly_recap.collectors.mashov import parse
from weekly_recap.models import BehaviorKind, MessageCategory


def beh(code, name, lesson_id, justified=-1, justification="ללא הערות"):
    return {"lessonId": lesson_id, "achvaCode": code, "achvaName": name, "lessonDate": "2026-11-08T00:00:00",
            "lesson": 2, "subject": "מתמטיקה", "reporter": "מורה בדיקה", "justified": justified,
            "justification": justification, "timestamp": "2026-11-08T10:00:00", "eventCode": code}


def test_behave_skips_presence_and_classifies():
    items = [beh(18, "נוכחות", 1), beh(5, "נוכחות בפרטני", 2), beh(1, "חיסור", 3, 4, "אישור מחנך חריג"),
             beh(2, "איחור", 4), beh(4, "חיזוק חיובי - הישגים לימודיים", 5), beh(13, "חיזוק חיובי - התנהגות", 6),
             beh(6, "היעדרות בפרטני", 7), beh(7, "אי הכנת שיעורי בית", 8)]
    ev = parse.parse_behave(items)
    kinds = [e.kind for e in ev]
    assert kinds == [BehaviorKind.ABSENCE, BehaviorKind.LATE, BehaviorKind.POSITIVE, BehaviorKind.POSITIVE,
                     BehaviorKind.ABSENCE, BehaviorKind.NOTE]
    absent = ev[0]
    assert absent.justified is True and absent.details == "אישור מחנך חריג"
    assert absent.date == "2026-11-08" and absent.external_id == "3:1" and absent.lesson == "2"
    assert ev[1].justified is False and ev[2].justified is None


def test_grades_homework_mail_board():
    g = parse.parse_grades([{"id": 9, "grade": 95, "gradingEvent": "פרק 3", "gradeType": "בוחן",
                             "subjectName": "מדעים", "teacherName": "מורה", "timestamp": "2026-11-07T12:30:00",
                             "eventDate": "2026-11-01T00:00:00"}])[0]
    assert (g.category, g.grade, g.title, g.date, g.external_id) == (
        MessageCategory.GRADE, "95", "בוחן – פרק 3", "2026-11-07T12:30", "grade:9")
    h = parse.parse_homework([{"lessonId": 5, "homework": "<b>עמ' 12</b> תרגילים", "remark": "",
                               "lessonDate": "2026-11-05T00:00:00", "subjectName": "אנגלית"}])[0]
    assert h.title == "עמ' 12 תרגילים" and h.category == MessageCategory.HOMEWORK and h.date == "2026-11-05"
    convs = [{"conversationId": "c1", "subject": "טיול שנתי - אישור הורים", "sendTime": "2026-11-08T10:56:50",
              "messages": [{"senderName": "רכזת"}]},
             {"conversationId": "c2", "subject": "עדכון לגבי המבחן", "sendTime": "2026-11-08T09:00:00", "messages": []}]
    m = parse.parse_conversations(convs)
    assert [x.category for x in m] == [MessageCategory.TRIP, MessageCategory.TEACHER]
    assert m[0].sender == "רכזת" and m[0].date == "2026-11-08T10:56"
    b = parse.parse_message_board([{"eventid": 3, "eventtext": "<p>טקס פתיחת השנה</p>"}])[0]
    assert b.category == MessageCategory.ACTIVITY and b.title == "טקס פתיחת השנה"
    assert parse.parse_behave([]) == [] and parse.parse_grades(None) == []
