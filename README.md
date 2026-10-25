# Undercover Video Maker

A local Windows app for turning a short, fixed-shot French Undercover clip into a manually corrected, captioned MP4.

## Requirements

- Windows
- Python 3.13 (the project runtime; do not install or use another Python version)
- Internet access on first transcription run to download the faster-whisper model

## Setup and transcription spike

From the project folder, create the virtual environment with Python 3.13 and install the pinned dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\transcription_spike.py "C:\path\to\sample.mp4"
```

The sample must be an MP4 between 30 and 60 seconds. The spike prints timestamped French transcription lines and separate PASS/FAIL results for transcription and ASS subtitle burn-in. It writes a short subtitle test video under `workdir\spike\`; open it to confirm the text is visible.

Whisper's `small` model can misrecognize rare words and overlapping speech. The app is designed for manual transcript correction, so treat the first transcript as a draft.

If the bundled FFmpeg fails the ASS test, install the approved full build and configure its executable explicitly:

```powershell
winget install --id Gyan.FFmpeg.Shared --exact
$env:FFMPEG_EXE = "C:\path\to\ffmpeg.exe"
.\.venv\Scripts\python.exe scripts\transcription_spike.py "C:\path\to\sample.mp4"
```

## Run the app (after the remaining build slices)

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The app runs locally; no account, API key, database, or deployment is needed.

Keep personal video samples and rendered MP4s out of Git. They are ignored by `.gitignore`.
