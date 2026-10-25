---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast

The regenerated sample report and verification clips were reviewed and approved before the source/docs commit and push. Motion-based speaker suggestions were tested and dropped after 2 of 4 assignments looked correct on the sample. Keep Upload and Transcript UI minimal; prioritize the end-to-end render over polish.

## Slices

- [x] **1. Prove Windows transcription, ordered alignment, and display timing**
  Becomes usable: Standalone spikes verify French word-level transcription and ASS burn-in on Windows, then report ordered clue matches, manually assigned players, and display times with playable three-second sample clips.
  Why now: These separate commands established the local media/transcription assumptions and validated the remaining matching/timing risk before building the browser flow.
  PRD ref: `prd.md > What We're Building`, `prd.md > Word placement`, `prd.md > Transcript review and manual player assignment`
  Spec ref: `spec.md > Transcription Worker`, `spec.md > Word Alignment and Manual Player Assignment`, `spec.md > Alignment Spike and Verification Clips`, `spec.md > ASS Renderer and Download`, `spec.md > Where It Runs and How Someone Tries It`
  Build: The Windows transcription/ASS spike and manual-player alignment spike are complete. The alignment parser accepts case-insensitive `word, Left|Center|Right` rows, matching is sequential and fuzzy, and the report records each assigned player and timing calculation.
  Verify (mechanical): The transcription spike passed on the local 58-second sample. The alignment spike matched all four clues, generated four 3-second 1080x1936 clips that decoded successfully, and produced display times of 0.45, 19.94, 27.84, and 52.06 seconds. The pre-commit test run passed all 31 tests; `pip check` and the staged whitespace check passed.
  Learner check: The learner reviewed all four clips, players, and times and approved them.
  Commit: Windows transcription spike previously committed; approved alignment implementation committed as `c0dd594`.

- [x] **2. Upload a clip and enter player and clue words**
  Becomes usable: The local page accepts a valid MP4, previews it, and lets the creator enter three player words, place/drag their markers, and enter ordered `word, Player` clue rows.
  Why now: Once the spike has exposed the matching and timing behavior, the browser can collect the exact data required by the approved core journey.
  PRD ref: `prd.md > The Core Journey`, `prd.md > Screens and Layout`, `prd.md > Upload and preview`, `prd.md > Word placement`
  Spec ref: `spec.md > Local FastAPI App and Static Interface`, `spec.md > Upload and Media Validation`, `spec.md > In-Process Job Tracker and API`, `spec.md > Data Model`, `spec.md > Look and Feel`
  Build: Complete the FastAPI and static-page Upload/Words flow. Accept readable MP4 files from 30 to 60 seconds, preview the clip, and store the three player words, marker percentages, and ordered clue/player rows in the active session. Keep fixed-shot and player count as guidance, not upload validation; show clear errors for invalid files and malformed clue rows.
  Verify (mechanical): `compileall`, all 36 unit tests, `node --check app\static\app.js`, and `git diff --check` passed. The local sample was accepted as 58 seconds at 1080x1936; the video endpoint returned byte ranges, unsupported file types were rejected, malformed clue rows returned line-specific errors, and saving/replacing a session behaved as expected.
  Learner check: The learner tried the Upload + Words flow and said it was good; no changes were requested.
  Commit: `a04e68a` — `Add local upload and word placement`.

- [x] **3. Transcribe, align, and review clue suggestions**
  Becomes usable: The Transcript step displays each ordered clue's matched transcript token(s), display time, manually assigned player, and match confidence; not-found rows can be fixed before rendering.
  Why now: This wires the validated alignment behavior into the active session and supplies the manual correction path required by the PRD.
  PRD ref: `prd.md > Transcript review and manual player assignment`, `prd.md > States and Boundaries`, `prd.md > The Core Journey`
  Spec ref: `spec.md > Transcription Worker`, `spec.md > Word Alignment and Manual Player Assignment`, `spec.md > Transcript Review Interface`, `spec.md > In-Process Job Tracker and API`, `spec.md > Data Model`
  Build: Added the local faster-whisper worker, in-process job status, and sequential clue alignment. The Transcript step shows timestamped words, match text and confidence, player assignment, and display time. It supports manual transcript-word selection, ±0.1-second nudges, player/clue edits, deletion, individual acceptance, and Accept all. Low-confidence matches remain renderable; only not-found entries block rendering.
  Verify (mechanical): `compileall`, all 43 unit tests, `node --check app\static\app.js`, and `git diff --check` passed. On the 58-second 1080x1936 sample, the browser transcription produced 188 timestamped words and four aligned rows (three high-confidence, one low-confidence). Browser checks covered player/timing edits and persistence, low-confidence acceptance, the not-found render blocker, and resolving it by selecting a transcript word.
  Learner check: Deferred to the final end-to-end review after Step 4, per the approved build pacing.
  Commit: `Add transcript alignment and review`.

