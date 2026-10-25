from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK_DIR = PROJECT_ROOT / "workdir"

PLAYER_COLORS = {
    "left": "#FF6B6B",
    "center": "#FFD166",
    "right": "#4CC9F0",
}

CLUE_OFFSET_SECONDS = 0.25

EXACT_MATCH_MAX_WORD_LENGTH = 4
FUZZY_MATCH_MAX_DISTANCE = 0.35
AUTO_ACCEPT_MAX_DISTANCE = 0.20
MAX_COMBINED_TOKEN_COUNT = 3

TRANSCRIPT_NUDGE_SECONDS = 0.1
LONG_INTERVAL_THRESHOLD_SECONDS = 0.8
LONG_INTERVAL_WORD_DURATION_SECONDS = 0.5
VERIFICATION_CLIP_LEAD_SECONDS = 1.0
VERIFICATION_CLIP_TAIL_SECONDS = 2.0

# The standalone alignment spike retains its original preview appearance.
CAPTION_BASELINE_PERCENT = 78


@dataclass(frozen=True)
class ClueWordStyle:
    font_name: str
    font_size: int
    text_color: str
    outline_color: str
    outline_width: int


CLUE_WORD_STYLE = ClueWordStyle(
    font_name="Arial",
    font_size=72,
    text_color="#FFFFFF",
    outline_color="#111111",
    outline_width=7,
)

OVERLAY_FONT_NAME = "Chewy"
OVERLAY_FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
OVERLAY_FONT_FILE = OVERLAY_FONT_DIR / "Chewy-Regular.ttf"
OVERLAY_DEFAULT_FONT_SIZE = 72
OVERLAY_DEFAULT_OUTLINE_WIDTH = 6
OVERLAY_FILL_COLOR = "#FFFFFF"
OVERLAY_OUTLINE_COLOR = "#000000"


@dataclass(frozen=True)
class GlowLayerStyle:
    border_width_ratio: float
    blur_ratio: float
    opacity: float


TITLE_OUTLINE_WIDTH_RATIO = 0.075
TITLE_GLOW_LAYERS = (
    GlowLayerStyle(border_width_ratio=0.23, blur_ratio=0.13, opacity=1.0),
    GlowLayerStyle(border_width_ratio=0.14, blur_ratio=0.035, opacity=1.0),
)
WORD_OUTLINE_WIDTH_RATIO = 0.075
WORD_GLOW_LAYERS = (
    GlowLayerStyle(border_width_ratio=0.22, blur_ratio=0.12, opacity=1.0),
    GlowLayerStyle(border_width_ratio=0.13, blur_ratio=0.03, opacity=1.0),
)

TITLE_TEXT = "Undercover"
TITLE_FONT_HEIGHT_PERCENT = 11.0
TITLE_CENTER_Y_PERCENT = 12.0
TITLE_MAX_WIDTH_PERCENT = 96.0
TITLE_GLOW_COLOR = "#FF1A1A"

PLAYER_WORD_FONT_HEIGHT_PERCENT = 7.0
CLUE_WORD_FONT_HEIGHT_PERCENT = 6.5
OVERLAY_MAX_WORD_WIDTH_PERCENT = 32.0

CIVILIAN_GLOW_COLOR = "#00FF2A"
UNDERCOVER_GLOW_COLOR = "#FF1A1A"
NEUTRAL_GLOW_COLOR = "#FFFFFF"

CLUE_STACK_START_PERCENT = 68.0
CLUE_STACK_LINE_SPACING_PERCENT = 7.5
CLUE_STACK_BOTTOM_SAFE_PERCENT = 85.0
CLUE_WORD_SLANT = 0.08

POP_IN_START_SCALE_PERCENT = 120
POP_IN_DURATION_MILLISECONDS = 150


def resolve_ffmpeg() -> Path:
    configured_path = os.environ.get("FFMPEG_EXE")
    if configured_path:
        ffmpeg_path = Path(configured_path).expanduser().resolve()
        if not ffmpeg_path.is_file():
            raise FileNotFoundError(
                f"FFMPEG_EXE does not point to a file: {ffmpeg_path}"
            )
    else:
        import imageio_ffmpeg

        ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()

    os.environ["IMAGEIO_FFMPEG_EXE"] = str(ffmpeg_path)
    return ffmpeg_path
