"""Orchestration: collect → store → snapshot. Separate from presentation."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from .collectors.base import Collector, available
from .config import Settings
from .database.db import Database, week_start_for
from .models import CollectorResult
from .processing.report import build_report, snapshot_values


def default_sources(settings: Settings) -> list[str]:
    if settings.is_demo:
        return ["demo"]
    raw = settings.get("WR_SOURCES", "mashov,classroom,galim")
    return [s.strip() for s in raw.split(",") if s.strip() and s.strip() != "demo"]


def make_collector(settings: Settings, name: str, log: Callable[[str], None] = print,
                   **kw) -> Collector:
    registry = available()
    if name not in registry:
        raise SystemExit(f"מקור לא מוכר: {name}. מקורות זמינים: {', '.join(sorted(registry))}")
    return registry[name](settings, log=log, **kw)


def run_recap(settings: Settings, collectors: list[Collector], *,
              now: datetime | None = None, log: Callable[[str], None] = print,
              on_result: Callable[[Collector, CollectorResult], CollectorResult] | None = None,
              ) -> tuple[dict, dict[str, CollectorResult]]:
    """Run all collectors once, store results, update this week's snapshot, return the report."""
    settings.ensure_dirs()
    now = now or datetime.now()
    lookback = int(settings.get("WR_LOOKBACK_DAYS", "14") or 14)
    db = Database(settings.db_path)
    try:
        run_id = db.start_run(now)
        # Messages reported in a previous run are not shown again.
        db.mark_shown_messages(before_run=run_id, now=now)
        results: dict[str, CollectorResult] = {}
        summary: dict[str, dict] = {}
        for col in collectors:
            log(f"• {col.display_name}: אוסף נתונים...")
            res = col.run()
            if on_result:
                res = on_result(col, res)
            results[col.name] = res
            db.record_source(res, now=now)
            stats = db.ingest(run_id, res, now=now, lookback_days=lookback)
            summary[col.name] = {"status": res.status, "message": res.message, **stats}
            icon = "✅" if res.status == "ok" else ("⚪" if res.status == "not_configured" else "⚠️")
            log(f"  {icon} {res.message or res.status}")
        db.finish_run(run_id, summary, now=now)

        report = build_report(db, now=now, is_demo=settings.is_demo, profile=settings.profile)
        behavior_ok = any(r.status == "ok" and r.provides_behavior for r in results.values())
        tasks_ok = any(r.status == "ok" and (r.tasks or r.complete_task_list)
                       for r in results.values())
        db.save_snapshot(week_start_for(now.date()).isoformat(), run_id,
                         snapshot_values(report, behavior_ok, tasks_ok), now=now)
        report = build_report(db, now=now, is_demo=settings.is_demo, profile=settings.profile)
        return report, results
    finally:
        db.close()