- [x] **4. Render and download the matched video**
  Becomes usable: The Render step produces a playable MP4 with each player word above its marker and every found clue beneath its assigned player; the user can download it or return to Transcript.
  Why now: Rendering is the end-to-end payoff and depends on valid marker positions and matched clue words.
  PRD ref: `prd.md > Render and download`, `prd.md > States and Boundaries`, `prd.md > The Core Journey`
  Spec ref: `spec.md > ASS Renderer and Download`, `spec.md > In-Process Job Tracker and API`, `spec.md > Data Model`, `spec.md > Where It Runs and How Someone Tries It`, `spec.md > Look and Feel`
  Build: Added a render job with FFmpeg progress and stage timings, output validation, freshness tracking, playback/download, and return-to-Transcript correction flow. The ASS renderer includes all player words and matched clues, preserves source dimensions and audio, and uses the agreed timing rules.
  Verify (mechanical): `compileall`, all 47 unit tests, `node --check app\static\app.js`, and `git diff --check` passed. The sample rendered and corrected rerender completed at 1080x1936 and 58 seconds; the extracted 2.5-second frame showed all three player-word pills and the matched clue. The corrected review persisted the Center assignment and 0.55-second display time.
  Learner check: Completed during the final hands-on review: the learner confirmed the player words, clue placement/timing, download, and corrected rerender all worked.
  Commit: `Render and download matched video`.

## Hands-on Checkpoints

- [x] Alignment evidence reviewed after Step 1; the user approved the report and clips before the source/docs commit and push.
- [x] Upload + Words hands-on check after Step 2; the learner tried the flow and reported it was good, with no changes requested.
- [x] Final kick-the-tires exploration and feedback completed after Step 4; the learner reported the complete flow, overlays, download, and corrected rerender worked.

## Final Review

- [x] Final review complete — feedback resolved and learner confirms ready to ship
  Outcome: No product changes requested; learner explicitly confirmed the proof of concept is ready to ship.

## Code Tour and App Map

- [x] Learning activity complete — connect one actual build decision or uncertainty to the learner's social-media productivity goal.
- [x] Optional edit and transfer reflection addressed — offer one optional reflection after the final review.
- [x] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: Focused evidence-based recap using the requested 58-second sample timings. The learner identified transcription as about 78% of total runtime and named beam size, CPU threads, word timestamps, and model size as possible investigations, with clue-match accuracy as the guardrail. The source code and render-progress test confirm where the measurements come from.
Route and stops: Reference route (not an interactive code tour): `app/static/app.js` `startRender()` and `showRenderedVideo()`; `app/main.py` `start_render()`, `_run_render()`, and `get_output()`; `app/rendering.py` `render_annotated_video()`.
Edit outcome: No optional edit requested or needed for the proof of concept.
Reflection: The learner supplied a project-grounded performance insight; no extra transfer question was needed.
Activity mode: Focused investigation/recap; the learner already completed the hands-on end-to-end review.

## Revisions

- Refined clue selection after sample evidence showed that a fuzzy phrase beginning with a preceding word could beat the exact clue token immediately after it. Matching now prefers the high-confidence tier, then the earliest occurrence within that tier; when only review-level candidates exist, it keeps the first eligible multi-token match.
- After the learner rejected motion attribution and approved manual player assignments, the completed transcription and alignment proofs were grouped as Step 1; Upload + Words is Step 2. The Render step will print per-stage elapsed time for model load, transcription, alignment, ASS generation, and FFmpeg rendering.
