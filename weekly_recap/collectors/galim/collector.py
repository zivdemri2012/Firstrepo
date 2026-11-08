"""גלים פרו (Galim Pro) — assignments/exercises, incomplete work, due dates.

Status: infrastructure ready; the parser is written after a calibration capture
from the real account, so the site's structure is not guessed.
"""
from __future__ import annotations

from ..base import register
from ..browser_site import BrowserSiteCollector


@register
class GalimCollector(BrowserSiteCollector):
    name = "galim"
    display_name = "גלים פרו"
    env_prefix = "GALIM"
