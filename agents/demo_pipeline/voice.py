"""Re-export from hapax-demo package for backwards compatibility."""
from demo.pipeline.voice import *  # noqa: F401, F403
from demo.pipeline.voice import generate_voice_segment, check_tts_available, generate_all_voice_segments  # noqa: F401

# Backwards-compatible alias
generate_all_voice = generate_all_voice_segments
