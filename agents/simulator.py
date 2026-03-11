"""Temporal simulator agent — generates realistic management activity over time.

Advances through simulated workdays, generating plausible events via LLM,
running tiered checkpoints, and producing a complete DATA_DIR snapshot.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from agents.simulator_pipeline.checkpoints import (
    run_deterministic_checkpoint,
    run_significant_event_checkpoint,
    run_weekly_checkpoint,
    should_run_weekly_checkpoint,
)
from agents.simulator_pipeline.context import (
    build_tick_prompt,
    compose_role_profile,
    load_org_dossier,
    load_role_matrix,
    load_scenarios,
    load_workflow_semantics,
    validate_distribution,
)
from agents.simulator_pipeline.event_gen import generate_tick_events
from agents.simulator_pipeline.renderer import render_events
from agents.simulator_pipeline.seed import rebase_seed_dates
from shared.config import config
from shared.simulation import (
    create_simulation,
    load_manifest,
    save_manifest,
    seed_simulation,
)
from shared.simulation_models import SimStatus

if TYPE_CHECKING:
    from agents.simulator_pipeline.models import SimulatedEvent

_log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_SEMANTICS = _PROJECT_ROOT / "docs" / "workflow-semantics.yaml"
_ROLE_MATRIX = _PROJECT_ROOT / "config" / "role-matrix.yaml"
_SCENARIOS = _PROJECT_ROOT / "config" / "scenarios.yaml"
_ORG_DOSSIER = _PROJECT_ROOT / "config" / "org-dossier.yaml"


def _parse_window(window: str) -> int:
    """Parse window string like '7d', '30d', '90d' into days."""
    if window.endswith("d"):
        return int(window[:-1])
    raise ValueError(f"Invalid window format: {window} (expected '7d', '30d', etc.)")


def _compute_dates(window_days: int) -> tuple[date, date]:
    """Compute start_date and end_date for a simulation window."""
    end = date.today()
    start = end - timedelta(days=window_days)
    return start, end


def _workdays(start: date, end: date) -> list[date]:
    """Generate list of workdays (Mon-Fri) between start and end inclusive."""
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _summarize_state(sim_dir: Path) -> str:
    """Generate a brief summary of current DATA_DIR state for the LLM."""
    summary_parts = []

    people_dir = sim_dir / "people"
    if people_dir.is_dir():
        people_files = list(people_dir.glob("*.md"))
        summary_parts.append(f"{len(people_files)} people files")

    for subdir in ("coaching", "feedback", "meetings", "incidents", "okrs", "goals"):
        d = sim_dir / subdir
        if d.is_dir():
            count = len(list(d.glob("*.md")))
            if count > 0:
                summary_parts.append(f"{count} {subdir}")

    return ", ".join(summary_parts) if summary_parts else "empty data directory"


async def run_simulation(
    *,
    role: str,
    variant: str = "experienced-em",
    window: str = "30d",
    seed: str = "demo-data/",
    scenario: str | None = None,
    audience: str | None = None,
    output: Path | None = None,
    resume_dir: Path | None = None,
    org_dossier: Path | None = None,
) -> Path:
    """Run a full temporal simulation. Returns the simulation directory path."""
    # Load config
    workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
    roles = load_role_matrix(_ROLE_MATRIX)
    scenarios = load_scenarios(_SCENARIOS) if _SCENARIOS.is_file() else {}

    scenario_def = scenarios.get(scenario) if scenario else None

    org_path = org_dossier or _ORG_DOSSIER
    org = load_org_dossier(org_path) if org_path.is_file() else None

    # Create or resume simulation
    if resume_dir:
        sim_dir = resume_dir
        manifest = load_manifest(sim_dir)
        role = manifest.role
        variant = manifest.variant or variant
        _log.info("Resuming simulation %s from tick %s", manifest.id, manifest.last_completed_tick)
    else:
        window_days = _parse_window(window)
        start_date, end_date = _compute_dates(window_days)

        sim_dir, manifest = create_simulation(
            role=role,
            window=window,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            seed=seed,
            variant=variant,
            scenario=scenario,
            audience=audience,
            output=output,
        )

        # Seed and rebase dates
        seed_path = Path(seed)
        if not seed_path.is_absolute():
            seed_path = _PROJECT_ROOT / seed_path
        seed_simulation(sim_dir, seed_path)
        rebase_seed_dates(sim_dir, sim_start=start_date)

    # Compose role profile
    profile = compose_role_profile(
        role_name=role,
        variant=variant,
        roles=roles,
        workflows=workflows,
        scenario=scenario_def,
        org=org,
    )

    # Compute workdays
    start_date = date.fromisoformat(manifest.start_date)
    end_date = date.fromisoformat(manifest.end_date)
    all_days = _workdays(start_date, end_date)

    # Skip already-completed ticks on resume
    if manifest.last_completed_tick:
        last_completed = date.fromisoformat(manifest.last_completed_tick)
        all_days = [d for d in all_days if d > last_completed]

    # Update manifest to running
    manifest.status = SimStatus.RUNNING
    save_manifest(sim_dir, manifest)

    # Point config at simulation directory
    config.set_data_dir(sim_dir)

    recent_events: list[str] = []
    all_events: list[SimulatedEvent] = []

    try:
        for tick_date in all_days:
            _log.info(
                "Tick: %s (%d/%d)",
                tick_date.isoformat(),
                manifest.ticks_completed + 1,
                manifest.ticks_total,
            )

            # Build prompt and generate events
            state_summary = _summarize_state(sim_dir)
            prompt = build_tick_prompt(
                profile=profile,
                current_date=tick_date.isoformat(),
                existing_state_summary=state_summary,
                recent_events=recent_events,
            )

            events = await generate_tick_events(prompt=prompt, valid_workflows=workflows)

            # Render events to files
            if events:
                render_events(events, sim_dir)
                all_events.extend(events)
                for event in events:
                    recent_events.append(
                        f"{event.date}: {event.workflow_type}"
                        + (f" ({event.participant})" if event.participant else "")
                    )

            # Run deterministic checkpoint every tick
            await run_deterministic_checkpoint()

            # Weekly checkpoint on Fridays
            if should_run_weekly_checkpoint(tick_date):
                await run_weekly_checkpoint()
                manifest.checkpoints_run += 1

            # Significant event checkpoint
            for event in events:
                if event.workflow_type in ("incident", "review_cycle"):
                    await run_significant_event_checkpoint(event.workflow_type)
                    manifest.checkpoints_run += 1
                    break  # One checkpoint per tick max

            # Update manifest progressively
            manifest.ticks_completed += 1
            manifest.last_completed_tick = tick_date.isoformat()
            save_manifest(sim_dir, manifest)

        # Mark completed
        manifest.status = SimStatus.COMPLETED
        manifest.completed_at = datetime.now(UTC)
        save_manifest(sim_dir, manifest)

        # Distribution validation
        role_def = roles.get(role, {})
        reference = role_def.get("reference_distribution_30d")
        if reference and all_events:
            window_days = (end_date - start_date).days
            dist_warnings = validate_distribution(all_events, reference, window_days)
            for w in dist_warnings:
                _log.warning("Distribution outlier: %s", w)

        _log.info(
            "Simulation %s completed: %d ticks, %d checkpoints",
            manifest.id,
            manifest.ticks_completed,
            manifest.checkpoints_run,
        )

    except Exception:
        manifest.status = SimStatus.FAILED
        save_manifest(sim_dir, manifest)
        _log.exception("Simulation %s failed at tick %s", manifest.id, manifest.last_completed_tick)
        raise
    finally:
        config.reset_data_dir()

    return sim_dir


async def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Temporal simulator — generate realistic management activity over time",
        prog="python -m agents.simulator",
    )
    parser.add_argument("--role", type=str, help="Role key (e.g. engineering-manager)")
    parser.add_argument("--variant", type=str, default=None, help="Role variant")
    parser.add_argument(
        "--window", type=str, default="30d", help="Simulation window (e.g. 7d, 30d, 90d)"
    )
    parser.add_argument("--seed", type=str, default="demo-data/", help="Seed corpus path")
    parser.add_argument("--scenario", type=str, default=None, help="Scenario modifier")
    parser.add_argument("--audience", type=str, default=None, help="Audience archetype")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    parser.add_argument("--resume", type=str, default=None, help="Resume from existing sim dir")
    parser.add_argument(
        "--org-dossier",
        type=str,
        default=None,
        help="Path to org-dossier.yaml (default: config/org-dossier.yaml)",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.resume:
        sim_dir = await run_simulation(resume_dir=Path(args.resume), role="")
    else:
        if not args.role:
            parser.error("--role is required (or use --resume)")

        sim_dir = await run_simulation(
            role=args.role,
            variant=args.variant or "experienced-em",
            window=args.window,
            seed=args.seed,
            scenario=args.scenario,
            audience=args.audience,
            output=Path(args.output) if args.output else None,
            org_dossier=Path(args.org_dossier) if args.org_dossier else None,
        )

    manifest = load_manifest(sim_dir)

    if args.json:
        print(manifest.model_dump_json(indent=2))
    else:
        print(f"Simulation complete: {sim_dir}")
        print(f"  Status: {manifest.status}")
        print(f"  Ticks: {manifest.ticks_completed}/{manifest.ticks_total}")
        print(f"  Checkpoints: {manifest.checkpoints_run}")


if __name__ == "__main__":
    asyncio.run(main())
