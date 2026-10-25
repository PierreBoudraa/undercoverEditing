from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.config import (
    CAPTION_BASELINE_PERCENT,
    CLUE_OFFSET_SECONDS,
    CLUE_WORD_MAX_DURATION_SECONDS,
    LONG_INTERVAL_THRESHOLD_SECONDS,
)
from app.rendering import (
    TranscriptLine,
    WordOverlay,
    ass_timestamp,
    build_ass_content,
    build_clue_events,
    clue_display_start,
    render_annotated_video,
    VideoMetadata,
)


WORDS = (
    WordOverlay("north", "left", 22, 42),
    WordOverlay("middle", "center", 50, 42),
    WordOverlay("south", "right", 78, 42),
)


class RenderingTests(unittest.TestCase):
    def test_ass_timestamp_formats_centiseconds(self) -> None:
        self.assertEqual(ass_timestamp(20.47), "0:00:20.47")

    def test_clue_events_end_at_next_same_player_clue_or_max_duration(self) -> None:
        lines = (
            TranscriptLine(1.0, 3.0, "fou", "left"),
            TranscriptLine(3.0, 4.0, "asile", "left"),
            TranscriptLine(2.0, 5.0, "rire", "right"),
            TranscriptLine(4.0, 5.0),
        )

        events = build_clue_events(lines, WORDS, 1080, 1936, duration=10.0)
        events_by_speaker = {
            speaker: [event for event in events if event.speaker == speaker]
            for speaker in ("left", "center", "right")
        }

        self.assertEqual(
            [(event.start, event.end) for event in events_by_speaker["left"]],
            [
                (2.35, 3.35),
                (3.35, 3.35 + CLUE_WORD_MAX_DURATION_SECONDS),
            ],
        )
        self.assertEqual(
            [(event.start, event.end) for event in events_by_speaker["right"]],
            [(4.35, 4.35 + CLUE_WORD_MAX_DURATION_SECONDS)],
        )
        self.assertEqual(events_by_speaker["center"], [])
        self.assertEqual(
            [event.x for event in events_by_speaker["left"]],
            [round(1080 * 22 / 100)] * 2,
        )
        self.assertTrue(
            all(
                event.bottom_y == round(1936 * CAPTION_BASELINE_PERCENT / 100)
                for event in events
            )
        )

    def test_clue_event_is_capped_at_video_duration(self) -> None:
        events = build_clue_events(
            (TranscriptLine(3.0, 3.6, "fin", "center"),),
            WORDS,
            1080,
            1936,
            duration=4.0,
        )

        self.assertEqual(
            [(event.start, event.end) for event in events],
            [(3.0 + CLUE_OFFSET_SECONDS, 4.0)],
        )

    def test_display_time_uses_end_anchor_only_for_long_intervals(self) -> None:
        self.assertEqual(clue_display_start(20.09, 20.35), 19.94)
        self.assertEqual(clue_display_start(52.21, 52.95), 52.06)
        self.assertEqual(clue_display_start(27.19, 28.49), 27.84)
        self.assertEqual(
            clue_display_start(3.0, 3.0 + LONG_INTERVAL_THRESHOLD_SECONDS),
            3.0 + CLUE_OFFSET_SECONDS,
        )

    def test_display_time_applies_the_review_nudge(self) -> None:
        self.assertEqual(clue_display_start(27.19, 28.49, 0.1), 27.94)
        self.assertEqual(clue_display_start(27.19, 28.49, -0.1), 27.74)

    def test_rows_without_clue_words_need_no_speaker_and_are_ignored(self) -> None:
        events = build_clue_events(
            (TranscriptLine(1.0, 2.0),),
            WORDS,
            1080,
            1936,
            duration=10.0,
        )

        self.assertEqual(events, [])

    def test_clue_word_requires_a_speaker(self) -> None:
        with self.assertRaisesRegex(ValueError, "speaker assignment"):
            build_clue_events(
                (TranscriptLine(1.0, 2.0, "fou"),),
                WORDS,
                1080,
                1936,
                duration=10.0,
            )

    def test_duplicate_same_speaker_start_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot start at the same time"):
            build_clue_events(
                (
                    TranscriptLine(1.0, 2.0, "fou", "left"),
                    TranscriptLine(1.0, 2.0, "asile", "left"),
                ),
                WORDS,
                1080,
                1936,
                duration=10.0,
            )

    def test_ass_contains_player_pills_and_single_line_clue_word(self) -> None:
        content = build_ass_content(
            1080,
            1936,
            58,
            WORDS,
            (TranscriptLine(18.47, 20.47, "psychiatrique", "left"),),
        )
        clue_dialogues = [
            line for line in content.splitlines() if line.startswith("Dialogue: 2,")
        ]

        self.assertIn("PlayResX: 1080", content)
        self.assertIn("PlayResY: 1936", content)
        self.assertIn("north", content)
        self.assertIn("middle", content)
        self.assertIn("south", content)
        self.assertIn(r"\p1", content)
        self.assertIn("Style: ClueWord,Arial,", content)
        self.assertIn("0:00:19.82", clue_dialogues[0])
        self.assertIn("0:00:23.82", clue_dialogues[0])
        self.assertIn(r"\pos(238,1510)", clue_dialogues[0])
        self.assertNotIn(r"\N", content)
        self.assertEqual(clue_dialogues[0].rsplit("}", 1)[-1], "psychiatrique")
        self.assertEqual(len(clue_dialogues), 1)

    def test_ass_rejects_backslashes_braces_and_control_characters(self) -> None:
        malformed_texts = (
            r"\N{bad}",
            r"{\bord0}hidden",
            "line\nbreak",
            "tab\tcharacter",
            "control\x01character",
        )
        for text in malformed_texts:
            with self.subTest(text=repr(text)):
                with self.assertRaisesRegex(ValueError, "ASS control characters"):
                    build_ass_content(
                        1080,
                        1936,
                        10,
                        WORDS,
                        (TranscriptLine(1.0, 2.0, text, "left"),),
                    )

    def test_ass_renders_all_matched_manual_clue_entries(self) -> None:
        transcript_lines = (
            TranscriptLine(1.0, 1.3, "first", "left"),
            TranscriptLine(2.0, 2.4, "second", "center"),
            TranscriptLine(3.0, 3.4, "third", "right"),
        )
        content = build_ass_content(1080, 1936, 58, WORDS, transcript_lines)
        clue_dialogues = [
            line for line in content.splitlines() if line.startswith("Dialogue: 2,")
        ]

        self.assertEqual(len(clue_dialogues), 3)
        for clue_word in ("first", "second", "third"):
            self.assertIn(clue_word, content)
        self.assertNotIn(r"\N", content)

    def test_invalid_timestamp_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_clue_events(
                (TranscriptLine(2, 1, "bad", "left"),),
                WORDS,
                1080,
                1936,
                duration=10.0,
            )

    def test_renderer_reports_ffmpeg_progress_and_stage_timings(self) -> None:
        class FakeProcess:
            stdout = iter(
                (
                    "out_time_us=10000000\n",
                    "progress=continue\n",
                    "out_time_us=58000000\n",
                    "progress=end\n",
                )
            )

            def wait(self) -> int:
                return 0

            def poll(self) -> int:
                return 0

            def kill(self) -> None:
                raise AssertionError("A completed FFmpeg process must not be killed.")

        with TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.mp4"
            output_path = root / "final.mp4"
            ffmpeg_path = root / "ffmpeg.exe"
            input_path.write_bytes(b"input")
            video_metadata = VideoMetadata(1080, 1936, 58.0)
            progress: list[int] = []
            timings: list[tuple[str, float]] = []

            def start_fake_ffmpeg(command, **_options):
                Path(command[-1]).write_bytes(b"rendered")
                return FakeProcess()

            with (
                patch(
                    "app.rendering._read_video_metadata",
                    return_value=video_metadata,
                ),
                patch("app.rendering.build_ass_content", return_value="[Script Info]\n"),
                patch(
                    "app.rendering.subprocess.Popen",
                    side_effect=start_fake_ffmpeg,
                ),
            ):
                render_annotated_video(
                    input_path,
                    output_path,
                    WORDS,
                    (TranscriptLine(1.0, 1.3, "fou", "left"),),
                    ffmpeg_path,
                    progress.append,
                    lambda stage, elapsed: timings.append((stage, elapsed)),
                )

            self.assertEqual(progress, [17, 99, 100])
            self.assertEqual(
                [stage for stage, _ in timings],
                ["ASS generation", "FFmpeg rendering"],
            )
            self.assertTrue(all(elapsed >= 0 for _, elapsed in timings))
            self.assertTrue(output_path.is_file())
            self.assertFalse(output_path.with_suffix(".ass").exists())


if __name__ == "__main__":
    unittest.main()
