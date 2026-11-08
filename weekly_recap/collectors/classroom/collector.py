"""Google Classroom — via the official Classroom API (read-only scopes, free).

Setup (one time):
1. In Google Cloud Console create a project, enable "Google Classroom API",
   create an OAuth client of type *Desktop app* and download its JSON.
2. Save it as ``data/profiles/<profile>/secrets/classroom_client.json``
   (or point ``CLASSROOM_CLIENT_SECRETS`` at it) and set ``CLASSROOM_ENABLED=true``.
3. ``weekly recap --login classroom`` → approve read-only access in the browser.

Note: some school Google Workspace domains block third-party apps; if so the
approval screen will say so and the school admin has to allow it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from ...models import CollectorResult, Task, TaskStatus
from ..base import Collector, NeedsLogin, register

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]

SUBMITTED_STATES = {"TURNED_IN", "RETURNED"}


def due_datetime(work: dict[str, Any], tz: str) -> datetime | None:
    """Classroom stores dueDate/dueTime in UTC. Returns a tz-aware local datetime."""
    d = work.get("dueDate")
    if not d or not all(k in d for k in ("year", "month", "day")):
        return None
    t = work.get("dueTime") or {}
    utc = datetime(d["year"], d["month"], d["day"], t.get("hours", 0), t.get("minutes", 0),
                   tzinfo=timezone.utc)
    return utc.astimezone(ZoneInfo(tz))


def map_task(course: dict[str, Any], work: dict[str, Any], submission: dict[str, Any] | None,
             teacher: str | None, now: datetime, tz: str) -> Task | None:
    if work.get("state", "PUBLISHED") != "PUBLISHED":
        return None
    due = due_datetime(work, tz)
    sub_state = (submission or {}).get("state")
    late_flag = bool((submission or {}).get("late"))
    if sub_state in SUBMITTED_STATES:
        status = TaskStatus.SUBMITTED
    elif late_flag or (due is not None and due < now):
        status = TaskStatus.LATE
    else:
        status = TaskStatus.OPEN
    return Task(
        external_id=f"{course['id']}:{work['id']}",
        title=work.get("title") or "(ללא כותרת)",
        status=status,
        subject=course.get("name"),
        teacher=teacher,
        due_at=due.replace(tzinfo=None).isoformat(timespec="minutes") if due else None,
        url=(submission or {}).get("alternateLink") or work.get("alternateLink"),
        submitted_late=late_flag if sub_state in SUBMITTED_STATES else None,
        created_at=work.get("creationTime"),
    )


def _paged(request_fn, key: str, **kw) -> Iterable[dict[str, Any]]:
    token = None
    while True:
        resp = request_fn(pageToken=token, **kw).execute()
        yield from resp.get(key, [])
        token = resp.get("nextPageToken")
        if not token:
            return


@register
class ClassroomCollector(Collector):
    name = "classroom"
    display_name = "Google Classroom"

    @property
    def client_secrets(self) -> Path:
        p = self.settings.get("CLASSROOM_CLIENT_SECRETS")
        return Path(p).expanduser() if p else self.settings.secrets_dir / "classroom_client.json"

    @property
    def token_path(self) -> Path:
        return self.settings.secrets_dir / "classroom_token.json"

    def is_configured(self) -> tuple[bool, str]:
        if self.settings.get("CLASSROOM_ENABLED").lower() not in {"1", "true", "yes", "on"}:
            return False, "לא הופעל (CLASSROOM_ENABLED=true בקובץ ‎.env)"
        if not self.client_secrets.is_file():
            return False, f"חסר קובץ OAuth של Google ({self.client_secrets.name})"
        return True, ""

    def _credentials(self, interactive: bool = False):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = None
        if self.token_path.is_file():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save(creds)
                return creds
            except Exception:
                creds = None
        if not interactive:
            raise NeedsLogin("נדרשת התחברות: weekly recap --login classroom")
        from google_auth_oauthlib.flow import InstalledAppFlow

        from ...launcher import open_in_chrome

        flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secrets), SCOPES)
        creds = self._run_flow(flow, open_in_chrome)
        self._save(creds)
        return creds

    @staticmethod
    def _run_flow(flow, opener):
        import webbrowser

        # Route the consent URL through our Chrome launcher (works from WSL too).
        class _Opener(webbrowser.BaseBrowser):
            def open(self, url, new=0, autoraise=True):
                print(f"\nאם הדפדפן לא נפתח, העתיקו את הקישור:\n{url}\n")
                return opener(url)

        webbrowser.register("wr-chrome", None, _Opener("wr-chrome"), preferred=True)
        return flow.run_local_server(
            host="localhost", port=0, open_browser=True,
            success_message="ההתחברות הושלמה. אפשר לסגור את החלון ולחזור לטרמינל.",
            access_type="offline", prompt="consent",
        )

    def _save(self, creds) -> None:
        self.settings.ensure_dirs()
        self.token_path.write_text(creds.to_json(), encoding="utf-8")
        self.token_path.chmod(0o600)

    def login(self) -> None:
        ok, why = self.is_configured()
        if not ok:
            raise SystemExit(why)
        self._credentials(interactive=True)
        print("✅ Google Classroom מחובר (הרשאות צפייה בלבד).")

    def collect(self) -> CollectorResult:
        from googleapiclient.discovery import build

        creds = self._credentials(interactive=False)
        svc = build("classroom", "v1", credentials=creds, cache_discovery=False)
        tz = self.settings.timezone
        now = datetime.now(ZoneInfo(tz))
        tasks: list[Task] = []
        courses = list(_paged(svc.courses().list, "courses", studentId="me",
                              courseStates=["ACTIVE"]))
        for course in courses:
            teacher = self._teacher_name(svc, course)
            subs = {s["courseWorkId"]: s for s in _paged(
                svc.courses().courseWork().studentSubmissions().list, "studentSubmissions",
                courseId=course["id"], courseWorkId="-", userId="me")}
            for work in _paged(svc.courses().courseWork().list, "courseWork",
                               courseId=course["id"]):
                task = map_task(course, work, subs.get(work["id"]), teacher, now, tz)
                if task:
                    tasks.append(task)
        return self.result("ok", f"{len(courses)} כיתות, {len(tasks)} משימות",
                           tasks=tasks, complete_task_list=True)

    @staticmethod
    def _teacher_name(svc, course: dict[str, Any]) -> str | None:
        try:
            teachers = list(_paged(svc.courses().teachers().list, "teachers",
                                   courseId=course["id"]))
        except Exception:
            return None
        owner = course.get("ownerId")
        pick = next((t for t in teachers if t.get("userId") == owner), teachers[0] if teachers else None)
        return ((pick or {}).get("profile") or {}).get("name", {}).get("fullName")
