"""Command line: ``weekly recap [options]``."""
from __future__ import annotations

import argparse
import sys

from . import launcher
from .collectors import browser
from .config import DEMO_PROFILE, load_settings
from .database.db import Database, week_start_for
from .models import CollectorResult
from .pipeline import default_sources, make_collector, run_recap

LOGIN_SOURCES = ("mashov", "classroom", "cet", "classit")
CAPTURE_SOURCES = ("mashov", "cet", "classit")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="weekly recap",
        description="Weekly Recap — איסוף נתוני בית הספר ופתיחת הדוח השבועי בכרום.",
    )
    ap.add_argument("--demo", action="store_true",
                    help="הצגת נתוני דמה (פרופיל נפרד, מסומן בבירור)")
    ap.add_argument("--profile", help="שם פרופיל (ברירת מחדל: WR_PROFILE או default)")
    ap.add_argument("--sources", help="רשימת מקורות מופרדת בפסיקים (ברירת מחדל: WR_SOURCES)")
    ap.add_argument("--no-collect", action="store_true", help="רק לפתוח את הדוח האחרון")
    ap.add_argument("--no-open", action="store_true", help="לא לפתוח את כרום")
    ap.add_argument("--login", choices=LOGIN_SOURCES, help="התחברות ידנית למקור ושמירת ההתחברות")
    ap.add_argument("--capture", choices=CAPTURE_SOURCES,
                    help="מצב כיול: הקלטת מבנה הנתונים של האתר (מקומית בלבד)")
    ap.add_argument("--status", action="store_true", help="הצגת מצב המקורות")
    ap.add_argument("--stop", action="store_true", help="עצירת שרת הדשבורד ברקע")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "recap":
        argv = argv[1:]
    args = build_parser().parse_args(argv)
    settings = load_settings(DEMO_PROFILE if args.demo else args.profile)

    if args.stop:
        print("השרת נעצר." if launcher.stop_server(settings) else "לא ניתן לעצור את השרת.")
        return 0

    if args.login or args.capture:
        name = args.login or args.capture
        col = make_collector(settings, name)
        col.login() if args.login else col.capture()
        return 0

    if args.status:
        return _status(settings)

    if not args.no_collect:
        names = ([s.strip() for s in args.sources.split(",")] if args.sources
                 else default_sources(settings))
        collectors = [make_collector(settings, n) for n in names]
        if settings.is_demo and settings.db_path.is_file():
            settings.db_path.unlink()  # demo preview always starts fresh (real profiles never do)
        print(f"📚 Weekly Recap — {'נתוני דמה' if settings.is_demo else 'פרופיל ' + settings.profile}")
        _, results = run_recap(settings, collectors, on_result=_maybe_login)
        if settings.is_demo:
            _seed_demo_history(settings)
        _hints(results)

    if args.no_open:
        print(f"הדוח זמין בכתובת: {launcher.dashboard_url(settings, settings.profile)}")
        return 0
    if not launcher.ensure_server(settings):
        print(f"❌ שרת הדשבורד לא עלה. פרטים: {settings.run_dir / 'server.log'}")
        return 1
    url = launcher.dashboard_url(settings, settings.profile)
    launcher.open_in_chrome(url, settings)
    print(f"🌐 הדוח נפתח בכרום: {url}")
    return 0


def _maybe_login(col, res: CollectorResult) -> CollectorResult:
    """When a session expired and we have a terminal, offer a manual login right away."""
    if res.status != "needs_login" or not browser.interactive():
        return res
    try:
        answer = input(f"  🔐 {col.display_name}: נדרשת התחברות. להתחבר עכשיו? [y/N] ")
    except EOFError:
        return res
    if answer.strip().lower() not in {"y", "yes", "כ", "כן"}:
        return res
    try:
        col.login()
    except Exception as e:  # e.g. Chromium system libraries missing
        return col.result("needs_login", str(e))
    return col.run()


def _seed_demo_history(settings) -> None:
    """Demo profile only: add a fictional previous-week snapshot for the comparison view."""
    from datetime import date, timedelta

    from .collectors.demo.collector import DemoCollector

    db = Database(settings.db_path)
    try:
        prev = (week_start_for(date.today()) - timedelta(days=7)).isoformat()
        if not db.get_snapshot(prev):
            run = db.latest_run()
            db.save_snapshot(prev, run["id"] if run else 0, DemoCollector.previous_week_snapshot())
    finally:
        db.close()


def _hints(results: dict[str, CollectorResult]) -> None:
    pending = [r for r in results.values() if r.status not in ("ok",)]
    if not pending:
        return
    print("\nמקורות שעדיין לא מחוברים:")
    for r in pending:
        print(f"  - {r.source}: {r.message}")
    if all(r.status == "not_configured" for r in results.values()):
        print("  טיפ: לצפייה בעיצוב עם נתוני דמה — weekly recap --demo")


def _status(settings) -> int:
    if not settings.db_path.is_file():
        print("עדיין לא בוצעה הפעלה בפרופיל הזה.")
        return 0
    db = Database(settings.db_path)
    try:
        for s in db.source_statuses():
            print(f"{s['source']:<10} {s['status']:<18} {s['last_success_at'] or '-':<20} {s['message']}")
        print("שרת:", "פועל" if launcher.server_alive(settings) else "כבוי")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
