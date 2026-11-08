"""ClassIt — משימות במתמטיקה (יחידות עבודה): משימות פתוחות, שהוגשו, מועדי הגשה.

The parser is written after a calibration capture from the real account
(``weekly recap --capture classit``), so the structure is not guessed.
"""
from __future__ import annotations

from ..base import register
from ..browser_site import BrowserSiteCollector


@register
class ClassitCollector(BrowserSiteCollector):
    name = "classit"
    display_name = "ClassIt (מתמטיקה)"
    env_prefix = "CLASSIT"
