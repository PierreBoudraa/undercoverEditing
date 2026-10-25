---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast
Push remote: `origin` at `https://github.com/PierreBoudraa/undercoverEditing.git`; push each verified commit after staged-diff review.

## Slices

- [x] **1. Prove Windows transcription and ASS burn-in**
  Becomes usable: A standalone command-line spike reports timestamped French transcription output and separate PASS/FAIL results for transcription and burning a visible one-line ASS subtitle into a short section of the sample clip.
  Why now: This independently runnable spike is the critical-risk exception: it verifies the local Whisper and FFmpeg assumptions before building the app around them.
  PRD ref: `prd.md > What We're Building`, `prd.md > Deferred From the POC`
  Spec ref: `spec.md > Transcription Worker`, `spec.md > ASS Renderer and Download`, `spec.md > Where It Runs and How Someone Tries It`
  Build: Create the Python 3.13 environment only and install the pinned dependencies; implement `scripts/transcription_spike.py` to inspect a local 30–60 second clip, run faster-whisper small on CPU int8 with French and VAD, print timestamped lines, and independently test visible ASS burn-in with the configured bundled FFmpeg. If the subtitle check fails, support the specified `FFMPEG_EXE` full-build fallback. Extend `.gitignore` for local environments, work files, logs, and media. Resolve any package incompatibility within Python 3.13; do not install another Python runtime. The tested PyAV dependency is pinned to 16.1.0.
  Verify (mechanical): Run `.\.venv\Scripts\python.exe -m compileall scripts`; run `.\.venv\Scripts\python.exe scripts\transcription_spike.py "<local 30-60 second sample.mp4>"` and confirm separate PASS results, timestamped lines, and a playable output with visible subtitle text.
  Learner check: Run the spike on your own short French clip in PowerShell. Check that the printed transcript is readable enough to correct and that the test output video visibly contains the subtitle.
  Commit: `Add Windows transcription and ASS spike`; push this verified commit to the configured learner-approved remote, or pause and ask for a remote before pushing.

- [ ] **2a. Render an annotated MP4 from hand-written data**
  Becomes usable: A no-UI command creates a playable MP4 from three words, normalized marker positions, and a few timed transcript lines with hand-assigned speakers.
  Why now: This proves the unique visual kernel using the renderer before the UI is built, and allows caption placement to be corrected before it is wired into the app.
  PRD ref: `prd.md > The Unique Kernel`, `prd.md > What "Working" Looks Like`
  Spec ref: `spec.md > Hand-Written Render Fixture`, `spec.md > ASS Renderer and Download`, `spec.md > Data Model`
  Build: Implement the shared ASS/render path and `scripts/render_fixture.py` using clearly labeled in-code fixture data. Preserve source dimensions and aspect ratio; show the three words and assigned timed subtitles using the approved positions/colors and overlap stacking. Keep the renderer callable later by FastAPI.
  Verify (mechanical): Run `.\.venv\Scripts\python.exe -m compileall app scripts`; run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; run the fixture script on a local MP4 and confirm it produces a playable output with unchanged dimensions and visible word/subtitle overlays.
  Learner check: Play the fixture output and check whether words sit above the intended positions, captions stay readable and inside the frame, and overlapping lines stack in the order you expect.
  Commit: `Add annotated MP4 fixture renderer`; push this verified commit to the configured learner-approved remote, or pause and ask for a remote before pushing.

- [ ] **2b. Upload a clip and place the three words**
  Becomes usable: The local browser page accepts a valid MP4, previews it, and lets the creator enter three words and place/drag normalized markers over the first frame.
  Why now: With overlay coordinates proven on an actual rendered file, wire the creator's inputs into a real local session while keeping validation limited to format and duration.
  PRD ref: `prd.md > The Core Journey`, `prd.md > Screens and Layout`, `prd.md > Upload and preview`, `prd.md > Word placement`
  Spec ref: `spec.md > Local FastAPI App and Static Interface`, `spec.md > Upload and Media Validation`, `spec.md > In-Process Job Tracker and API`, `spec.md > Data Model`, `spec.md > Look and Feel`
  Build: Bootstrap FastAPI/static serving and the Upload/Words screens; accept only readable MP4 files of 30–60 seconds, preview the clip, and let the user place/drag Left/Center/Right markers and enter words. Validate no player count or fixed-shot detection. A new valid clip clears prior clip work and output; keep current session state in memory. Show basic plain-language input errors.
  Verify (mechanical): Run `.\.venv\Scripts\python.exe -m compileall app scripts`; run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; start Uvicorn and verify the page loads, an in-range MP4 is accepted, the returned duration/dimensions are correct, and invalid format/duration are rejected.
  Learner check: Open the local page, upload your sample, and place/drag the three markers and enter their words; confirm the preview and word labels match the intended screen positions.
  Commit: `Add local upload and word placement`; push this verified commit to the configured learner-approved remote, or pause and ask for a remote before pushing.

