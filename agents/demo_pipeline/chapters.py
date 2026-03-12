"""Re-export from hapax-demo package for backwards compatibility."""
from demo.pipeline.chapters import *  # noqa: F401, F403
from demo.pipeline.chapters import generate_ffmetadata, build_chapter_list_from_script, inject_chapters, _get_wav_duration, _get_ffprobe_path  # noqa: F401
# Backwards-compatible alias
get_ffmpeg_path = _get_ffprobe_path
