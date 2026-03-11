"""Tiered checkpoint runner for the temporal simulator.

Every tick: deterministic cache refresh (nudges, team health, activity).
Weekly boundaries (Friday): LLM synthesis (briefing, snapshot, profiler).
On significant events: immediate synthesis for relevant agents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

_log = logging.getLogger(__name__)


def should_run_weekly_checkpoint(current_date: date) -> bool:
    """Return True if this date is a weekly checkpoint boundary (Friday)."""
    return current_date.weekday() == 4  # Friday


async def run_deterministic_checkpoint() -> None:
    """Run deterministic agents: cache refresh, nudge recalculation."""
    _log.info("Running deterministic checkpoint")
    await _refresh_caches()


async def run_weekly_checkpoint() -> None:
    """Run LLM synthesis agents at weekly boundary."""
    _log.info("Running weekly synthesis checkpoint")
    await _run_briefing()
    await _run_snapshot()
    await _run_profiler()


async def run_significant_event_checkpoint(event_type: str) -> None:
    """Run synthesis for significant events (incidents, review cycles)."""
    _log.info("Running significant event checkpoint for %s", event_type)
    if event_type == "incident":
        await _run_snapshot()
    elif event_type == "review_cycle":
        await _run_snapshot()
        await _run_briefing()


async def _refresh_caches() -> None:
    """Refresh data caches (management state, nudges, team health)."""
    try:
        from cockpit.api.cache import cache

        await cache.refresh()
    except Exception:
        _log.debug("Cache refresh skipped (not in API context)")


async def _run_briefing() -> None:
    """Run management_briefing synthesis."""
    try:
        from agents.management_briefing import format_briefing_md, generate_briefing
        from shared.config import PROFILES_DIR
        from shared.vault_writer import write_briefing_to_vault

        briefing = await generate_briefing()
        md = format_briefing_md(briefing)
        write_briefing_to_vault(md)
        (PROFILES_DIR / "management-briefing.json").write_text(briefing.model_dump_json(indent=2))
        _log.info("Briefing synthesized: %s", briefing.headline)
    except Exception:
        _log.exception("Briefing synthesis failed")


async def _run_snapshot() -> None:
    """Run team snapshot synthesis."""
    try:
        from agents.management_prep import format_snapshot_md, generate_team_snapshot
        from shared.vault_writer import write_team_snapshot_to_vault

        snapshot = await generate_team_snapshot()
        write_team_snapshot_to_vault(format_snapshot_md(snapshot))
        _log.info("Snapshot synthesized: %s", snapshot.headline)
    except Exception:
        _log.exception("Snapshot synthesis failed")


async def _run_profiler() -> None:
    """Run management profiler synthesis."""
    try:
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
        _log.info("Profile synthesized: v%s, %d facts", profile.version, len(facts))
    except Exception:
        _log.exception("Profiler synthesis failed")
