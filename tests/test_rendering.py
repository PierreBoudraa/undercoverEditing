from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.config import (
    CLUE_STACK_BOTTOM_SAFE_PERCENT,
    CLUE_STACK_LINE_SPACING_PERCENT,
    CLUE_STACK_START_PERCENT,
    CLUE_WORD_SLANT,
    CLUE_OFFSET_SECONDS,
    LONG_INTERVAL_THRESHOLD_SECONDS,
    OVERLAY_MAX_WORD_WIDTH_PERCENT,
    CLUE_WORD_FONT_HEIGHT_PERCENT,
    POP_IN_START_SCALE_PERCENT,
    UNDERCOVER_GLOW_COLOR,
    CIVILIAN_GLOW_COLOR,
    NEUTRAL_GLOW_COLOR,
)
from app.rendering import (
    TranscriptLine,
    WordOverlay,
    _estimated_text_width,
    ass_timestamp,
    build_ass_content,
    build_clue_events,
    clue_display_start,
    infer_player_glows,
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

    def test_clue_events_stack_and_persist_until_video_end(self) -> None:
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
                (2.75, 10.0),
                (3.75, 10.0),
            ],
        )
        self.assertEqual(
            [(event.start, event.end) for event in events_by_speaker["right"]],
            [(4.75, 10.0)],
        )
        self.assertEqual(events_by_speaker["center"], [])
        self.assertEqual(
            [event.center_y for event in events_by_speaker["left"]],
            [
                round(1936 * CLUE_STACK_START_PERCENT / 100),
                round(1936 * CLUE_STACK_START_PERCENT / 100)
                + round(1936 * CLUE_STACK_LINE_SPACING_PERCENT / 100),
            ],
        )
        self.assertEqual(
            [event.x for event in events_by_speaker["left"]],
            [round(1080 * 22 / 100)] * 2,
        )

    def test_clue_event_persists_to_the_video_end(self) -> None:
        events = build_clue_events(
            (TranscriptLine(3.0, 3.6, "fin", "center"),),
            WORDS,
            1080,
            1936,
            duration=10.0,
        )

        self.assertEqual(
            [(event.start, event.end) for event in events],
            [(3.0 + CLUE_OFFSET_SECONDS, 10.0)],
        )

    def test_clue_stack_fits_above_the_bottom_safe_margin(self) -> None:
        lines = tuple(
            TranscriptLine(index + 1.0, index + 1.2, "psychiatrique", "left")
            for index in range(8)
        )
        events = build_clue_events(lines, WORDS, 1080, 1936, duration=10.0)
        safe_y = round(1936 * CLUE_STACK_BOTTOM_SAFE_PERCENT / 100)
        base_font_size = round(1936 * CLUE_WORD_FONT_HEIGHT_PERCENT / 100)

        self.assertEqual(len(events), 8)
        self.assertLess(events[0].font_size, base_font_size)
        self.assertLessEqual(
            events[-1].center_y + events[-1].font_size / 2,
            safe_y,
        )
        self.assertTrue(
            all(
                (
                    _estimated_text_width(event.text.upper(), event.font_size)
                    + event.font_size * abs(CLUE_WORD_SLANT)
                )
                * POP_IN_START_SCALE_PERCENT
                / 100
                <= 1080 * OVERLAY_MAX_WORD_WIDTH_PERCENT / 100
                for event in events
            )
        )

    def test_role_glows_identify_only_one_unique_word_as_undercover(self) -> None:
        glows = infer_player_glows(
            (
                WordOverlay("Asile", "left", 18, 42),
                WordOverlay("asile", "center", 50, 42),
                WordOverlay("Prison", "right", 82, 42),
            )
        )

        self.assertEqual(
            glows,
            {
                "left": CIVILIAN_GLOW_COLOR,
                "center": CIVILIAN_GLOW_COLOR,
                "right": UNDERCOVER_GLOW_COLOR,
            },
        )

    def test_role_glow_is_neutral_for_all_equal_or_all_different_words(self) -> None:
        for player_words in (
            ("same", "same", "same"),
            ("left", "center", "right"),
        ):
            with self.subTest(player_words=player_words):
                glows = infer_player_glows(
                    tuple(
                        WordOverlay(text, speaker, 50, 40)
                        for text, speaker in zip(
                            player_words, ("left", "center", "right")
                        )
                    )
                )
                self.assertEqual(
                    glows,
                    {speaker: NEUTRAL_GLOW_COLOR for speaker in ("left", "center", "right")},
                )

    def test_display_time_uses_end_anchor_only_for_long_intervals(self) -> None:
        self.assertEqual(clue_display_start(20.09, 20.35), 20.34)
        self.assertEqual(clue_display_start(52.21, 52.95), 52.46)
        self.assertEqual(clue_display_start(27.19, 28.49), 28.24)
        self.assertEqual(
            clue_display_start(3.0, 3.0 + LONG_INTERVAL_THRESHOLD_SECONDS),
            3.25,
        )

    def test_display_time_applies_the_review_nudge(self) -> None:
        self.assertEqual(clue_display_start(27.19, 28.49, 0.1), 28.34)
        self.assertAlmostEqual(clue_display_start(27.19, 28.49, -0.1), 28.14)

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

    def test_ass_contains_text_overlays_and_single_line_clue_word(self) -> None:
        content = build_ass_content(
            1080,
            1936,
            58,
            (
                WordOverlay("north", "left", 22, 42),
                WordOverlay("north", "center", 50, 42),
                WordOverlay("south", "right", 78, 42),
            ),
            (TranscriptLine(18.47, 20.47, "psychiatrique", "left"),),
        )
        clue_dialogues = [
            line for line in content.splitlines() if line.startswith("Dialogue: 10,")
        ]
        events = content.splitlines()
        clue_word_dialogues = [
            line for line in events if line.endswith("PSYCHIATRIQUE")
        ]
        title_glow_dialogues = [
            line
            for line in events
            if line.startswith(("Dialogue: 0,", "Dialogue: 1,"))
        ]
        player_word_dialogues = [
            line
            for line in events
            if line.startswith(("Dialogue: 2,", "Dialogue: 3,", "Dialogue: 4,"))
        ]

        self.assertIn("PlayResX: 1080", content)
        self.assertIn("PlayResY: 1936", content)
        self.assertIn("Style: OverlayText,Chewy,", content)
        self.assertIn("Undercover", content)
        self.assertIn("Dialogue: 2,0:00:00.00,0:00:58.00", content)
        self.assertIn("NORTH", content)
        self.assertIn("NORTH", content)
        self.assertIn("SOUTH", content)
        self.assertNotIn(r"\p1", content)
        self.assertTrue(any(r"\fnChewy" in line for line in events))
        self.assertTrue(all(r"\fax" not in line for line in player_word_dialogues))
        self.assertTrue(any(r"\t(0,150,\fscx100\fscy100)" in line for line in events))
        self.assertEqual(len(title_glow_dialogues), 2)
        self.assertTrue(all(r"\fax" not in line for line in title_glow_dialogues))
        self.assertTrue(
            all(r"\3a&H00&" in line for line in title_glow_dialogues)
        )
        self.assertTrue(
            all(
                r"\t(0,150,\fscx100\fscy100)" in line
                for line in title_glow_dialogues
            )
        )
        self.assertNotEqual(
            title_glow_dialogues[0].split(r"\blur", 1)[1].split("\\", 1)[0],
            title_glow_dialogues[1].split(r"\blur", 1)[1].split("\\", 1)[0],
        )
        self.assertIn("0:00:20.22", clue_dialogues[0])
        self.assertIn("0:00:58.00", clue_dialogues[0])
        self.assertIn(r"\pos(238,1316)", clue_dialogues[0])
        self.assertIn(_ass_color(CIVILIAN_GLOW_COLOR), content)
        self.assertIn(_ass_color(UNDERCOVER_GLOW_COLOR), content)
        self.assertEqual(len(clue_word_dialogues), 3)
        self.assertTrue(
            all(
                f"\\fax{CLUE_WORD_SLANT:g}" in line
                for line in clue_word_dialogues
            )
        )
        self.assertNotIn(r"\N", content)
        self.assertEqual(clue_dialogues[0].rsplit("}", 1)[-1], "PSYCHIATRIQUE")
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
            line for line in content.splitlines() if line.startswith("Dialogue: 10,")
        ]

        self.assertEqual(len(clue_dialogues), 3)
        for clue_word in ("FIRST", "SECOND", "THIRD"):
            self.assertIn(clue_word, content)
        self.assertTrue(all("0:00:58.00" in line for line in clue_dialogues))
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
            command_arguments: list[str] = []

            def start_fake_ffmpeg(command, **_options):
                command_arguments.extend(command)
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
            self.assertIn("fontsdir=", command_arguments[command_arguments.index("-vf") + 1])


def _ass_color(value: str) -> str:
    red, green, blue = (
        int(value[index : index + 2], 16) for index in (1, 3, 5)
    )
    return f"&H00{blue:02X}{green:02X}{red:02X}"


if __name__ == "__main__":
    unittest.main()
