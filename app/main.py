from __future__ import annotations

import logging
import shutil
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.alignment import (
    ClueInput,
    ClueMatch,
    Speaker,
    TranscriptWord,
    align_clue_words,
    normalize_text,
    parse_clue_list,
)
from app.config import WORK_DIR
from app.media import (
    MediaInfo,
    MediaValidationError,
    inspect_mp4,
    validate_video_duration,
)
from app.rendering import clue_display_start
from app.transcription import NoSpeechDetectedError, transcribe_words


STATIC_DIR = Path(__file__).resolve().parent / "static"
CURRENT_WORK_DIR = WORK_DIR / "current"
INPUT_VIDEO_PATH = CURRENT_WORK_DIR / "input.mp4"
FINAL_VIDEO_PATH = WORK_DIR / "final.mp4"
PLAYERS: tuple[Speaker, ...] = ("left", "center", "right")
LOGGER = logging.getLogger(__name__)


@dataclass
class ActiveSession:
    video_path: Path
    media: MediaInfo
    setup: dict[str, object] | None = None
    transcript_words: list[TranscriptWord] = field(default_factory=list)
    clue_entries: list[ClueReviewEntry] = field(default_factory=list)
    transcription_info: dict[str, object] | None = None
    transcript_text: str = ""


@dataclass
class ClueReviewEntry:
    id: str
    clue_word: str
    speaker: Speaker
    matched_text: str | None
    token_start_index: int | None
    token_end_index: int | None
    start: float | None
    end: float | None
    absolute_distance: int | None
    normalized_distance: float | None
    confidence: Literal["high", "review", "not_found"]
    review_status: Literal["pending", "accepted"]
    manual_match: bool = False
    time_nudge_seconds: float = 0.0
    display_time_seconds: float | None = None


@dataclass
class TranscriptionJob:
    id: str
    state: Literal["queued", "running", "completed", "failed"]
    message: str
    progress: int | None = None
    error: str | None = None


def _review_entry_from_match(match: ClueMatch) -> ClueReviewEntry:
    return ClueReviewEntry(
        id=str(uuid.uuid4()),
        clue_word=match.clue_word,
        speaker=match.speaker,
        matched_text=match.matched_text,
        token_start_index=match.token_start_index,
        token_end_index=match.token_end_index,
        start=match.start,
        end=match.end,
        absolute_distance=match.absolute_distance,
        normalized_distance=match.normalized_distance,
        confidence=match.confidence,
        review_status="accepted" if match.confidence == "high" else "pending",
        display_time_seconds=(
            clue_display_start(match.start, match.end)
            if match.start is not None and match.end is not None
            else None
        ),
    )


def _entry_response(entry: ClueReviewEntry) -> dict[str, object]:
    return asdict(entry)


def _session_response(session: ActiveSession) -> dict[str, object]:
    return {
        "video": _video_response(session.media),
        "setup": session.setup,
        "transcript_words": [asdict(word) for word in session.transcript_words],
        "transcript_text": session.transcript_text,
        "clue_entries": [_entry_response(entry) for entry in session.clue_entries],
        "transcription_info": session.transcription_info,
        "transcription_job": (
            _job_response(transcription_job) if transcription_job is not None else None
        ),
    }


def _job_response(job: TranscriptionJob) -> dict[str, object]:
    return asdict(job)


class MarkerPosition(BaseModel):
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class SetupRequest(BaseModel):
    player_words: dict[Speaker, str]
    marker_positions: dict[Speaker, MarkerPosition]
    clue_text: str


class ReviewEntryUpdate(BaseModel):
    id: str
    clue_word: str
    speaker: Speaker
    token_start_index: int | None
    token_end_index: int | None
    manual_match: bool
    time_nudge_seconds: float = Field(allow_inf_nan=False)
    review_status: Literal["pending", "accepted"]


class ReviewRequest(BaseModel):
    clue_entries: list[ReviewEntryUpdate]


app = FastAPI(title="Undercover Video Maker")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
active_session: ActiveSession | None = None
transcription_job: TranscriptionJob | None = None
job_lock = threading.Lock()


def _video_response(media: MediaInfo) -> dict[str, object]:
    return {
        "duration_seconds": media.duration_seconds,
        "width": media.width,
        "height": media.height,
        "url": "/api/video",
    }


def _job_is_running() -> bool:
    return transcription_job is not None and transcription_job.state in (
        "queued",
        "running",
    )


def _update_job(
    job_id: str,
    *,
    state: Literal["queued", "running", "completed", "failed"] | None = None,
    message: str | None = None,
    progress: int | None = None,
    error: str | None = None,
) -> None:
    with job_lock:
        if transcription_job is None or transcription_job.id != job_id:
            return
        if state is not None:
            transcription_job.state = state
        if message is not None:
            transcription_job.message = message
        transcription_job.progress = progress
        transcription_job.error = error


