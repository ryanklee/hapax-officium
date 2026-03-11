"""Post-simulation warm-up — runs agent pipeline to guarantee fresh data.

Executes the same agent sequence as bootstrap Phase 4:
activity metrics, profiler, briefing, digest, team snapshot.
Each agent is called with try/except so individual failures
don't abort the warm-up.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from shared.config import config

if TYPE_CHECKING:
    from pathlib import Path

_log = logging.getLogger(__name__)


async def run_warmup(sim_dir: Path) -> None:
    """Run full agent warm-up against a simulation directory.

    Sets config.data_dir to sim_dir, runs agents, resets on completion.
    """
    config.set_data_dir(sim_dir)
    _log.info("Running post-simulation warm-up against %s", sim_dir)

    try:
        # 1. Deterministic: management activity metrics
        try:
            _run_activity()
            _log.info("Warm-up: activity metrics complete")
        except Exception:
            _log.exception("Warm-up: activity metrics failed")

        # 2. LLM: management profiler
        try:
            await _run_profiler()
            _log.info("Warm-up: profiler complete")
        except Exception:
            _log.exception("Warm-up: profiler failed")

        # 3. LLM: management briefing
        try:
            await _run_briefing()
            _log.info("Warm-up: briefing complete")
        except Exception:
            _log.exception("Warm-up: briefing failed")

        # 4. LLM: digest
        try:
            await _run_digest()
            _log.info("Warm-up: digest complete")
        except Exception:
            _log.exception("Warm-up: digest failed")

        # 5. LLM: team snapshot
        try:
            await _run_snapshot()
            _log.info("Warm-up: team snapshot complete")
        except Exception:
            _log.exception("Warm-up: team snapshot failed")

    finally:
        config.reset_data_dir()

    _log.info("Post-simulation warm-up complete")


def _run_activity() -> None:
    """Run management_activity to compute metrics."""
    from agents.management_activity import generate_management_report
    from shared.config import PROFILES_DIR

    report = generate_management_report()
    (PROFILES_DIR / "management-activity.json").write_text(report.model_dump_json(indent=2))


async def _run_profiler() -> None:
    """Run management_profiler synthesis."""
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


async def _run_briefing() -> None:
    """Run management_briefing synthesis."""
    from agents.management_briefing import format_briefing_md, generate_briefing
    from shared.config import PROFILES_DIR
    from shared.vault_writer import write_briefing_to_vault

    briefing = await generate_briefing()
    md = format_briefing_md(briefing)
    write_briefing_to_vault(md)
    (PROFILES_DIR / "management-briefing.json").write_text(briefing.model_dump_json(indent=2))


async def _run_digest() -> None:
    """Run digest synthesis."""
    from agents.digest import generate_digest
    from shared.config import PROFILES_DIR

    digest = await generate_digest()
    (PROFILES_DIR / "digest.json").write_text(digest.model_dump_json(indent=2))


async def _run_snapshot() -> None:
    """Run team snapshot synthesis."""
    from agents.management_prep import format_snapshot_md, generate_team_snapshot
    from shared.vault_writer import write_team_snapshot_to_vault

    snapshot = await generate_team_snapshot()
    write_team_snapshot_to_vault(format_snapshot_md(snapshot))
