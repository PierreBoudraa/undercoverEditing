---
doc: prd
status: approved
---

# Undercover Video Maker — Product Requirements

A local editing tool for turning a short, fixed-shot video of three friends playing Undercover in French into a captioned MP4 for social media.
Source: `scope.md > The Unique Kernel`, `scope.md > Who It's For`.

## The Core Journey

1. Open the app and see a four-step progress bar with Upload active. Choose a 30–60 second MP4 of three players in a fixed shot.
2. Preview the accepted clip, then go to Words. Enter one word per player and click the video frame to mark where each word should appear.
3. Transcribe the clip. Review the timestamped lines, edit or delete lines, and assign each remaining line to Left, Center, or Right.
4. Render the video. Check that each word stays above the right player, subtitles appear under the assigned player at the right time, and the timing matches the audio. Download the MP4.
5. If corrections are needed, return to the transcript, make changes, and render again without repeating upload or word placement.

## Screens and Layout

One centered, single-column page, about 900 px maximum width, with a four-step progress bar at the top: Upload, Words, Transcript, Render. The active step is clear; no menus, settings, or sidebars. Each step replaces the main content. Large buttons and generous spacing keep the video and editing content prominent. Mobile-friendly layout is welcome but not required for this local desktop tool.

- **Upload:** A large drop zone supports drag-and-drop or click-to-browse and says “Drop your Undercover clip here,” with the hint “Fixed shot, 3 players, 30-60 seconds, MP4”. After acceptance, show a playable video preview, duration, and Continue.
- **Words:** Show the video’s first frame above three labeled rows: Left, Center, Right. Each row contains its word field and uses its assigned player color. The user selects a row, clicks above that player's head to place its marker, and can drag the marker to adjust it.
- **Transcript:** Show the video player above a chronological list of transcript rows. Each row contains a timestamp range, editable text, Left/Center/Right speaker buttons, and a delete control. Clicking the timestamp plays that segment.
- **Render:** Show rendering progress while working, then the final video player and Download MP4 when complete.

## Look and Feel

Use a dark, focused editing-tool look, like a lightweight video editor rather than a generic dashboard. Dark charcoal background; vivid purple for primary actions and progress. Keep player colors consistent everywhere: Left = coral, Center = yellow, Right = cyan. Reserve orange for the “Who said this?” state and red for errors. Use a clean sans-serif interface font (Inter-like); use bold, rounded lettering for on-video words and subtitles. Subtitles are white with a thick dark outline; each word appears above its player in a rounded pill filled with that player's color.

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
- The on-screen Left, Center, and Right positions identify the three players; face tracking is not part of the workflow.
- Keep Transcribe disabled until all three markers are placed and all three words are entered. Highlight each incomplete row in red with a specific message, such as “Place a marker for Center” or “Enter a word for Right”.
- Transcribe starts speech recognition and shows progress while it runs. Cancelling the transcription job and preserving all work is optional hardening if time remains.

### Transcript review and speaker assignment

Develops `scope.md > The Core Loop` and `scope.md > The POC Boundary`.

- Show recognized lines in time order with start/end timestamps. Clicking a timestamp seeks to and plays that segment.
- Let the user edit a line's text inline. Deleting a line removes it; Undo restores the most recently deleted line.
- Each line has color-coded Left, Center, and Right controls. Clicking one assigns the speaker; clicking another changes the assignment.
- A line without an assigned speaker is highlighted orange and labeled “Who said this?”. Show an assignment counter, such as “12 of 15 assigned”. Render stays disabled until every remaining line has a speaker and at least one line remains.
- If all lines have been deleted, show “0 lines, add or restore at least one to render”. Undo can restore the last deleted line; rerunning transcription from this state is optional hardening if time remains.
- Timestamps from transcription are used as-is and are not editable in the normal review flow.
- On transcription failure, show a plain-language message. Detailed retry actions and preservation of all prior work are hardening if time remains; send technical details to a log file rather than the screen if that hardening is completed.
- If transcription returns no usable lines, show “No speech detected in this clip”. Detailed retry/back actions and preserving all work are hardening if time remains.
- Show transcription progress while it runs. A Cancel action that stops the worker and returns to Words with all work intact is hardening if time remains.

### Render and download

Develops `scope.md > The Unique Kernel`, `scope.md > The Core Loop`, and `scope.md > What "Working" Looks Like`.