def _run_transcription(
    job_id: str,
    video_path: Path,
    clues: list[ClueInput],
) -> None:
    try:
        _update_job(job_id, state="running", message="Loading the French speech model.")

        def update_progress(segment_count: int) -> None:
            _update_job(
                job_id,
                message=f"Transcribing French speech… {segment_count} segments processed.",
            )

        transcript_words, info = transcribe_words(
            video_path,
            [clue.clue_word for clue in clues],
            update_progress,
        )
        matches = align_clue_words(clues, transcript_words)

        if active_session is None or active_session.video_path != video_path:
            raise RuntimeError("The active clip changed during transcription.")
        active_session.transcript_words = transcript_words
        active_session.transcript_text = " ".join(word.text for word in transcript_words)
        active_session.clue_entries = [
            _review_entry_from_match(match) for match in matches
        ]
        active_session.transcription_info = info
        _update_job(
            job_id,
            state="completed",
            message="Transcription and clue matching are complete.",
            progress=100,
        )
    except NoSpeechDetectedError as exc:
        _update_job(
            job_id,
            state="failed",
            message=str(exc),
            error=str(exc),
        )
    except Exception as exc:
        LOGGER.exception("Local transcription failed.")
        message = f"Transcription failed: {exc}"
        _update_job(
            job_id,
            state="failed",
            message=message,
            error=message,
        )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)) -> dict[str, object]:
    global active_session, transcription_job

    if _job_is_running():
        raise HTTPException(
            status_code=409,
            detail="Wait for transcription to finish before replacing the clip.",
        )

    candidate_path: Path | None = None
    try:
        filename = file.filename or ""
        if Path(filename).suffix.casefold() != ".mp4":
            raise HTTPException(
                status_code=415,
                detail="Choose an MP4 file. Other video formats are not supported.",
            )

        WORK_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".mp4",
            prefix="upload-",
            dir=WORK_DIR,
            delete=False,
        ) as candidate:
            candidate_path = Path(candidate.name)
            shutil.copyfileobj(file.file, candidate)

        try:
            media = inspect_mp4(candidate_path)
            validate_video_duration(media.duration_seconds)
        except MediaValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=500,
                detail="FFmpeg is unavailable. Check the local FFmpeg configuration.",
            ) from exc
        except OSError as exc:
            LOGGER.exception("FFmpeg could not be started while inspecting the clip.")
            raise HTTPException(
                status_code=500,
                detail="FFmpeg could not be started to inspect the clip.",
            ) from exc

        if CURRENT_WORK_DIR.exists():
            shutil.rmtree(CURRENT_WORK_DIR)
        CURRENT_WORK_DIR.mkdir(parents=True, exist_ok=True)
        INPUT_VIDEO_PATH.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.replace(INPUT_VIDEO_PATH)
        candidate_path = None
        FINAL_VIDEO_PATH.unlink(missing_ok=True)

        active_session = ActiveSession(video_path=INPUT_VIDEO_PATH, media=media)
        transcription_job = None
        return {"video": _video_response(media), "setup": None}
    except OSError as exc:
        LOGGER.exception("Failed to save the uploaded clip to the local work folder.")
        raise HTTPException(
            status_code=500,
            detail="The clip could not be saved to the local work folder.",
        ) from exc
    finally:
        if candidate_path is not None:
            candidate_path.unlink(missing_ok=True)
        await file.close()


@app.get("/api/session")
def get_session() -> dict[str, object]:
    if active_session is None:
        return {"video": None, "setup": None}
    return _session_response(active_session)


