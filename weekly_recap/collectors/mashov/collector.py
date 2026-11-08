"""משוב (Mashov) — behavior, attendance, important messages, new grades.

How it works (built from a calibration capture of the real site):
* You log in manually once (``weekly recap --login mashov``); cookies are saved locally.
* Each run reads the same JSON endpoints the student site itself uses, with
  read-only GET requests (no browser window needed). Nothing is ever sent or changed.
* When the login expires, the run reports "needs_login" and offers to log in again.

Kept (and nothing else): absences, lates, positive reinforcements, other behavior
events, homework, teacher/school messages (classified into trips/activities/...),
and newly entered grades.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ...models import CollectorResult
from .. import browser
from ..base import NeedsLogin, register
from ..browser_site import BrowserSiteCollector
from . import parse

API = "https://web.mashov.info/api"
_GUID_RE = re.compile(r"/api/students/([0-9a-fA-F-]{36})/")


@register
class MashovCollector(BrowserSiteCollector):
    name = "mashov"
    display_name = "משוב"
    env_prefix = "MASHOV"
    provides_behavior = True

    # ---- student id (from your own captured traffic; stored locally) --------
    @property
    def _meta_path(self) -> Path:
        return self.settings.sessions_dir / "mashov_meta.json"

    def student_id(self) -> str | None:
        configured = self.settings.get("MASHOV_STUDENT_ID")
        if configured:
            return configured
        if self._meta_path.is_file():
            sid = json.loads(self._meta_path.read_text()).get("student_id")
            if sid:
                return sid
        caps = sorted((self.settings.captures_dir / self.name).glob("*.jsonl"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        for cap in caps:
            with cap.open(encoding="utf-8") as f:
                for line in f:
                    m = _GUID_RE.search(json.loads(line).get("url", ""))
                    if m:
                        self._save_meta(m.group(1))
                        return m.group(1)
        return None

    def _save_meta(self, sid: str) -> None:
        self.settings.ensure_dirs()
        self._meta_path.write_text(json.dumps({"student_id": sid}))
        self._meta_path.chmod(0o600)

    def is_calibrated(self) -> bool:
        return self.student_id() is not None

    # ---- collection --------------------------------------------------------
    def collect(self) -> CollectorResult:
        from playwright.sync_api import sync_playwright

        state_file = browser.session_path(self.settings, self.name)
        if not state_file.is_file():
            raise NeedsLogin("נדרשת התחברות ידנית: weekly recap --login mashov")
        sid = self.student_id()
        if not sid:
            from ..base import NeedsCalibration
            raise NeedsCalibration("חסר מזהה תלמיד. הריצו: weekly recap --capture mashov")

        state = json.loads(state_file.read_text())
        csrf = next((c["value"] for c in state.get("cookies", [])
                     if c.get("name", "").lower() == "csrf-token"), None)
        if not csrf:
            raise NeedsLogin("ההתחברות השמורה חסרה. הריצו: weekly recap --login mashov")

        with sync_playwright() as p:
            req = p.request.new_context(storage_state=str(state_file),
                                        extra_http_headers={"x-csrf-token": csrf})
            try:
                def get(path: str, required: bool = True):
                    r = req.get(f"{API}{path}")
                    if r.status in (400, 401, 403):
                        raise NeedsLogin("פג תוקף ההתחברות למשוב. הריצו: weekly recap --login mashov")
                    if not r.ok:
                        if required:
                            raise RuntimeError(f"Mashov {path}: HTTP {r.status}")
                        return []
                    return r.json()

                behave = get(f"/students/{sid}/behave")
                grades = get(f"/students/{sid}/grades")
                homework = get(f"/students/{sid}/homework", required=False)
                mail = get("/mail/inbox/conversations", required=False)
                board = get(f"/students/{sid}/messageBoard", required=False)
                # Keep refreshed cookies (if the site rotated them).
                req.storage_state(path=str(state_file))
                state_file.chmod(0o600)
            finally:
                req.dispose()

        events = parse.parse_behave(behave)
        messages = (parse.parse_grades(grades) + parse.parse_homework(homework)
                    + parse.parse_conversations(mail) + parse.parse_message_board(board))
        return self.result(
            "ok", f"{len(events)} אירועי התנהגות, {len(messages)} הודעות/ציונים",
            behavior=events, messages=messages,
        )
