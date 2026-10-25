# Undercover Video Maker

A local Windows app for turning a short, fixed-shot French Undercover clip into an MP4 with ordered clue words aligned to speech and placed beneath the manually selected player.

## Requirements

- Windows
- Python 3.13 (the project runtime; do not install or use another Python version)
- Internet access on first transcription run to download the faster-whisper model

## Setup and Windows transcription spike

From the project folder, create the virtual environment with Python 3.13 and install the pinned dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\transcription_spike.py "C:\path\to\sample.mp4"
```

The sample must be an MP4 between 30 and 60 seconds. The spike prints timestamped French transcription lines and separate PASS/FAIL results for transcription and ASS subtitle burn-in. It writes a short subtitle test video under `workdir\spike\`; open it to confirm the text is visible.

## Run the manual-player alignment spike

The spike transcribes word-level timestamps, aligns the ordered clue list, applies the configured display timing, and writes a JSON report plus three-second verification clips:

```powershell
.\.venv\Scripts\python.exe scripts\alignment_spike.py "C:\path\to\sample.mp4"
```

The sample fixture contains the ordered assignments `psychiatrique, Left`, `fou, Center`, `Monopoly, Right`, and `abandonné, Left`. Results are written under `workdir\verification_clips\`; the script opens that folder after it finishes. Check the report's match confidence, manually supplied player, anchor time, display time, and clip for each found clue. Low-confidence matches need a look but do not block rendering; only a not-found clue blocks it.

The earlier motion-attribution experiment was dropped after 2 of 4 player suggestions looked correct on the sample.

For display timing, intervals longer than 0.8 seconds anchor at the later of the interval start or 0.5 seconds before its end. Shorter intervals anchor at their start. The configured `CLUE_OFFSET_SECONDS` is then applied; review nudges are 0.1 seconds.

Planning references: [scope](devpost/scope.md), [PRD](devpost/prd.md), [technical spec](devpost/spec.md).

If the bundled FFmpeg fails the ASS test, install the approved full build and configure its executable explicitly:

```powershell
winget install --id Gyan.FFmpeg.Shared --exact
$env:FFMPEG_EXE = "C:\path\to\ffmpeg.exe"
.\.venv\Scripts\python.exe scripts\transcription_spike.py "C:\path\to\sample.mp4"
```

## Run the local app

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The app supports Upload, Words, and Transcript: upload a readable 30–60 second MP4, enter each player's word, click the first-frame preview to place their marker, and enter ordered clues as `word, Left|Center|Right`. Save the setup, then start local French transcription. The first transcription run may download the faster-whisper model. Review each matched clue, adjust its player or timing, accept low-confidence matches, and select a transcript word for any not-found clue. Rendering is the next build step.

The app runs locally; no account, API key, database, or deployment is needed.

Keep personal video samples and rendered MP4s out of Git. They are ignored by `.gitignore`.
