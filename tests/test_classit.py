"""ClassIt parser tests — synthetic HTML shaped like the real student pages (no real data)."""
from weekly_recap.collectors.classit import parse
from weekly_recap.models import MessageCategory, TaskStatus

DONE = """<html><body>שלום תלמיד <a>יציאה</a>
<table id="student_table"><thead><tr>
<th>#</th><th> תאריך סיום</th><th>המסלול</th><th>איחור</th><th>המסלול</th>
<th>תרגילי חימום 1</th><th><span>ציון</span></th><th><span>ציון מקורי</span></th><th>1</th>
</tr></thead><tbody>
<tr><td>1</td><td><span class=finished_date>22/09/2026 15:54</span></td><td>חוק הפילוג</td><td>0</td>
<td><a href='https://www.classit.co.il/student/meta_unit/10326'><span>חוק הפילוג</span></a></td>
<td>--</td><td>100</td><td>95</td>
<td><div><table><tr><td>inner</td></tr></table></div></td></tr>
<tr><td>2</td><td>01/10/2026 08:05</td><td>משוואות</td><td>2</td>
<td><a href='/student/meta_unit/10400'>משוואות</a></td><td>--</td><td>--</td><td>--</td><td></td></tr>
</tbody></table></body></html>"""


def test_done_units():
    tasks, grades = parse.parse_done_units(DONE)
    assert [t.external_id for t in tasks] == ["classit:10326", "classit:10400"]
    assert all(t.status == TaskStatus.SUBMITTED and t.subject == "מתמטיקה" for t in tasks)
    assert tasks[0].submitted_late is False and tasks[1].submitted_late is True
    assert tasks[1].url == "https://www.classit.co.il/student/meta_unit/10400"
    assert len(grades) == 1
    g = grades[0]
    assert (g.category, g.grade, g.date, g.title) == (MessageCategory.GRADE, "100", "2026-09-22T15:54", "חוק הפילוג")


def test_work_units_empty_and_login_detection():
    html = "<html>שלום <a>יציאה</a><p>אין לך יחידות פתוחות לעבודה.</p></html>"
    assert parse.parse_work_units(html) == ([], True)
    assert parse.logged_in(html)
    assert not parse.logged_in("<html>כניסת תלמידים יציאה</html>")


def test_work_units_unknown_structure_is_flagged():
    assert parse.parse_work_units("<html><div>יחידה חדשה</div></html>") == ([], False)


def test_parse_date():
    assert parse.parse_date("5/1/2027") == "2027-01-05"
    assert parse.parse_date("--") is None
