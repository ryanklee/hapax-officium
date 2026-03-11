"""Test OLLAMA_URL env var support in shared/config."""

from unittest.mock import patch


def test_ollama_url_default():
    """OLLAMA_URL defaults to localhost:11534 (offset for isolated stack)."""
    with patch.dict("os.environ", {}, clear=False):
        import importlib

        import shared.config as cfg

        importlib.reload(cfg)
        assert cfg.OLLAMA_URL == "http://localhost:11534"


def test_ollama_url_from_env():
    """OLLAMA_URL reads from environment."""
    with patch.dict("os.environ", {"OLLAMA_URL": "http://ollama:11434"}):
        import importlib

        import shared.config as cfg

        importlib.reload(cfg)
        assert cfg.OLLAMA_URL == "http://ollama:11434"


def test_ollama_client_uses_url():
    """_get_ollama_client passes OLLAMA_URL to Client constructor."""
    with patch.dict("os.environ", {"OLLAMA_URL": "http://ollama:11434"}):
        import importlib

        import shared.config as cfg

        importlib.reload(cfg)
        cfg._ollama_client = None
        with patch("ollama.Client") as mock_client:
            cfg._get_ollama_client()
            mock_client.assert_called_once_with(host="http://ollama:11434", timeout=120)
