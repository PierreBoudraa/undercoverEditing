---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast

No commit or push before the user reviews and approves the regenerated sample report and verification clips. Motion-based speaker suggestions were tested and dropped after 2 of 4 assignments looked correct on the sample. Keep Upload and Transcript UI minimal; prioritize the end-to-end render over polish.

## Slices

- [x] **1. Prove Windows transcription and ASS burn-in**
  Becomes usable: A standalone command-line spike reports timestamped French transcription output and separate PASS/FAIL results for transcription and burning a visible ASS subtitle into a short section of the sample clip.
  Why now: This independently runnable spike verified the local Whisper and FFmpeg assumptions before the app was built around them.
  PRD ref: `prd.md > What We're Building`, `prd.md > Deferred From the POC`
  Spec ref: `spec.md > Transcription Worker`, `spec.md > ASS Renderer and Download`, `spec.md > Where It Runs and How Someone Tries It`
  Build: This slice was completed earlier. Its script, pinned dependencies, and ignored local outputs remain the evidence.
  Verify (mechanical): The original verification ran `.\.venv\Scripts\python.exe -m compileall scripts` and `.\.venv\Scripts\python.exe scripts\transcription_spike.py "<local sample.mp4>"`; it confirmed timestamped output and separate PASS results, and the ASS test video was inspected.
  Learner check: The Windows sample transcription and subtitle output were inspected during the earlier spike.
  Commit: Previously committed as `Add Windows transcription and ASS spike`.

- [ ] **2. Validate ordered clue alignment and display timing**
  Becomes usable: A runnable alignment spike produces a per-clue report and three-second verification clips from the local sample, making word matches, manually assigned players, and computed display times inspectable before UI integration.
  Why now: Word alignment and timing are the remaining algorithmic uncertainties. Testing them independently exposes failures before the browser workflow is built; the regenerated result must be approved before any commit.
  PRD ref: `prd.md > Transcript review and manual player assignment`, `prd.md > Word placement`
  Spec ref: `spec.md > Transcription Worker`, `spec.md > Word Alignment and Manual Player Assignment`, `spec.md > Alignment Spike and Verification Clips`, `spec.md > Data Model`, `spec.md > Where It Runs and How Someone Tries It`
  Build: Parse one `word, Left|Center|Right` clue per line, with case-insensitive players and clear line-numbered errors. Implement accent-insensitive sequential matching of one to three transcript tokens, exact matching for short words, normalized Levenshtein distances, and single-use ordered matches. Prefer high-confidence candidates, then the earliest occurrence in that tier and the shortest span; if no high-confidence candidate exists, preserve the first eligible review match. Transcribe with French, CPU int8, VAD, `word_timestamps=True`, and the clue list as hotwords; fail explicitly if word timestamps are absent. Apply the configured long-interval anchor, offset, and nudge rule. Write a JSON report and three-second clips for `psychiatrique, Left`, `fou, Center`, `Monopoly, Right`, and `abandonné, Left`. Low confidence is non-blocking; not-found rows block rendering. Open the verification folder after a successful run.
  Verify (mechanical): Run `.\.venv\Scripts\python.exe -m compileall app scripts`; run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; run `.\.venv\Scripts\python.exe scripts\alignment_spike.py "C:\path\to\sample.mp4"`. Confirm each clue's match, assigned player, detected interval, anchor/display time, confidence, block status, and clip path in the report; confirm each generated clip is three seconds and playable. Explicitly report any not-found clue.
  Learner check: Inspect the regenerated JSON report and each verification clip. Confirm the ordered match times, manually supplied players, and display times are the intended ones. No commit is made until you approve these results.
  Commit: After explicit approval of the report and clips, commit the code and updated scope, PRD, spec, and checklist, then push to `origin`; exclude all generated media.

- [ ] **3. Upload a clip and enter player and clue words**
  Becomes usable: The local page accepts a valid MP4, previews it, and lets the creator enter three player words, place/drag their markers, and enter ordered `word, Player` clue rows.
  Why now: Once the spike has exposed the matching and timing behavior, the browser can collect the exact data required by the approved core journey.
  PRD ref: `prd.md > The Core Journey`, `prd.md > Screens and Layout`, `prd.md > Upload and preview`, `prd.md > Word placement`
  Spec ref: `spec.md > Local FastAPI App and Static Interface`, `spec.md > Upload and Media Validation`, `spec.md > In-Process Job Tracker and API`, `spec.md > Data Model`, `spec.md > Look and Feel`
  Build: Complete the FastAPI and static-page Upload/Words flow. Accept readable MP4 files from 30 to 60 seconds, preview the clip, and store the three player words, marker percentages, and ordered clue/player rows in the active session. Keep fixed-shot and player count as guidance, not upload validation; show clear errors for invalid files and malformed clue rows.
  Verify (mechanical): Run `.\.venv\Scripts\python.exe -m compileall app scripts`; run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; start Uvicorn and verify the page loads, a valid sample is accepted with correct dimensions/duration, and invalid formats or durations are rejected.
  Learner check: Open the local page, upload the sample, enter the player words and ordered clue words, and place/drag each marker; confirm the words and markers line up with the intended players.
  Commit: `Add local upload and word placement`.

