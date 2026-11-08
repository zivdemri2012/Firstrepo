"""מט"ח (CET) — קורס לשון והבעה: משימות, מטלות שלא הושלמו, מועדי הגשה.

The course contains two subjects — לשון and הבעה — so every task is tagged with
the right subject. The parser is written after a calibration capture from the
real account (``weekly recap --capture cet``), so the structure is not guessed.
"""
from __future__ import annotations

from ..base import register
from ..browser_site import BrowserSiteCollector


@register
class CetCollector(BrowserSiteCollector):
    name = "cet"
    display_name = "לשון והבעה (מט\"ח)"
    env_prefix = "CET"
    subjects = ("לשון", "הבעה")
