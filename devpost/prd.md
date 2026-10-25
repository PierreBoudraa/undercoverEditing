---
doc: prd
status: approved
---

# Undercover Video Maker — Product Requirements

A local editing tool for turning a short, fixed-shot video of three friends playing Undercover in French into an MP4 with selected clue words for social media.
Source: `scope.md > The Unique Kernel`, `scope.md > Who It's For`.

## The Core Journey

1. Open the app and see a four-step progress bar with Upload active. Choose a 30–60 second MP4 of three players in a fixed shot.
2. Preview the accepted clip, then go to Words. Enter one player word per person, click the video frame to mark each head, and enter each spoken clue as `word, Left|Center|Right`, one per line in the order heard.
3. Transcribe locally with French word timestamps and the clue list as hotwords. The app aligns each list entry once, in order, among one-token or 2–3-token matches remaining after the previous match. Prefer high-confidence candidates, then the earliest occurrence in that confidence tier, then the shortest span. The player entered beside each clue is its assigned player; the app does not infer speakers. Review the matched transcript and time, manually select a transcript word when not found, nudge time by ±0.1 seconds, change the player if needed, edit/delete entries, or use Accept all. Low-confidence matches are orange but do not block rendering; only not-found rows block it.
4. Render found entries. For a matched interval longer than 0.8 seconds, anchor at `max(start, end - 0.5 seconds)`; otherwise use its start, then add the configured offset. Each clue appears below its assigned player and remains visible through the end of the video. Later clues for that player stack below earlier clues. Download the MP4.
5. If corrections are needed, return to Transcript, adjust the matched word, time, or player, then render again without repeating upload or word placement.

## Screens and Layout

One centered, single-column page, about 900 px maximum width, with a four-step progress bar at the top: Upload, Words, Transcript, Render. The active step is clear; no menus, settings, or sidebars. Each step replaces the main content. Large buttons and generous spacing keep the video and editing content prominent. Mobile-friendly layout is welcome but not required for this local desktop tool.

- **Upload:** A large drop zone supports drag-and-drop or click-to-browse and says “Drop your Undercover clip here,” with the hint “Fixed shot, 3 players, 30-60 seconds, MP4”. After acceptance, show a playable video preview, duration, and Continue.
- **Words:** Show the video’s first frame above three labeled rows: Left, Center, Right. Each row contains its player-word field and uses its assigned color. The user clicks above each player's head to place its marker and can drag it to adjust. Also provide a multiline clue field with one `word, Left|Center|Right` entry per line, in spoken order. Player names are case-insensitive; malformed lines show a line-specific error.
- **Transcript:** Show the video player and a review list, one row per requested clue word. Each row shows the entered spelling, matched transcript word(s), display time, manually assigned player, and match confidence. The user can select a transcript word manually for a not-found clue, nudge time by ±0.1 seconds, change player in one click, edit or delete the clue, and use Accept all. Low-confidence rows are orange and non-blocking; only not-found rows prevent rendering.
- **Render:** Show rendering progress while working, then the final video player and Download MP4 when complete.

## Look and Feel

Keep the web interface's dark editing-tool look and its existing player colors: Left = coral, Center = yellow, Right = cyan. Reserve orange for not-found or low-confidence matches and red for errors; do not change the review screen or its player colors.

Use the bundled, Apache-2.0-licensed Chewy font for video overlays. Keep a large, centered, mixed-case `Undercover` title visible for the whole video near 12% of frame height, with white fill, a thick black outline, and saturated red glow. Render player words above their heads in uppercase with the same white, black-outline style. The title and words use two fully opaque glow layers: a wide, blurred outer halo and a tighter, brighter core that fades softly at the edge. A single word that appears once while another appears twice identifies the undercover; glow that word vivid red (`#FF1A1A`) and the repeated civilian word vivid green (`#00FF2A`). If all three words are identical or all different, use a neutral white glow. Clue words use the glow of their assigned player's role and a slight configured slant.

Each overlay word scales from 120% to 100% over 0.15 seconds when it appears; all glow and text layers animate together. Fit each player and clue word to at most about one third of the frame width. Clues begin around 68% of frame height, remain visible until video end, and stack downward per player. Reduce configured line spacing and font size as needed to keep the stack above the bottom 15% safe area. Keep title and word glow colors, layer widths, blur, opacity, style, sizing, stack, and safe-margin values in `app/config.py`.

## Features and Behavior

### Upload and preview

Develops `scope.md > The Core Loop` and `scope.md > What "Working" Looks Like`.

