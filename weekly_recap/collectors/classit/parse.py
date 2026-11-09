"""ClassIt HTML → normalized records.

ClassIt is server-rendered (no JSON API). The structure comes from a calibration
capture of the real student site (``weekly recap --capture classit``):

* ``/student/done_units/`` — table ``#student_table``; columns are read by their
  header text (תאריך סיום, המסלול, איחור, ציון), and each row links to
  ``/student/meta_unit/<id>``.
* ``/student/work_units/`` — open units. When there are none the page says
  "אין לך יחידות פתוחות". The capture had no open units, so open units are read
  with the same table reader and the result says so if nothing could be read.

Pure functions (stdlib ``html.parser``) → unit-tested with synthetic fixtures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from ...models import Message, MessageCategory, Task, TaskStatus

SUBJECT = "מתמטיקה"
BASE = "https://www.classit.co.il"
NO_OPEN_UNITS = "אין לך יחידות פתוחות"
_UNIT_RE = re.compile(r"/student/meta_unit/(\d+)")
_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")


@dataclass
class Row:
    cells: list[str] = field(default_factory=list)
    unit_id: str | None = None
    unit_url: str | None = None


class _TableReader(HTMLParser):
    """Collects header texts and row cell texts of the first ``#student_table``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headers: list[str] = []
        self.rows: list[Row] = []
        self._depth = 0          # nesting depth inside the target table (0 = outside)
        self._done = False
        self._cell: list[str] | None = None
        self._in_th = False
        self._row: Row | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if self._depth:
                self._depth += 1
            elif not self._done and a.get("id") == "student_table":
                self._depth = 1
            return
        if not self._depth:
            return
        if tag == "tr" and self._depth == 1:
            self._row = Row()
        elif tag in ("td", "th") and self._depth == 1:
            self._cell = []
            self._in_th = tag == "th"
        elif tag == "a" and self._row is not None and not self._row.unit_id:
            m = _UNIT_RE.search(a.get("href") or "")
            if m:
                self._row.unit_id = m.group(1)
                href = a["href"]
                self._row.unit_url = href if href.startswith("http") else BASE + href

    def handle_endtag(self, tag):
        if not self._depth:
            return
        if tag == "table":
            self._depth -= 1
            if not self._depth:
                self._done = True
            return
        if tag in ("td", "th") and self._depth == 1 and self._cell is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            if self._in_th:
                self.headers.append(text)
            elif self._row is not None:
                self._row.cells.append(text)
            self._cell = None
        elif tag == "tr" and self._depth == 1 and self._row is not None:
            if self._row.cells:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def read_table(html: str) -> tuple[list[str], list[Row]]:
    r = _TableReader()
    r.feed(html or "")
    return r.headers, r.rows


def _col(headers: list[str], *names: str) -> int | None:
    for i, h in enumerate(headers):
        if any(n in h for n in names):
            return i
    return None


def _cell(row: Row, idx: int | None) -> str:
    return row.cells[idx] if idx is not None and idx < len(row.cells) else ""


def parse_date(text: str) -> str | None:
    """'22/09/2026 15:54' → '2026-09-22T15:54' (local time, as shown on the site)."""
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    d, mo, y, hh, mm = m.groups()
    iso = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return f"{iso}T{int(hh):02d}:{mm}" if hh else iso


def _is_late(value: str) -> bool | None:
    v = value.strip()
    if v in ("", "--"):
        return None
    return v not in ("0", "לא")


def logged_in(html: str) -> bool:
    return "יציאה" in (html or "") and "כניסת תלמידים" not in (html or "")


def parse_done_units(html: str) -> tuple[list[Task], list[Message]]:
    headers, rows = read_table(html)
    i_date = _col(headers, "תאריך סיום")
    i_title = _col(headers, "המסלול")
    i_late = _col(headers, "איחור")
    i_grade = next((i for i, h in enumerate(headers) if h == "ציון"), None)
    tasks: list[Task] = []
    grades: list[Message] = []
    for r in rows:
        title = _cell(r, i_title)
        if not r.unit_id or not title:
            continue
        done_at = parse_date(_cell(r, i_date))
        tasks.append(Task(
            external_id=f"classit:{r.unit_id}",
            title=title,
            status=TaskStatus.SUBMITTED,
            subject=SUBJECT,
            url=r.unit_url,
            submitted_late=_is_late(_cell(r, i_late)),
        ))
        grade = _cell(r, i_grade)
        if grade and grade != "--":
            grades.append(Message(
                external_id=f"classitgrade:{r.unit_id}",
                category=MessageCategory.GRADE,
                title=title,
                date=done_at,
                sender="ClassIt",
                subject=SUBJECT,
                url=r.unit_url,
                grade=grade,
            ))
    return tasks, grades


def parse_work_units(html: str) -> tuple[list[Task], bool]:
    """Returns (open tasks, understood). ``understood`` is False when the page lists
    open units in a structure the capture did not show yet."""
    if NO_OPEN_UNITS in (html or ""):
        return [], True
    headers, rows = read_table(html)
    i_title = _col(headers, "המסלול", "יחידה", "שם")
    i_due = _col(headers, "יעד", "הגשה", "תאריך")
    tasks = []
    for r in rows:
        title = _cell(r, i_title)
        if not r.unit_id or not title:
            continue
        tasks.append(Task(
            external_id=f"classit:{r.unit_id}",
            title=title,
            status=TaskStatus.OPEN,
            subject=SUBJECT,
            due_at=parse_date(_cell(r, i_due)),
            url=r.unit_url,
        ))
    if not tasks:
        # Fallback: any unit links on the page (title = link text is unknown → skip).
        return [], False
    return tasks, True
