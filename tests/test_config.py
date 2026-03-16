"""Smoke tests for shared config and agent loading."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from shared.config import (
    DATA_DIR,
    EMBEDDING_MODEL,
    LITELLM_BASE,
    LITELLM_KEY,
    MODELS,
    PROFILES_DIR,
    QDRANT_URL,
    embed,
    get_model,
    get_qdrant,
)


def test_model_aliases_defined():
    assert "fast" in MODELS
    assert "balanced" in MODELS
    assert "reasoning" in MODELS
    assert "coding" in MODELS
    assert "local-fast" in MODELS


def test_embedding_model_is_v2():
    assert "v2" in EMBEDDING_MODEL


def test_env_defaults():
    assert LITELLM_BASE.startswith("http")
    assert QDRANT_URL.startswith("http")
    assert isinstance(LITELLM_KEY, str)


def test_get_model_returns_correct_type():
    model = get_model("balanced")
    assert model.model_name == "claude-sonnet"


def test_get_model_alias_fallthrough():
    model = get_model("anthropic/claude-opus-4")
    assert model.model_name == "anthropic/claude-opus-4"


def test_get_qdrant_returns_client():
    from qdrant_client import QdrantClient

    client = get_qdrant()
    assert isinstance(client, QdrantClient)


def test_profiles_dir_is_path():
    assert isinstance(PROFILES_DIR, Path)
    assert PROFILES_DIR.name == "profiles"


def test_embed_error_handling():
    import pytest

    mock_client = MagicMock()
    mock_client.embed.side_effect = ConnectionError("Ollama is down")
    with patch("shared.config._get_ollama_client", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Embedding failed") as exc_info:
            embed("test text")
        assert "Ollama is down" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None


def test_embed_dimension_validation():
    """embed() rejects vectors with wrong dimensions."""
    import pytest

    wrong_dim = [0.1] * 512  # 512 instead of 768
    mock_client = MagicMock()
    mock_client.embed.return_value = {"embeddings": [wrong_dim]}
    with (
        patch("shared.config._get_ollama_client", return_value=mock_client),
        pytest.raises(RuntimeError, match="Expected 768-dim embedding, got 512"),
    ):
        embed("test text")


def test_embed_dimension_validation_correct():
    """embed() accepts vectors with correct dimensions."""
    correct = [0.1] * 768
    mock_client = MagicMock()
    mock_client.embed.return_value = {"embeddings": [correct]}
    with patch("shared.config._get_ollama_client", return_value=mock_client):
        result = embed("test text")
        assert len(result) == 768


# ── Project path constants ──────────────────────────────────────────────────


def test_project_paths_exist():
    """Local project path constants should be importable from config."""
    from shared.config import AXIOMS_DIR, PROJECT_ROOT

    assert isinstance(AXIOMS_DIR, Path)
    assert isinstance(PROJECT_ROOT, Path)
    assert AXIOMS_DIR.name == "axioms"


def test_no_path_home_in_shared():
    """shared/ modules should use config constants, not Path.home() directly.

    Exception: config.py itself (defines the root constants).
    """
    shared_dir = Path(__file__).resolve().parent.parent / "shared"
    violations = []
    for py_file in shared_dir.rglob("*.py"):
        if py_file.name == "config.py":
            continue
        source = py_file.read_text()
        if "Path.home()" in source:
            count = source.count("Path.home()")
            violations.append(f"{py_file.relative_to(shared_dir.parent)}: {count}")
    assert violations == [], "Path.home() in shared/ modules:\n" + "\n".join(violations)


def test_no_path_home_in_agents():
    """agents/ modules should use config constants, not Path.home() directly.

    Exceptions: drift_detector.py and introspect.py use Path.home() for
    tilde-expansion in display strings and host-level path resolution.
    """
    agents_dir = Path(__file__).resolve().parent.parent / "agents"
    # Files allowed to use Path.home() for display/formatting purposes
    allowed = {"drift_detector.py", "introspect.py"}
    violations = []
    for py_file in agents_dir.rglob("*.py"):
        if py_file.name in allowed:
            continue
        source = py_file.read_text()
        if "Path.home()" in source:
            count = source.count("Path.home()")
            violations.append(f"{py_file.relative_to(agents_dir.parent)}: {count}")
    assert violations == [], "Path.home() in agents/ modules:\n" + "\n".join(violations)


# ── DATA_DIR ───────────────────────────────────────────────────────────────


def test_data_dir_default():
    """DATA_DIR defaults to ai-agents/data relative to config.py."""
    assert DATA_DIR.name == "data"
    assert DATA_DIR.parent.name == "ai-agents" or DATA_DIR.exists()


def test_data_dir_is_path():
    """DATA_DIR should be a Path instance."""
    assert isinstance(DATA_DIR, Path)


def test_data_dir_env_override():
    """DATA_DIR respects HAPAX_DATA_DIR environment variable."""
    import importlib
    import os

    with patch.dict(os.environ, {"HAPAX_DATA_DIR": "/tmp/test-hapax-data"}):
        import shared.config as cfg

        importlib.reload(cfg)
        assert Path("/tmp/test-hapax-data") == cfg.DATA_DIR

    # Reload to restore default
    import shared.config as cfg

    importlib.reload(cfg)
