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
    CIVILIAN_GLOW_COLOR,
    CLUE_WORD_SLANT,
    CLUE_STACK_BOTTOM_SAFE_PERCENT,
    CLUE_STACK_LINE_SPACING_PERCENT,
    CLUE_STACK_START_PERCENT,
    CLUE_WORD_FONT_HEIGHT_PERCENT,
    CLUE_OFFSET_SECONDS,
    LONG_INTERVAL_THRESHOLD_SECONDS,
    LONG_INTERVAL_WORD_DURATION_SECONDS,
    NEUTRAL_GLOW_COLOR,
    GlowLayerStyle,
    OVERLAY_DEFAULT_FONT_SIZE,
    OVERLAY_FILL_COLOR,
    OVERLAY_FONT_DIR,
    OVERLAY_FONT_FILE,
    OVERLAY_FONT_NAME,
    OVERLAY_MAX_WORD_WIDTH_PERCENT,
    OVERLAY_OUTLINE_COLOR,
    OVERLAY_DEFAULT_OUTLINE_WIDTH,
    PLAYER_WORD_FONT_HEIGHT_PERCENT,
    PLAYER_COLORS,
    POP_IN_DURATION_MILLISECONDS,
    POP_IN_START_SCALE_PERCENT,
    TITLE_CENTER_Y_PERCENT,
    TITLE_FONT_HEIGHT_PERCENT,
    TITLE_GLOW_COLOR,
    TITLE_GLOW_LAYERS,
    TITLE_MAX_WIDTH_PERCENT,
    TITLE_OUTLINE_WIDTH_RATIO,
    TITLE_TEXT,
    UNDERCOVER_GLOW_COLOR,
    WORD_GLOW_LAYERS,
    WORD_OUTLINE_WIDTH_RATIO,
    resolve_ffmpeg,
)


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
    center_y: int
    font_size: int


def infer_player_glows(words: Sequence[WordOverlay]) -> dict[Speaker, str]:
    normalized_words = [word.text.strip().casefold() for word in words]
    word_counts = {
        text: normalized_words.count(text) for text in set(normalized_words)
    }
    unique_words = [text for text, count in word_counts.items() if count == 1]
    repeated_words = [text for text, count in word_counts.items() if count == 2]
    if len(unique_words) == 1 and len(repeated_words) == 1:
        undercover_word = unique_words[0]
        return {
            word.speaker: (
                UNDERCOVER_GLOW_COLOR
                if word.text.strip().casefold() == undercover_word
                else CIVILIAN_GLOW_COLOR
            )
            for word in words
        }
    return {word.speaker: NEUTRAL_GLOW_COLOR for word in words}


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
    units = sum(
        0.34 if char in narrow else 0.90 if char in wide else 0.59
        for char in text
    )
    return units * font_size * 1.03


def _fit_font_size(
    text: str,
    font_size: int,
    frame_width: int,
    max_width_percent: float,
    shear_x: float = 0.0,
) -> int:
    if not math.isfinite(max_width_percent) or not 0 < max_width_percent <= 100:
        raise ValueError("Overlay maximum width must be between 0 and 100 percent.")
    if not math.isfinite(shear_x):
        raise ValueError("Overlay horizontal shear must be finite.")
    max_width = (
        frame_width * max_width_percent / 100 / (POP_IN_START_SCALE_PERCENT / 100)
    )
    width_at_one_pixel = _estimated_text_width(text, 1) + abs(shear_x)
    if width_at_one_pixel <= 0:
        raise ValueError("Overlay text must have a measurable width.")
    return max(1, min(font_size, math.floor(max_width / width_at_one_pixel)))


def _stack_layout(count: int, height: int) -> tuple[list[int], int]:
    if count < 1:
        return [], 0
    if not 0 < CLUE_STACK_START_PERCENT < CLUE_STACK_BOTTOM_SAFE_PERCENT < 100:
        raise ValueError("Clue stack start and safe-margin percentages are invalid.")
    if not math.isfinite(CLUE_STACK_LINE_SPACING_PERCENT) or CLUE_STACK_LINE_SPACING_PERCENT <= 0:
        raise ValueError("Clue stack line spacing must be positive and finite.")
    available_height = (
        CLUE_STACK_BOTTOM_SAFE_PERCENT - CLUE_STACK_START_PERCENT
    ) * height / 100
    requested_font_size = round(height * CLUE_WORD_FONT_HEIGHT_PERCENT / 100)
    font_size = max(1, min(requested_font_size, math.floor(available_height / count)))
    start_y = round(height * CLUE_STACK_START_PERCENT / 100)
    if count == 1:
        return [start_y], font_size
    max_spacing = (available_height - font_size) / (count - 1)
    requested_spacing = height * CLUE_STACK_LINE_SPACING_PERCENT / 100
    spacing = max(font_size, min(requested_spacing, max_spacing))
    return [
        round(start_y + index * spacing) for index in range(count)
    ], font_size


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
    _validate_words(words)
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

        center_ys, stack_font_size = _stack_layout(len(speaker_lines), height)
        for (display_start, line), center_y in zip(speaker_lines, center_ys):
            end = duration
            events.append(
                ClueWordEvent(
                    start=display_start,
                    end=end,
                    text=line.clue_word.strip(),
                    speaker=speaker,
                    x=marker_x[speaker],
                    center_y=center_y,
                    font_size=_fit_font_size(
                        line.clue_word.strip().upper(),
                        stack_font_size,
                        width,
                        OVERLAY_MAX_WORD_WIDTH_PERCENT,
                        CLUE_WORD_SLANT,
                    ),
                )
            )

    return sorted(events, key=lambda event: (event.start, event.speaker, event.center_y))


