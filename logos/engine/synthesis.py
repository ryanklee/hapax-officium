"""Synthesis scheduler — auto-triggers LLM synthesis after management data changes.

Accumulates filesystem change signals, waits for a quiet window,
then submits synthesis ActionPlans to the executor.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from logos.engine.models import Action, ActionPlan, DeliveryItem

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from logos.engine.delivery import DeliveryQueue
    from logos.engine.executor import PhasedExecutor

_log = logging.getLogger(__name__)

# ── Path classification ──────────────────────────────────────────────

HOT_PATH = frozenset({"people", "coaching", "feedback"})
WARM_PATH = frozenset(
    {"meetings", "okrs", "goals", "incidents", "postmortem-actions", "review-cycles"}
)
SYNTHESIS_RELEVANT = HOT_PATH | WARM_PATH

# Reschedule delay when suppressed (seconds)
_SUPPRESSION_DELAY = 60.0


# ── Synthesis handlers ───────────────────────────────────────────────


async def _synthesize_briefing() -> str:
    from agents.management_briefing import format_briefing_md, generate_briefing
    from shared.config import PROFILES_DIR
    from shared.vault_writer import write_briefing_to_vault

    briefing = await generate_briefing()
    md = format_briefing_md(briefing)
    write_briefing_to_vault(md)
    (PROFILES_DIR / "management-briefing.json").write_text(briefing.model_dump_json(indent=2))
    return f"briefing: {briefing.headline}"


async def _synthesize_snapshot() -> str:
    from agents.management_prep import format_snapshot_md, generate_team_snapshot
    from shared.vault_writer import write_team_snapshot_to_vault

    snapshot = await generate_team_snapshot()
    write_team_snapshot_to_vault(format_snapshot_md(snapshot))
    return f"snapshot: {snapshot.headline}"


async def _synthesize_overview() -> str:
    from agents.management_prep import format_overview_md, generate_overview
    from shared.vault_writer import write_management_overview_to_vault

    overview = await generate_overview()
    write_management_overview_to_vault(format_overview_md(overview))
    return f"overview: {overview.headline}"


async def _synthesize_profile_light() -> str:
    from agents.management_profiler import (
        build_profile,
        generate_and_load_management_facts,
        load_existing_profile,
        save_profile,
        synthesize_profile,
    )

    facts = generate_and_load_management_facts()
    existing = load_existing_profile()
    synthesis = await synthesize_profile(facts)
    sources = (existing.sources_processed if existing else []) + ["management-bridge"]
    profile = build_profile(facts, synthesis, sorted(set(sources)), existing)
    save_profile(profile)
    return f"profile v{profile.version}: {len(facts)} facts"


# ── Scheduler ────────────────────────────────────────────────────────


class SynthesisScheduler:
    """Accumulate change signals, wait for quiet, trigger LLM synthesis."""

    def __init__(
        self,
        executor: PhasedExecutor,
        delivery: DeliveryQueue,
        agent_run_manager: object,
        ignore_fn: Callable[[Path], None] | None = None,
        quiet_window_s: float | None = None,
        profiler_interval_s: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._executor = executor
        self._delivery = delivery
        self._arm = agent_run_manager
        self._ignore_fn = ignore_fn

        if quiet_window_s is None:
            quiet_window_s = float(os.environ.get("ENGINE_SYNTHESIS_QUIET_S", "180"))
        if profiler_interval_s is None:
            profiler_interval_s = float(os.environ.get("ENGINE_PROFILER_INTERVAL_S", "86400"))
        if enabled is None:
            enabled = os.environ.get("ENGINE_SYNTHESIS_ENABLED", "true").lower() in (
                "true",
                "1",
                "yes",
            )

        self._quiet_window_s = quiet_window_s
        self._profiler_interval_s = profiler_interval_s
        self._enabled = enabled

        # Mutable state
        self._dirty: set[str] = set()
        self._timer: asyncio.TimerHandle | None = None
        self._last_synthesis_at: float = 0.0
        self._profiler_dirty: bool = False
        self._last_profiler_at: float = 0.0
        self._running_synthesis: bool = False
        self._profiler_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the profiler check loop."""
        if not self._enabled:
            _log.info("SynthesisScheduler disabled")
            return

        # Initialize profiler timestamp from existing profile if available
        self._last_profiler_at = self._load_profiler_timestamp()

        self._profiler_task = asyncio.create_task(self._profiler_loop())
        _log.info("SynthesisScheduler started (quiet=%ss)", self._quiet_window_s)

    async def stop(self) -> None:
        """Stop the scheduler, cancelling pending work."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._profiler_task is not None:
            self._profiler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._profiler_task
            self._profiler_task = None
        _log.info("SynthesisScheduler stopped (dirty lost: %s)", self._dirty)

    def signal(self, subdirectory: str) -> None:
        """Receive a change signal from the engine."""
        if not self._enabled:
            return
        if subdirectory not in SYNTHESIS_RELEVANT:
            return

        self._dirty.add(subdirectory)
        self._profiler_dirty = True

        # Reset quiet-window timer
        if self._timer is not None:
            self._timer.cancel()
        loop = asyncio.get_running_loop()
        self._timer = loop.call_later(self._quiet_window_s, self._schedule_synthesis)

    async def force(self) -> None:
        """Force immediate synthesis, bypassing quiet window."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        await self._on_quiet_window()

    def status(self) -> dict:
        """Return scheduler status for API consumption."""
        return {
            "enabled": self._enabled,
            "dirty": sorted(self._dirty),
            "quiet_window_s": self._quiet_window_s,
            "timer_active": self._timer is not None,
            "last_synthesis_at": (
                datetime.fromtimestamp(
                    time.time() - (time.monotonic() - self._last_synthesis_at),
                    tz=UTC,
                ).isoformat()
                if self._last_synthesis_at > 0
                else None
            ),
            "last_profiler_at": (
                datetime.fromtimestamp(
                    time.time() - (time.monotonic() - self._last_profiler_at),
                    tz=UTC,
                ).isoformat()
                if self._last_profiler_at > 0
                else None
            ),
            "profiler_dirty": self._profiler_dirty,
        }

    # ── Internal ─────────────────────────────────────────────────────

    def _schedule_synthesis(self) -> None:
        """Called by the event loop when the quiet window expires."""
        self._timer = None
        asyncio.ensure_future(self._on_quiet_window())

    async def _on_quiet_window(self) -> None:
        """Execute reactive synthesis if conditions are met."""
        if self._running_synthesis:
            _log.info("Synthesis already running, rescheduling")
            self._reschedule(_SUPPRESSION_DELAY)
            return

        if getattr(self._arm, "is_running", False):
            _log.info("Manual agent running, rescheduling synthesis")
            self._reschedule(_SUPPRESSION_DELAY)
            return

        self._running_synthesis = True
        try:
            snapshot = frozenset(self._dirty)
            self._dirty.clear()

            if snapshot & HOT_PATH:
                await self._run_reactive_synthesis(snapshot)
        finally:
            self._running_synthesis = False

    async def _run_reactive_synthesis(self, snapshot: frozenset[str]) -> None:
        """Build and execute the reactive synthesis plan."""
        plan = ActionPlan(
            created_at=datetime.now(UTC),
            trigger=None,
            actions=[
                Action(
                    name="synthesize_briefing",
                    handler=_synthesize_briefing,
                    phase=1,
                    priority=0,
                ),
                Action(
                    name="synthesize_snapshot",
                    handler=_synthesize_snapshot,
                    phase=1,
                    priority=1,
                ),
                Action(
                    name="synthesize_overview",
                    handler=_synthesize_overview,
                    phase=1,
                    priority=2,
                ),
            ],
        )

        try:
            await self._executor.execute(plan)
        except Exception:
            _log.exception("Synthesis executor failed")
            self._dirty |= HOT_PATH
            return

        # Check for individual action failures
        reactive_names = {"synthesize_briefing", "synthesize_snapshot", "synthesize_overview"}
        if any(name in plan.errors for name in reactive_names):
            _log.warning("Synthesis partial failure: %s", plan.errors)
            self._dirty |= HOT_PATH

        # Enqueue delivery items
        now = datetime.now(UTC)
        for name, result in plan.results.items():
            self._delivery.enqueue(
                DeliveryItem(
                    title=name,
                    detail=str(result),
                    priority="medium",
                    category="generated",
                    source_action=name,
                    timestamp=now,
                )
            )
        for name, error in plan.errors.items():
            self._delivery.enqueue(
                DeliveryItem(
                    title=f"{name} failed",
                    detail=error,
                    priority="high",
                    category="error",
                    source_action=name,
                    timestamp=now,
                )
            )

        # Refresh cache so API serves fresh artifacts
        try:
            from logos.api.cache import cache

            await cache.refresh()
        except Exception:
            _log.exception("Post-synthesis cache refresh failed")

        self._last_synthesis_at = time.monotonic()
        _log.info("Reactive synthesis complete: %s", list(plan.results.keys()))

    def _reschedule(self, delay: float) -> None:
        """Reschedule the quiet-window timer."""
        if self._timer is not None:
            self._timer.cancel()
        loop = asyncio.get_running_loop()
        self._timer = loop.call_later(delay, self._schedule_synthesis)

    async def _profiler_loop(self) -> None:
        """Hourly check for profiler synthesis trigger."""
        # Wait 1 hour before first check (not immediately on startup)
        await asyncio.sleep(3600)

        while True:
            try:
                await self._check_profiler()
            except asyncio.CancelledError:
                raise
            except Exception:
                _log.exception("Profiler check failed")
            await asyncio.sleep(3600)

    async def _check_profiler(self) -> None:
        """Run profiler if dirty and interval elapsed."""
        if not self._profiler_dirty:
            return
        if (time.monotonic() - self._last_profiler_at) < self._profiler_interval_s:
            return
        if self._running_synthesis:
            return
        if getattr(self._arm, "is_running", False):
            return

        self._running_synthesis = True
        try:
            plan = ActionPlan(
                created_at=datetime.now(UTC),
                trigger=None,
                actions=[
                    Action(
                        name="synthesize_profile",
                        handler=_synthesize_profile_light,
                        phase=1,
                        priority=0,
                    ),
                ],
            )
            await self._executor.execute(plan)

            if "synthesize_profile" not in plan.errors:
                self._profiler_dirty = False
                self._last_profiler_at = time.monotonic()

            now = datetime.now(UTC)
            for name, result in plan.results.items():
                self._delivery.enqueue(
                    DeliveryItem(
                        title=name,
                        detail=str(result),
                        priority="medium",
                        category="generated",
                        source_action=name,
                        timestamp=now,
                    )
                )
        except Exception:
            _log.exception("Profiler synthesis failed")
        finally:
            self._running_synthesis = False

    def _load_profiler_timestamp(self) -> float:
        """Load last profiler run time from existing profile file."""
        try:
            import json

            from shared.config import PROFILES_DIR

            profile_path = PROFILES_DIR / "management-profile.json"
            if profile_path.is_file():
                data = json.loads(profile_path.read_text())
                updated = data.get("updated_at")
                if updated:
                    dt = datetime.fromisoformat(updated)
                    # Convert to monotonic-compatible offset
                    age = (datetime.now(UTC) - dt).total_seconds()
                    return max(0.0, time.monotonic() - age)
        except Exception:
            _log.debug("Could not load profiler timestamp, starting fresh")
        return 0.0