- [ ] **2c. Transcribe, edit, and assign speakers**
  Becomes usable: The Transcript step shows timestamped French lines that can be played, edited, deleted/restored, and manually assigned to Left, Center, or Right.
  Why now: This connects the already-verified transcription spike to the real clip and marker session while keeping speaker attribution under the creator's control.
  PRD ref: `prd.md > The Core Journey`, `prd.md > Transcript review and speaker assignment`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > Transcription Worker`, `spec.md > In-Process Job Tracker and API`, `spec.md > Transcript Review Interface`, `spec.md > Data Model`
  Build: Add the local transcription job and polling with simple progress feedback; display timestamped lines with segment playback, inline text editing, speaker assignment/change, delete and last-delete Undo. Show unassigned rows and prevent rendering until every remaining row has a speaker and at least one line remains. Show a basic plain-language transcription error or no-speech message; detailed retry/cancel/recovery remains in Slice 3.
  Verify (mechanical): Run `.\.venv\Scripts\python.exe -m compileall app scripts`; run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; run the app with the local sample, confirm transcript row data and that edits/assignments/deletions reach the active session correctly.
  Learner check: Transcribe your sample, play a line from its timestamp, edit its text, assign/change a speaker, delete and undo a line, then confirm an unassigned line prevents rendering.
  Commit: `Add transcript editing and speaker assignment`; push this verified commit to the configured learner-approved remote, or pause and ask for a remote before pushing.

- [ ] **2d. Render and download from the app**
  Becomes usable: The Render step shows the percentage/status, plays the final MP4, and offers a download of the video produced from the creator's edited session.
  Why now: The renderer is already proven independently and now receives real uploaded video, normalized word positions, and manually assigned transcript rows.
  PRD ref: `prd.md > The Core Journey`, `prd.md > Render and download`, `prd.md > What We're Building`
  Spec ref: `spec.md > ASS Renderer and Download`, `spec.md > In-Process Job Tracker and API`, `spec.md > Data Model`, `spec.md > Where It Runs and How Someone Tries It`
  Build: Connect the Render screen to the shared ASS renderer; expose FFmpeg progress, show the finished MP4 in a player, and provide Download MP4 and Back to transcript for rerendering. Preserve source dimensions/aspect and audio timing. Show basic plain-language render failures and do not expose technical details. Keep final output after app exit until a new valid upload.
  Verify (mechanical): Run `.\.venv\Scripts\python.exe -m compileall app scripts`; run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; execute the full clip-to-output journey and verify the produced MP4 plays, has the source dimensions, and visibly contains positioned words and correctly timed speaker captions.
  Learner check: Render the edited sample, play it, and check that words stay over the intended heads, captions appear beneath the assigned speaker at the right times, and the download works.
  Commit: `Connect render progress and MP4 download`; push this verified commit to the configured learner-approved remote, or pause and ask for a remote before pushing.

- [ ] **3. Optional: harden cancellation and recovery if time remains**
  Becomes usable: If completed, long jobs can be cancelled safely, and no-speech/failure/retry paths preserve the work and clean partial output as defined in the PRD.
  Why now: The complete happy path and visual kernel are already usable; this is explicitly conditional hardening, not a blocker for the core demo.
  PRD ref: `prd.md > States and Boundaries`, `prd.md > Deferred From the POC`
  Spec ref: `spec.md > In-Process Job Tracker and API`, `spec.md > ASS Renderer and Download`, `spec.md > Local Logging`, `spec.md > Important Failure Modes`
  Build: Only if time remains, implement cancellation and partial-file cleanup, detailed retry/back and state preservation, no-speech recovery actions, and technical diagnostic logging. Extend focused standard-library tests for these cases. If time does not remain, record the agreed deferral under Revisions and keep the core app's basic plain-language errors.
  Verify (mechanical): If implemented, run `.\.venv\Scripts\python.exe -m compileall app scripts` and `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`; exercise cancel/failure and confirm partial files are removed and session data remains. If deferred, update the PRD/spec/checklist to say the core POC was completed with basic errors and advanced hardening was deferred.
  Learner check: If implemented, cancel a transcription or render and trigger a failure; confirm the app returns to the expected step with the work intact. If deferred, review the basic error behavior during final kick-the-tires instead.
  Commit: `Harden cancellation and recovery` if implemented; push each verified commit to the configured learner-approved remote. If deferred, commit the documented plan revision and push it to that remote.

## Hands-on Checkpoints

- [ ] Early technical behavior explored — after Slice 1, run the spike on the learner's own Windows sample and use the results to decide whether the approved fallback/model checks need to be applied before renderer implementation.
- [ ] Rendered kernel preview explored — after Slice 2a, inspect the annotated MP4 and resolve any placement or overlap feedback before wiring the renderer into the UI.
- [ ] Final kick-the-tires exploration and feedback completed — after Slice 2d if hardening is deferred, or after Slice 3 if it is built; try the complete local workflow and a rerender.

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning activity complete — connect the technical spike's pass/fail evidence and resulting implementation choice to the learner's productivity goal.
- [ ] Optional edit and transfer reflection addressed — offer one optional reflection after the build review.
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: not started
Route and stops: not started; derive from actual finished code
Edit outcome: not started
Reflection: not started
Activity mode: not started

## Revisions

- Split the app build into a headless hand-written-data renderer proof, Upload/Words, Transcript, and Render commits. The learner requested these smaller verified checkpoints so the visual kernel can be inspected before UI integration.
- Moved detailed cancellation, retry/recovery, cleanup, and diagnostic logging to the final conditional hardening slice; the learner prioritized the full happy path within about one day and approved basic errors/progress as the core baseline.
- Changed the runtime target from Python 3.11 to the learner's installed Python 3.13.5; the learner explicitly requested no other Python installation and approved resolving any dependency compatibility issue within 3.13.
- Added the renderer-test words, approximate head height, and 78% caption baseline configuration requested by the learner.
- Verified the Python 3.13.5 spike on the learner's 58-second sample: 45 French timestamped segments, visible ASS subtitle, and the learner judged the transcript sufficient for manual correction. The sample and generated test artifacts remain local.
