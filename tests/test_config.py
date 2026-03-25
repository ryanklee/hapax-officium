"""Tests for shared.config — env loading and feature-flagged settings."""

from __future__ import annotations

import importlib
import os
from unittest.mock import patch


def test_config_defaults_without_settings_flag():
    """Config loads defaults via os.environ when HAPAX_USE_SETTINGS is unset."""
    with patch.dict(os.environ, {}, clear=True):
        import shared.config as cfg

        cfg = importlib.reload(cfg)
    assert cfg.LITELLM_BASE == "http://localhost:4100"
    assert cfg.QDRANT_URL == "http://localhost:6433"
    assert cfg.OLLAMA_URL == "http://localhost:11534"


def test_config_uses_settings_when_flagged():
    """Config reads from OfficiumSettings when HAPAX_USE_SETTINGS=1."""
    env = {
        "HAPAX_USE_SETTINGS": "1",
        "LITELLM_API_BASE": "http://typed:5000",
        "QDRANT_URL": "http://typed-qdrant:7000",
        "OLLAMA_URL": "http://typed-ollama:8000",
    }
    with patch.dict(os.environ, env, clear=True):
        import shared.config as cfg

        cfg = importlib.reload(cfg)
    assert cfg.LITELLM_BASE == "http://typed:5000"
    assert cfg.QDRANT_URL == "http://typed-qdrant:7000"
    assert cfg.OLLAMA_URL == "http://typed-ollama:8000"
