"""shared/cycle_mode.py — Cycle mode reader.

Single source of truth for the current cycle mode (dev or prod).
The mode file is written by the hapax-mode CLI script and the
logos API. Agents read it at invocation to adjust thresholds.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path


class CycleMode(StrEnum):
    PROD = "prod"
    DEV = "dev"


_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")))
MODE_FILE = _CACHE_DIR / "hapax" / "cycle-mode"


def get_cycle_mode() -> CycleMode:
    """Read the current cycle mode. Defaults to PROD if file is missing or invalid."""
    try:
        return CycleMode(MODE_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return CycleMode.PROD
