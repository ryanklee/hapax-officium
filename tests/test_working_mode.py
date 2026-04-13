"""Tests for shared/working_mode.py and the deprecated cycle_mode shim."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path


def test_working_mode_default_rnd(tmp_path: Path):
    """Mode file missing → defaults to RND."""
    mode_file = tmp_path / "working-mode"
    with patch("shared.working_mode.WORKING_MODE_FILE", mode_file):
        from shared.working_mode import WorkingMode, get_working_mode

        assert get_working_mode() == WorkingMode.RND


def test_working_mode_invalid_value_falls_back(tmp_path: Path):
    """Mode file with garbage → defaults to RND."""
    mode_file = tmp_path / "working-mode"
    mode_file.write_text("garbage")
    with patch("shared.working_mode.WORKING_MODE_FILE", mode_file):
        from shared.working_mode import WorkingMode, get_working_mode

        assert get_working_mode() == WorkingMode.RND


def test_working_mode_research(tmp_path: Path):
    mode_file = tmp_path / "working-mode"
    mode_file.write_text("research")
    with patch("shared.working_mode.WORKING_MODE_FILE", mode_file):
        from shared.working_mode import (
            WorkingMode,
            get_working_mode,
            is_research,
            is_rnd,
        )

        assert get_working_mode() == WorkingMode.RESEARCH
        assert is_research()
        assert not is_rnd()


def test_working_mode_set_round_trip(tmp_path: Path):
    mode_file = tmp_path / "working-mode"
    with patch("shared.working_mode.WORKING_MODE_FILE", mode_file):
        from shared.working_mode import (
            WorkingMode,
            get_working_mode,
            set_working_mode,
        )

        set_working_mode(WorkingMode.RESEARCH)
        assert get_working_mode() == WorkingMode.RESEARCH

        set_working_mode(WorkingMode.RND)
        assert get_working_mode() == WorkingMode.RND


def test_no_fortress_mode():
    """Officium intentionally omits council's `fortress` mode."""
    from shared.working_mode import WorkingMode

    assert {m.value for m in WorkingMode} == {"research", "rnd"}
    assert "fortress" not in {m.value for m in WorkingMode}


def test_cycle_mode_shim_re_exports_working_mode():
    """The deprecated cycle_mode shim aliases to WorkingMode symbols."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from shared.cycle_mode import (
            MODE_FILE,
            CycleMode,
            get_cycle_mode,
            set_cycle_mode,
        )
        from shared.working_mode import (
            WORKING_MODE_FILE,
            WorkingMode,
            get_working_mode,
            set_working_mode,
        )

    assert CycleMode is WorkingMode
    assert MODE_FILE == WORKING_MODE_FILE
    assert get_cycle_mode is get_working_mode
    assert set_cycle_mode is set_working_mode


def test_cycle_mode_shim_emits_deprecation_warning():
    """Importing from shared.cycle_mode logs a DeprecationWarning."""
    import importlib
    import warnings

    import shared.cycle_mode as cycle_mode_module

    importlib.reload(cycle_mode_module)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Trigger __getattr__ via `getattr` to force the warning path
        _ = cycle_mode_module.__getattr__("CycleMode")

    assert any(issubclass(x.category, DeprecationWarning) for x in w)