- The user can drop a video file or browse to select it.
- Validate only that the file is an MP4 and is 30–60 seconds long. The fixed-shot, three-player requirement is guidance in the upload hint; the app does not detect or validate the number of players or whether the shot is fixed.
- Once accepted, show the clip in a player with its duration. Continue advances to Words.
- A wrong format or out-of-range duration displays a clear error in the drop zone; do not advance.
- Returning to Upload to choose another clip resets the existing markers and words.

### Word placement

Develops `scope.md > The Core Loop` and `scope.md > Explicitly Cut`.

- Provide Left, Center, and Right word fields and matching color-coded rows.
- The user selects a row and clicks the first frame to place that player's marker. Show a numbered marker in the row's color and preview the entered word beside it. Allow dragging the marker to adjust its position.
- Provide a multiline field with one `word, Left|Center|Right` entry per line in the order heard. Parse player names case-insensitively and show a clear line-numbered error for malformed entries. Keep the user's clue spelling for the final video.
- The on-screen Left, Center, and Right positions identify the three players; the user-provided player assignment is authoritative. Automatic speaker attribution is not part of the workflow.
- Keep Transcribe disabled until all three markers and player words are set and at least one valid clue/player row is entered. Highlight missing player setup and malformed clue rows with specific errors.
- Transcribe starts speech recognition and shows progress while it runs. Use faster-whisper French, VAD, `word_timestamps=True`, and pass the clue list as hotwords. Cancelling the transcription job and preserving all work is optional hardening if time remains.

### Transcript review and manual player assignment

Develops `scope.md > The Core Loop` and `scope.md > The POC Boundary`.

- Align each requested clue word once, in list order, searching forward from the previous match. Normalize case, accents, and punctuation before calculating normalized Levenshtein distance. For words under five letters require an exact normalized match; for longer words accept distance ≤0.35. Compare each target against one token and concatenations of two or three adjacent tokens. Accept distance ≤0.20 automatically; flag distances >0.20 through 0.35 for review. Preserve the user's entered spelling in output.
- The player beside each clue in the ordered input is authoritative. Show the assigned player in each review row; allow changing it in one click.
- If no acceptable match is found, show “Not found” and let the user pick the correct transcript word manually. Show matched token(s), display time, distance, assigned player, and match confidence for each row.
- For a matched interval longer than `LONG_INTERVAL_THRESHOLD_SECONDS` (default `0.8`), use `max(start, end - LONG_INTERVAL_WORD_DURATION_SECONDS)` (default duration `0.5` seconds) as the anchor. For shorter or equal intervals, use `start`. Then add `CLUE_OFFSET_SECONDS` (default `-0.15`). The review controls nudge the resulting display time by ±0.1 seconds.
- A high-confidence match is ready automatically. A low-confidence match is shown in orange for attention but does not block rendering; only not-found entries block it. The user can change the player, nudge time, edit/delete the clue, accept one row, or use Accept all.
- Clicking a row's time seeks to and plays that moment. Keep the original transcript text available as context. Timestamps are editable only through the explicit ±0.1-second nudge controls or manual word selection.
- On transcription failure, show a plain-language message. Detailed retry actions and preservation of all prior work are hardening if time remains; send technical details to a log file rather than the screen if that hardening is completed.
- If transcription returns no usable lines, show “No speech detected in this clip”. Detailed retry/back actions and preserving all work are hardening if time remains.
- Show transcription progress while it runs. A Cancel action that stops the worker and returns to Words with all work intact is hardening if time remains.

### Render and download

Develops `scope.md > The Unique Kernel`, `scope.md > The Core Loop`, and `scope.md > What "Working" Looks Like`.

- Render advances to step 4 and shows a percentage progress bar and short status, such as “Rendering your video... 40%”. No time estimate is needed. Locking the other steps while rendering and providing Cancel are optional hardening if time remains.
- A basic rendering error is shown in plain language. If cancellation is implemented, it stops rendering, deletes partial output, and returns to Transcript with edits and speaker assignments intact.
- On success, replace progress with a player for the finished MP4 and a Download MP4 button. Include Back to transcript so the user can correct and rerender without repeating Upload or Words.
- On failure, show a plain-language error. Detailed retry/back actions and preservation of all prior work are hardening if time remains; technical details go to a log file rather than the screen if that hardening is completed.
- The output displays the persistent title, each player's word above their head, and every found clue below its manually assigned player, including low-confidence matches. A clue uses the long-interval anchor rule when its interval exceeds 0.8 seconds, otherwise its matched start; it then adds the configured `CLUE_OFFSET_SECONDS` (default `-0.15`). Every clue stays visible until video end; subsequent clues for a player appear below the previous ones. Auto-fit text and the configured safe margin keep overlay words inside their columns and stacks above the bottom 15% of the frame.

## States and Boundaries

