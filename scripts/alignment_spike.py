from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.alignment import (
    ClueInput,
    ClueMatch,
    TranscriptWord,
    align_clue_words,
    normalize_text,
)
from app.config import (
    AUTO_ACCEPT_MAX_DISTANCE,
    CAPTION_BASELINE_PERCENT,
    CLUE_OFFSET_SECONDS,
    CLUE_WORD_STYLE,
    EXACT_MATCH_MAX_WORD_LENGTH,
    FUZZY_MATCH_MAX_DISTANCE,
    LONG_INTERVAL_THRESHOLD_SECONDS,
    LONG_INTERVAL_WORD_DURATION_SECONDS,
    MAX_COMBINED_TOKEN_COUNT,
    VERIFICATION_CLIP_LEAD_SECONDS,
    VERIFICATION_CLIP_TAIL_SECONDS,
    WORK_DIR,
    resolve_ffmpeg,
)
from app.rendering import clue_anchor_time, clue_display_start
from scripts.alignment_fixture_data import CLUE_FIXTURES
from scripts.transcription_spike import (
    escape_filter_path,
    format_timestamp,
    read_video_metadata,
)


OUTPUT_DIR = WORK_DIR / "verification_clips"
REPORT_PATH = OUTPUT_DIR / "attribution_report.json"
CLUES = tuple(
    ClueInput(fixture.clue_word, fixture.player) for fixture in CLUE_FIXTURES
)
PLAYER_MARKER_X_PERCENT = {
    "left": 22.0,
    "center": 50.0,
    "right": 78.0,
}


def transcribe_words(
    video_path: Path,
) -> tuple[list[TranscriptWord], dict[str, Any]]:
    from faster_whisper import WhisperModel

    hotwords = ", ".join(clue.clue_word for clue in CLUES)
    print(
        "Transcribing with faster-whisper small on CPU int8, French, "
        "VAD, and word timestamps..."
    )
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(video_path),
        language="fr",
        vad_filter=True,
        word_timestamps=True,
        hotwords=hotwords,
    )

    transcript_words: list[TranscriptWord] = []
    excluded_words: list[dict[str, Any]] = []
    segment_count = 0
    for segment in segments:
        segment_count += 1
        for word in segment.words or ():
            text = word.word.strip()
            if not text:
                continue
            start = float(word.start)
            end = float(word.end)
            if (
                not math.isfinite(start)
                or not math.isfinite(end)
                or start < 0
                or end <= start
            ):
                excluded_words.append(
                    {
                        "text": text,
                        "start": start,
                        "end": end,
                        "reason": "word timestamp has no positive duration",
                    }
                )
                continue
            probability = (
                float(word.probability) if word.probability is not None else None
            )
            transcript_words.append(
                TranscriptWord(
                    text=text,
                    start=start,
                    end=end,
                    probability=probability,
                )
            )
    if not transcript_words:
        raise RuntimeError(
            "faster-whisper returned no word-level timestamps; "
            "segment times will not be substituted."
        )

    info_summary = {
        "language": info.language,
        "language_probability": float(info.language_probability),
        "segment_count": segment_count,
        "word_count": len(transcript_words),
        "excluded_word_timestamps": excluded_words,
    }
    print(
        f"Transcription returned {len(transcript_words)} timestamped words "
        f"from {segment_count} segments."
    )
    if excluded_words:
        print(
            f"Warning: excluded {len(excluded_words)} words with unusable "
            "timestamps (they are listed in the JSON report)."
        )
    return transcript_words, info_summary


def _ass_color(value: str) -> str:
    normalized = value.removeprefix("#")
    if len(normalized) != 6:
        raise ValueError(f"Expected a six-digit RGB color, got {value!r}.")
    red, green, blue = (
        int(normalized[index : index + 2], 16) for index in (0, 2, 4)
    )
    return f"&H00{blue:02X}{green:02X}{red:02X}"


