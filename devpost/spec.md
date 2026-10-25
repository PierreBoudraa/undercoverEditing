---
doc: spec
status: approved
---

# Undercover Video Maker — Technical Spec

## How This Works, In Plain Language

The app runs on your Windows computer. A web page served by a small Python app gives you the four editing steps; the page sends the clip and your edits to that local app, not to a cloud service. Python checks the MP4, runs faster-whisper on the clip, keeps the transcript and speaker choices for the current session, and asks FFmpeg to put the words and captions onto a copy of the video.

The first build step is a separate spike script: it tests transcription on a real 30–60 second French clip, then tries burning a styled ASS subtitle file into a few seconds of that clip. It prints a separate pass/fail for each check. This catches the two main technical risks before the editing interface is built. The small Whisper model is the first attempt; try medium only if the small model’s result is too poor to correct.

There is no account, database, hosted API, or web deployment. The clip and temporary work stay in a local work folder. Closing the app does not restore an unfinished session, but the last completed MP4 remains in the work folder until a new valid clip is uploaded.

## The Core Journey Through the System

PRD ref: `prd.md > The Core Journey`.

1. The browser lets the user choose a video and sends it to the local FastAPI app. The app uses FFmpeg to confirm it can read an MP4 and determine its duration. It validates only MP4 format and 30–60 seconds—not the player count or camera framing.
2. The app stores the accepted clip in the work folder and returns its dimensions and duration. The browser previews the clip, shows its first frame on Words, and maps clicks/drags to positions expressed as percentages of the original frame.
3. When the user starts transcription, the in-process job tracker starts a worker. faster-whisper runs locally with French, CPU int8, VAD filtering, and the small model; it returns timestamped segments. The browser polls the job for progress and then displays the transcript for editing and manual Left/Center/Right assignment. Cancelling this worker is optional hardening if time remains.
4. The browser sends the edited lines and word positions to the app. The renderer writes an ASS subtitle file, then runs FFmpeg to burn the three player words and timed captions into a new MP4 without cropping or resizing the input. FFmpeg's progress is translated into a percentage.
5. On completion, the browser plays and downloads the rendered file. Returning to Transcript retains the active session data for corrections and another render.

```text
Browser (one editing session)
   │ upload, edits, poll
   ▼
Local FastAPI app ─── work folder: input, session data, ASS, partial/final MP4
   ├── transcription worker ───────────── faster-whisper + cached local model
   └── managed FFmpeg process ──────────── ASS overlay + MP4 output
```

## Stack

