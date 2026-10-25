from __future__ import annotations

import shutil
import tempfile
import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.alignment import Speaker, parse_clue_list
from app.config import WORK_DIR
from app.media import (
    MediaInfo,
    MediaValidationError,
    inspect_mp4,
    validate_video_duration,
)


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


class MarkerPosition(BaseModel):
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class SetupRequest(BaseModel):
    player_words: dict[Speaker, str]
    marker_positions: dict[Speaker, MarkerPosition]
    clue_text: str


app = FastAPI(title="Undercover Video Maker")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
active_session: ActiveSession | None = None


def _video_response(media: MediaInfo) -> dict[str, object]:
    return {
        "duration_seconds": media.duration_seconds,
        "width": media.width,
        "height": media.height,
        "url": "/api/video",
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)) -> dict[str, object]:
    global active_session

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
            LOGGER.exception("Failed to save the uploaded clip to the local work folder.")
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
        return {"video": _video_response(media), "setup": None}
    except OSError as exc:
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
    return {
        "video": _video_response(active_session.media),
        "setup": active_session.setup,
    }


@app.put("/api/session")
def save_setup(setup: SetupRequest) -> dict[str, object]:
    if active_session is None:
        raise HTTPException(status_code=409, detail="Upload a clip before saving setup.")

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

    active_session.setup = {
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
    return {"setup": active_session.setup, "ready": True}


@app.get("/api/video")
def get_video() -> FileResponse:
    if active_session is None or not active_session.video_path.is_file():
        raise HTTPException(status_code=404, detail="Upload a clip to preview it.")
    return FileResponse(
        active_session.video_path,
        media_type="video/mp4",
    )
