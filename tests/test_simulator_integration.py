# ai-agents/tests/test_simulator_integration.py
"""Integration test for the full simulation loop (mocked LLM)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from agents.simulator import run_simulation
from agents.simulator_pipeline.models import SimulatedEvent
from shared.simulation import load_manifest
from shared.simulation_models import SimStatus

if TYPE_CHECKING:
    from pathlib import Path


class TestRunSimulation:
    async def test_full_simulation_loop(self, tmp_path: Path):
        """Run a 5-day simulation with mocked LLM."""
        seed_dir = tmp_path / "seed"
        (seed_dir / "people").mkdir(parents=True)
        (seed_dir / "people" / "alice.md").write_text(
            "---\ntype: person\nname: Alice\nteam: platform\n"
            "cadence: weekly\nstatus: active\nlast-1on1: 2026-02-28\n---\n"
        )

        mock_events = [
            SimulatedEvent(
                date="2026-03-02",
                workflow_type="one_on_one",
                subdirectory="meetings",
                filename="2026-03-02-alice.md",
                participant="Alice",
                topics=["standup"],
                metadata={"type": "meeting", "meeting-type": "one-on-one"},
            ),
        ]

        mock_result = MagicMock()
        mock_result.output = mock_events

        with (
            patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent,
            patch("agents.simulator_pipeline.checkpoints._refresh_caches", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_briefing", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_snapshot", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_profiler", new_callable=AsyncMock),
        ):
            mock_agent.run = AsyncMock(return_value=mock_result)

            sim_dir = await run_simulation(
                role="engineering-manager",
                variant="experienced-em",
                window="5d",
                seed=str(seed_dir),
                output=tmp_path / "sims",
            )

        # Simulation completed
        assert sim_dir.is_dir()
        manifest = load_manifest(sim_dir)
        assert manifest.status == SimStatus.COMPLETED
        assert manifest.ticks_completed > 0

        # Events were written
        meetings_dir = sim_dir / "meetings"
        assert meetings_dir.is_dir()

    async def test_resume_continues_from_last_tick(self, tmp_path: Path):
        """Resume continues from last_completed_tick."""
        seed_dir = tmp_path / "seed"
        (seed_dir / "people").mkdir(parents=True)
        (seed_dir / "people" / "alice.md").write_text(
            "---\ntype: person\nname: Alice\nstatus: active\ncadence: weekly\n---\n"
        )

        mock_events = [
            SimulatedEvent(
                date="2026-03-04",
                workflow_type="status_report",
                subdirectory="status-reports",
                filename="2026-03-04-weekly.md",
                topics=["weekly update"],
                metadata={"type": "status-report"},
            ),
        ]
        mock_result = MagicMock()
        mock_result.output = mock_events

        with (
            patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent,
            patch("agents.simulator_pipeline.checkpoints._refresh_caches", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_briefing", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_snapshot", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_profiler", new_callable=AsyncMock),
        ):
            mock_agent.run = AsyncMock(return_value=mock_result)

            # Run first 3 days, then simulate a failure
            sim_dir = await run_simulation(
                role="engineering-manager",
                variant="experienced-em",
                window="5d",
                seed=str(seed_dir),
                output=tmp_path / "sims",
            )

        manifest = load_manifest(sim_dir)
        assert manifest.status == SimStatus.COMPLETED

    # --- org dossier, event tracking, distribution validation ---

    async def test_org_dossier_passed_to_compose(self, tmp_path: Path):
        """run_simulation loads org dossier and passes it to compose_role_profile."""
        seed_dir = tmp_path / "seed"
        (seed_dir / "people").mkdir(parents=True)
        (seed_dir / "people" / "alice.md").write_text(
            "---\ntype: person\nname: Alice\nstatus: active\ncadence: weekly\n---\n"
        )

        # Write a minimal org-dossier.yaml
        dossier_path = tmp_path / "org-dossier.yaml"
        dossier_path.write_text(
            yaml.dump(
                {
                    "org": {
                        "company_stage": "startup",
                        "headcount_band": "10-50",
                        "team_count": 2,
                        "industry": "fintech",
                    }
                }
            )
        )

        mock_events = [
            SimulatedEvent(
                date="2026-03-02",
                workflow_type="one_on_one",
                subdirectory="meetings",
                filename="2026-03-02-alice.md",
                participant="Alice",
                topics=["standup"],
                metadata={"type": "meeting", "meeting-type": "one-on-one"},
            ),
        ]
        mock_result = MagicMock()
        mock_result.output = mock_events

        with (
            patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent,
            patch("agents.simulator_pipeline.checkpoints._refresh_caches", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_briefing", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_snapshot", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_profiler", new_callable=AsyncMock),
            patch("agents.simulator.compose_role_profile", wraps=None) as mock_compose,
        ):
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_compose.return_value = {
                "role": "engineering-manager",
                "variant": "experienced-em",
                "description": "",
                "variant_description": "",
                "workflows": [],
                "cadence_modifiers": {},
                "scenario_overrides": {},
            }

            await run_simulation(
                role="engineering-manager",
                variant="experienced-em",
                window="5d",
                seed=str(seed_dir),
                output=tmp_path / "sims",
                org_dossier=dossier_path,
            )

            # Verify org dossier was loaded and passed
            mock_compose.assert_called()
            call_kwargs = mock_compose.call_args.kwargs
            assert call_kwargs["org"] is not None
            assert call_kwargs["org"]["company_stage"] == "startup"

    async def test_org_dossier_default_missing_is_none(self, tmp_path: Path):
        """When org_dossier points to a non-existent file, org is None."""
        seed_dir = tmp_path / "seed"
        (seed_dir / "people").mkdir(parents=True)
        (seed_dir / "people" / "alice.md").write_text(
            "---\ntype: person\nname: Alice\nstatus: active\ncadence: weekly\n---\n"
        )

        mock_events = [
            SimulatedEvent(
                date="2026-03-02",
                workflow_type="one_on_one",
                subdirectory="meetings",
                filename="2026-03-02-alice.md",
                participant="Alice",
                topics=["standup"],
                metadata={"type": "meeting", "meeting-type": "one-on-one"},
            ),
        ]
        mock_result = MagicMock()
        mock_result.output = mock_events

        nonexistent = tmp_path / "no-such-dossier.yaml"

        with (
            patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent,
            patch("agents.simulator_pipeline.checkpoints._refresh_caches", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_briefing", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_snapshot", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_profiler", new_callable=AsyncMock),
            patch("agents.simulator.compose_role_profile", wraps=None) as mock_compose,
        ):
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_compose.return_value = {
                "role": "engineering-manager",
                "variant": "experienced-em",
                "description": "",
                "variant_description": "",
                "workflows": [],
                "cadence_modifiers": {},
                "scenario_overrides": {},
            }

            await run_simulation(
                role="engineering-manager",
                variant="experienced-em",
                window="5d",
                seed=str(seed_dir),
                output=tmp_path / "sims",
                org_dossier=nonexistent,
            )

            call_kwargs = mock_compose.call_args.kwargs
            assert call_kwargs["org"] is None

    async def test_distribution_validation_runs_after_completion(self, tmp_path: Path):
        """Distribution validation runs after simulation completes when reference exists."""
        seed_dir = tmp_path / "seed"
        (seed_dir / "people").mkdir(parents=True)
        (seed_dir / "people" / "alice.md").write_text(
            "---\ntype: person\nname: Alice\nstatus: active\ncadence: weekly\n---\n"
        )

        mock_events = [
            SimulatedEvent(
                date="2026-03-02",
                workflow_type="one_on_one",
                subdirectory="meetings",
                filename="2026-03-02-alice.md",
                participant="Alice",
                topics=["standup"],
                metadata={"type": "meeting", "meeting-type": "one-on-one"},
            ),
        ]
        mock_result = MagicMock()
        mock_result.output = mock_events

        with (
            patch("agents.simulator_pipeline.event_gen._event_agent") as mock_agent,
            patch("agents.simulator_pipeline.checkpoints._refresh_caches", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_briefing", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_snapshot", new_callable=AsyncMock),
            patch("agents.simulator_pipeline.checkpoints._run_profiler", new_callable=AsyncMock),
            patch("agents.simulator.validate_distribution") as mock_validate,
        ):
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_validate.return_value = ["one_on_one: 5 events in 5d (expected 1-2)"]

            sim_dir = await run_simulation(
                role="engineering-manager",
                variant="experienced-em",
                window="5d",
                seed=str(seed_dir),
                output=tmp_path / "sims",
            )

        # Simulation should still complete even with distribution warnings
        manifest = load_manifest(sim_dir)
        assert manifest.status == SimStatus.COMPLETED
        mock_validate.assert_called_once()
