from __future__ import annotations

import unittest

from app.alignment import (
    ClueInput,
    TranscriptWord,
    align_clue_words,
    levenshtein_distance,
    normalize_text,
    parse_clue_list,
)
from scripts.alignment_spike import verification_clip_bounds
from scripts.alignment_fixture_data import CLUE_FIXTURES


class ClueListParserTests(unittest.TestCase):
    def test_parses_ordered_words_and_players_case_insensitively(self) -> None:
        clues = parse_clue_list(
            "psychiatrique, Left\nfou, center\nMonopoly, RIGHT\nabandonné, left"
        )

        self.assertEqual(
            clues,
            [
                ClueInput("psychiatrique", "left"),
                ClueInput("fou", "center"),
                ClueInput("Monopoly", "right"),
                ClueInput("abandonné", "left"),
            ],
        )

    def test_ignores_blank_lines(self) -> None:
        self.assertEqual(
            parse_clue_list("\nfou, Center\n\n"),
            [ClueInput("fou", "center")],
        )

    def test_reports_malformed_lines_with_line_numbers(self) -> None:
        malformed = (
            ("fou", "Line 1: expected"),
            (", Left", "Line 1: enter a clue word"),
            ("fou,", "Line 1: enter a player"),
            ("fou, Middle", "Line 1: player must be Left, Center, or Right"),
            ("fou, Left, extra", "Line 1: expected"),
        )
        for text, message in malformed:
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, message):
                parse_clue_list(text)

    def test_reports_original_line_number_after_blank_or_valid_rows(self) -> None:
        with self.assertRaisesRegex(ValueError, "Line 3: player must be"):
            parse_clue_list("fou, Left\n\nrire, Middle")

    def test_rejects_clue_without_letters_or_numbers_with_line_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "Line 1: clue words must contain"):
            parse_clue_list("?!, Left")

    def test_empty_input_requires_at_least_one_clue(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one clue"):
            parse_clue_list(" \n")


class TextMatchingTests(unittest.TestCase):
    def test_normalization_removes_accents_case_and_punctuation(self) -> None:
        self.assertEqual(normalize_text("Abandonné?!"), "abandonne")

    def test_levenshtein_distance(self) -> None:
        self.assertEqual(levenshtein_distance("monopoly", "monopoli"), 1)
        self.assertEqual(levenshtein_distance("", "word"), 4)

    def test_matches_short_words_exactly_after_normalization(self) -> None:
        words = (
            TranscriptWord("fou,", 1.0, 1.3),
            TranscriptWord("fouu", 2.0, 2.3),
        )

        matches = align_clue_words(
            (ClueInput("fou", "center"), ClueInput("fou", "left")), words
        )

        self.assertEqual(matches[0].matched_text, "fou,")
        self.assertEqual(matches[0].confidence, "high")
        self.assertEqual(matches[0].speaker, "center")
        self.assertEqual(matches[1].confidence, "not_found")

    def test_matches_multitoken_word_and_reports_edit_distances(self) -> None:
        words = (
            TranscriptWord("Ele", 3.0, 3.1),
            TranscriptWord("phan", 3.1, 3.35),
            TranscriptWord("t", 3.35, 3.7),
        )

        match = align_clue_words((ClueInput("elephantine", "left"),), words)[0]

        self.assertEqual(match.matched_text, "Ele phan t")
        self.assertEqual((match.token_start_index, match.token_end_index), (0, 2))
        self.assertEqual((match.start, match.end), (3.0, 3.7))
        self.assertIsNotNone(match.absolute_distance)
        self.assertGreater(match.normalized_distance or 0, 0.2)
        self.assertLessEqual(match.normalized_distance or 1, 0.35)
        self.assertEqual(match.confidence, "review")

    def test_auto_accepts_small_normalized_distance(self) -> None:
        match = align_clue_words(
            (ClueInput("Monopoly", "right"),),
            (TranscriptWord("monopoli", 4.0, 4.5),),
        )[0]

        self.assertEqual(match.confidence, "high")
        self.assertEqual(match.absolute_distance, 1)

    def test_exact_word_beats_fuzzy_phrase_starting_before_it(self) -> None:
        words = (
            TranscriptWord("dire", 1.0, 1.2),
            TranscriptWord("psychiatrique,", 1.2, 1.8),
        )

        match = align_clue_words((ClueInput("psychiatrique", "left"),), words)[0]

        self.assertEqual(match.matched_text, "psychiatrique,")
        self.assertEqual(match.start, 1.2)
        self.assertEqual(match.absolute_distance, 0)

    def test_searches_forward_and_does_not_reuse_matched_tokens(self) -> None:
        words = (
            TranscriptWord("fou", 1.0, 1.2),
            TranscriptWord("rire", 2.0, 2.3),
            TranscriptWord("fou", 3.0, 3.2),
        )

        matches = align_clue_words(
            (
                ClueInput("fou", "left"),
                ClueInput("fou", "center"),
                ClueInput("fou", "right"),
            ),
            words,
        )

        self.assertEqual(
            [(match.token_start_index, match.start) for match in matches[:2]],
            [(0, 1.0), (2, 3.0)],
        )
        self.assertEqual(matches[2].confidence, "not_found")

    def test_preserves_clue_spelling_and_manual_player(self) -> None:
        match = align_clue_words(
            (ClueInput("Monopoly", "right"),),
            (TranscriptWord("monopoli", 5.0, 5.4),),
        )[0]

        self.assertEqual(match.clue_word, "Monopoly")
        self.assertEqual(match.speaker, "right")

    def test_rejects_clue_without_letters_or_numbers(self) -> None:
        with self.assertRaisesRegex(ValueError, "Clue words"):
            align_clue_words((ClueInput("?!", "left"),), ())


class VerificationClipTests(unittest.TestCase):
    def test_manual_sample_fixture_contains_only_clue_players_and_times(self) -> None:
        self.assertEqual(
            [
                (
                    clue.clue_word,
                    clue.player,
                    clue.detected_start_seconds,
                    clue.detected_end_seconds,
                    clue.display_time_seconds,
                )
                for clue in CLUE_FIXTURES
            ],
            [
                ("psychiatrique", "left", 0.60, 1.32, 0.85),
                ("fou", "center", 20.09, 20.35, 20.34),
                ("Monopoly", "right", 27.19, 28.49, 28.24),
                ("abandonné", "left", 52.21, 52.95, 52.46),
            ],
        )

    def test_clip_is_three_seconds_and_starts_one_second_before_match(self) -> None:
        self.assertEqual(verification_clip_bounds(20.0, 58.0), (19.0, 22.0))

    def test_clip_at_video_end_remains_three_seconds(self) -> None:
        self.assertEqual(verification_clip_bounds(57.5, 58.0), (55.0, 58.0))

    def test_video_shorter_than_clip_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "too short"):
            verification_clip_bounds(1.0, 2.9)


if __name__ == "__main__":
    unittest.main()
