"""CI discovery — find live Configuration Items for coverage enforcement.

Discovers agents, timers, and services from the filesystem and Docker.
Adapted for the hapax-mgmt self-contained repo (no systemd, no multi-repo scan).
Zero LLM calls.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

# Project root for local discovery
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def discover_agents(agents_dir: Path | None = None) -> list[str]:
    """Discover agent modules by scanning for files with __main__ blocks."""
    if agents_dir is None:
        agents_dir = _PROJECT_ROOT / "agents"

    if not agents_dir.is_dir():
        return []

    agents = []
    for py_file in sorted(agents_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            content = py_file.read_text(errors="replace")
            if "__name__" in content and "__main__" in content:
                name = py_file.stem.replace("_", "-")
                agents.append(name)
        except OSError:
            continue
    return agents


def discover_services(compose_dir: Path | None = None) -> list[str]:
    """Discover running Docker Compose services."""
    if compose_dir is None:
        compose_dir = _PROJECT_ROOT.parent / "llm-stack"

    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(compose_dir) if compose_dir.is_dir() else None,
        )
        if result.returncode != 0:
            return []
        return [s.strip() for s in result.stdout.strip().splitlines() if s.strip()]
    except (OSError, subprocess.TimeoutExpired):
        return []
