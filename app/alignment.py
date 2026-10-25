from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import Literal, Sequence

from app.config import (
    AUTO_ACCEPT_MAX_DISTANCE,
    EXACT_MATCH_MAX_WORD_LENGTH,
    FUZZY_MATCH_MAX_DISTANCE,
    MAX_COMBINED_TOKEN_COUNT,
)


Speaker = Literal["left", "center", "right"]


@dataclass(frozen=True)
class ClueInput:
    clue_word: str
    speaker: Speaker

    def __post_init__(self) -> None:
        if not isinstance(self.clue_word, str) or not self.clue_word.strip():
            raise ValueError("Clue words must be non-empty text.")
        if self.speaker not in ("left", "center", "right"):
            raise ValueError("Every clue must have a Left, Center, or Right player.")


@dataclass(frozen=True)
class TranscriptWord:
    text: str
    start: float
    end: float
    probability: float | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Transcript words cannot be empty.")
        if not math.isfinite(self.start) or not math.isfinite(self.end):
            raise ValueError("Transcript word timestamps must be finite.")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Transcript words must have a positive time range.")
        if self.probability is not None and not math.isfinite(self.probability):
            raise ValueError("Transcript word probability must be finite.")


@dataclass(frozen=True)
class ClueMatch:
    clue_word: str
    speaker: Speaker
    matched_text: str | None
    token_start_index: int | None
    token_end_index: int | None
    start: float | None
    end: float | None
    absolute_distance: int | None
    normalized_distance: float | None
    confidence: Literal["high", "review", "not_found"]


def parse_clue_list(text: str) -> list[ClueInput]:
    if not isinstance(text, str):
        raise ValueError("Clue list must be text.")

    speakers: dict[str, Speaker] = {
        "left": "left",
        "center": "center",
        "right": "right",
    }
    clues: list[ClueInput] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if line.count(",") != 1:
            raise ValueError(
                f"Line {line_number}: expected 'word, Left|Center|Right'."
            )
        clue_word, speaker_text = (part.strip() for part in line.split(",", 1))
        if not clue_word:
            raise ValueError(f"Line {line_number}: enter a clue word before the comma.")
        if not normalize_text(clue_word):
            raise ValueError(
                f"Line {line_number}: clue words must contain a letter or number."
            )
        if not speaker_text:
            raise ValueError(f"Line {line_number}: enter a player after the comma.")
        speaker = speakers.get(speaker_text.casefold())
        if speaker is None:
            raise ValueError(
                f"Line {line_number}: player must be Left, Center, or Right."
            )
        clues.append(ClueInput(clue_word=clue_word, speaker=speaker))

    if not clues:
        raise ValueError("Enter at least one clue as 'word, Player'.")
    return clues


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character) and character.isalnum()
    )


def levenshtein_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def _normalized_distance(target: str, candidate: str) -> tuple[int, float]:
    absolute_distance = levenshtein_distance(target, candidate)
    denominator = max(len(target), len(candidate))
    return absolute_distance, absolute_distance / denominator


def _candidate_is_acceptable(
    target: str, candidate: str, normalized_distance: float
) -> bool:
    if len(target) <= EXACT_MATCH_MAX_WORD_LENGTH:
        return target == candidate
    return normalized_distance <= FUZZY_MATCH_MAX_DISTANCE


def align_clue_words(
    clues: Sequence[ClueInput], transcript_words: Sequence[TranscriptWord]
) -> list[ClueMatch]:
    if MAX_COMBINED_TOKEN_COUNT < 1:
        raise ValueError("MAX_COMBINED_TOKEN_COUNT must be at least one.")

    normalized_transcript = [normalize_text(word.text) for word in transcript_words]
    matches: list[ClueMatch] = []
    cursor = 0

    for clue in clues:
        if not isinstance(clue, ClueInput):
            raise ValueError("Each clue must include a word and player assignment.")
        target = normalize_text(clue.clue_word)
        if not target:
            raise ValueError("Clue words must contain at least one letter or number.")

        candidates: list[tuple[int, int, int, float, ClueMatch]] = []
        for start_index in range(cursor, len(transcript_words)):
            max_count = min(
                MAX_COMBINED_TOKEN_COUNT,
                len(transcript_words) - start_index,
            )
            for token_count in range(1, max_count + 1):
                token_end_index = start_index + token_count
                candidate = "".join(
                    normalized_transcript[start_index:token_end_index]
                )
                if not candidate:
                    continue
                absolute_distance, distance = _normalized_distance(target, candidate)
                if not _candidate_is_acceptable(target, candidate, distance):
                    continue
                confidence: Literal["high", "review"] = (
                    "high" if distance <= AUTO_ACCEPT_MAX_DISTANCE else "review"
                )
                candidates.append(
                    (
                        0 if confidence == "high" else 1,
                        start_index,
                        token_count,
                        distance,
                        ClueMatch(
                            clue_word=clue.clue_word,
                            speaker=clue.speaker,
                            matched_text=" ".join(
                                word.text.strip()
                                for word in transcript_words[
                                    start_index:token_end_index
                                ]
                            ),
                            token_start_index=start_index,
                            token_end_index=token_end_index - 1,
                            start=transcript_words[start_index].start,
                            end=transcript_words[token_end_index - 1].end,
                            absolute_distance=absolute_distance,
                            normalized_distance=distance,
                            confidence=confidence,
                        ),
                    )
                )

        selected = min(candidates, default=None, key=lambda item: item[:4])
        if selected is not None:
            cursor = selected[1] + selected[2]
            matches.append(selected[4])
        else:
            matches.append(
                ClueMatch(
                    clue_word=clue.clue_word,
                    speaker=clue.speaker,
                    matched_text=None,
                    token_start_index=None,
                    token_end_index=None,
                    start=None,
                    end=None,
                    absolute_distance=None,
                    normalized_distance=None,
                    confidence="not_found",
                )
            )
    return matches
