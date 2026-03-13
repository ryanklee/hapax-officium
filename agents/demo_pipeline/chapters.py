"""Re-export from hapax-demo package for backwards compatibility."""

from demo.pipeline.chapters import *  # noqa: F401, F403
from demo.pipeline.chapters import (  # noqa: F401
    _get_ffprobe_path,
    _get_wav_duration,
    build_chapter_list_from_script,
    generate_ffmetadata,
    inject_chapters,
)

# Backwards-compatible alias
get_ffmpeg_path = _get_ffprobe_path
