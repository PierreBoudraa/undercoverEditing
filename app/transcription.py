from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from app.alignment import TranscriptWord


class NoSpeechDetectedError(RuntimeError):
    pass


def transcribe_words(
    video_path: Path,
    hotwords: Sequence[str],
    progress_callback: Callable[[int], None] | None = None,
    timing_callback: Callable[[str, float], None] | None = None,
) -> tuple[list[TranscriptWord], dict[str, Any]]:
    from faster_whisper import WhisperModel

    model_started = perf_counter()
    model = WhisperModel("small", device="cpu", compute_type="int8")
    if timing_callback is not None:
        timing_callback("Model load", perf_counter() - model_started)

    transcription_started = perf_counter()
    segments, info = model.transcribe(
        str(video_path),
        language="fr",
        vad_filter=True,
        word_timestamps=True,
        hotwords=", ".join(hotwords),
    )

    transcript_words: list[TranscriptWord] = []
    segment_count = 0
    for segment in segments:
        segment_count += 1
        if progress_callback is not None:
            progress_callback(segment_count)
        for word in segment.words or ():
            text = word.word.strip()
            if not text or word.start is None or word.end is None:
                continue
            start = float(word.start)
            end = float(word.end)
            if not math.isfinite(start) or not math.isfinite(end) or end <= start:
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

    if timing_callback is not None:
        timing_callback("Transcription", perf_counter() - transcription_started)

    if segment_count == 0:
        raise NoSpeechDetectedError(
            "No speech was detected. Check that the clip contains audible speech and try again."
        )
    if not transcript_words:
        raise RuntimeError(
            "Transcription returned no usable word-level timestamps. "
            "Segment timestamps cannot be substituted."
        )

    return transcript_words, {
        "language": info.language,
        "language_probability": float(info.language_probability),
        "segment_count": segment_count,
        "word_count": len(transcript_words),
    }
