"""Tests for mutable DATA_DIR config holder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from shared.config import DATA_DIR, config


class TestMutableConfig:
    def test_data_dir_returns_path(self):
        """config.data_dir returns a Path object."""
        assert isinstance(config.data_dir, Path)

    def test_data_dir_matches_module_constant(self):
        """config.data_dir matches the module-level DATA_DIR at import time."""
        assert config.data_dir == DATA_DIR

    def test_set_data_dir_changes_value(self, tmp_path: Path):
        """set_data_dir() changes what config.data_dir returns."""
        original = config.data_dir
        try:
            config.set_data_dir(tmp_path)
            assert config.data_dir == tmp_path
        finally:
            config.set_data_dir(original)

    def test_set_data_dir_does_not_change_module_constant(self, tmp_path: Path):
        """Changing config.data_dir does not affect the module-level DATA_DIR constant."""
        original = config.data_dir
        try:
            config.set_data_dir(tmp_path)
            assert tmp_path != DATA_DIR
        finally:
            config.set_data_dir(original)

    def test_reset_data_dir(self, tmp_path: Path):
        """reset_data_dir() restores the original value."""
        original = config.data_dir
        config.set_data_dir(tmp_path)
        config.reset_data_dir()
        assert config.data_dir == original

    def test_env_var_override(self, tmp_path: Path):
        """HAPAX_DATA_DIR env var is respected at init time."""
        with patch.dict("os.environ", {"HAPAX_DATA_DIR": str(tmp_path)}):
            from shared.config import _Config

            c = _Config()
            assert c.data_dir == tmp_path
