# ai-agents/shared/simulation.py
"""Simulation directory lifecycle — create, seed, manifest I/O, cleanup."""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import date, timedelta
from pathlib import Path

import yaml

from shared.simulation_models import SimManifest

_log = logging.getLogger(__name__)

_SUBDIRS = (
    "people",
    "coaching",
    "feedback",
    "meetings",
    "okrs",
    "goals",
    "incidents",
    "postmortem-actions",
    "review-cycles",
    "status-reports",
    "decisions",
    "references",
    "1on1-prep",
    "briefings",
    "status-updates",
    "review-prep",
)

_MANIFEST_FILE = ".sim-manifest.yaml"

_DEFAULT_BASE_DIR = Path("/tmp")


def _count_workdays(start: date, end: date) -> int:
    """Count weekday days between start and end (inclusive)."""
    if end < start:
        return 0
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            count += 1
        current += timedelta(days=1)
    return count


def create_simulation(
    *,
    role: str,
    window: str,
    start_date: str,
    end_date: str,
    seed: str,
    variant: str | None = None,
    scenario: str | None = None,
    audience: str | None = None,
    output: Path | None = None,
) -> tuple[Path, SimManifest]:
    """Create a new simulation directory with manifest and subdirectories."""
    base_dir = output if output is not None else _DEFAULT_BASE_DIR
    sim_id = f"hapax-sim-{uuid.uuid4().hex[:12]}"
    sim_dir = base_dir / sim_id
    sim_dir.mkdir(parents=True)

    for subdir in _SUBDIRS:
        (sim_dir / subdir).mkdir()

    ticks_total = _count_workdays(
        date.fromisoformat(start_date),
        date.fromisoformat(end_date),
    )

    manifest = SimManifest(
        id=sim_id,
        role=role,
        variant=variant,
        window=window,
        start_date=start_date,
        end_date=end_date,
        scenario=scenario,
        audience=audience,
        seed=seed,
        ticks_total=ticks_total,
    )
    save_manifest(sim_dir, manifest)

    _log.info("Created simulation %s at %s", sim_id, sim_dir)
    return sim_dir, manifest


def seed_simulation(sim_dir: Path, seed_dir: Path) -> None:
    """Copy seed corpus files into a simulation directory. Does not overwrite existing."""
    if not seed_dir.is_dir():
        raise ValueError(f"Seed directory does not exist: {seed_dir}")

    for src_file in seed_dir.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(seed_dir)
        dst = sim_dir / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst)

    _log.info("Seeded simulation from %s", seed_dir)


def save_manifest(sim_dir: Path, manifest: SimManifest) -> None:
    """Write manifest to .sim-manifest.yaml in the simulation directory."""
    path = sim_dir / _MANIFEST_FILE
    data = {"simulation": manifest.model_dump(mode="json")}
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def load_manifest(sim_dir: Path) -> SimManifest:
    """Load manifest from .sim-manifest.yaml."""
    path = sim_dir / _MANIFEST_FILE
    if not path.is_file():
        raise FileNotFoundError(f"No manifest at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SimManifest.model_validate(data["simulation"])


def cleanup_simulation(sim_dir: Path) -> None:
    """Remove a simulation directory. Refuses if not a simulation dir."""
    if not (sim_dir / _MANIFEST_FILE).is_file():
        raise ValueError(f"{sim_dir} is not a simulation directory (no {_MANIFEST_FILE})")
    shutil.rmtree(sim_dir)
    _log.info("Cleaned up simulation at %s", sim_dir)


def list_simulations(base_dir: Path) -> list[SimManifest]:
    """List all simulation manifests in a base directory."""
    manifests = []
    if not base_dir.is_dir():
        return manifests
    for child in sorted(base_dir.iterdir()):
        if child.is_dir() and (child / _MANIFEST_FILE).is_file():
            try:
                manifests.append(load_manifest(child))
            except Exception:
                _log.warning("Failed to load manifest from %s", child)
    return manifests