- **Python 3.13.5** for the local app and spike, using the runtime already installed on the learner's Windows system. Verify compatible prebuilt dependency wheels in the spike; resolve any incompatibility within Python 3.13 rather than installing another Python runtime. [Python documentation](https://docs.python.org/3.13/)
- **FastAPI + Uvicorn** for a single local HTTP server that serves the page and handles the browser's upload, job, transcript, and file requests. No separate job queue or database. [FastAPI](https://fastapi.tiangolo.com/) · [Uvicorn](https://www.uvicorn.org/)
- **python-multipart** for FastAPI's multipart clip upload endpoint. [python-multipart](https://github.com/Kludex/python-multipart)
- **Plain HTML, CSS, and browser JavaScript** for the four-step interface, with no React, Node, or frontend build step.
- **faster-whisper** for local French transcription, CPU `int8`, VAD enabled, starting with `small`; test `medium` only if the first result is too poor to correct. Model files download into the local model cache on first use. [faster-whisper documentation and repository](https://github.com/SYSTRAN/faster-whisper)
- **FFmpeg** for input metadata and final MP4 rendering. First try the executable bundled by **imageio-ffmpeg**; the spike must verify that it includes the ASS/libass subtitle filter by burning in a test subtitle. If that fails, use a full system FFmpeg build and configure its executable path with `FFMPEG_EXE`; do not depend on PATH. [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) · [FFmpeg subtitles/ASS filter](https://ffmpeg.org/ffmpeg-filters.html#subtitles-1) · [ASS format guide](https://github.com/libass/libass/wiki/ASS-File-Format-Guide)
- **ASS subtitle file** for timed player words and captions. Use ASS vector drawings for the rounded word pills and normal styled subtitle events for outlined white captions. Validate the needed subtitle filter and styling in the spike before building the renderer.

The exact tested dependency set is pinned in `requirements.txt`. On Python 3.13.5, faster-whisper 1.2.1 failed with PyAV 19.0.2 because its audio decoder passes a removed `metadata_errors` argument; PyAV 16.1.0 worked from a Windows wheel. Keep the tested PyAV pin unless the full transcription spike is rerun.

## Where It Runs and How Someone Tries It

The app binds to `127.0.0.1` on the Windows computer. No API keys or deployment are needed. Internet access is needed on first run to download the selected faster-whisper model; it is cached locally for later runs. Submission still needs a short demo video and a public GitHub repository; recording the app running locally is sufficient.

PowerShell setup and first validation:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\transcription_spike.py "C:\path\to\sample.mp4"
```

The spike prints timestamped transcription lines and distinct PASS/FAIL results for transcription and ASS subtitle burn-in. It exits unsuccessfully if either check fails. If the bundled FFmpeg does not pass the burn-in test, install a full build with the documented Windows command `winget install --id Gyan.FFmpeg.Shared --exact`, then set its executable explicitly before starting the app:

```powershell
$env:FFMPEG_EXE = "C:\path\to\ffmpeg.exe"
```

Start the app and open the printed local URL:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` in a browser. For the demo, use a 30–60 second French clip, enter the three words, mark the players, review/edit/assign transcript lines, render, and play/download the output. Keep the sample clip and generated output out of the public repository.

## Look and Feel

Implement the PRD's single-column, approximately 900 px editing surface in plain CSS. Use a charcoal background, vivid purple primary controls/progress, and consistent Left coral, Center yellow, Right cyan. Orange is reserved for unassigned speakers and red for errors. Use an Inter-like sans-serif interface stack with system fallbacks; no network font dependency. Make the video and editing content prominent, with spacious controls and no sidebars or menus.

On the video, draw each entered word in a rounded pill in its player's color, centered on that player's normalized marker. Draw subtitles in white with a thick dark outline. Caption columns use the corresponding marker's x-position as center, are at most about one third of the frame width, wrap text, and clamp to remain inside the left and right edges. All three columns share a lower-frame baseline around 78% height, leaving the bottom 15% clear for social UI. When lines assigned to one player overlap, stack them in chronological order, earlier above later; the latest active line sits at the baseline and earlier lines stack upward. Recalculate positions when an overlap ends so a remaining line returns to the baseline. Different players have independent caption columns.

### Renderer fixture defaults

For the renderer fixture, use “asile” for Left and Center and “prison” for Right. The player's heads are around 47–50% of frame height; position markers against the actual frame. Set the shared caption baseline with `CAPTION_BASELINE_PERCENT = 78` in `app/config.py` so it can be adjusted.

## Components

### Local FastAPI App and Static Interface

Serve the static HTML/CSS/JavaScript and expose only local workflow endpoints. The browser owns the current visible step and user interactions; the server owns media processing and the authoritative session data. Bind to localhost only.

Implements `prd.md > Screens and Layout`, `prd.md > Look and Feel`, and `prd.md > States and Boundaries`.

### Upload and Media Validation

Accept one MP4 upload at a time. Use the configured FFmpeg executable to inspect whether the file is readable and determine duration and frame dimensions. Reject unsupported format or a duration outside 30–60 seconds with plain-language feedback. The hint's “fixed shot, 3 players” is guidance only; do not detect players or framing. Keep dimensions and aspect ratio unchanged.

Validate a candidate upload before replacing the current work. After a new valid upload is accepted, remove the prior clip, transcript/session files, partial renders, and prior final MP4, then create the new active work area. The browser previews the selected file and uses the original frame dimensions to convert marker positions into percentages.

Implements `prd.md > Upload and preview` and `prd.md > Word placement`.

### In-Process Job Tracker and API

Keep one active project session and one active processing job in memory; no external queue. Return a job ID when transcription or rendering starts. The browser polls a job-status endpoint for state, message, and progress. A cancel endpoint signals the transcription worker or terminates the FFmpeg process. FFmpeg percentage is based on its reported output time relative to the source duration.

Suggested small API surface:

- `POST /api/upload` — multipart MP4; returns validated duration and frame dimensions.
- `POST /api/transcription` — starts transcription; returns a job ID.
- `GET /api/jobs/{job_id}` — returns queued/running/completed/failed/cancelled state, message, and optional percentage.
- `DELETE /api/jobs/{job_id}` — optional cancellation endpoint, implemented in the final hardening slice only if time remains.
- `GET /api/session` — returns the active session, including transcript rows, for the browser to display.
- `PUT /api/session` — saves word positions, words, transcript text, and speaker choices for the active session.
- `POST /api/render` — starts rendering for the current session; returns a job ID.
- `GET /api/output` — serves the latest completed MP4 for preview/download.

Use ordinary HTTP polling; no WebSockets or external job system. The core flow shows progress/status; detailed cancellation is optional hardening. If implemented, Whisper cancellation is cooperative between generated segments: the current inference step may finish before the worker stops and the UI returns to Words. FFmpeg is a subprocess and can be terminated directly; discard its partial output before returning to Transcript.

Implements `prd.md > Word placement`, `prd.md > Transcript review and speaker assignment`, `prd.md > Render and download`, and `prd.md > States and Boundaries`.

### Transcription Worker

Load the configured faster-whisper model on CPU with `compute_type="int8"`, `language="fr"`, and VAD enabled. Start with `small`; print or log timestamped segments. Do not attempt automatic speaker attribution. If no segments are returned, show a basic no-speech message; if the model cannot load or the file cannot be read, report a plain-language failure. Detailed retry/recovery and diagnostic logging are optional hardening if time remains.

The spike uses this same transcription setup before the UI is built. The user evaluates readability on the sample; no numeric accuracy target is established. If small output needs too many corrections, rerun the spike with medium and compare quality against speed before choosing the model for the app.

Implements `prd.md > What We're Building`, `prd.md > Transcript review and speaker assignment`, and `prd.md > Deferred From the POC`.

### Transcript Review Interface

Represent each transcript row with an ID, start and end seconds, editable text, and optional speaker value (`left`, `center`, `right`). Show rows in time order. The browser lets the user seek/play a row's time range, edit its text, assign/change its speaker, delete it, and undo the last deletion. Disable rendering when any line lacks a speaker or no lines remain. Save edits to the active session before a render starts.

Implements `prd.md > Transcript review and speaker assignment` and `prd.md > States and Boundaries`.

### ASS Renderer and Download

Generate an ASS file from the current session. Store marker coordinates as normalized percentages of the source frame, then scale them against the original width and height when producing the overlay. Use ASS for word labels and timed lines; use vector paths for rounded word-pill shapes. For captions, clamp each player's horizontal center so the one-third-frame maximum width stays in frame. Build timed caption events so simultaneously active lines for one speaker stack in chronological order and a remaining line returns to the shared baseline after another ends.

Run FFmpeg with argument arrays (not through a shell), the original MP4 as input, and an ASS filter. Escape the ASS filename for FFmpeg's filter parser separately from normal Windows process arguments. Re-encode video only as needed to burn in overlays, preserving source width, height, and aspect ratio; keep the audio synchronized and unchanged where the source permits. Write to a partial filename, report progress, and rename to the final output only after success. On failure, remove the partial file and preserve any earlier completed output for the active clip. If cancellation hardening is implemented, cancellation also removes its partial file.

The spike must test the configured binary with a short sample segment and a one-line styled ASS subtitle; print a separate ASS burn-in PASS/FAIL, and verify the resulting MP4 plays with visible text. Test rounded vector styling as part of the same smoke test if feasible; the full player layout is implemented only after the filter check passes.

Implements `prd.md > Render and download`, `prd.md > What We're Building`, and `prd.md > States and Boundaries`.

### Hand-Written Render Fixture

Provide `scripts/render_fixture.py` as a headless proof of the renderer. It passes a small clearly labeled in-code fixture—three words, normalized marker positions, and a few timed lines with manually assigned speakers—to the same ASS/rendering functions used by the app and writes a sample MP4. It has no UI and is not a replacement for live transcription or the app journey. Use it to inspect the Undercover composition before connecting the renderer to browser edits.

Implements `prd.md > The Unique Kernel` and `prd.md > What "Working" Looks Like`.

### Local Logging

If time remains for hardening, write technical exceptions and FFmpeg/transcription diagnostics to `logs/app.log`; show only plain-language messages and retry/back actions in the interface. Keep logs outside the per-clip work folder so replacing a clip does not erase diagnostics. Do not log transcript contents unnecessarily.

Implements `prd.md > Transcript review and speaker assignment`, `prd.md > Render and download`, and `prd.md > States and Boundaries`.

## Data Model

- **Active session (memory):** session ID, uploaded file path, duration, original width/height, three words, normalized marker positions, transcript rows and latest render status. It exists only while the app process is running; the app does not restore it after restart.
- **Transcript row:** stable row ID, start/end timestamps in seconds, editable text, and nullable speaker. The server stores and updates these when the browser submits edits.
- **Job (memory):** ID, type (`transcription` or `render`), state, user-facing status, optional percentage, and output/error reference. A cancellation signal is added only if the optional hardening slice is built. The job is removed or replaced after resolution.
- **Work files:** current input, a session JSON/transcript copy, ASS file, and render partial live under `workdir/current/`. `workdir/final.mp4` is the latest completed MP4. A newly accepted valid upload cleans the old work and final output; failure deletes only partial output. If cancellation hardening is built, cancellation also deletes its partial output. The final MP4 survives app exit and remains until a new valid clip is uploaded.
- **Model cache:** faster-whisper's downloaded model stays in the normal local cache across runs; it is not part of the per-video work folder.
- **Logs:** if optional diagnostic logging is implemented, technical details go to `logs/app.log`, outside the cleaned work folder.
- **Repository hygiene:** ignore `workdir/`, logs, virtual environment, and generated model/media files. Do not commit source videos or rendered personal clips.

## File Structure

```text
undercoverEditing/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, local API, static page
│   ├── config.py               # work paths, FFMPEG_EXE, and caption baseline
│   ├── jobs.py                 # in-process job state and cancellation
│   ├── media.py                # MP4 readability/duration inspection
│   ├── transcription.py        # faster-whisper setup and segment results
│   ├── rendering.py            # ASS generation and FFmpeg process
│   └── static/
│       ├── index.html          # four-step interface
│       ├── styles.css          # theme, player colors, responsive layout
│       └── app.js              # step navigation, preview, edits, polling
├── scripts/
│   ├── transcription_spike.py  # Windows transcription + ASS burn-in checks
│   └── render_fixture.py       # hand-written-data annotated MP4 proof, no UI
├── workdir/                    # ignored: current input/session and final MP4
├── logs/                       # ignored: technical app log
├── devpost/                    # planning and learning documents
├── requirements.txt            # pinned Python dependencies after spike
├── .gitignore                  # excludes local media, logs, and environments
└── README.md                   # setup, FFmpeg fallback, and local run steps
```

## External Services and Dependencies

- **No hosted service:** no API calls, accounts, keys, or cloud deployment.
- **faster-whisper model download:** first model use downloads weights from the model repository into the local cache; later runs use that cache. No API key is planned. [faster-whisper model and installation documentation](https://github.com/SYSTRAN/faster-whisper)
- **FFmpeg binary:** first try `imageio-ffmpeg`'s bundled executable. Verify the `ass`/`subtitles` filter at the spike. If unavailable, use the documented Gyan full-build install and explicitly configure `FFMPEG_EXE`. [imageio-ffmpeg bundled binary details](https://github.com/imageio/imageio-ffmpeg) · [FFmpeg filter documentation](https://ffmpeg.org/ffmpeg-filters.html#subtitles-1)
- **No database, external storage, or frontend package service.**

## Important Failure Modes

- **Model cannot install/load or CPU transcription is too slow/poor** → spike reports transcription FAIL and prints any available segments; test medium only if small is not readable. Do not build the full workflow until the Windows sample test passes.
- **Bundled FFmpeg lacks ASS/libass or cannot render the sample** → spike reports burn-in FAIL; install the full Windows build and set `FFMPEG_EXE`, then rerun the same test.
- **Upload or rendering input is unreadable / FFmpeg fails** → display a basic plain-language error and remove partial output. Preserving all work, retry/back actions, and diagnostic logs are optional hardening if time remains.

## What Was Simplified and Why

- One local FastAPI process and one active session instead of accounts, a database, or a job-queue service — enough for one creator and a short demo.
- In-memory editing state plus local work files instead of resume/recovery across restarts — preserves the approved no-database boundary.
- Manual speaker assignment instead of diarization — avoids the most uncertain part of overlapping speech and keeps the rendered proof controllable.
- Small Whisper model first, medium only if needed — tests the fastest plausible local path before increasing model cost.
- Fixed-shot player markers and source dimensions instead of face tracking or crop conversion — preserves manual placement without requiring tracking or coordinate remapping across formats.
- Polling instead of real-time sockets — sufficient for one local job and easier to debug.
- Basic progress and plain-language errors in the core flow; detailed cancellation, retry/recovery, and diagnostic logging are deferred so the complete manual-attribution render is built first.

## Decisions and Open Issues

### Decisions

- **Learner-approved stack:** Python + FastAPI, static HTML/CSS/vanilla JavaScript, faster-whisper on CPU int8, and FFmpeg with ASS overlays. No React, Node, database, or hosted services.
- **Learner-approved core job flow:** one in-process job tracker and browser polling for progress. Detailed cancellation of transcription/FFmpeg is optional hardening if time remains; Whisper cancellation is cooperative at segment boundaries, while FFmpeg can be terminated as a process.
- **Learner-approved file lifetime:** current clip/session files and old final output are cleaned only when a new valid clip is accepted. The newest final MP4 remains after app exit; an unfinished session is not restored after restart.
- **Learner-approved frame geometry:** preserve input width, height, and aspect ratio; no crop or resize. Word marker positions are normalized percentages of the original frame.
- **Learner-approved FFmpeg setup:** bundled `imageio-ffmpeg` first, with a documented full-build install and explicit `FFMPEG_EXE` fallback if the subtitle smoke test fails.
- **Learner-approved captions:** use each word marker's x-position for its caption column; shared baseline around 75–80% of frame height; max width about one third of the frame; clamp at edges and keep captions above the bottom 15%. Overlapping lines for a player stack in chronological order, with remaining lines returning to baseline when overlaps end.
- **Learner-approved build sequence:** after the transcription/ASS spike, prove the renderer headlessly with hand-written words, positions, and speaker-assigned lines, then build Upload/Words, Transcript, and Render surfaces in separate verified commits.
- **Learner-approved priority:** basic plain-language errors and progress belong in the core flow. Detailed cancellation, retry, preservation, cleanup, and diagnostic-logging behavior comes last and is conditional on remaining time.
- **Derived implementation detail:** overlays require video re-encoding, while the input remains MP4 at its original dimensions; audio should remain synchronized and be copied unchanged when compatible.

### Decisions and Checks During the Build

The learner added renderer-test words (“asile” for Left/Center, “prison” for Right) and requested a configurable 78% caption baseline in `app/config.py`; sample player heads are around 47–50% of frame height.

- The learner's useful technical uncertainty is whether faster-whisper's small CPU model can produce readable French on laughter/overlap and whether the bundled FFmpeg supports ASS burn-in on Windows. The agreed spike checks both before app code: print timestamped lines and separate PASS/FAIL results, burn a one-line ASS subtitle into a few seconds of the sample and confirm visible playback, then test medium or use the system FFmpeg fallback only when indicated by the result.
- The learner specified the already-installed Python 3.13.5 only and does not want another Python runtime installed. If a dependency fails, resolve it within 3.13 using a compatible version or alternative. Pin exact package versions that pass the Windows spike; verify a compatible FFmpeg codec/filter build there. No other product-defining decisions remain open.
