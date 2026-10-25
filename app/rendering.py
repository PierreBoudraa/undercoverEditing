from __future__ import annotations

import math
import os
import subprocess
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Literal, Sequence

import imageio_ffmpeg

from app.config import (
    CAPTION_BASELINE_PERCENT,
    CLUE_OFFSET_SECONDS,
    CLUE_WORD_MAX_DURATION_SECONDS,
    CLUE_WORD_STYLE,
    LONG_INTERVAL_THRESHOLD_SECONDS,
    LONG_INTERVAL_WORD_DURATION_SECONDS,
    PLAYER_COLORS,
    WORD_PILL_STYLE,
    resolve_ffmpeg,
)


BASE_STYLE_WIDTH = 1080
Speaker = Literal["left", "center", "right"]


@dataclass(frozen=True)
class WordOverlay:
    text: str
    speaker: Speaker
    x_percent: float
    y_percent: float


@dataclass(frozen=True)
class TranscriptLine:
    start: float
    end: float
    clue_word: str | None = None
    speaker: Speaker | None = None
    nudge_seconds: float = 0.0


@dataclass(frozen=True)
class ClueWordEvent:
    start: float
    end: float
    text: str
    speaker: Speaker
    x: int
    bottom_y: int


def ass_timestamp(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("ASS timestamps must be finite and non-negative.")

    centiseconds = round(seconds * 100)
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{whole_seconds:02}.{fraction:02}"


def _validate_overlay_text(text: str, label: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{label} cannot be empty.")
    if any(char in "\\{}" for char in text) or any(
        unicodedata.category(char) == "Cc" or char in "\u2028\u2029"
        for char in text
    ):
        raise ValueError(
            f"{label} must be single-line and cannot contain ASS control characters."
        )


def _validate_line(line: TranscriptLine) -> None:
    if line.speaker is None or line.speaker not in PLAYER_COLORS:
        raise ValueError("Every clue word must have a valid speaker assignment.")
    if not isinstance(line.clue_word, str):
        raise ValueError("A rendered transcript line must have a clue word.")
    if not math.isfinite(line.start) or not math.isfinite(line.end):
        raise ValueError("Transcript timestamps must be finite.")
    if line.start < 0 or line.end <= line.start:
        raise ValueError("Each transcript line must have a positive time range.")
    if not math.isfinite(line.nudge_seconds):
        raise ValueError("Transcript time nudges must be finite.")
    _validate_overlay_text(line.clue_word, "Clue word")


def clue_anchor_time(start: float, end: float) -> float:
    if (
        not math.isfinite(start)
        or not math.isfinite(end)
        or start < 0
        or end <= start
    ):
        raise ValueError("Clue timestamps must have a finite, positive time range.")
    if (
        not math.isfinite(LONG_INTERVAL_THRESHOLD_SECONDS)
        or LONG_INTERVAL_THRESHOLD_SECONDS < 0
    ):
        raise ValueError("The long-interval threshold must be finite and non-negative.")
    if (
        not math.isfinite(LONG_INTERVAL_WORD_DURATION_SECONDS)
        or LONG_INTERVAL_WORD_DURATION_SECONDS <= 0
    ):
        raise ValueError("The long-interval anchor duration must be positive and finite.")
    if end - start > LONG_INTERVAL_THRESHOLD_SECONDS:
        return max(start, end - LONG_INTERVAL_WORD_DURATION_SECONDS)
    return start


def clue_display_start(
    start: float, end: float, nudge_seconds: float = 0.0
) -> float:
    if not math.isfinite(nudge_seconds):
        raise ValueError("Transcript time nudges must be finite.")
    if not math.isfinite(CLUE_OFFSET_SECONDS):
        raise ValueError("The clue display offset must be finite.")
    return max(
        0.0,
        clue_anchor_time(start, end) + CLUE_OFFSET_SECONDS + nudge_seconds,
    )


def _validate_words(words: Sequence[WordOverlay]) -> None:
    speakers = [word.speaker for word in words]
    if len(words) != len(PLAYER_COLORS) or set(speakers) != set(PLAYER_COLORS):
        raise ValueError("Provide exactly one word marker for each player.")
    for word in words:
        _validate_overlay_text(word.text, f"The {word.speaker} player's word")
        if not math.isfinite(word.x_percent) or not 0 <= word.x_percent <= 100:
            raise ValueError(f"{word.speaker} x position must be between 0 and 100.")
        if not math.isfinite(word.y_percent) or not 0 <= word.y_percent <= 100:
            raise ValueError(f"{word.speaker} y position must be between 0 and 100.")


def _rgb_to_ass_color(value: str) -> str:
    normalized = value.removeprefix("#")
    if len(normalized) != 6:
        raise ValueError(f"Expected a six-digit RGB color, got {value!r}.")
    red, green, blue = (
        int(normalized[index : index + 2], 16) for index in (0, 2, 4)
    )
    return f"&H00{blue:02X}{green:02X}{red:02X}"


def _estimated_text_width(text: str, font_size: int) -> float:
    narrow = " ilI!.,:;'|"
    wide = "MW@%&"
    units = sum(0.29 if char in narrow else 0.88 if char in wide else 0.54 for char in text)
    return units * font_size


def build_clue_events(
    transcript_lines: Sequence[TranscriptLine],
    words: Sequence[WordOverlay],
    width: int,
    height: int,
    duration: float,
) -> list[ClueWordEvent]:
    if width <= 0 or height <= 0:
        raise ValueError("Video dimensions must be positive.")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Video duration must be positive and finite.")
    if not 0 < CAPTION_BASELINE_PERCENT < 100:
        raise ValueError("Clue-word baseline must be between 0 and 100 percent.")
    if (
        not math.isfinite(CLUE_WORD_MAX_DURATION_SECONDS)
        or CLUE_WORD_MAX_DURATION_SECONDS <= 0
    ):
        raise ValueError("Clue-word maximum duration must be positive and finite.")
    _validate_words(words)
    baseline_y = round(height * CAPTION_BASELINE_PERCENT / 100)
    marker_x = {word.speaker: round(width * word.x_percent / 100) for word in words}
    lines_by_speaker: dict[Speaker, list[tuple[float, TranscriptLine]]] = {
        speaker: [] for speaker in PLAYER_COLORS
    }
    for line in transcript_lines:
        if line.clue_word is None:
            continue
        if not isinstance(line.clue_word, str):
            raise ValueError("A clue word must be text.")
        if not line.clue_word.strip():
            continue
        _validate_line(line)
        if line.start >= duration:
            raise ValueError("A clue word starts at or after the video duration.")
        if line.speaker is None:
            raise ValueError("Every clue word must have a valid speaker assignment.")
        display_start = clue_display_start(
            line.start, line.end, line.nudge_seconds
        )
        if display_start >= duration:
            raise ValueError("A clue word displays at or after the video duration.")
        lines_by_speaker[line.speaker].append((display_start, line))

    events: list[ClueWordEvent] = []
    for speaker in PLAYER_COLORS:
        speaker_lines = sorted(lines_by_speaker[speaker], key=lambda item: item[0])
        for current, following in zip(speaker_lines, speaker_lines[1:]):
            if current[0] == following[0]:
                raise ValueError(
                    f"Two {speaker} clue words cannot start at the same time."
                )

        for index, (display_start, line) in enumerate(speaker_lines):
            next_start = (
                speaker_lines[index + 1][0]
                if index + 1 < len(speaker_lines)
                else duration
            )
            end = min(
                display_start + CLUE_WORD_MAX_DURATION_SECONDS,
                next_start,
                duration,
            )
            events.append(
                ClueWordEvent(
                    start=display_start,
                    end=end,
                    text=line.clue_word.strip(),
                    speaker=speaker,
                    x=marker_x[speaker],
                    bottom_y=baseline_y,
                )
            )

    return sorted(events, key=lambda event: (event.start, event.speaker, event.bottom_y))


def _escape_ass_text(text: str) -> str:
    _validate_overlay_text(text, "Overlay text")
    return text


def _rounded_rectangle_path(width: int, height: int, radius: int) -> str:
    radius = max(1, min(radius, width // 2, height // 2))
    control = round(radius * 0.5523)
    return (
        f"m {radius} 0 l {width - radius} 0 "
        f"b {width - radius + control} 0 {width} {radius - control} {width} {radius} "
        f"l {width} {height - radius} "
        f"b {width} {height - radius + control} "
        f"{width - radius + control} {height} {width - radius} {height} "
        f"l {radius} {height} "
        f"b {radius - control} {height} 0 {height - radius + control} 0 {height - radius} "
        f"l 0 {radius} "
        f"b 0 {radius - control} {radius - control} 0 {radius} 0 c"
    )


def _word_events(
    words: Sequence[WordOverlay],
    width: int,
    height: int,
    duration: float,
) -> list[str]:
    scale = width / BASE_STYLE_WIDTH
    font_size = max(12, round(WORD_PILL_STYLE.font_size * scale))
    padding_x = max(1, round(WORD_PILL_STYLE.padding_x * scale))
    padding_y = max(1, round(WORD_PILL_STYLE.padding_y * scale))
    radius = max(1, round(WORD_PILL_STYLE.corner_radius * scale))
    text_outline = max(0, round(WORD_PILL_STYLE.outline_width * scale))
    start, end = ass_timestamp(0), ass_timestamp(duration)
    events: list[str] = []

    for word in words:
        color = _rgb_to_ass_color(PLAYER_COLORS[word.speaker])
        text_width = math.ceil(_estimated_text_width(word.text, font_size))
        pill_width = max(font_size, text_width + padding_x * 2)
        pill_height = font_size + padding_y * 2
        if pill_width > width or pill_height > height:
            raise ValueError(f"The {word.speaker} word pill is larger than the video frame.")
        center_x = round(width * word.x_percent / 100)
        center_y = round(height * word.y_percent / 100)
        left = max(0, min(width - pill_width, center_x - pill_width // 2))
        top = max(0, min(height - pill_height, center_y - pill_height // 2))
        center_x = left + pill_width // 2
        center_y = top + pill_height // 2
        path = _rounded_rectangle_path(pill_width, pill_height, radius)
        events.append(
            f"Dialogue: 0,{start},{end},WordText,,0,0,0,,"
            f"{{\\an7\\pos({left},{top})\\p1\\bord0\\shad0\\1c{color}}}{path}{{\\p0}}"
        )
        events.append(
            f"Dialogue: 1,{start},{end},WordText,,0,0,0,,"
            f"{{\\an5\\pos({center_x},{center_y})"
            f"\\fs{font_size}\\1c{_rgb_to_ass_color(WORD_PILL_STYLE.text_color)}"
            f"\\3c{_rgb_to_ass_color(WORD_PILL_STYLE.outline_color)}"
            f"\\bord{text_outline}\\shad0}}{_escape_ass_text(word.text)}"
        )

    return events


def build_ass_content(
    width: int,
    height: int,
    duration: float,
    words: Sequence[WordOverlay],
    transcript_lines: Sequence[TranscriptLine],
) -> str:
    if width <= 0 or height <= 0:
        raise ValueError("Video dimensions must be positive.")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Video duration must be positive and finite.")
    _validate_words(words)

    scale = width / BASE_STYLE_WIDTH
    clue_font_size = max(12, round(CLUE_WORD_STYLE.font_size * scale))
    clue_outline = max(0, round(CLUE_WORD_STYLE.outline_width * scale))
    styles = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        (
            f"Style: WordText,{WORD_PILL_STYLE.font_name},"
            f"{int(WORD_PILL_STYLE.font_size * scale)},"
            f"{_rgb_to_ass_color(WORD_PILL_STYLE.text_color)},"
            "&H000000FF,&H00000000,&H80000000,-1,0,1,"
            f"{int(WORD_PILL_STYLE.outline_width * scale)},0,5,10,10,10,1"
        ),
        (
            f"Style: ClueWord,{CLUE_WORD_STYLE.font_name},{clue_font_size},"
            f"{_rgb_to_ass_color(CLUE_WORD_STYLE.text_color)},&H000000FF,"
            f"{_rgb_to_ass_color(CLUE_WORD_STYLE.outline_color)},&H80000000,"
            f"-1,0,1,{clue_outline},0,2,0,0,0,1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = _word_events(words, width, height, duration)
    for event in build_clue_events(
        transcript_lines, words, width, height, duration
    ):
        events.append(
            f"Dialogue: 2,{ass_timestamp(event.start)},{ass_timestamp(event.end)},"
            f"ClueWord,,0,0,0,,{{\\an2\\pos({event.x},{event.bottom_y})}}"
            f"{_escape_ass_text(event.text)}"
        )
    return "\n".join([*styles, *events, ""])


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    duration: float


def _read_video_metadata(video_path: Path, ffmpeg_path: Path) -> VideoMetadata:
    os.environ["IMAGEIO_FFMPEG_EXE"] = str(ffmpeg_path)
    reader = imageio_ffmpeg.read_frames(str(video_path), pix_fmt="rgb24")
    try:
        metadata = next(reader)
        next(reader)
    except StopIteration as error:
        raise RuntimeError(f"FFmpeg could not decode a frame from {video_path}.") from error
    finally:
        reader.close()

    if not isinstance(metadata, dict):
        raise RuntimeError(f"FFmpeg returned invalid metadata for {video_path}.")
    size = metadata.get("size")
    duration = metadata.get("duration")
    if (
        not isinstance(size, (tuple, list))
        or len(size) != 2
        or not all(isinstance(dimension, int) for dimension in size)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
    ):
        raise RuntimeError(f"FFmpeg returned incomplete video metadata for {video_path}.")
    return VideoMetadata(size[0], size[1], float(duration))


def _escape_filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")


def render_annotated_video(
    input_path: Path,
    output_path: Path,
    words: Sequence[WordOverlay],
    transcript_lines: Sequence[TranscriptLine],
    ffmpeg_path: Path | None = None,
    progress_callback: Callable[[int], None] | None = None,
    timing_callback: Callable[[str, float], None] | None = None,
) -> Path:
    input_path = input_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input video not found: {input_path}")
    if input_path.suffix.lower() != ".mp4":
        raise ValueError("Input video must be an MP4.")

    ffmpeg_path = (ffmpeg_path or resolve_ffmpeg()).resolve()
    input_metadata = _read_video_metadata(input_path, ffmpeg_path)
    width, height = input_metadata.width, input_metadata.height
    duration = input_metadata.duration
    ass_path = output_path.with_suffix(".ass")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f"{output_path.stem}.partial{output_path.suffix}"
    )
    completed = False
    ffmpeg_started: float | None = None
    try:
        ass_started = perf_counter()
        try:
            ass_content = build_ass_content(
                width, height, duration, words, transcript_lines
            )
            ass_path.write_text(ass_content, encoding="utf-8")
        finally:
            if timing_callback is not None:
                timing_callback("ASS generation", perf_counter() - ass_started)

        filter_value = f"subtitles=filename='{_escape_filter_path(ass_path)}'"
        command = [
            str(ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            filter_value,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(temporary_path),
        ]
        ffmpeg_started = perf_counter()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            output_lines: list[str] = []
            last_progress = -1
            try:
                if process.stdout is None:
                    raise RuntimeError("FFmpeg progress output could not be read.")
                for line in process.stdout:
                    key, separator, value = line.strip().partition("=")
                    if separator and key in ("out_time_us", "out_time_ms"):
                        try:
                            output_seconds = float(value) / 1_000_000
                        except ValueError:
                            continue
                        progress = min(99, max(0, round(output_seconds / duration * 100)))
                        if progress_callback is not None and progress != last_progress:
                            progress_callback(progress)
                        last_progress = progress
                    elif key == "progress" and value == "end":
                        if progress_callback is not None:
                            progress_callback(100)
                        last_progress = 100
                    elif line.strip():
                        output_lines.append(line.strip())
                        if len(output_lines) > 30:
                            output_lines.pop(0)
                return_code = process.wait()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

            if return_code != 0:
                raise subprocess.CalledProcessError(
                    return_code,
                    command,
                    output="\n".join(output_lines),
                )
            if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
                raise OSError("FFmpeg did not create a non-empty output MP4.")

            output_metadata = _read_video_metadata(temporary_path, ffmpeg_path)
            if (output_metadata.width, output_metadata.height) != (
                input_metadata.width,
                input_metadata.height,
            ):
                raise RuntimeError(
                    f"Output dimensions {(output_metadata.width, output_metadata.height)} "
                    f"do not match the source dimensions "
                    f"{(input_metadata.width, input_metadata.height)}."
                )
            if abs(output_metadata.duration - input_metadata.duration) > 0.5:
                raise RuntimeError(
                    f"Output duration {output_metadata.duration:.2f}s does not match "
                    f"the source duration {input_metadata.duration:.2f}s."
                )
            temporary_path.replace(output_path)
            completed = True
        finally:
            if timing_callback is not None:
                timing_callback("FFmpeg rendering", perf_counter() - ffmpeg_started)
    finally:
        if not completed and temporary_path.exists():
            temporary_path.unlink()
        ass_path.unlink(missing_ok=True)

    if progress_callback is not None and last_progress != 100:
        progress_callback(100)
    return output_path
