from __future__ import annotations

import unittest
from pathlib import Path

from fastapi import HTTPException

from app import main
from app.alignment import TranscriptWord
from app.media import MediaInfo
from app.rendering import clue_display_start


class TranscriptReviewApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_session = main.active_session
        self.previous_job = main.transcription_job
        main.transcription_job = None
        main.active_session = main.ActiveSession(
            video_path=Path("sample.mp4"),
            media=MediaInfo(58.0, 1080, 1936),
            transcript_words=[
                TranscriptWord("Monopoly", 2.0, 2.4),
                TranscriptWord("rire", 3.0, 3.3),
            ],
            clue_entries=[
                main.ClueReviewEntry(
                    id="missing-clue",
                    clue_word="Monopoly",
                    speaker="left",
                    matched_text=None,
                    token_start_index=None,
                    token_end_index=None,
                    start=None,
                    end=None,
                    absolute_distance=None,
                    normalized_distance=None,
                    confidence="not_found",
                    review_status="pending",
                ),
            ],
            transcription_info={"language": "fr"},
        )

    def tearDown(self) -> None:
        main.active_session = self.previous_session
        main.transcription_job = self.previous_job

    def test_manual_transcript_selection_sets_match_and_nudged_time(self) -> None:
        response = main.save_review(
            main.ReviewRequest(
                clue_entries=[
                    main.ReviewEntryUpdate(
                        id="missing-clue",
                        clue_word="monopoly",
                        speaker="right",
                        token_start_index=0,
                        token_end_index=0,
                        manual_match=True,
                        time_nudge_seconds=0.1,
                        review_status="accepted",
                    )
                ]
            )
        )

        entry = response["clue_entries"][0]
        self.assertEqual(entry["matched_text"], "Monopoly")
        self.assertEqual(entry["speaker"], "right")
        self.assertEqual(entry["confidence"], "review")
        self.assertEqual(entry["review_status"], "accepted")
        self.assertEqual(
            entry["display_time_seconds"],
            clue_display_start(2.0, 2.4, 0.1),
        )

    def test_rejects_selection_outside_transcript(self) -> None:
        with self.assertRaises(HTTPException) as context:
            main.save_review(
                main.ReviewRequest(
                    clue_entries=[
                        main.ReviewEntryUpdate(
                            id="missing-clue",
                            clue_word="Monopoly",
                            speaker="left",
                            token_start_index=5,
                            token_end_index=5,
                            manual_match=True,
                            time_nudge_seconds=0.0,
                            review_status="pending",
                        )
                    ]
                )
            )

        self.assertEqual(context.exception.status_code, 422)

    def test_omitted_review_entries_are_deleted(self) -> None:
        main.save_review(main.ReviewRequest(clue_entries=[]))

        self.assertEqual(main.active_session.clue_entries, [])


if __name__ == "__main__":
    unittest.main()
