"""Background data cache for the logos API.

Refreshes management data collectors on a 5-minute interval.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("logos.api")


@dataclass
class DataCache:
    """In-memory cache for management data collector results."""

    management: Any = None
    briefing: dict | None = None
    nudges: list = field(default_factory=list)
    goals: Any = None
    agents: list = field(default_factory=list)
    team_health: Any = None
    okrs: Any = None
    smart_goals: Any = None
    incidents: Any = None
    postmortem_actions: Any = None
    review_cycles: Any = None
    status_reports: Any = None

    _refreshed_at: float = 0.0
    _last_hot_change_at: float = 0.0
    _last_warm_change_at: float = 0.0

    def cache_age(self) -> int:
        """Seconds since last refresh, or -1 if never refreshed."""
        if self._refreshed_at == 0.0:
            return -1
        return int(time.monotonic() - self._refreshed_at)

    def record_hot_change(self) -> None:
        """Record that a hot-path data change occurred now."""
        self._last_hot_change_at = time.monotonic()

    def record_warm_change(self) -> None:
        """Record that a warm-path data change occurred now."""
        self._last_warm_change_at = time.monotonic()

    def hot_change_age(self) -> int:
        """Seconds since last hot-path change, or -1 if none."""
        if self._last_hot_change_at == 0.0:
            return -1
        return int(time.monotonic() - self._last_hot_change_at)

    def warm_change_age(self) -> int:
        """Seconds since last warm-path change, or -1 if none."""
        if self._last_warm_change_at == 0.0:
            return -1
        return int(time.monotonic() - self._last_warm_change_at)

    async def refresh(self) -> None:
        """Refresh all management data collectors."""
        await asyncio.to_thread(self._refresh_sync)
        self._refreshed_at = time.monotonic()

    def _refresh_sync(self) -> None:
        """Synchronous data collection (runs in thread pool).

        Computes the management snapshot once and threads it through
        team_health and nudges to avoid redundant DATA_DIR scans.
        """
        import json as _json

        from logos.data.agents import get_agent_registry
        from logos.data.goals import collect_goals
        from logos.data.management import collect_management_state
        from logos.data.nudges import collect_nudges
        from logos.data.team_health import collect_team_health
        from shared.config import PROFILES_DIR

        # Load latest briefing JSON (written by management_briefing --save)
        briefing_json = PROFILES_DIR / "management-briefing.json"
        try:
            if briefing_json.is_file():
                self.briefing = _json.loads(briefing_json.read_text())
        except Exception as e:
            log.warning("Refresh briefing failed: %s", e)

        # Compute management snapshot once — shared by team_health and nudges
        snapshot = None
        try:
            snapshot = collect_management_state()
            self.management = snapshot
        except Exception as e:
            log.warning("Refresh management failed: %s", e)

        for name, fn in [
            ("goals", collect_goals),
            ("agents", get_agent_registry),
        ]:
            try:
                setattr(self, name, fn())
            except Exception as e:
                log.warning("Refresh %s failed: %s", name, e)

        try:
            self.team_health = collect_team_health(snapshot=snapshot)
        except Exception as e:
            log.warning("Refresh team_health failed: %s", e)

        # New Tier 1 collectors
        for name, import_path, fn_name in [
            ("okrs", "logos.data.okrs", "collect_okr_state"),
            ("smart_goals", "logos.data.smart_goals", "collect_smart_goal_state"),
            ("incidents", "logos.data.incidents", "collect_incident_state"),
            (
                "postmortem_actions",
                "logos.data.postmortem_actions",
                "collect_postmortem_action_state",
            ),
            ("review_cycles", "logos.data.review_cycles", "collect_review_cycle_state"),
            ("status_reports", "logos.data.status_reports", "collect_status_report_state"),
        ]:
            try:
                import importlib

                mod = importlib.import_module(import_path)
                setattr(self, name, getattr(mod, fn_name)())
            except Exception as e:
                log.warning("Refresh %s failed: %s", name, e)

        try:
            self.nudges = collect_nudges(snapshot=snapshot)
        except Exception as e:
            log.warning("Nudge collection error: %s", e)


# Singleton cache instance
cache = DataCache()

REFRESH_INTERVAL = 300  # seconds

_background_tasks: set[asyncio.Task] = set()


async def start_refresh_loop() -> None:
    """Start background refresh task. Called from FastAPI lifespan."""
    await cache.refresh()

    async def _loop():
        while True:
            await asyncio.sleep(REFRESH_INTERVAL)
            await cache.refresh()

    task = asyncio.create_task(_loop())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
