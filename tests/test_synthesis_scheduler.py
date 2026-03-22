"""Tests for logos/engine/synthesis.py — SynthesisScheduler."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from logos.engine.synthesis import (
    HOT_PATH,
    SynthesisScheduler,
)


def _make_scheduler(
    *,
    agent_running: bool = False,
    quiet_window_s: float = 0.05,
    profiler_interval_s: float = 86400,
    enabled: bool = True,
) -> tuple[SynthesisScheduler, AsyncMock]:
    """Create a scheduler with mocked dependencies."""
    executor = AsyncMock()
    delivery = MagicMock()
    delivery.enqueue = MagicMock()
    arm = MagicMock()
    arm.is_running = agent_running

    scheduler = SynthesisScheduler(
        executor=executor,
        delivery=delivery,
        agent_run_manager=arm,
        quiet_window_s=quiet_window_s,
        profiler_interval_s=profiler_interval_s,
        enabled=enabled,
    )
    return scheduler, executor


class TestSignal:
    def test_irrelevant_subdirectory(self):
        """decisions/, status-reports/, references/, 1on1-prep/ don't affect dirty set."""
        scheduler, _ = _make_scheduler()
        for subdir in (
            "decisions",
            "status-reports",
            "references",
            "1on1-prep",
            "inbox",
            "processed",
        ):
            scheduler.signal(subdir)
        assert len(scheduler._dirty) == 0
        assert scheduler._profiler_dirty is False

    async def test_hot_path_sets_dirty(self):
        """people/ adds to dirty set and sets profiler dirty."""
        scheduler, _ = _make_scheduler()
        scheduler.signal("people")
        assert "people" in scheduler._dirty
        assert scheduler._profiler_dirty is True
        # Cleanup timer
        if scheduler._timer:
            scheduler._timer.cancel()

    async def test_warm_path_sets_profiler_dirty(self):
        """meetings/ sets profiler dirty but doesn't add to hot-path-triggering dirty."""
        scheduler, _ = _make_scheduler()
        scheduler.signal("meetings")
        assert "meetings" in scheduler._dirty
        assert scheduler._profiler_dirty is True
        # Cleanup timer
        if scheduler._timer:
            scheduler._timer.cancel()


class TestQuietWindow:
    async def test_timer_resets_on_signal(self):
        """Second signal cancels and reschedules timer."""
        scheduler, _ = _make_scheduler(quiet_window_s=10.0)

        scheduler.signal("people")
        first_timer = scheduler._timer
        assert first_timer is not None

        scheduler.signal("coaching")
        second_timer = scheduler._timer
        assert second_timer is not first_timer
        assert {"people", "coaching"} <= scheduler._dirty

        # Cleanup
        if scheduler._timer:
            scheduler._timer.cancel()

    async def test_synthesis_fires_after_quiet_window(self):
        """Handlers called after timer expires."""
        scheduler, executor = _make_scheduler(quiet_window_s=0.05)

        with (
            patch("logos.engine.synthesis._synthesize_briefing", new_callable=AsyncMock),
            patch("logos.engine.synthesis._synthesize_snapshot", new_callable=AsyncMock),
            patch("logos.engine.synthesis._synthesize_overview", new_callable=AsyncMock),
            patch("logos.api.cache.cache") as mock_cache,
        ):
            mock_cache.refresh = AsyncMock()

            scheduler.signal("people")
            # Wait for quiet window + execution
            await asyncio.sleep(0.1)

            assert executor.execute.called
            plan = executor.execute.call_args[0][0]
            action_names = {a.name for a in plan.actions}
            assert "synthesize_briefing" in action_names
            assert "synthesize_snapshot" in action_names
            assert "synthesize_overview" in action_names
            assert plan.trigger is None