def _escape_ass_text(text: str) -> str:
    _validate_overlay_text(text, "Overlay text")
    return text


def _text_dialogues(
    text: str,
    start: float,
    end: float,
    x: int,
    y: int,
    font_size: int,
    glow_color: str,
    glow_layers: tuple[GlowLayerStyle, ...],
    outline_width_ratio: float,
    base_layer: int,
    max_width_percent: float,
    frame_width: int,
    shear_x: float = 0.0,
) -> list[str]:
    fitted_size = _fit_font_size(
        text, font_size, frame_width, max_width_percent, shear_x
    )
    escaped_text = _escape_ass_text(text)
    shear_override = f"\\fax{shear_x:g}" if shear_x else ""
    dialogues: list[str] = []
    for layer_offset, glow_layer in enumerate(glow_layers):
        transparency = round((1 - glow_layer.opacity) * 255)
        dialogues.append(
            (
                f"Dialogue: {base_layer + layer_offset},"
                f"{ass_timestamp(start)},{ass_timestamp(end)},"
                f"OverlayText,,0,0,0,,{{\\an5\\pos({x},{y})\\fn{OVERLAY_FONT_NAME}"
                f"{shear_override}"
                f"\\fs{fitted_size}\\fscx{POP_IN_START_SCALE_PERCENT}"
                f"\\fscy{POP_IN_START_SCALE_PERCENT}"
                f"\\1c{_rgb_to_ass_color(glow_color)}\\3c{_rgb_to_ass_color(glow_color)}"
                f"\\bord{max(1, round(fitted_size * glow_layer.border_width_ratio))}"
                f"\\blur{max(1, round(fitted_size * glow_layer.blur_ratio))}"
                f"\\1a&HFF&\\3a&H{transparency:02X}&\\shad0"
                f"\\t(0,{POP_IN_DURATION_MILLISECONDS},\\fscx100\\fscy100)}}"
                f"{escaped_text}"
            )
        )
    dialogues.append(
        (
            f"Dialogue: {base_layer + len(glow_layers)},"
            f"{ass_timestamp(start)},{ass_timestamp(end)},"
            f"OverlayText,,0,0,0,,{{\\an5\\pos({x},{y})\\fn{OVERLAY_FONT_NAME}"
            f"{shear_override}"
            f"\\fs{fitted_size}\\fscx{POP_IN_START_SCALE_PERCENT}"
            f"\\fscy{POP_IN_START_SCALE_PERCENT}"
            f"\\1c{_rgb_to_ass_color(OVERLAY_FILL_COLOR)}"
            f"\\3c{_rgb_to_ass_color(OVERLAY_OUTLINE_COLOR)}"
            f"\\bord{max(1, round(fitted_size * outline_width_ratio))}"
            f"\\shad0\\t(0,{POP_IN_DURATION_MILLISECONDS},\\fscx100\\fscy100)}}"
            f"{escaped_text}"
        ),
    )
    return dialogues


def _word_events(
    words: Sequence[WordOverlay],
    width: int,
    height: int,
    duration: float,
) -> list[str]:
    glows = infer_player_glows(words)
    events: list[str] = []
    for word in words:
        events.extend(
            _text_dialogues(
                word.text.strip().upper(),
                0,
                duration,
                round(width * word.x_percent / 100),
                round(height * word.y_percent / 100),
                round(height * PLAYER_WORD_FONT_HEIGHT_PERCENT / 100),
                glows[word.speaker],
                WORD_GLOW_LAYERS,
                WORD_OUTLINE_WIDTH_RATIO,
                2,
                OVERLAY_MAX_WORD_WIDTH_PERCENT,
                width,
            )
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
            f"Style: OverlayText,{OVERLAY_FONT_NAME},{OVERLAY_DEFAULT_FONT_SIZE},"
            f"{_rgb_to_ass_color(OVERLAY_FILL_COLOR)},&H000000FF,"
            f"{_rgb_to_ass_color(OVERLAY_OUTLINE_COLOR)},&H00000000,"
            f"-1,0,1,{OVERLAY_DEFAULT_OUTLINE_WIDTH},0,5,10,10,10,1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    title = _text_dialogues(
        TITLE_TEXT,
        0,
        duration,
        width // 2,
        round(height * TITLE_CENTER_Y_PERCENT / 100),
        round(height * TITLE_FONT_HEIGHT_PERCENT / 100),
        TITLE_GLOW_COLOR,
        TITLE_GLOW_LAYERS,
        TITLE_OUTLINE_WIDTH_RATIO,
        0,
        TITLE_MAX_WIDTH_PERCENT,
        width,
    )
    events = [*title, *_word_events(words, width, height, duration)]
    player_glows = infer_player_glows(words)
    for event in build_clue_events(transcript_lines, words, width, height, duration):
        events.extend(
            _text_dialogues(
                event.text.upper(),
                event.start,
                event.end,
                event.x,
                event.center_y,
                event.font_size,
                player_glows[event.speaker],
                WORD_GLOW_LAYERS,
                WORD_OUTLINE_WIDTH_RATIO,
                8,
                OVERLAY_MAX_WORD_WIDTH_PERCENT,
                width,
                CLUE_WORD_SLANT,
            )
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
    if not OVERLAY_FONT_FILE.is_file():
        raise FileNotFoundError(
            f"The bundled overlay font is missing: {OVERLAY_FONT_FILE}"
        )

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

        filter_value = (
            f"subtitles=filename='{_escape_filter_path(ass_path)}':"
            f"fontsdir='{_escape_filter_path(OVERLAY_FONT_DIR)}'"
        )
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