- [ ] **4. Transcribe, align, and review clue suggestions**
  Becomes usable: The Transcript step displays each ordered clue's matched transcript token(s), display time, manually assigned player, and match confidence; not-found rows can be fixed before rendering.
  Why now: This wires the validated alignment behavior into the active session and supplies the manual correction path required by the PRD.
  PRD ref: `prd.md > Transcript review and manual player assignment`, `prd.md > States and Boundaries`, `prd.md > The Core Journey`
  Spec ref: `spec.md > Transcription Worker`, `spec.md > Word Alignment and Manual Player Assignment`, `spec.md > Transcript Review Interface`, `spec.md > In-Process Job Tracker and API`, `spec.md > Data Model`
  Build: Add the local transcription/alignment job and progress reporting. Display found, low-confidence, and not-found entries. Support manual transcript-word selection, ±0.1-second nudges, player changes, clue edits/deletion, individual acceptance, and Accept all. Low-confidence matches remain renderable; only not-found entries block rendering. Preserve typed spelling and assigned player.
  Verify (mechanical): Run `.\.venv\Scripts\python.exe -m compileall app scripts`; run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; run the sample through the UI and confirm the session and review state reflect manual corrections, that low-confidence matches remain renderable, and that not-found entries block rendering.
  Learner check: Transcribe the sample, inspect matched words and assigned players, correct one match or time, and confirm low-confidence entries do not block rendering while not-found entries do.
  Commit: `Add transcript alignment and review`.

- [ ] **5. Render and download the matched video**
  Becomes usable: The Render step produces a playable MP4 with each player word above its marker and every found clue beneath its assigned player; the user can download it or return to Transcript.
  Why now: Rendering is the end-to-end payoff and depends on valid marker positions and matched clue words.
  PRD ref: `prd.md > Render and download`, `prd.md > States and Boundaries`, `prd.md > The Core Journey`
  Spec ref: `spec.md > ASS Renderer and Download`, `spec.md > In-Process Job Tracker and API`, `spec.md > Data Model`, `spec.md > Where It Runs and How Someone Tries It`, `spec.md > Look and Feel`
  Build: Adapt the shared ASS renderer to accept all matched entries. For intervals longer than 0.8 seconds, use `max(start, end - 0.5 seconds)`; otherwise use `start`, then add `CLUE_OFFSET_SECONDS` and the review nudge. End each clue at the next clue for that player, the configured four-second cap, or video end. Preserve input dimensions and audio timing, show basic render progress/errors, provide playback/download, and retain the active session for corrections and rerendering.
  Verify (mechanical): Run `.\.venv\Scripts\python.exe -m compileall app scripts`; run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; render the sample end-to-end and verify the MP4 is playable, preserves source dimensions and duration, and shows the expected player words and matched clue overlays at the expected times.
  Learner check: Play the rendered sample and inspect the overlays and download; return to Transcript, change one accepted entry, rerender, and confirm the change appears.
  Commit: `Render and download matched video`.

## Hands-on Checkpoints

- [ ] Alignment evidence reviewed after Slice 2; user explicitly approves the report and clips before committing and pushing source and updated planning documents.
- [ ] Final kick-the-tires exploration and feedback completed after Slice 5; try the complete workflow, awkward inputs, and a corrected rerender.

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning activity complete — connect one actual build decision or uncertainty to the learner's social-media productivity goal.
- [ ] Optional edit and transfer reflection addressed — offer one optional reflection after the final review.
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: not started
Route and stops: not started; derive from actual finished code
Edit outcome: not started
Reflection: not started
Activity mode: not started

## Revisions

- Refined clue selection after sample evidence showed that a fuzzy phrase beginning with a preceding word could beat the exact clue token immediately after it. Matching now prefers the high-confidence tier, then the earliest occurrence within that tier; when only review-level candidates exist, it keeps the first eligible multi-token match.
