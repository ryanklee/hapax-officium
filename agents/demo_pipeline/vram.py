"""Re-export from hapax-demo package for backwards compatibility."""
from demo.pipeline.vram import *  # noqa: F401, F403
from demo.pipeline.vram import get_vram_free_mb, unload_ollama_models, ensure_vram_available  # noqa: F401