class TestSuppression:
    async def test_suppressed_when_agent_running(self):
        """Reschedules 60s when manual agent active."""
        scheduler, executor = _make_scheduler(agent_running=True, quiet_window_s=0.05)

        scheduler.signal("people")
        await asyncio.sleep(0.2)

        # Should not have fired — agent is running
        assert not executor.execute.called
        # Timer should have been rescheduled
        assert scheduler._timer is not None

        # Cleanup
        if scheduler._timer:
            scheduler._timer.cancel()

    async def test_suppressed_when_synthesis_running(self):
        """Re-entrant guard prevents concurrent synthesis."""
        scheduler, executor = _make_scheduler(quiet_window_s=0.05)
        scheduler._running_synthesis = True

        scheduler.signal("people")
        await asyncio.sleep(0.2)

        assert not executor.execute.called

        # Cleanup
        scheduler._running_synthesis = False
        if scheduler._timer:
            scheduler._timer.cancel()


class TestFailure:
    async def test_dirty_preserved_on_failure(self):
        """Dirty set restored when executor raises."""
        scheduler, executor = _make_scheduler(quiet_window_s=0.05)
        executor.execute = AsyncMock(side_effect=Exception("LLM down"))

        with patch("logos.api.cache.cache") as mock_cache:
            mock_cache.refresh = AsyncMock()
            scheduler.signal("people")
            await asyncio.sleep(0.1)

        # Dirty should be restored after failure
        assert scheduler._dirty & HOT_PATH


class TestForce:
    async def test_force_bypasses_quiet_window(self):
        """force() triggers immediate synthesis."""
        scheduler, executor = _make_scheduler(quiet_window_s=999)

        with patch("logos.api.cache.cache") as mock_cache:
            mock_cache.refresh = AsyncMock()
            scheduler.signal("people")
            await scheduler.force()

        assert executor.execute.called
        assert scheduler._timer is None


class TestDisabled:
    def test_signal_noop_when_disabled(self):
        """signal() is a no-op when scheduler is disabled."""
        scheduler, _ = _make_scheduler(enabled=False)
        scheduler.signal("people")
        assert len(scheduler._dirty) == 0
        assert scheduler._timer is None


class TestProfiler:
    async def test_profiler_skipped_within_24h(self):
        """Recent profiler timestamp prevents re-run."""
        scheduler, executor = _make_scheduler(quiet_window_s=0.05)
        scheduler._profiler_dirty = True
        scheduler._last_profiler_at = time.monotonic()  # just ran

        await scheduler._check_profiler()
        assert not executor.execute.called

    async def test_profiler_fires_when_stale_and_dirty(self):
        """Old timestamp + dirty flag triggers profiler."""
        scheduler, executor = _make_scheduler(
            quiet_window_s=0.05,
            profiler_interval_s=0,  # no minimum interval
        )
        scheduler._profiler_dirty = True
        scheduler._last_profiler_at = 0.0  # never ran

        await scheduler._check_profiler()
        assert executor.execute.called
        plan = executor.execute.call_args[0][0]
        assert any(a.name == "synthesize_profile" for a in plan.actions)


class TestStop:
    async def test_stop_cancels_pending_timer(self):
        """stop() cancels timer and profiler loop."""
        scheduler, _ = _make_scheduler(quiet_window_s=999)
        scheduler.signal("people")
        assert scheduler._timer is not None

        # Simulate profiler task
        scheduler._profiler_task = asyncio.create_task(asyncio.sleep(999))

        await scheduler.stop()
        assert scheduler._timer is None
        assert scheduler._profiler_task is None


class TestStatus:
    async def test_status_returns_scheduler_state(self):
        """Status dict has correct shape."""
        scheduler, _ = _make_scheduler()
        scheduler.signal("people")

        status = scheduler.status()
        assert "enabled" in status
        assert "dirty" in status
        assert "people" in status["dirty"]
        assert "quiet_window_s" in status
        assert "timer_active" in status
        assert "profiler_dirty" in status
        assert status["profiler_dirty"] is True

        # Cleanup
        if scheduler._timer:
            scheduler._timer.cancel()
