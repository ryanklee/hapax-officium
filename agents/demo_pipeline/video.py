"""Re-export from hapax-demo package for backwards compatibility."""
from demo.pipeline.video import *  # noqa: F401, F403
from demo.pipeline.video import CROSSFADE_DURATION, FPS, SCENE_TITLE_DURATION, TITLE_DURATION, assemble_video, _build_scene_clips, _title_clip  # noqa: F401

# moviepy is now a hard dependency of hapax-sdlc[demo], so always True
_HAS_MOVIEPY = True
