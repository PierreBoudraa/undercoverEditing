from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "workdir" / "spike"
MIN_DURATION_SECONDS = 30
MAX_DURATION_SECONDS = 60


def resolve_ffmpeg() -> Path:
    configured_path = os.environ.get("FFMPEG_EXE")
    if configured_path:
        path = Path(configured_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"FFMPEG_EXE does not point to a file: {path}")
        return path.resolve()

    import imageio_ffmpeg

    return Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()


def read_video_metadata(video_path: Path, ffmpeg_path: Path) -> dict[str, Any]:
    import imageio_ffmpeg

    os.environ["IMAGEIO_FFMPEG_EXE"] = str(ffmpeg_path)
    reader = imageio_ffmpeg.read_frames(str(video_path), pix_fmt="rgb24")
    try:
        metadata = next(reader)
        next(reader)
    except StopIteration as error:
        raise RuntimeError("FFmpeg could not decode a video frame.") from error
    finally:
        reader.close()

    return metadata


def format_timestamp(seconds: float) -> str:
    centiseconds = round(seconds * 100)
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{whole_seconds:02}.{fraction:02}"


def escape_filter_path(path: Path) -> str:
    normalized = path.resolve().as_posix()
    return normalized.replace(":", r"\:").replace("'", r"\'")


def write_ass_test(path: Path, width: int, height: int) -> None:
    content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,42,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,1,4,0,5,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{format_timestamp(0.5)},{format_timestamp(2.8)},Default,,0,0,0,,{{\\an5\\pos({width // 2},{height // 2})}}ASS subtitle burn-in test
"""
    path.write_text(content, encoding="utf-8")


def transcribe(video_path: Path) -> int:
    from faster_whisper import WhisperModel

    print("Transcribing with faster-whisper small on CPU (int8), French, VAD enabled...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(video_path),
        language="fr",
        vad_filter=True,
    )

    count = 0
    print(f"Detected language: {info.language} ({info.language_probability:.2f})")
    for segment in segments:
        print(
            f"[{format_timestamp(segment.start)} --> "
            f"{format_timestamp(segment.end)}] {segment.text.strip()}"
        )
        count += 1

    if count == 0:
        raise RuntimeError("No speech segments were returned for this clip.")

    return count


def burn_in_ass(video_path: Path, ffmpeg_path: Path, metadata: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ass_path = OUTPUT_DIR / "subtitle_test.ass"
    output_path = OUTPUT_DIR / "subtitle_test.mp4"
    write_ass_test(ass_path, int(metadata["size"][0]), int(metadata["size"][1]))

    filter_value = f"subtitles=filename='{escape_filter_path(ass_path)}'"
    command = [
        str(ffmpeg_path),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        "0",
        "-i",
        str(video_path),
        "-t",
        "3",
        "-vf",
        filter_value,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
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
        raise OSError("FFmpeg did not create a non-empty subtitle test MP4.")

    output_metadata = read_video_metadata(output_path, ffmpeg_path)
    if output_metadata["size"] != metadata["size"]:
        raise RuntimeError(
            f"Rendered dimensions changed from {metadata['size']} "
            f"to {output_metadata['size']}."
        )

    return output_path


def print_failure(label: str, error: Exception) -> None:
    if isinstance(error, subprocess.CalledProcessError):
        detail = str(error.stderr).strip()
    else:
        detail = f"{type(error).__name__}: {error}"
    print(f"{label}: FAIL - {detail}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Test French faster-whisper transcription and ASS subtitle burn-in "
            "on a local 30-60 second MP4."
        )
    )
    parser.add_argument("video", type=Path, help="Path to a local MP4 sample")
    args = parser.parse_args()
    video_path = args.video.expanduser().resolve()

    try:
        if not video_path.is_file():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if video_path.suffix.lower() != ".mp4":
            raise ValueError("The sample must be an MP4 file.")
        ffmpeg_path = resolve_ffmpeg()
        metadata = read_video_metadata(video_path, ffmpeg_path)
        duration = float(metadata["duration"])
        if not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS:
            raise ValueError(
                f"Sample duration is {duration:.1f} seconds; expected "
                f"{MIN_DURATION_SECONDS}-{MAX_DURATION_SECONDS} seconds."
            )
    except (FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as error:
        print_failure("TRANSCRIPTION", error)
        print_failure("ASS BURN-IN", error)
        return 1

    print(
        f"Input: {video_path.name} - {duration:.1f}s, "
        f"{metadata['size'][0]}x{metadata['size'][1]}"
    )

    passed = True
    try:
        segment_count = transcribe(video_path)
        print(f"TRANSCRIPTION: PASS - {segment_count} timestamped segments")
    except (ImportError, OSError, RuntimeError, TypeError, ValueError) as error:
        print_failure("TRANSCRIPTION", error)
        passed = False

    try:
        output_path = burn_in_ass(video_path, ffmpeg_path, metadata)
        print(f"ASS BURN-IN: PASS - playable test output: {output_path}")
    except (
        ImportError,
        OSError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        print_failure("ASS BURN-IN", error)
        passed = False

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
