from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import main
from app.media import MediaInfo


class RenderApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_session = main.active_session
        self.previous_job = main.processing_job
        main.processing_job = None
        main.active_session = main.ActiveSession(
            video_path=Path("sample.mp4"),
            media=MediaInfo(58.0, 1080, 1936),
            setup={
                "player_words": {
                    "left": "Pomme",
                    "center": "Banane",
                    "right": "Orange",
                },
                "marker_positions": {
                    "left": {"x": 20.0, "y": 25.0},
                    "center": {"x": 50.0, "y": 25.0},
                    "right": {"x": 80.0, "y": 25.0},
                },
                "clue_text": "Monopoly, Left",
                "clues": [{"word": "Monopoly", "player": "left"}],
            },
            transcription_info={"language": "fr"},
            clue_entries=[
                main.ClueReviewEntry(
                    id="matched-clue",
                    clue_word="Monopoly",
                    speaker="left",
                    matched_text="Monopoly",
                    token_start_index=4,
                    token_end_index=4,
                    start=2.0,
                    end=2.4,
                    absolute_distance=0,
                    normalized_distance=0.0,
                    confidence="high",
                    review_status="accepted",
                    time_nudge_seconds=0.1,
                    display_time_seconds=1.95,
                )
            ],
        )

    def tearDown(self) -> None:
        main.active_session = self.previous_session
        main.processing_job = self.previous_job

    def test_requires_a_found_clue_to_render(self) -> None:
        main.active_session.clue_entries = []

        with self.assertRaises(HTTPException) as context:
            main.start_render()

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("At least one clue", context.exception.detail)

    def test_not_found_clues_block_rendering(self) -> None:
        main.active_session.clue_entries[0].confidence = "not_found"
        main.active_session.clue_entries[0].start = None
        main.active_session.clue_entries[0].end = None

        with self.assertRaises(HTTPException) as context:
            main.start_render()

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("not-found", context.exception.detail)

    def test_queues_render_with_player_positions_and_matched_lines(self) -> None:
        with patch.object(main.threading, "Thread") as thread:
            job = main.start_render()

        self.assertEqual(job["kind"], "render")
        self.assertEqual(job["state"], "queued")
        thread.assert_called_once()
        args = thread.call_args.kwargs["args"]
        self.assertEqual(args[0], job["id"])
        self.assertEqual(
            [
                (word.speaker, word.text, word.x_percent, word.y_percent)
                for word in args[2]
            ],
            [
                ("left", "Pomme", 20.0, 25.0),
                ("center", "Banane", 50.0, 25.0),
                ("right", "Orange", 80.0, 25.0),
            ],
        )
        self.assertEqual(
            (
                args[3][0].start,
                args[3][0].end,
                args[3][0].clue_word,
                args[3][0].speaker,
                args[3][0].nudge_seconds,
            ),
            (2.0, 2.4, "Monopoly", "left", 0.1),
        )


if __name__ == "__main__":
    unittest.main()
