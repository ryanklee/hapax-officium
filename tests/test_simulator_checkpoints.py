# ai-agents/tests/test_simulator_checkpoints.py
"""Tests for tiered checkpoint runner."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

from agents.simulator_pipeline.checkpoints import (
    run_deterministic_checkpoint,
    run_weekly_checkpoint,
    should_run_weekly_checkpoint,
)


class TestCheckpointScheduling:
    def test_weekly_on_friday(self):
        """Weekly checkpoint fires on Fridays."""
        # 2026-03-06 is a Friday
        assert should_run_weekly_checkpoint(date(2026, 3, 6)) is True

    def test_not_weekly_on_wednesday(self):
        """Weekly checkpoint doesn't fire on non-Fridays."""
        # 2026-03-04 is a Wednesday
        assert should_run_weekly_checkpoint(date(2026, 3, 4)) is False


class TestDeterministicCheckpoint:
    async def test_runs_cache_refresh(self):
        """Deterministic checkpoint refreshes caches."""
        with patch(
            "agents.simulator_pipeline.checkpoints._refresh_caches", new_callable=AsyncMock
        ) as mock_refresh:
            await run_deterministic_checkpoint()
            mock_refresh.assert_called_once()


class TestWeeklyCheckpoint:
    async def test_runs_synthesis_agents(self):
        """Weekly checkpoint runs briefing, snapshot, overview synthesis."""
        with (
            patch(
                "agents.simulator_pipeline.checkpoints._run_briefing", new_callable=AsyncMock
            ) as mock_brief,
            patch(
                "agents.simulator_pipeline.checkpoints._run_snapshot", new_callable=AsyncMock
            ) as mock_snap,
            patch(
                "agents.simulator_pipeline.checkpoints._run_profiler", new_callable=AsyncMock
            ) as mock_prof,
        ):
            await run_weekly_checkpoint()
            mock_brief.assert_called_once()
            mock_snap.assert_called_once()
            mock_prof.assert_called_once()
