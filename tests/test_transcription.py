from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from app.transcription import NoSpeechDetectedError, transcribe_words


class TranscriptionWorkerTests(unittest.TestCase):
    def _run_with_segments(self, segments):
        model_calls = {}

        class FakeWhisperModel:
            def __init__(self, model_name, *, device, compute_type):
                model_calls["model"] = (model_name, device, compute_type)

            def transcribe(self, video_path, **options):
                model_calls["transcribe"] = (video_path, options)
                return iter(segments), SimpleNamespace(
                    language="fr",
                    language_probability=0.98,
                )

        fake_module = ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeWhisperModel
        return model_calls, patch.dict(sys.modules, {"faster_whisper": fake_module})

    def test_uses_approved_french_word_timestamp_configuration(self) -> None:
        segments = [
            SimpleNamespace(
                words=[
                    SimpleNamespace(
                        word=" Bonjour ",
                        start=0.1,
                        end=0.5,
                        probability=0.9,
                    ),
                ]
            ),
        ]
        model_calls, mocked_module = self._run_with_segments(segments)
        progress: list[int] = []

        with mocked_module:
            words, info = transcribe_words(
                Path("sample.mp4"),
                ["bonjour", "Monopoly"],
                progress.append,
            )

        self.assertEqual(model_calls["model"], ("small", "cpu", "int8"))
        path, options = model_calls["transcribe"]
        self.assertEqual(path, "sample.mp4")
        self.assertEqual(
            options,
            {
                "language": "fr",
                "vad_filter": True,
                "word_timestamps": True,
                "hotwords": "bonjour, Monopoly",
            },
        )
        self.assertEqual([(word.text, word.start, word.end) for word in words], [
            ("Bonjour", 0.1, 0.5),
        ])
        self.assertEqual(progress, [1])
        self.assertEqual(info["word_count"], 1)
        self.assertEqual(info["language"], "fr")

    def test_skips_words_with_unusable_timestamp_ranges(self) -> None:
        segments = [
            SimpleNamespace(
                words=[
                    SimpleNamespace(word="bad", start=None, end=0.4, probability=None),
                    SimpleNamespace(word="empty", start=0.5, end=0.5, probability=None),
                    SimpleNamespace(word="good", start=0.6, end=0.8, probability=None),
                ]
            ),
        ]
        _, mocked_module = self._run_with_segments(segments)

        with mocked_module:
            words, _ = transcribe_words(Path("sample.mp4"), [])

        self.assertEqual([word.text for word in words], ["good"])

    def test_reports_no_speech_separately(self) -> None:
        _, mocked_module = self._run_with_segments([])

        with mocked_module, self.assertRaisesRegex(NoSpeechDetectedError, "No speech"):
            transcribe_words(Path("sample.mp4"), [])

    def test_rejects_segments_without_word_level_timestamps(self) -> None:
        segments = [SimpleNamespace(words=None)]
        _, mocked_module = self._run_with_segments(segments)

        with mocked_module, self.assertRaisesRegex(RuntimeError, "word-level timestamps"):
            transcribe_words(Path("sample.mp4"), [])


if __name__ == "__main__":
    unittest.main()
