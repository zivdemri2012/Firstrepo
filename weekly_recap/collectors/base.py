"""Collector interface + registry.

Adding a new website = adding a module with a ``Collector`` subclass decorated
with ``@register``, and listing it in ``WR_SOURCES`` in ``.env``.
Collectors are strictly read-only: they never submit, edit or send anything.
"""
from __future__ import annotations

import abc
import traceback
from typing import Callable

from ..config import Settings
from ..models import CollectorResult

_REGISTRY: dict[str, type["Collector"]] = {}


def register(cls: type["Collector"]) -> type["Collector"]:
    _REGISTRY[cls.name] = cls
    return cls


def available() -> dict[str, type["Collector"]]:
    # Import side effect: modules register themselves.
    from . import cet, classit, classroom, demo, mashov  # noqa: F401
    return dict(_REGISTRY)


class Collector(abc.ABC):
    #: Stable identifier, used in the DB and in ``WR_SOURCES``.
    name: str = ""
    #: Hebrew display name for the dashboard.
    display_name: str = ""
    #: Whether the source can provide behavior/attendance data.
    provides_behavior: bool = False

    def __init__(self, settings: Settings, log: Callable[[str], None] = print):
        self.settings = settings
        self.log = log

    # -- lifecycle -------------------------------------------------------
    @abc.abstractmethod
    def is_configured(self) -> tuple[bool, str]:
        """Return (configured, Hebrew explanation if not)."""

    @abc.abstractmethod
    def collect(self) -> CollectorResult:
        """Fetch data. May raise NeedsLogin / NeedsCalibration."""

    def login(self) -> None:
        """Interactive manual login (opens a browser window). Optional."""
        raise NotImplementedError(f"{self.name} does not support interactive login")

    # -- helpers ---------------------------------------------------------
    def result(self, status: str, message: str = "", **kw) -> CollectorResult:
        return CollectorResult(source=self.name, status=status, message=message,
                               provides_behavior=self.provides_behavior, **kw)

    def run(self) -> CollectorResult:
        ok, why = self.is_configured()
        if not ok:
            return self.result("not_configured", why)
        try:
            return self.collect()
        except NeedsLogin as e:
            return self.result("needs_login", str(e) or "נדרשת התחברות ידנית")
        except NeedsCalibration as e:
            return self.result("needs_calibration", str(e))
        except Exception as e:  # never let one source break the whole recap
            self.log(traceback.format_exc())
            return self.result("error", f"{type(e).__name__}: {e}")


class NeedsLogin(Exception):
    """The saved session is missing/expired; the user must log in manually."""


class NeedsCalibration(Exception):
    """Logged in, but the parser for this site was not yet built from real pages."""