def _write_clue_ass(
    ass_path: Path,
    width: int,
    height: int,
    text: str,
    x: int,
    y: int,
    start: float,
    end: float,
) -> None:
    if not text.strip() or any(
        character in "\\{}" or ord(character) < 32 for character in text
    ):
        raise ValueError("Verification text must be non-empty, single-line, and safe.")
    outline = CLUE_WORD_STYLE.outline_width
    content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ClueWord,{CLUE_WORD_STYLE.font_name},{CLUE_WORD_STYLE.font_size},{_ass_color(CLUE_WORD_STYLE.text_color)},&H000000FF,{_ass_color(CLUE_WORD_STYLE.outline_color)},&H80000000,-1,0,1,{outline},0,2,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{format_timestamp(start)},{format_timestamp(end)},ClueWord,,0,0,0,,{{\\an2\\pos({x},{y})}}{text}
"""
    ass_path.write_text(content, encoding="utf-8")


def verification_clip_bounds(
    detected_start: float, duration: float
) -> tuple[float, float]:
    if not math.isfinite(detected_start) or not math.isfinite(duration):
        raise ValueError("Clip timestamps must be finite.")
    clip_length = VERIFICATION_CLIP_LEAD_SECONDS + VERIFICATION_CLIP_TAIL_SECONDS
    if duration < clip_length:
        raise ValueError(
            "The input video is too short for a three-second verification clip."
        )
    desired_start = max(0.0, detected_start - VERIFICATION_CLIP_LEAD_SECONDS)
    clip_start = min(desired_start, duration - clip_length)
    return clip_start, clip_start + clip_length


def export_verification_clip(
    video_path: Path,
    ffmpeg_path: Path,
    video_metadata: dict[str, Any],
    clue_match: ClueMatch,
    output_path: Path,
) -> tuple[float, float, float]:
    if clue_match.start is None or clue_match.end is None:
        raise ValueError("Cannot export a verification clip without a matched time.")
    duration = float(video_metadata["duration"])
    clip_start, clip_end = verification_clip_bounds(clue_match.start, duration)
    display_time = clue_display_start(clue_match.start, clue_match.end)
    clip_duration = clip_end - clip_start
    overlay_start = max(0.0, display_time - clip_start)
    if overlay_start >= clip_duration:
        raise RuntimeError(
            "The clue display time falls outside its verification clip."
        )

    width, height = (int(value) for value in video_metadata["size"])
    x_percent = PLAYER_MARKER_X_PERCENT[clue_match.speaker]
    x = round(width * x_percent / 100)
    y = round(height * CAPTION_BASELINE_PERCENT / 100)
    ass_path = output_path.with_suffix(".ass")
    _write_clue_ass(
        ass_path,
        width,
        height,
        clue_match.clue_word,
        x,
        y,
        overlay_start,
        clip_duration,
    )

    filter_value = f"subtitles=filename='{escape_filter_path(ass_path)}'"
    command = [
        str(ffmpeg_path),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{clip_start:.3f}",
        "-i",
        str(video_path),
        "-t",
        f"{clip_duration:.3f}",
        "-vf",
        filter_value,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "25",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "FFmpeg exited without diagnostic output."
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=detail,
        )
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise OSError(f"FFmpeg did not create a verification clip: {output_path}")
    return clip_start, clip_end, display_time


def serialize_match(
    match: ClueMatch,
    clue_index: int,
    video_path: Path,
    ffmpeg_path: Path,
    metadata: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    blocking = match.confidence == "not_found"
    row: dict[str, Any] = {
        "clue_word": match.clue_word,
        "player": match.speaker,
        "match_status": "not_found" if blocking else "matched",
        "matched_transcript_text": match.matched_text,
        "token_start_index": match.token_start_index,
        "token_end_index": match.token_end_index,
        "detected_start_seconds": match.start,
        "detected_end_seconds": match.end,
        "absolute_edit_distance": match.absolute_distance,
        "normalized_edit_distance": match.normalized_distance,
        "match_confidence": match.confidence,
        "review_required": match.confidence == "review",
        "render_blocked": blocking,
        "anchor_time_seconds": None,
        "display_time_seconds": None,
        "time_nudge_seconds": 0.0,
        "verification_clip": None,
    }
    if blocking:
        print(f"{clue_index + 1}. {match.clue_word} ({match.speaker}): NOT FOUND")
        return row

    if match.start is None or match.end is None:
        raise RuntimeError("A matched clue is missing word-level timestamps.")
    row["anchor_time_seconds"] = clue_anchor_time(match.start, match.end)
    row["display_time_seconds"] = clue_display_start(match.start, match.end)

    name = f"{clue_index + 1:02d}_{normalize_text(match.clue_word)}.mp4"
    clip_path = output_dir / name
    clip_start, clip_end, display_time = export_verification_clip(
        video_path,
        ffmpeg_path,
        metadata,
        match,
        clip_path,
    )
    row.update(
        {
            "display_time_seconds": display_time,
            "verification_clip": str(clip_path),
            "verification_clip_start_seconds": clip_start,
            "verification_clip_end_seconds": clip_end,
        }
    )
    print(
        f"{clue_index + 1}. {match.clue_word} ({match.speaker}): "
        f"{match.matched_text!r} at {match.start:.3f}-{match.end:.3f}s; "
        f"match={match.confidence}, "
        f"display={display_time:.3f}s, "
        f"{'needs review but does not block' if row['review_required'] else 'high confidence'}; "
        f"clip={clip_path.name}"
    )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Align ordered clue words to French word timestamps using the "
            "manually supplied player for each clue, then export verification clips."
        )
    )
    parser.add_argument("video", type=Path, help="Path to a local 30-60 second MP4")
    args = parser.parse_args()
    video_path = args.video.expanduser().resolve()
    if not video_path.is_file():
        parser.error(f"Video file not found: {video_path}")
    if video_path.suffix.lower() != ".mp4":
        parser.error("The sample must be an MP4 file.")

    try:
        ffmpeg_path = resolve_ffmpeg()
        metadata = read_video_metadata(video_path, ffmpeg_path)
        duration = float(metadata["duration"])
        if not 30 <= duration <= 60:
            raise ValueError(
                f"Sample duration is {duration:.1f}s; expected 30-60 seconds."
            )
        print(
            f"Input: {video_path.name} - {duration:.2f}s, "
            f"{metadata['size'][0]}x{metadata['size'][1]}"
        )
        transcript_words, transcription = transcribe_words(video_path)
        matches = align_clue_words(CLUES, transcript_words)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for index, clue in enumerate(CLUES, start=1):
            base_path = OUTPUT_DIR / f"{index:02d}_{normalize_text(clue.clue_word)}"
            for suffix in (".mp4", ".ass"):
                old_output = base_path.with_suffix(suffix)
                if old_output.exists():
                    old_output.unlink()

        rows = [
            serialize_match(
                match,
                index,
                video_path,
                ffmpeg_path,
                metadata,
                OUTPUT_DIR,
            )
            for index, match in enumerate(matches)
        ]
        report = {
            "input_video": str(video_path),
            "duration_seconds": duration,
            "frame_size": {
                "width": int(metadata["size"][0]),
                "height": int(metadata["size"][1]),
            },
            "transcription": transcription,
            "hotwords": [clue.clue_word for clue in CLUES],
            "player_assignments": [
                {"clue_word": clue.clue_word, "player": clue.speaker}
                for clue in CLUES
            ],
            "configuration": {
                "exact_match_max_word_length": EXACT_MATCH_MAX_WORD_LENGTH,
                "fuzzy_match_max_distance": FUZZY_MATCH_MAX_DISTANCE,
                "auto_accept_max_distance": AUTO_ACCEPT_MAX_DISTANCE,
                "max_combined_token_count": MAX_COMBINED_TOKEN_COUNT,
                "clue_offset_seconds": CLUE_OFFSET_SECONDS,
                "long_interval_threshold_seconds": LONG_INTERVAL_THRESHOLD_SECONDS,
                "long_interval_word_duration_seconds": LONG_INTERVAL_WORD_DURATION_SECONDS,
            },
            "low_confidence_blocks_rendering": False,
            "not_found_blocks_rendering": True,
            "matches": rows,
        }
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Report: {REPORT_PATH}")
        print(f"Verification clips: {OUTPUT_DIR}")
        os.startfile(str(OUTPUT_DIR))
        return 0
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"Alignment spike failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