- Render advances to step 4 and shows a percentage progress bar and short status, such as “Rendering your video... 40%”. No time estimate is needed. Locking the other steps while rendering and providing Cancel are optional hardening if time remains.
- A basic rendering error is shown in plain language. If cancellation is implemented, it stops rendering, deletes partial output, and returns to Transcript with edits and speaker assignments intact.
- On success, replace progress with a player for the finished MP4 and a Download MP4 button. Include Back to transcript so the user can correct and rerender without repeating Upload or Words.
- On failure, show a plain-language error. Detailed retry/back actions and preservation of all prior work are hardening if time remains; technical details go to a log file rather than the screen if that hardening is completed.
- The output displays each player's word above their head and each sentence below the manually assigned speaker at the corresponding time, synchronized with the audio.

## States and Boundaries

- **Initial use:** Upload is active; the drop zone explains the supported clip.
- **Invalid upload:** Explain the problem in the drop zone and remain on Upload.
- **Incomplete word placement:** Keep Transcribe disabled and identify missing markers or words.
- **Transcribing:** Show progress. Cancellation that returns to Words without losing work is optional hardening if time remains.
- **Transcription failure:** Show a basic plain-language error. Retry actions and preservation of video and Words data are optional hardening if time remains.
- **No detected speech:** Explain that no speech was detected. Retry/back actions and preserving the video, markers, and words are optional hardening if time remains.
- **Unassigned lines:** Highlight them in orange and prevent rendering until all remaining lines are assigned.
- **No remaining lines:** Prevent rendering and offer Undo. Rerunning transcription from this state is optional hardening if time remains.
- **Rendering:** Show percentage and status. Disabling navigation and cancellation that deletes partial output and returns to Transcript with work intact are optional hardening if time remains.
- **Render failure:** Show a basic plain-language error. Retry/back actions and preserving work are optional hardening if time remains; do not show technical log details in the interface.
- **Render success:** Play and download the completed MP4; allow return to Transcript for corrections and another render.
- **Session boundary:** The app is local and has no accounts or database. Cross-session persistence is not established and is not required for the proof of concept.

## Product Decisions

- The intended input is a 30–60 second fixed-shot MP4 of three friends playing Undercover in French, to keep transcription and rendering fast. Upload validation checks only MP4 format and duration; fixed framing and player count are not detected.
- Player zones and words are entered manually; automatic speaker attribution is not required.
- The three player positions are Left, Center, and Right by their on-screen location.
- Transcript text is editable, laughter/noise rows can be deleted, and speaker assignment is manual. Transcribed timestamps are not edited.
- No detected speech shows a plain-language message; retry/back actions are optional hardening. Manually adding a transcript line is not essential now.
- At least one transcript line is required to render; a video with only the three words is out of scope.
- Failures show plain-language messages. Preserving work through failures and writing technical diagnostics to a log are part of optional hardening.
- The visual direction and fixed player/error colors are learner-specified in `Look and Feel`.
- The core workflow, including a basic plain-language error for upload, transcription, or rendering failures and progress on long operations, takes priority. Detailed cancellation, retry, cleanup, recovery, and diagnostic logging are optional hardening only if time remains.

## What We're Building

- A Windows-runnable local web app for the described three-player French video workflow.
- A first technical proof that faster-whisper can transcribe a 30–60 second sample on Windows and produce roughly readable French text despite laughter; occasional line corrections are acceptable.
- Upload and preview, word entry and manual position marking, transcript correction and manual speaker assignment, and an end-to-end MP4 render with on-video words and timed subtitles.
- Upload validation, transcription/render progress, and basic plain-language error messages.

## Deferred From the POC

- **Manually adding transcript lines with custom start and end times:** useful if speech recognition misses a line, but not essential to proving the main workflow.
- **Automatic speaker attribution:** only consider if the transcription spike and manual end-to-end render are complete and time remains.
- **Detailed cancellation and recovery hardening:** canceling jobs, removing partial files, retries, preserving all work through failures, and technical diagnostic logs are optional if time remains after the core workflow.

## Possible Later Enhancements

Improve attribution, recovery, and diagnostic logging beyond the manual corrections and basic error messages required for the core proof of concept.

## Non-Goals

- Accounts, a database, or online multiplayer: this is a local, single-creator workflow.
- Face tracking: the creator places the three fixed word zones.
- AI word generation: the creator supplies the words.
- Other video formats: this proof is specifically for fixed-shot, three-player Undercover clips.
- Cloud hosting or deployment: the app runs locally.
- A render with only player words and no subtitles: at least one transcript line is required.

## Open Questions

- The learner's actual editing workflow and the precise look of the rendered video beyond the agreed overlays are not established; the spec can keep the design focused on the agreed proof.
- Windows transcription reliability is an explicit first validation step, not an assumed capability.
