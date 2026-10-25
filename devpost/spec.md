---
doc: spec
status: approved
---

# Undercover Video Maker — Technical Spec

## How This Works, In Plain Language

The app runs on your Windows computer. A web page served by a small Python app gives you the four editing steps; the page sends the clip and your edits to that local app, not to a cloud service. Python checks the MP4, runs faster-whisper with your ordered clue list, and matches those words to word-level timestamps. You enter the player beside each clue, so the app does not guess speakers. FFmpeg places found clue words and the three player words onto a copy of the video.

The first build step is a separate spike script: it tests transcription on a real 30–60 second French clip and ASS burn-in. The alignment spike then checks word-level matching, the manually supplied players, display timing, and three-second verification clips on that sample. It keeps the uncertain local matching behavior testable before it is wired into the app. The small Whisper model is the first attempt; try medium only if its transcript is too poor to match and review.

There is no account, database, hosted API, or web deployment. The clip and temporary work stay in a local work folder. Closing the app does not restore an unfinished session, but the last completed MP4 remains in the work folder until a new valid clip is uploaded.

## The Core Journey Through the System

PRD ref: `prd.md > The Core Journey`.

1. The browser lets the user choose a video and sends it to the local FastAPI app. The app uses FFmpeg to confirm it can read an MP4 and determine its duration. It validates only MP4 format and 30–60 seconds—not the player count or camera framing.
2. The app stores the accepted clip in the work folder and returns its dimensions and duration. The browser previews the clip, shows its first frame on Words, and maps marker clicks/drags to percentages of the original frame. The user enters three player words and an ordered list of `word, Left|Center|Right` clue rows.
3. The transcription worker runs faster-whisper locally with French, CPU int8, VAD, `word_timestamps=True`, and the clue list as hotwords. Alignment searches forward once through word timestamps, including 2–3 adjacent token concatenations. Each clue keeps the player the user entered. The browser shows its transcript match, display time, player, and confidence; the user can correct a not-found match and nudge timing. Low-confidence matches are a visual cue, not a render blocker.
4. The browser sends matched entries and word positions to the app. The renderer writes an ASS subtitle file, then runs FFmpeg to burn the three player words and found clue words into a new MP4 without cropping or resizing the input. For intervals longer than 0.8 seconds, it anchors at the later of start or end minus 0.5 seconds; otherwise it uses start. It then adds the configured offset. Each clue ends at that player's next clue, its four-second cap, or the video end.
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
- **No computer-vision or speaker-diarization package:** the player assignment comes directly from the user's ordered clue rows.
- **FFmpeg** for input metadata and final MP4 rendering. First try the executable bundled by **imageio-ffmpeg**; the spike must verify that it includes the ASS/libass subtitle filter by burning in a test subtitle. If that fails, use a full system FFmpeg build and configure its executable path with `FFMPEG_EXE`; do not depend on PATH. [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) · [FFmpeg subtitles/ASS filter](https://ffmpeg.org/ffmpeg-filters.html#subtitles-1) · [ASS format guide](https://github.com/libass/libass/wiki/ASS-File-Format-Guide)
- **ASS subtitle file** for timed player words and found clue words. Use ASS vector drawings for the rounded word pills and single-line styled subtitle events for large outlined white clue words. Validate the needed subtitle filter and styling in the spike before building the renderer.

The exact tested dependency set is pinned in `requirements.txt`. On Python 3.13.5, faster-whisper 1.2.1 failed with PyAV 19.0.2 because its audio decoder passes a removed `metadata_errors` argument; PyAV 16.1.0 worked from a Windows wheel. Keep the tested PyAV pin unless the full transcription spike is rerun.

## Where It Runs and How Someone Tries It

The app binds to `127.0.0.1` on the Windows computer. No API keys or deployment are needed. Internet access is needed on first run to download the selected faster-whisper model; it is cached locally for later runs. Submission still needs a short demo video and a public GitHub repository; recording the app running locally is sufficient.

PowerShell setup and first validation:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\transcription_spike.py "C:\path\to\sample.mp4"
.\.venv\Scripts\python.exe scripts\alignment_spike.py "C:\path\to\sample.mp4"
```

The first spike prints timestamped transcription lines and distinct PASS/FAIL results for transcription and ASS subtitle burn-in. The alignment spike prints each requested word's matched transcript text/time, edit distance, manually assigned player, anchor time, and display time. It exports one three-second verification clip for each found word under `workdir\verification_clips\`, writes a JSON report, and opens that folder. Low-confidence matches remain non-blocking; only not-found rows block rendering. If bundled FFmpeg does not pass burn-in, install a full build with the documented Windows command `winget install --id Gyan.FFmpeg.Shared --exact`, then set its executable explicitly before starting the app:

```powershell
$env:FFMPEG_EXE = "C:\path\to\ffmpeg.exe"
```

Start the app and open the printed local URL:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` in a browser. For the demo, use a 30–60 second French clip, enter the three player words and ordered clue/player list, mark the players, run transcription/alignment, review flagged matches and timing, then render and play/download the output. Keep the sample clip and generated output out of the public repository.

## Look and Feel

Implement the PRD's single-column, approximately 900 px editing surface in plain CSS. Use a charcoal background, vivid purple primary controls/progress, and consistent Left coral, Center yellow, Right cyan. Orange is reserved for not-found or low-confidence entries and red for errors. Use an Inter-like sans-serif interface stack with system fallbacks; no network font dependency. Make the video and editing content prominent, with spacious controls and no sidebars or menus.

Keep Upload and Transcript minimal and task-focused. Complete and verify the end-to-end render before spending time on visual polish.

On the video, draw each entered player word in a rounded pill in its player's color, centered on that player's normalized marker. Draw every found clue in large, bold white text with a thick dark outline, centered at the assigned player's marker x-position and a shared baseline around 78% of frame height. Keep clue words on one line; do not wrap or stack them. Use the long-interval anchor rule, then add `CLUE_OFFSET_SECONDS` (default `-0.15`). For each player, end a clue at the earliest of that player's next clue start, four seconds after its start, or the video end. This keeps the bottom 15% clear for social UI.

### Renderer fixture defaults

For the renderer fixture, use “asile” for Left and Center and “prison” for Right. The player's heads are around 47–50% of frame height; position markers against the actual frame. Keep the baseline, clue offset, maximum duration, clue style, and pill style in `app/config.py`.

Keep the word-pill font, size, fill colors, padding, corner radius, and outline in `WORD_PILL_STYLE` in `app/config.py`, so the baseline and pill appearance are easy to tune together.

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
- `PUT /api/session` — saves player words/positions, ordered clue/player rows, aligned word data, review status, and manual corrections.
- `POST /api/render` — starts rendering for the current session; returns a job ID.
- `GET /api/output` — serves the latest completed MP4 for preview/download.

Use ordinary HTTP polling; no WebSockets or external job system. The core flow shows progress/status; detailed cancellation is optional hardening. If implemented, Whisper cancellation is cooperative between generated segments: the current inference step may finish before the worker stops and the UI returns to Words. FFmpeg is a subprocess and can be terminated directly; discard its partial output before returning to Transcript.

Implements `prd.md > Word placement`, `prd.md > Transcript review and manual player assignment`, `prd.md > Render and download`, and `prd.md > States and Boundaries`.

### Transcription Worker

Load faster-whisper locally on CPU with `compute_type="int8"`, `language="fr"`, `vad_filter=True`, and `word_timestamps=True`. Pass the user's ordered clue list as a comma-separated `hotwords` string. Start with `small`; if it returns no word timestamps, fail clearly rather than silently substituting segment times. If the model cannot load or the file cannot be read, report a plain-language failure. Detailed retry/recovery and diagnostic logging are optional hardening if time remains.

The first spike tests transcription before the UI is built. The alignment spike consumes its word stream. If small output is too poor to match and review, rerun with medium and compare quality against speed before choosing the app model.

Implements `prd.md > Word placement`, `prd.md > Transcript review and manual player assignment`, and `prd.md > Deferred From the POC`.

### Word Alignment and Manual Player Assignment

Normalize transcript tokens and requested words by case-folding, removing accents and punctuation. For each requested word, search forward after the previous match among one token or concatenations of two or three adjacent tokens. Prefer high-confidence candidates (distance at or below `AUTO_ACCEPT_MAX_DISTANCE`), then the earliest occurrence within that confidence tier, then the shortest token span. This avoids a loose phrase immediately before an exact word while preserving the first low-confidence occurrence when no high-confidence match exists. Each transcript token can be consumed only once. For requested words shorter than five letters, require exact normalized equality; for longer words, allow normalized Levenshtein distance up to `FUZZY_MATCH_MAX_DISTANCE = 0.35`. A larger accepted distance is low-confidence and needs review. Preserve the typed clue spelling in the render.

Parse each non-empty clue row as exactly `word, Player`, accepting Left, Center, and Right case-insensitively. Reject malformed rows with their line number. Store that player assignment with the clue; there is no automatic speaker inference. Low-confidence matches are flagged for review but do not block rendering; only not-found rows block it.

For a matched interval longer than `LONG_INTERVAL_THRESHOLD_SECONDS` (default `0.8`), calculate the anchor as `max(start, end - LONG_INTERVAL_WORD_DURATION_SECONDS)` (default `0.5` seconds). For shorter or equal intervals, use `start`. Add `CLUE_OFFSET_SECONDS` (default `-0.15`) to get the display time, then apply the user's accumulated ±0.1-second review nudges. Keep the threshold, anchor duration, offset, and nudge step in `app/config.py`.

Implements `prd.md > Word placement`, `prd.md > Transcript review and manual player assignment`, and `prd.md > States and Boundaries`.

### Transcript Review Interface

Represent each requested clue as an entry containing its typed spelling, manually assigned player, optional matched transcript text/token indices, detected start/end, normalized and absolute edit distance, confidence, review status, and accumulated timing nudge. A not-found entry has no match/time; let the user select a transcript word manually. Let the user nudge time by ±0.1 seconds, change player, edit/delete the clue, accept a single row, or use Accept all. Low-confidence results remain renderable; only not-found entries block the final render. Keep the source transcript available as context.

Implements `prd.md > Transcript review and manual player assignment` and `prd.md > States and Boundaries`.

### ASS Renderer and Download

Generate an ASS file from the current session and render every matched entry. Store marker coordinates as normalized percentages of the source frame, then scale them against the original width and height. Use ASS vector paths for rounded player-word pills and single-line styled events for clue words. Anchor long matched intervals at `max(start, end - 0.5 seconds)` and shorter intervals at `start`, then add `CLUE_OFFSET_SECONDS` and any manual nudge. End each clue at the next matched clue for that player, its configured maximum duration (about four seconds), or video end, whichever comes first. Do not wrap, stack, or clamp clue text. Reject backslashes, braces, and control characters in rendered text to prevent ASS override tags and line breaks.

Run FFmpeg with argument arrays (not through a shell), the original MP4 as input, and an ASS filter. Escape the ASS filename for FFmpeg's filter parser separately from normal Windows process arguments. Re-encode video only as needed to burn in overlays, preserving source width, height, and aspect ratio; keep the audio synchronized and unchanged where the source permits. Write to a partial filename, report progress, and rename to the final output only after success. On failure, remove the partial file and preserve any earlier completed output for the active clip. If cancellation hardening is implemented, cancellation also removes its partial file.

The spike must test the configured binary with a short sample segment and a one-line styled ASS subtitle; print a separate ASS burn-in PASS/FAIL, and verify the resulting MP4 plays with visible text. Test rounded vector styling as part of the same smoke test if feasible; the full player layout is implemented only after the filter check passes.

Implements `prd.md > Render and download`, `prd.md > What We're Building`, and `prd.md > States and Boundaries`.

### Alignment Spike and Verification Clips

Provide `scripts/alignment_spike.py` as a headless proof of word alignment and manual player assignment on the local sample. Use the ordered rows `psychiatrique, Left`, `fou, Center`, `Monopoly, Right`, and `abandonné, Left`. Print, for each request, the chosen transcript token(s), detected interval, absolute and normalized edit distance, assigned player, confidence, anchor time, display time, and whether rendering is blocked. Save the same data as JSON under `workdir\verification_clips\`.

For every found word, export a three-second MP4 starting one second before the detected start and ending two seconds after. Burn the entered spelling beneath the manually assigned player at the computed display time. Open the output folder after successful export. Do not create a clip when no match/time exists; report that explicitly. These clips are local QA artifacts and never part of the app transcript flow or repository.

Implements `prd.md > The Core Journey`, `prd.md > Transcript review and manual player assignment`, and `prd.md > What We're Building`.

### Local Logging

If time remains for hardening, write technical exceptions and FFmpeg/transcription diagnostics to `logs/app.log`; show only plain-language messages and retry/back actions in the interface. Keep logs outside the per-clip work folder so replacing a clip does not erase diagnostics. Do not log transcript contents unnecessarily.

Implements `prd.md > Transcript review and manual player assignment`, `prd.md > Render and download`, and `prd.md > States and Boundaries`.

## Data Model

- **Active session (memory):** session ID, uploaded file path, duration, original width/height, three player words, normalized marker positions, ordered clue/player rows, word transcript, aligned clue entries, review status, and latest render status. It exists only while the app process is running; the app does not restore it after restart.
- **Transcript word:** recognized token, start/end seconds, and optional recognition probability.
- **Clue entry:** stable ID, typed display spelling, manually assigned player, optional matched token text/index range, detected start/end, normalized and absolute edit distance, confidence/review status, and accumulated ±0.1-second nudge. Every matched entry creates a render event; only not-found entries block rendering.
- **Job (memory):** ID, type (`transcription` or `render`), state, user-facing status, optional percentage, and output/error reference. A cancellation signal is added only if the optional hardening slice is built. The job is removed or replaced after resolution.
- **Work files:** current input, session/transcript data, ASS file, and render partial live under `workdir/current/`. `workdir/final.mp4` is the latest completed MP4. The local alignment spike writes `workdir/verification_clips/attribution_report.json` and three-second per-word MP4s. These files are ignored and never committed. A newly accepted valid upload cleans the old work and final output; failure deletes only partial output.
- **Model cache:** faster-whisper's downloaded model stays in the normal local cache across runs; it is not part of the per-video work folder.
- **Logs:** if optional diagnostic logging is implemented, technical details go to `logs/app.log`, outside the cleaned work folder.
- **Repository hygiene:** ignore `workdir/`, logs, virtual environment, and generated model/media files. Do not commit source videos or rendered personal clips.

## File Structure

```text
undercoverEditing/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, local API, static page
│   ├── config.py               # paths, match and timing thresholds, clue style, and pill style
│   ├── jobs.py                 # in-process job state and cancellation
│   ├── media.py                # MP4 readability/duration inspection
│   ├── transcription.py        # faster-whisper word timestamps and hotwords
│   ├── alignment.py            # ordered clue parsing and sequential fuzzy matching
│   ├── rendering.py            # ASS generation and FFmpeg
│   └── static/
│       ├── index.html          # four-step interface
│       ├── styles.css          # theme, player colors, responsive layout
│       └── app.js              # step navigation, preview, edits, polling
├── scripts/
│   ├── transcription_spike.py  # Windows transcription + ASS burn-in checks
│   ├── alignment_fixture_data.py # local sample clue/player rows
│   └── alignment_spike.py      # alignment report and verification clips
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
- **No computer-vision dependency:** player assignment is explicit user input; no image analysis or speaker model is needed.
- **FFmpeg binary:** first try `imageio-ffmpeg`'s bundled executable. Verify the `ass`/`subtitles` filter at the spike. If unavailable, use the documented Gyan full-build install and explicitly configure `FFMPEG_EXE`. [imageio-ffmpeg bundled binary details](https://github.com/imageio/imageio-ffmpeg) · [FFmpeg filter documentation](https://ffmpeg.org/ffmpeg-filters.html#subtitles-1)
- **No database, external storage, or frontend package service.**

## Important Failure Modes

- **Model cannot install/load or CPU transcription is too slow/poor** → spike reports transcription FAIL and prints any available segments; test medium only if small is not readable. Do not build the full workflow until the Windows sample test passes.
- **Bundled FFmpeg lacks ASS/libass or cannot render the sample** → spike reports burn-in FAIL; install the full Windows build and set `FFMPEG_EXE`, then rerun the same test.
- **Word timestamps or ordered matching fail** → report unmatched clue words explicitly and allow manual transcript-word selection; do not invent a timestamp.
- **A clue is not found in the transcript** → mark it not found and allow manual word selection; only this unresolved state blocks rendering. Low-confidence matches remain renderable.
- **Upload or rendering input is unreadable / FFmpeg fails** → display a basic plain-language error and remove partial output. Preserving all work, retry/back actions, and diagnostic logs are optional hardening if time remains.

## What Was Simplified and Why

- One local FastAPI process and one active session instead of accounts, a database, or a job-queue service — enough for one creator and a short demo.
- In-memory editing state plus local work files instead of resume/recovery across restarts — preserves the approved no-database boundary.
- Manually supplied player assignments instead of face tracking, a learned diarization model, or a hosted service — avoids unreliable speaker guesses and keeps the proof small.
- A user-supplied ordered clue list instead of extracting every speech word — aligns only the words needed for the Undercover edit.
- One selected clue word per player at a time instead of full-sentence subtitles, with no stacking or wrapping — keeps the requested output clear and the renderer small.
- Small Whisper model first, medium only if needed — tests the fastest plausible local path before increasing model cost.
- Fixed-shot player markers and source dimensions instead of face tracking or crop conversion — preserves manual placement without requiring tracking or coordinate remapping across formats.
- Polling instead of real-time sockets — sufficient for one local job and easier to debug.
- Motion suggestions were tested and dropped after 2 of 4 assignments looked correct on the sample; the creator enters each player directly. Basic progress and plain-language errors stay in the core flow; detailed cancellation, retry/recovery, and diagnostic logging are deferred.

## Decisions and Open Issues

### Decisions

- **Learner-approved stack:** Python + FastAPI, static HTML/CSS/vanilla JavaScript, faster-whisper on CPU int8, and FFmpeg with ASS overlays. No React, Node, database, or hosted services.
- **Learner-approved core job flow:** one in-process job tracker and browser polling for progress. Detailed cancellation of transcription/FFmpeg is optional hardening if time remains; Whisper cancellation is cooperative at segment boundaries, while FFmpeg can be terminated as a process.
- **Learner-approved file lifetime:** current clip/session files and old final output are cleaned only when a new valid clip is accepted. The newest final MP4 remains after app exit; an unfinished session is not restored after restart.
- **Learner-approved frame geometry:** preserve input width, height, and aspect ratio; no crop or resize. Word marker positions are normalized percentages of the original frame.
- **Learner-approved FFmpeg setup:** bundled `imageio-ffmpeg` first, with a documented full-build install and explicit `FFMPEG_EXE` fallback if the subtitle smoke test fails.
- **Learner-approved alignment and assignment:** parse each clue as `word, Left|Center|Right`; use word-level timestamps, user-list hotwords, and forward-only normalized edit-distance matching (including 2–3 adjacent tokens). The entered player is authoritative; do not infer speakers.
- **Learner-approved confidence behavior:** low-confidence matches are orange but non-blocking, and Accept all remains available. Only not-found rows block rendering; manual transcript-word selection can resolve them.
- **Learner-approved timing:** intervals longer than `0.8` seconds anchor at `max(start, end - 0.5)`; shorter intervals anchor at `start`. Add `CLUE_OFFSET_SECONDS = -0.15` and allow ±0.1-second review nudges.
- **Clue-word output:** render every matched clue under its entered player's marker at the 78% baseline. End at that player's next clue, after at most four seconds, or at video end.
- **Learner-approved build sequence:** after the transcription/ASS spike, validate ordered matching and timing with a manual-player report and short verification clips, then build Upload/Words, Transcript review, and Render surfaces in separate verified slices.
- **Learner-approved UI priority:** keep Upload and Transcript minimal; complete the end-to-end render before spending time on visual polish.
- **Learner-approved priority:** basic plain-language errors and progress belong in the core flow. Detailed cancellation, retry, preservation, cleanup, and diagnostic-logging behavior comes last and is conditional on remaining time.
- **Derived implementation detail:** overlays require video re-encoding, while the input remains MP4 at its original dimensions; audio should remain synchronized and be copied unchanged when compatible.

### Decisions and Checks During the Build

The learner provided the ordered sample rows `psychiatrique, Left`, `fou, Center`, `Monopoly, Right`, and `abandonné, Left`. Keep the original player-word fixture labels (“asile” for Left/Center, “prison” for Right) only for render/layout tests; verification clips show each requested clue beneath its explicitly entered player.

- The useful remaining technical uncertainty is whether fuzzy word alignment and the agreed display timing remain usable on the noisy French sample; the report and clips will check this. The earlier Windows transcription/ASS spike already passed on the sample.
- The learner specified the already-installed Python 3.13.5 only and does not want another Python runtime installed. If a dependency fails, resolve it within 3.13 using a compatible version or alternative. Pin exact package versions that pass the Windows spike; verify a compatible FFmpeg codec/filter build there. No other product-defining decisions remain open.
- The learner set the 3-second verification window to begin one second before the detected word and end two seconds after. Apply the long-interval anchor rule, then the configured `-0.15` second render offset; the report includes each resulting display time.
