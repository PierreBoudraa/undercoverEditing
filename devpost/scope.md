---
doc: scope
status: approved
---

# Undercover Video Maker

A local web app that turns a three-person French Undercover recording into a social-ready video with each player's word and their spoken lines placed on screen.

## The Unique Kernel
It turns a lively, overlapping three-person French conversation into one Undercover-specific composition: each player's word stays above their head, while each line appears beneath the person speaking. The creator can correct who said each line instead of relying on automatic speaker attribution.

## Who It's For
The creator, making social media posts from videos of them and two friends playing Undercover. Their existing editing workflow is not yet established.

## The Core Loop
Open the local app, upload a fixed-shot clip, mark the three players' word zones and enter their words, review the timestamped transcript, edit or delete lines and assign each sentence to left, center, or right with one click in the same screen, and render an MP4.

## Inspiration & Identity
A focused, practical editing tool for this specific video format. Visual style is not decided yet.

## Why This Matters to the Learner
“I would like to create this app so I can use it to improve my productivity for social media posting.”

## What "Working" Looks Like
In a short demo, upload a 30–60 second clip of three friends playing Undercover in French, place the three word zones, enter the words, review and edit or delete transcript lines, assign speakers manually, and render. The resulting MP4 plays correctly, keeps each word above the right head, and displays subtitles beneath the right speaker at the right time. Transcription can need a few corrections, but must run on Windows and be roughly readable despite laughter.

## The POC Boundary
- First, test faster-whisper on a 30–60 second sample on Windows, including the French speech, laughter, and overlapping voices.
- Then, deliver a local end-to-end flow for a fixed-shot, three-person clip: transcript with timestamps, manual sentence-to-speaker assignment, and an MP4 with the three words above the players and subtitles under the current speaker.
- Keep the speaker correction manual and the workflow limited to this video format.

## Later
- Automatic speaker attribution, only if time remains after the transcription spike and manual end-to-end render work.

## Explicitly Cut
- Accounts and a database: this is a local tool and neither is needed to prove the workflow.
- Face tracking: the three player positions are marked manually for the fixed shot.
- AI word generation: the creator supplies the three words.
- Online multiplayer: the workflow is for one creator at a time.
- Other video formats: the proof is limited to fixed-shot, three-player Undercover clips.
- Cloud hosting or deployment: the app runs locally.
