"""Tests for post-simulation warm-up."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from agents.simulator_pipeline.warmup import run_warmup
from shared.config import config

if TYPE_CHECKING:
    from pathlib import Path


class TestRunWarmup:
    async def test_calls_all_agents_in_order(self, tmp_path: Path):
        """Warm-up calls all 5 agents sequentially."""
        with (
            patch("agents.simulator_pipeline.warmup._run_activity") as mock_act,
            patch(
                "agents.simulator_pipeline.warmup._run_profiler", new_callable=AsyncMock
            ) as mock_prof,
            patch(
                "agents.simulator_pipeline.warmup._run_briefing", new_callable=AsyncMock
            ) as mock_brief,
            patch(
                "agents.simulator_pipeline.warmup._run_digest", new_callable=AsyncMock
            ) as mock_digest,
            patch(
                "agents.simulator_pipeline.warmup._run_snapshot", new_callable=AsyncMock
            ) as mock_snap,
        ):
            await run_warmup(tmp_path)
            mock_act.assert_called_once()
            mock_prof.assert_called_once()
            mock_brief.assert_called_once()
            mock_digest.assert_called_once()
            mock_snap.assert_called_once()

    async def test_sets_and_resets_data_dir(self, tmp_path: Path):
        """Warm-up sets config.data_dir to sim_dir and resets after."""
        original = config.data_dir
        captured_dir = None

        async def capture_dir():
            nonlocal captured_dir
            captured_dir = config.data_dir

        with (
            patch("agents.simulator_pipeline.warmup._run_activity"),
            patch(
                "agents.simulator_pipeline.warmup._run_profiler",
                new_callable=AsyncMock,
                side_effect=capture_dir,
            ),
            patch("agents.simulator_pipeline.warmup._run_briefing", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.warmup._run_digest", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.warmup._run_snapshot", new_callable=AsyncMock),
        ):
            await run_warmup(tmp_path)

        assert captured_dir == tmp_path
        assert config.data_dir == original

    async def test_individual_failure_does_not_abort(self, tmp_path: Path):
        """If one agent fails, the rest still run."""
        with (
            patch(
                "agents.simulator_pipeline.warmup._run_activity",
                side_effect=RuntimeError("activity failed"),
            ),
            patch(
                "agents.simulator_pipeline.warmup._run_profiler", new_callable=AsyncMock
            ) as mock_prof,
            patch(
                "agents.simulator_pipeline.warmup._run_briefing", new_callable=AsyncMock
            ) as mock_brief,
            patch(
                "agents.simulator_pipeline.warmup._run_digest", new_callable=AsyncMock
            ) as mock_digest,
            patch(
                "agents.simulator_pipeline.warmup._run_snapshot", new_callable=AsyncMock
            ) as mock_snap,
        ):
            await run_warmup(tmp_path)
            # All subsequent agents still called despite activity failure
            mock_prof.assert_called_once()
            mock_brief.assert_called_once()
            mock_digest.assert_called_once()
            mock_snap.assert_called_once()
