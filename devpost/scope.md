---
doc: scope
status: approved
---

# Undercover Video Maker

A local web app that turns a three-person French Undercover recording into a social-ready video with each player's word and selected spoken clue words placed on screen.

## The Unique Kernel
It turns a lively, overlapping three-person French conversation into one Undercover-specific composition: each player's word stays above their head, while each ordered clue word is matched to word-level timestamps and placed beneath the player explicitly entered beside it. The app does not guess who spoke; the creator supplies that assignment.

## Who It's For
The creator, making social media posts from videos of them and two friends playing Undercover. Their existing editing workflow is not yet established.

## The Core Loop
Open the local app, upload a fixed-shot clip, mark the three players' word zones and enter their words, then enter each spoken clue as `word, Left|Center|Right` in the order heard. Local transcription aligns each clue to word-level timestamps. Review low-confidence matches and adjust their timing, then render an MP4 with each player word and each found clue beneath its manually assigned player.

## Inspiration & Identity
A focused, practical editing tool for this specific video format, with a dark video-editor look, vivid purple actions, and consistent coral, yellow, and cyan player colors.

## Why This Matters to the Learner
“I would like to create this app so I can use it to improve my productivity for social media posting.”

## What "Working" Looks Like
In a short demo, upload a 30–60 second clip of three friends playing Undercover in French, place the three player-word zones, then enter ordered `word, Player` clues. The creator can review matches, manually select a transcript word when a clue is not found, nudge timing by 0.1 seconds, change a player assignment, or delete an entry. Low-confidence matches are marked for attention but do not block rendering; only not-found clues block it. The resulting MP4 keeps each player word above the right head and displays each found clue beneath its entered player. The pipeline runs locally on Windows with no API key.

## The POC Boundary
- First, test faster-whisper on a 30–60 second sample on Windows, including the French speech, laughter, and overlapping voices.
- Then, validate word-level timestamp alignment on the sample using the player explicitly entered beside each clue. Check how the timing rule places short and long matched intervals.
- Deliver a local end-to-end flow for a fixed-shot, three-person clip: player-word placement, ordered `word, Player` clues, transcription with word timestamps and hotwords, sequential fuzzy matching, review/correction, and an MP4 with player words above the players and found clue words beneath them.
- Keep speaker assignment explicit and local; do not rely on face recognition, a hosted API, or automatic diarization.

## Later
- Motion-based speaker suggestions were tested and dropped after only 2 of 4 assignments looked correct on the sample. Revisit speaker automation only if entering a player beside each clue becomes a demonstrated bottleneck.
- Stronger diarization, face tracking, or recovery/logging improvements, only if the local proof shows they are needed and time remains.

## Explicitly Cut
- Accounts and a database: this is a local tool and neither is needed to prove the workflow.
- Face tracking: the three player positions are marked manually for the fixed shot.
- AI word generation: the creator supplies the three words.
- Online multiplayer: the workflow is for one creator at a time.
- Other video formats: the proof is limited to fixed-shot, three-player Undercover clips.
- Cloud hosting or deployment: the app runs locally.
- Automatic speaker attribution: the creator enters the player beside each clue word.
