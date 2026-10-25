from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import resolve_ffmpeg


MIN_VIDEO_DURATION_SECONDS = 30.0
MAX_VIDEO_DURATION_SECONDS = 60.0

_DURATION_PATTERN = re.compile(
    r"Duration:\s*(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+(?:\.\d+)?)"
)
_INPUT_FORMAT_PATTERN = re.compile(
    r"Input #\d+,\s*(?P<formats>.*?),\s+from\s+['\"]", re.IGNORECASE
)
_VIDEO_SIZE_PATTERN = re.compile(
    r"\bVideo:\s*[^\r\n]*?\b(?P<width>\d{2,})x(?P<height>\d{2,})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MediaInfo:
    duration_seconds: float
    width: int
    height: int


class MediaValidationError(ValueError):
    pass


def parse_ffmpeg_media_info(output: str) -> MediaInfo:
    input_match = _INPUT_FORMAT_PATTERN.search(output)
    duration_match = _DURATION_PATTERN.search(output)
    size_match = _VIDEO_SIZE_PATTERN.search(output)
    if input_match is None:
        raise MediaValidationError("Choose a playable MP4 video.")
    formats = {item.strip().casefold() for item in input_match["formats"].split(",")}
    if "mp4" not in formats:
        raise MediaValidationError(
            "Choose an MP4 video. Other video formats are not supported."
        )
    if duration_match is None or size_match is None:
        raise MediaValidationError(
            "FFmpeg could not read the clip's duration and video dimensions."
        )

    duration = (
        int(duration_match["hours"]) * 3600
        + int(duration_match["minutes"]) * 60
        + float(duration_match["seconds"])
    )
    width = int(size_match["width"])
    height = int(size_match["height"])
    if duration <= 0 or width <= 0 or height <= 0:
        raise MediaValidationError("The selected MP4 has invalid video metadata.")
    return MediaInfo(duration_seconds=duration, width=width, height=height)


def validate_video_duration(duration_seconds: float) -> None:
    if not MIN_VIDEO_DURATION_SECONDS <= duration_seconds <= MAX_VIDEO_DURATION_SECONDS:
        raise MediaValidationError(
            "The clip must be between 30 and 60 seconds long. "
            f"This clip is {duration_seconds:.1f} seconds."
        )


def inspect_mp4(path: Path) -> MediaInfo:
    ffmpeg_path = resolve_ffmpeg()
    try:
        result = subprocess.run(
            [
                str(ffmpeg_path),
                "-hide_banner",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaValidationError(
            "FFmpeg took too long to inspect this clip. Try another MP4."
        ) from exc

    if result.returncode != 0:
        raise MediaValidationError(
            "This file could not be read as a playable MP4 video."
        )
    return parse_ffmpeg_media_info(result.stderr)
