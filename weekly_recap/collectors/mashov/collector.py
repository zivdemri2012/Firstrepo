"""משוב (Mashov) — behavior, attendance, important messages, new grades.

Status: infrastructure ready; the parser is written only after a calibration
capture from the real account (see ``BrowserSiteCollector``), so no field names
or URLs are guessed. What will be kept (and nothing else):

* behavior: absences, lates, positive reinforcements (ח"ח), events/notes
* messages: homework, trips, activities, teacher announcements
* grades: only newly entered grades
"""
from __future__ import annotations

from ..base import register
from ..browser_site import BrowserSiteCollector


@register
class MashovCollector(BrowserSiteCollector):
    name = "mashov"
    display_name = "משוב"
    env_prefix = "MASHOV"
    provides_behavior = True
