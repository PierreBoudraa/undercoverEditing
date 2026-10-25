from __future__ import annotations

import unittest

from app.media import (
    MediaInfo,
    MediaValidationError,
    parse_ffmpeg_media_info,
    validate_video_duration,
)


class MediaInfoTests(unittest.TestCase):
    def test_parses_duration_and_video_dimensions(self) -> None:
        info = parse_ffmpeg_media_info(
            "Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'clip.mp4':\n"
            "Duration: 00:00:58.17, start: 0.000000, bitrate: 1200 kb/s\n"
            "Stream #0:0: Video: h264, yuv420p, 1080x1936, 30 fps"
        )

        self.assertEqual(info, MediaInfo(58.17, 1080, 1936))

    def test_rejects_missing_metadata(self) -> None:
        with self.assertRaisesRegex(MediaValidationError, "duration and video dimensions"):
            parse_ffmpeg_media_info(
                "Input #0, mov,mp4,m4a, from 'clip.mp4':\n"
                "Invalid data found when processing input"
            )

    def test_rejects_non_mp4_container_even_when_file_has_mp4_extension(self) -> None:
        with self.assertRaisesRegex(MediaValidationError, "Choose an MP4"):
            parse_ffmpeg_media_info(
                "Input #0, matroska,webm, from 'renamed.mp4':\n"
                "Duration: 00:00:40.0\n"
                "Stream #0:0: Video: vp9, 1280x720"
            )

    def test_accepts_inclusive_duration_boundaries(self) -> None:
        validate_video_duration(30.0)
        validate_video_duration(60.0)

    def test_rejects_clips_outside_duration_boundaries(self) -> None:
        for duration in (29.99, 60.01):
            with self.subTest(duration=duration), self.assertRaisesRegex(
                MediaValidationError, "between 30 and 60 seconds"
            ):
                validate_video_duration(duration)


if __name__ == "__main__":
    unittest.main()
