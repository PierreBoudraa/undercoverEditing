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

CAPTION_BASELINE_PERCENT = 78
CLUE_WORD_MAX_DURATION_SECONDS = 4.0
CLUE_OFFSET_SECONDS = -0.15

EXACT_MATCH_MAX_WORD_LENGTH = 4
FUZZY_MATCH_MAX_DISTANCE = 0.35
AUTO_ACCEPT_MAX_DISTANCE = 0.20
MAX_COMBINED_TOKEN_COUNT = 3

TRANSCRIPT_NUDGE_SECONDS = 0.1
LONG_INTERVAL_THRESHOLD_SECONDS = 0.8
LONG_INTERVAL_WORD_DURATION_SECONDS = 0.5
VERIFICATION_CLIP_LEAD_SECONDS = 1.0
VERIFICATION_CLIP_TAIL_SECONDS = 2.0


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

@dataclass(frozen=True)
class WordPillStyle:
    font_name: str
    font_size: int
    padding_x: int
    padding_y: int
    corner_radius: int
    text_color: str
    outline_color: str
    outline_width: int


WORD_PILL_STYLE = WordPillStyle(
    font_name="Arial",
    font_size=48,
    padding_x=26,
    padding_y=14,
    corner_radius=20,
    text_color="#FFFFFF",
    outline_color="#111111",
    outline_width=3,
)


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
