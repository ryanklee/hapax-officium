"""Tests for shared.settings — typed configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_default_settings_load():
    """Settings model loads with defaults when no env vars set."""
    from shared.settings import OfficiumSettings

    with patch.dict(os.environ, {}, clear=True):
        s = OfficiumSettings()
    assert s.litellm.base_url == "http://localhost:4100"
    assert s.qdrant.url == "http://localhost:6433"
    assert s.ollama.url == "http://localhost:11534"
    assert s.langfuse.host == "http://localhost:3100"
    assert s.engine.debounce_ms == 200
    assert s.engine.llm_concurrency == 2
    assert s.engine.delivery_interval_s == 300
    assert s.engine.action_timeout_s == 60.0
    assert s.logging.hapax_service == "hapax-officium"


def test_settings_override_from_env():
    """Env vars override defaults."""
    from shared.settings import OfficiumSettings

    env = {
        "LITELLM_API_BASE": "http://example:9000",
        "QDRANT_URL": "http://qdrant:6334",
        "OLLAMA_URL": "http://ollama:9999",
    }
    with patch.dict(os.environ, env, clear=True):
        s = OfficiumSettings()
    assert s.litellm.base_url == "http://example:9000"
    assert s.qdrant.url == "http://qdrant:6334"
    assert s.ollama.url == "http://ollama:9999"


def test_settings_rejects_invalid_debounce():
    """Negative debounce_ms rejected."""
    from shared.settings import OfficiumSettings

    with patch.dict(os.environ, {"ENGINE_DEBOUNCE_MS": "-5"}, clear=True), pytest.raises(
        ValueError
    ):
        OfficiumSettings()


def test_secret_str_hides_api_key():
    """API keys use SecretStr to prevent accidental logging."""
    from shared.settings import OfficiumSettings

    env = {"LITELLM_API_KEY": "sk-secret-key-123"}
    with patch.dict(os.environ, env, clear=True):
        s = OfficiumSettings()
    assert "sk-secret-key-123" not in str(s.litellm)
    assert s.litellm.api_key.get_secret_value() == "sk-secret-key-123"