@app.put("/api/session")
def save_setup(setup: SetupRequest) -> dict[str, object]:
    if active_session is None:
        raise HTTPException(status_code=409, detail="Upload a clip before saving setup.")
    if _job_is_running():
        raise HTTPException(
            status_code=409,
            detail="Wait for transcription to finish before changing the setup.",
        )

    expected_players = set(PLAYERS)
    if set(setup.player_words) != expected_players:
        raise HTTPException(
            status_code=422,
            detail="Enter a word for Left, Center, and Right.",
        )
    if any(not word.strip() for word in setup.player_words.values()):
        raise HTTPException(
            status_code=422,
            detail="Enter a word for Left, Center, and Right.",
        )
    if set(setup.marker_positions) != expected_players:
        raise HTTPException(
            status_code=422,
            detail="Place a marker for Left, Center, and Right.",
        )

    try:
        clues = parse_clue_list(setup.clue_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    new_setup = {
        "player_words": setup.player_words,
        "marker_positions": {
            player: marker.model_dump()
            for player, marker in setup.marker_positions.items()
        },
        "clue_text": setup.clue_text,
        "clues": [
            {"word": clue.clue_word, "player": clue.speaker} for clue in clues
        ],
    }
    if active_session.setup != new_setup:
        active_session.transcript_words.clear()
        active_session.clue_entries.clear()
        active_session.transcription_info = None
        active_session.transcript_text = ""
    active_session.setup = new_setup
    return {"setup": active_session.setup, "ready": True}


@app.post("/api/transcription")
def start_transcription() -> dict[str, object]:
    global transcription_job

    if active_session is None:
        raise HTTPException(status_code=409, detail="Upload a clip before transcription.")
    if active_session.setup is None:
        raise HTTPException(status_code=409, detail="Save the player and clue setup first.")
    if _job_is_running():
        raise HTTPException(status_code=409, detail="Transcription is already running.")

    clues = [
        ClueInput(clue_word=item["word"], speaker=item["player"])
        for item in active_session.setup["clues"]
    ]
    transcription_job = TranscriptionJob(
        id=str(uuid.uuid4()),
        state="queued",
        message="Waiting to start transcription.",
    )
    job = transcription_job
    active_session.transcript_words.clear()
    active_session.clue_entries.clear()
    active_session.transcription_info = None
    active_session.transcript_text = ""
    threading.Thread(
        target=_run_transcription,
        args=(job.id, active_session.video_path, clues),
        daemon=True,
    ).start()
    return _job_response(job)


@app.get("/api/jobs/{job_id}")
def get_transcription_job(job_id: str) -> dict[str, object]:
    with job_lock:
        if transcription_job is None or transcription_job.id != job_id:
            raise HTTPException(status_code=404, detail="Transcription job not found.")
        return _job_response(transcription_job)


@app.put("/api/review")
def save_review(review: ReviewRequest) -> dict[str, object]:
    if active_session is None or active_session.transcription_info is None:
        raise HTTPException(status_code=409, detail="Transcribe the clip before reviewing.")
    if _job_is_running():
        raise HTTPException(
            status_code=409,
            detail="Wait for transcription to finish before changing the review.",
        )

    current_entries = {entry.id: entry for entry in active_session.clue_entries}
    ids = [entry.id for entry in review.clue_entries]
    if len(ids) != len(set(ids)) or any(entry_id not in current_entries for entry_id in ids):
        raise HTTPException(status_code=422, detail="Review entries are invalid.")

    updated_entries: list[ClueReviewEntry] = []
    for update in review.clue_entries:
        clue_word = update.clue_word.strip()
        if not clue_word:
            raise HTTPException(status_code=422, detail="Clue words cannot be empty.")
        if not normalize_text(clue_word):
            raise HTTPException(
                status_code=422,
                detail="Clue words must contain a letter or number.",
            )
        if (update.token_start_index is None) != (update.token_end_index is None):
            raise HTTPException(status_code=422, detail="Transcript selection is incomplete.")

        existing = current_entries[update.id]
        start_index = update.token_start_index
        end_index = update.token_end_index
        if start_index is None:
            matched_text = None
            start = None
            end = None
            confidence: Literal["high", "review", "not_found"] = "not_found"
            absolute_distance = None
            normalized_distance = None
            display_time = None
            manual_match = False
        else:
            if (
                end_index is None
                or start_index < 0
                or end_index < start_index
                or end_index >= len(active_session.transcript_words)
            ):
                raise HTTPException(status_code=422, detail="Transcript selection is invalid.")
            selected_words = active_session.transcript_words[start_index : end_index + 1]
            matched_text = " ".join(word.text for word in selected_words)
            start = selected_words[0].start
            end = selected_words[-1].end
            confidence = "review" if update.manual_match else existing.confidence
            if confidence == "not_found":
                confidence = "review"
            absolute_distance = existing.absolute_distance
            normalized_distance = existing.normalized_distance
            display_time = clue_display_start(start, end, update.time_nudge_seconds)
            manual_match = update.manual_match

        updated_entries.append(
            ClueReviewEntry(
                id=update.id,
                clue_word=clue_word,
                speaker=update.speaker,
                matched_text=matched_text,
                token_start_index=start_index,
                token_end_index=end_index,
                start=start,
                end=end,
                absolute_distance=absolute_distance,
                normalized_distance=normalized_distance,
                confidence=confidence,
                review_status=update.review_status,
                manual_match=manual_match,
                time_nudge_seconds=update.time_nudge_seconds,
                display_time_seconds=display_time,
            )
        )

    active_session.clue_entries = updated_entries
    return {"clue_entries": [_entry_response(entry) for entry in updated_entries]}


@app.get("/api/video")
def get_video() -> FileResponse:
    if active_session is None or not active_session.video_path.is_file():
        raise HTTPException(status_code=404, detail="Upload a clip to preview it.")
    return FileResponse(
        active_session.video_path,
        media_type="video/mp4",
    )
