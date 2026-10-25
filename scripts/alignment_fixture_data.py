from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Speaker = Literal["left", "center", "right"]


@dataclass(frozen=True)
class ClueFixture:
    clue_word: str
    player: Speaker
    detected_start_seconds: float
    detected_end_seconds: float
    display_time_seconds: float


CLUE_FIXTURES = (
    ClueFixture("psychiatrique", "left", 0.60, 1.32, 0.85),
    ClueFixture("fou", "center", 20.09, 20.35, 20.34),
    ClueFixture("Monopoly", "right", 27.19, 28.49, 28.24),
    ClueFixture("abandonné", "left", 52.21, 52.95, 52.46),
)
