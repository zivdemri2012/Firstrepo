"""מט"ח (CET) — קורס לשון והבעה: משימות, מטלות שלא הושלמו, מועדי הגשה, ציונים.

How it works (built from a calibration capture of the real site):
* You log in manually once (``weekly recap --login cet``); cookies are saved locally.
* Each run reads the same JSON endpoints the course player uses, with read-only GET
  requests (no browser window). Nothing is ever submitted or changed.
* The course holds two classes (לשון, הבעה); every task is tagged with its subject.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ...models import CollectorResult
from .. import browser
from ..base import NeedsLogin, register
from ..browser_site import BrowserSiteCollector
from . import parse

STATE_API = "https://apigateway.cet.ac.il/AccessMngApi/state"
PRODUCT_API = "https://productplayerservices.cet.ac.il"
TREE_API = "https://treeservice.cet.ac.il/api/TreeLMS"
PRODUCT_NAME = "lashontcourse"


@register
class CetCollector(BrowserSiteCollector):
    name = "cet"
    display_name = "לשון והבעה (מט\"ח)"
    env_prefix = "CET"
    subjects = ("לשון", "הבעה")

    def is_calibrated(self) -> bool:
        return True

    def collect(self) -> CollectorResult:
        from playwright.sync_api import sync_playwright

        state_file = browser.session_path(self.settings, self.name)
        if not state_file.is_file():
            raise NeedsLogin("נדרשת התחברות ידנית: weekly recap --login cet")
        expired = NeedsLogin("פג תוקף ההתחברות למט\"ח. הריצו: weekly recap --login cet")

        tz = self.settings.timezone
        now = datetime.now(ZoneInfo(tz))
        tasks, grades, classes = [], [], []
        with sync_playwright() as p:
            req = p.request.new_context(storage_state=str(state_file))
            try:
                def get(url: str, **params):
                    r = req.get(url, params=params or None)
                    if r.status in (401, 403):
                        raise expired
                    if not r.ok:
                        raise RuntimeError(f"CET {url.split('/')[-1]}: HTTP {r.status}")
                    if "json" not in r.headers.get("content-type", ""):
                        raise expired          # redirected to a login page
                    return r.json()

                me = get(STATE_API)
                uid, school = me.get("userId"), me.get("schoolId")
                if not uid or not school:
                    raise expired
                product = get(f"{PRODUCT_API}/GetProductConfigurationByName/{PRODUCT_NAME}")
                pid = product["productId"]
                audiences = get(f"{PRODUCT_API}/GetUserAudiences",
                                userId=uid, schoolId=school, productId=pid)
                for a in audiences or []:
                    subject = parse.subject_of(a.get("title", ""))
                    classes.append(subject)
                    env_tasks = get(f"{TREE_API}/GetAllEnvironmentTasks/{a['id']}")
                    scores = get(f"{TREE_API}/GetStudentScores/{uid}/{school}/{pid}/{a['audienceId']}/he/")
                    tasks += parse.map_tasks(env_tasks, scores, subject, self.start_url, now, tz)
                    grades += parse.map_grades(scores, subject, self.start_url, tz)
                req.storage_state(path=str(state_file))
                state_file.chmod(0o600)
            finally:
                req.dispose()

        open_n = sum(1 for t in tasks if t.status.value != "submitted")
        return self.result(
            "ok", f"{len(tasks)} משימות ({' + '.join(classes) or 'אין כיתות'}), {open_n} לא הוגשו",
            tasks=tasks, messages=grades, complete_task_list=bool(classes),
        )
