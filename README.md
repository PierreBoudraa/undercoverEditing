# Undercover Video Maker

Undercover Video Maker is a local Windows app for turning a short French Undercover recording into an edited MP4. It transcribes the clip, aligns creator-supplied clue words to timestamps, and renders each player's word and assigned clue words onto the video.

## Full flow

Upload → Words → Transcript → Render.

1. **Upload** a readable MP4 between 30 and 60 seconds long.
2. **Words:** enter one word for each player, click above each player's head to place its marker, then enter clue assignments in the order spoken. Use one `word, Left|Center|Right` entry per line, for example `psychiatrique, Left`.
3. **Transcript:** run local French transcription, review the matched word and timing, change a player or nudge timing, and manually select a transcript word for any not-found clue. Low-confidence matches are allowed; not-found clues must be resolved or deleted before rendering.
4. **Render:** preview and download the MP4. Return to Transcript to correct an entry and render again without redoing Upload or Words.

## How to run (Windows)

Requirements: Python 3.13 and internet access on the first transcription run. From the project folder, create the environment, install the pinned dependencies, and start the local server:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. On the first transcription, faster-whisper downloads its model to the local cache; later runs reuse it. Transcription uses the local CPU by default and requires no API key.

### FFmpeg

The app first uses the FFmpeg executable bundled with `imageio-ffmpeg`; it must include the ASS subtitle filter. If that filter is unavailable, install a full Windows build and set `FFMPEG_EXE` in the same PowerShell window before starting the app:

```powershell
winget install --id Gyan.FFmpeg.Shared --exact
$env:FFMPEG_EXE = "C:\path\to\ffmpeg.exe"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Sample processing timings

One local run on a 58-second clip took about 92 seconds overall. These are observations from one machine, not a performance benchmark.

| Stage | Time |
| --- | ---: |
| Model load | 5.1 s |
| Transcription | 71.8 s |
| Alignment | 0.05 s |
| ASS generation | 0.01 s |
| FFmpeg rendering | 14.7 s |

A corrected rerender took about 16 seconds in FFmpeg. The stages are timed separately so future performance work can focus on the actual bottleneck.

## Speaker assignment

The creator enters each clue's player explicitly; automatic speaker attribution is not used. A motion-based attribution experiment was dropped after only 2 of 4 player suggestions looked correct on the sample.

## Project documents

- [Project scope](devpost/scope.md)
- [Product requirements](devpost/prd.md)
- [Technical specification](devpost/spec.md)
- [Build checklist and review record](devpost/checklist.md)
- [App map](devpost/app-map.html)

Keep personal video samples and rendered MP4s out of Git. They are local work files and are ignored by `.gitignore`.