- **Initial use:** Upload is active; the drop zone explains the supported clip.
- **Invalid upload:** Explain the problem in the drop zone and remain on Upload.
- **Incomplete word placement:** Keep Transcribe disabled and identify missing markers or words.
- **Transcribing:** Show progress. Cancellation that returns to Words without losing work is optional hardening if time remains.
- **Transcription failure:** Show a basic plain-language error. Retry actions and preservation of video and Words data are optional hardening if time remains.
- **No detected speech:** Explain that no speech was detected. Retry/back actions and preserving the video, markers, and words are optional hardening if time remains.
- **No clue words entered:** Keep Transcribe disabled and prompt the user to enter the ordered clue list.
- **Clue not found:** Mark it not found; allow manual selection from transcript words. It blocks rendering until it has a valid match.
- **Low-confidence match:** Show the row in orange as a review cue; it does not block rendering. Accept all remains available.
- **No matched clue entries:** Prevent rendering and explain that at least one clue needs a valid transcript match.
- **Rendering:** Show percentage and status. Disabling navigation and cancellation that deletes partial output and returns to Transcript with work intact are optional hardening if time remains.
- **Render failure:** Show a basic plain-language error. Retry/back actions and preserving work are optional hardening if time remains; do not show technical log details in the interface.
- **Render success:** Play and download the completed MP4; allow return to Transcript for corrections and another render.
- **Session boundary:** The app is local and has no accounts or database. Cross-session persistence is not established and is not required for the proof of concept.

## Product Decisions

- The intended input is a 30–60 second fixed-shot MP4 of three friends playing Undercover in French, to keep transcription and rendering fast. Upload validation checks only MP4 format and duration; fixed framing and player count are not detected.
- Player zones, player words, and each clue's player assignment are entered manually. The user enters clues in the format `word, Left|Center|Right`; word alignment remains automatic.
- The three player positions are Left, Center, and Right by their on-screen location.
- The user supplies spoken clue words and their players in order; the app aligns them to word-level transcript timestamps. The user can manually match a transcript word, change the player, nudge time, edit or delete a clue. Every found match can render; low confidence is non-blocking.
- No detected speech shows a plain-language message; retry/back actions are optional hardening. Manually adding a transcript line is not essential now.
- At least one matched clue word is required to render; a video with only the three player words is out of scope.
- Failures show plain-language messages. Preserving work through failures and writing technical diagnostics to a log are part of optional hardening.
- The visual direction and fixed player/error colors are learner-specified in `Look and Feel`.
- The core workflow, including a basic plain-language error for upload, transcription, or rendering failures and progress on long operations, takes priority. Detailed cancellation, retry, cleanup, recovery, and diagnostic logging are optional hardening only if time remains.
- Keep the Upload and Transcript screens minimal; reaching a working end-to-end render matters more than visual polish.

## What We're Building

- A Windows-runnable local web app for the described three-player French video workflow, with a manually supplied player for each clue.
- A first technical proof that faster-whisper can transcribe a 30–60 second sample on Windows and produce roughly readable French text despite laughter; occasional line corrections are acceptable.
- Upload and preview, player-word entry and manual marker placement, ordered `word, Player` clue entry, word-level transcription and fuzzy matching, a review screen for match confidence and timing, and an end-to-end MP4 render with on-video player words and timed clue words.
- Upload validation, transcription/render progress, and basic plain-language error messages.

## Deferred From the POC

- **Manually adding transcript lines with custom start and end times:** useful if speech recognition misses a line, but not essential to proving the main workflow.
- **Automatic speaker attribution:** the user supplies each player's assignment; no face model or hosted speaker service is used.
- **Detailed cancellation and recovery hardening:** canceling jobs, removing partial files, retries, preserving all work through failures, and technical diagnostic logs are optional if time remains after the core workflow.

## Possible Later Enhancements

Motion-based speaker suggestions were tested and dropped after 2 of 4 assignments looked correct on the sample. Reconsider speaker automation only if manual assignment proves cumbersome. Recovery and diagnostic logging may also be added if the core workflow leaves time.

## Non-Goals

- Accounts, a database, or online multiplayer: this is a local, single-creator workflow.
- Face tracking and automatic diarization: player zones and clue assignments are entered manually.
- AI word generation: the creator supplies the words.
- Other video formats: this proof is specifically for fixed-shot, three-player Undercover clips.
- Cloud hosting or deployment: the app runs locally.
- Full-sentence subtitles and wrapping clue words: the rendered output shows selected clue words, stacking them below each assigned player.
- A render with only player words and no clue words: at least one assigned clue word is required.

## Open Questions

- The learner's actual editing workflow and the precise look of the rendered video beyond the agreed overlays are not established; the spec can keep the design focused on the agreed proof.
- Windows transcription reliability is an explicit first validation step, not an assumed capability.
