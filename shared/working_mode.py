"""shared/working_mode.py — Working mode reader for officium.

Single source of truth for the operator's current working mode.

Officium recognizes two modes (the workspace-wide system also has `fortress`,
which is council-specific for studio livestream gating; officium has no studio
surface and intentionally omits it):

    research — experiment-safe; slower timers, suppressed probes
    rnd      — full speed; accelerated timers, probes active

The mode file is shared with all hapax services at
`~/.cache/hapax/working-mode`. The `hapax-working-mode` script in the council
repo writes this file; officium reads it and can also write it via the
`/api/working-mode` endpoint.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path


class WorkingMode(StrEnum):
    RESEARCH = "research"
    RND = "rnd"


_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")))
WORKING_MODE_FILE = _CACHE_DIR / "hapax" / "working-mode"


def get_working_mode() -> WorkingMode:
    """Read the current working mode. Defaults to RND if file is missing or invalid."""
    try:
        return WorkingMode(WORKING_MODE_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return WorkingMode.RND


def set_working_mode(mode: WorkingMode) -> None:
    """Write the working mode file."""
    WORKING_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    WORKING_MODE_FILE.write_text(mode.value)


def is_research() -> bool:
    return get_working_mode() == WorkingMode.RESEARCH


def is_rnd() -> bool:
    return get_working_mode() == WorkingMode.RND
