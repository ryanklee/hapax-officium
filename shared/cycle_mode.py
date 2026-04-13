"""shared/cycle_mode.py — DEPRECATED backward-compat shim.

The cycle_mode (dev/prod) system has been replaced by working_mode
(research/rnd). New code should import from shared.working_mode directly.

This module re-exports the working_mode symbols under the old cycle_mode
names so any straggling import keeps working during the migration window.
The mode FILE has moved from `~/.cache/hapax/cycle-mode` to
`~/.cache/hapax/working-mode` — the constant `MODE_FILE` here points at
the new location.

Slated for deletion per `hapax-council/docs/officium-design-language.md` §9.
"""

from __future__ import annotations

import warnings

from shared.working_mode import (
    WORKING_MODE_FILE as MODE_FILE,
)
from shared.working_mode import (
    WorkingMode,
    get_working_mode,
    set_working_mode,
)

# Old name retained for backward compat. The values are research/rnd, not
# dev/prod — any caller still passing dev/prod was already broken because
# the workspace migrated long ago.
CycleMode = WorkingMode

# Old function name aliases.
get_cycle_mode = get_working_mode
set_cycle_mode = set_working_mode

__all__ = ["MODE_FILE", "CycleMode", "get_cycle_mode", "set_cycle_mode"]


def __getattr__(name: str):  # pragma: no cover — defensive deprecation hook
    """Emit DeprecationWarning when a caller imports from this module."""
    if name in __all__:
        warnings.warn(
            f"shared.cycle_mode.{name} is deprecated; import from shared.working_mode instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return globals()[name]
    raise AttributeError(f"module 'shared.cycle_mode' has no attribute {name!r}")
