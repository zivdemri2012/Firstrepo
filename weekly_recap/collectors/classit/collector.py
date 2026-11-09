"""ClassIt — משימות במתמטיקה (יחידות עבודה): יחידות פתוחות, יחידות שסיימת, ציונים.

How it works (built from a calibration capture of the real site):
* You log in manually once (``weekly recap --login classit``); cookies are saved locally.
* Each run reads the two student pages with read-only GET requests (no browser
  window) and parses their HTML. Nothing is ever submitted or changed.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ...models import CollectorResult, TaskStatus
from .. import browser
from ..base import NeedsLogin, register
from ..browser_site import BrowserSiteCollector
from . import parse

WORK_URL = f"{parse.BASE}/student/work_units/"
DONE_URL = f"{parse.BASE}/student/done_units/"


@register
class ClassitCollector(BrowserSiteCollector):
    name = "classit"
    display_name = "ClassIt (מתמטיקה)"
    env_prefix = "CLASSIT"
    capture_dom = True

    def is_calibrated(self) -> bool:
        return True

    def collect(self) -> CollectorResult:
        from playwright.sync_api import sync_playwright

        state_file = browser.session_path(self.settings, self.name)
        if not state_file.is_file():
            raise NeedsLogin("נדרשת התחברות ידנית: weekly recap --login classit")

        with sync_playwright() as p:
            req = p.request.new_context(storage_state=str(state_file))
            try:
                def get(url: str) -> str:
                    r = req.get(url)
                    if r.status in (401, 403):
                        raise NeedsLogin("פג תוקף ההתחברות ל-ClassIt. הריצו: weekly recap --login classit")
                    if not r.ok:
                        raise RuntimeError(f"ClassIt {url}: HTTP {r.status}")
                    html = r.text()
                    if not parse.logged_in(html):
                        raise NeedsLogin("פג תוקף ההתחברות ל-ClassIt. הריצו: weekly recap --login classit")
                    return html

                work_html = get(WORK_URL)
                done_html = get(DONE_URL)
                req.storage_state(path=str(state_file))
                state_file.chmod(0o600)
            finally:
                req.dispose()

        open_tasks, understood = parse.parse_work_units(work_html)
        done_tasks, grades = parse.parse_done_units(done_html)
        now = datetime.now(ZoneInfo(self.settings.timezone)).replace(tzinfo=None)
        for t in open_tasks:
            if t.due_at and datetime.fromisoformat(t.due_at) < now:
                t.status = TaskStatus.LATE
        done_ids = {t.external_id for t in done_tasks}
        tasks = [t for t in open_tasks if t.external_id not in done_ids] + done_tasks

        msg = f"{len(open_tasks)} יחידות פתוחות, {len(done_tasks)} שסיימת"
        if not understood:
            msg += (" · ⚠️ יש יחידות פתוחות שעוד לא ידוע איך לקרוא — "
                    "הריצו: weekly recap --capture classit")
        return self.result("ok", msg, tasks=tasks, messages=grades,
                           complete_task_list=understood)
