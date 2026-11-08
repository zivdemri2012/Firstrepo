"""Generic base for websites accessed through a manually-logged-in browser session.

Flow per site:
1. ``<PREFIX>_URL`` is set in ``.env`` (the address *you* provide — nothing is guessed).
2. ``weekly recap --login <source>`` → you log in by hand; the session is saved locally.
3. ``weekly recap --capture <source>`` → you browse the relevant pages once; the JSON the
   site loads is recorded locally so a parser can be written against the real structure.
4. Once ``parse()`` is implemented for the site, every run collects headlessly, read-only.
"""
from __future__ import annotations

from ..models import CollectorResult
from . import browser
from .base import Collector, NeedsCalibration, NeedsLogin


class BrowserSiteCollector(Collector):
    env_prefix: str = ""
    #: Pages (relative or absolute URLs) to visit during collection. Set by the parser.
    pages: list[str] = []

    @property
    def start_url(self) -> str:
        return self.settings.get(f"{self.env_prefix}_URL")

    def is_configured(self) -> tuple[bool, str]:
        if not self.start_url:
            return False, f"חסרה כתובת האתר ({self.env_prefix}_URL בקובץ ‎.env)"
        return True, ""

    def login(self) -> None:
        ok, why = self.is_configured()
        if not ok:
            raise SystemExit(why)
        browser.manual_login(self.settings, self.name, self.start_url, self.display_name)

    def capture(self) -> None:
        ok, why = self.is_configured()
        if not ok:
            raise SystemExit(why)
        browser.capture_session(self.settings, self.name, self.start_url, self.display_name)

    def collect(self) -> CollectorResult:
        if not browser.has_session(self.settings, self.name):
            raise NeedsLogin(f"נדרשת התחברות ידנית: weekly recap --login {self.name}")
        if not self.is_calibrated():
            raise NeedsCalibration(
                "מחובר, אך מבנה הנתונים של האתר עוד לא מופה. "
                f"הריצו פעם אחת: weekly recap --capture {self.name}"
            )
        with browser.HeadlessSession(self.settings, self.name) as s:
            for url in self.pages:
                s.page.goto(url if url.startswith("http") else self.start_url.rstrip("/") + "/" + url.lstrip("/"))
                s.page.wait_for_load_state("networkidle")
            if self.session_expired(s):
                raise NeedsLogin(f"פג תוקף ההתחברות: weekly recap --login {self.name}")
            return self.parse(s)

    # -- to be implemented per site after calibration with real data ----------
    def is_calibrated(self) -> bool:
        return False

    def session_expired(self, s: browser.HeadlessSession) -> bool:
        return False

    def parse(self, s: browser.HeadlessSession) -> CollectorResult:
        raise NeedsCalibration("parser not implemented")
