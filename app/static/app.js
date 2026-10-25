"use strict";

const PLAYERS = [
  { id: "left", name: "Left", initial: "L", markerNumber: "1" },
  { id: "center", name: "Center", initial: "C", markerNumber: "2" },
  { id: "right", name: "Right", initial: "R", markerNumber: "3" },
];

const elements = {
  uploadPanel: document.querySelector("#upload-panel"),
  wordsPanel: document.querySelector("#words-panel"),
  dropZone: document.querySelector("#drop-zone"),
  fileInput: document.querySelector("#file-input"),
  chooseFile: document.querySelector("#choose-file"),
  replaceVideo: document.querySelector("#replace-video"),
  uploadStatus: document.querySelector("#upload-status"),
  uploadPreviewCard: document.querySelector("#upload-preview-card"),
  uploadPreview: document.querySelector("#upload-preview"),
  wordsVideo: document.querySelector("#words-video"),
  clipDuration: document.querySelector("#clip-duration"),
  clipDimensions: document.querySelector("#clip-dimensions"),
  continueToWords: document.querySelector("#continue-to-words"),
  globalError: document.querySelector("#global-error"),
  videoStage: document.querySelector("#video-stage"),
  markerLayer: document.querySelector("#marker-layer"),
  clueText: document.querySelector("#clue-text"),
  clueError: document.querySelector("#clue-error"),
  saveSetup: document.querySelector("#save-setup"),
  transcribeButton: document.querySelector("#transcribe-button"),
  setupStatus: document.querySelector("#setup-status"),
  setupStatusDot: document.querySelector("#setup-status-dot"),
  stepCount: document.querySelector(".step-count"),
  uploadStep: document.querySelector('[data-go-step="upload"]'),
  wordsStep: document.querySelector('[data-go-step="words"]'),
};

let video = null;
let selectedPlayer = "left";
let markerPositions = {};
let draggingPlayer = null;
let savedSetupSnapshot = "";

function setGlobalError(message = "") {
  elements.globalError.textContent = message;
  elements.globalError.hidden = !message;
}

function setUploadStatus(message, isError = false) {
  elements.uploadStatus.textContent = message;
  elements.uploadStatus.classList.toggle("error", isError);
}

function setStep(step) {
  const isWords = step === "words";
  elements.uploadPanel.hidden = isWords;
  elements.wordsPanel.hidden = !isWords;
  elements.uploadStep.classList.toggle("active", !isWords);
  elements.uploadStep.classList.toggle("complete", isWords);
  elements.wordsStep.classList.toggle("active", isWords);
  elements.wordsStep.disabled = !video;
  elements.uploadStep.removeAttribute("aria-current");
  elements.wordsStep.removeAttribute("aria-current");
  (isWords ? elements.wordsStep : elements.uploadStep).setAttribute("aria-current", "step");
  elements.stepCount.setAttribute("aria-label", isWords ? "Step 2 of 4" : "Step 1 of 4");
  elements.stepCount.querySelector(".step-count-number").textContent = isWords ? "02" : "01";
  setGlobalError();

  if (isWords && elements.wordsVideo.readyState >= 1) {
    elements.wordsVideo.pause();
    elements.wordsVideo.currentTime = 0;
  }
  if (isWords && video) {
    requestAnimationFrame(() => fitVideoStage(video));
  }
}

function fitVideoStage(info) {
  const card = elements.videoStage.parentElement;
  const cardStyle = window.getComputedStyle(card);
  const availableWidth = card.clientWidth
    - Number.parseFloat(cardStyle.paddingLeft)
    - Number.parseFloat(cardStyle.paddingRight);
  if (availableWidth <= 0) return;

  const maxHeight = Math.max(180, Math.min(window.innerHeight * 0.68, 680));
  const scale = Math.min(availableWidth / info.width, maxHeight / info.height);
  elements.videoStage.style.width = `${Math.round(info.width * scale)}px`;
  elements.videoStage.style.height = `${Math.round(info.height * scale)}px`;
}

function videoUrl() {
  return `/api/video?session=${Date.now()}`;
}

function displayVideo(info) {
  video = info;
  const source = videoUrl();
  elements.uploadPreview.src = source;
  elements.wordsVideo.src = source;
  elements.clipDuration.textContent = `${info.duration_seconds.toFixed(1)} sec`;
  elements.clipDimensions.textContent = `${info.width} × ${info.height}`;
  elements.uploadPreviewCard.hidden = false;
  elements.dropZone.hidden = true;
  elements.continueToWords.disabled = false;
  elements.wordsStep.disabled = false;
  elements.videoStage.style.aspectRatio = `${info.width} / ${info.height}`;
  setUploadStatus("Video checked and ready.");
}

function showUploadPicker() {
  elements.fileInput.value = "";
  elements.fileInput.click();
}

async function readResponse(response) {
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`The server returned an unreadable response (${response.status}).`);
  }
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "The request could not be completed.");
  }
  return data;
}

async function uploadFile(file) {
  setGlobalError();
  const previousVideo = video;
  elements.continueToWords.disabled = true;
  setUploadStatus("Checking your MP4…");

  const form = new FormData();
  form.append("file", file);
  try {
    const result = await readResponse(
      await fetch("/api/upload", { method: "POST", body: form }),
    );
    resetSetup();
    displayVideo(result.video);
    await loadSetup(result.setup);
  } catch (error) {
    setUploadStatus(error.message, true);
    setGlobalError(previousVideo ? error.message : "");
    elements.continueToWords.disabled = !previousVideo;
    elements.wordsStep.disabled = !previousVideo;
  }
}

function clueValidation(text) {
  const lines = text.split(/\r?\n/);
  let validRows = 0;
  const playerNames = new Set(PLAYERS.map((player) => player.id));

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.trim()) continue;
    if ((line.match(/,/g) || []).length !== 1) {
      return `Line ${index + 1}: expected "word, Left|Center|Right".`;
    }
    const [word, rawPlayer] = line.split(",").map((part) => part.trim());
    if (!word) return `Line ${index + 1}: enter a clue word before the comma.`;
    if (!/[\p{L}\p{N}]/u.test(word)) {
      return `Line ${index + 1}: clue words must contain a letter or number.`;
    }
    if (!rawPlayer) return `Line ${index + 1}: enter a player after the comma.`;
    if (!playerNames.has(rawPlayer.toLocaleLowerCase())) {
      return `Line ${index + 1}: player must be Left, Center, or Right.`;
    }
    validRows += 1;
  }

  if (validRows === 0) return "Enter at least one clue as “word, Player”.";
  return "";
}

function playerWord(playerId) {
  return document.querySelector(`[data-player-word="${playerId}"]`).value.trim();
}

function validateSetup() {
  const missingPlayer = PLAYERS.find((player) => !playerWord(player.id));
  const missingMarker = PLAYERS.find((player) => !markerPositions[player.id]);
  const clueError = clueValidation(elements.clueText.value);

  for (const player of PLAYERS) {
    const error = document.querySelector(`[data-player-error="${player.id}"]`);
    const input = document.querySelector(`[data-player-word="${player.id}"]`);
    const missing = !playerWord(player.id);
    error.textContent = missing ? "Enter this player's word." : "";
    error.hidden = !missing;
    input.setAttribute("aria-invalid", missing ? "true" : "false");
  }

  elements.clueError.textContent = clueError;
  elements.clueError.hidden = !clueError;
  elements.clueText.setAttribute("aria-invalid", clueError ? "true" : "false");

  const ready = Boolean(video && !missingPlayer && !missingMarker && !clueError);
  elements.saveSetup.disabled = !ready;
  elements.transcribeButton.disabled = true;
  elements.setupStatus.classList.toggle("ready", ready);
  elements.setupStatusDot.classList.toggle("status-dot-muted", !ready);

  if (ready) {
    elements.setupStatus.textContent = setupSnapshot() === savedSetupSnapshot
      ? "Setup saved for this session. Transcription is added in the next build step."
      : "Setup is ready. Save it to this session before transcription is added.";
  } else if (missingPlayer) {
    elements.setupStatus.textContent = `Enter a word for ${missingPlayer.name}.`;
  } else if (missingMarker) {
    elements.setupStatus.textContent = `Place a marker for ${missingMarker.name}.`;
  } else {
    elements.setupStatus.textContent = "Fix the clue list to continue.";
  }
  return ready;
}

function setupSnapshot() {
  return JSON.stringify({
    player_words: Object.fromEntries(PLAYERS.map((player) => [player.id, playerWord(player.id)])),
    marker_positions: markerPositions,
    clue_text: elements.clueText.value,
  });
}

function renderMarkers() {
  elements.markerLayer.replaceChildren();
  for (const player of PLAYERS) {
    const position = markerPositions[player.id];
    if (!position) continue;

    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = `player-marker player-${player.id}`;
    marker.dataset.markerPlayer = player.id;
    marker.setAttribute("aria-label", `Move ${player.name} marker`);
    marker.style.left = `${position.x}%`;
    marker.style.top = `${position.y}%`;

    const token = document.createElement("span");
    token.className = "player-token";
    token.textContent = player.markerNumber;
    const word = document.createElement("span");
    word.className = "marker-word";
    word.textContent = playerWord(player.id) || "Add word";
    marker.append(token, word);
    elements.markerLayer.append(marker);
  }
}

function setMarkerPosition(playerId, clientX, clientY) {
  const bounds = elements.videoStage.getBoundingClientRect();
  const x = Math.min(100, Math.max(0, ((clientX - bounds.left) / bounds.width) * 100));
  const y = Math.min(100, Math.max(0, ((clientY - bounds.top) / bounds.height) * 100));
  markerPositions[playerId] = { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) };
  const marker = elements.markerLayer.querySelector(`[data-marker-player="${playerId}"]`);
  if (marker) {
    marker.style.left = `${markerPositions[playerId].x}%`;
    marker.style.top = `${markerPositions[playerId].y}%`;
  } else {
    renderMarkers();
  }
  validateSetup();
}

function setSelectedPlayer(playerId) {
  selectedPlayer = playerId;
  for (const player of PLAYERS) {
    const button = document.querySelector(`[data-select-player="${player.id}"]`);
    button.classList.toggle("selected", player.id === playerId);
    button.setAttribute("aria-pressed", String(player.id === playerId));
  }
}

function applySetup(setup) {
  if (!setup) return;
  for (const player of PLAYERS) {
    const word = setup.player_words?.[player.id];
    if (typeof word === "string") {
      document.querySelector(`[data-player-word="${player.id}"]`).value = word;
    }
  }
  if (setup.marker_positions && typeof setup.marker_positions === "object") {
    markerPositions = setup.marker_positions;
  }
  if (typeof setup.clue_text === "string") {
    elements.clueText.value = setup.clue_text;
  }
  savedSetupSnapshot = setupSnapshot();
  renderMarkers();
  validateSetup();
}

function resetSetup() {
  for (const player of PLAYERS) {
    document.querySelector(`[data-player-word="${player.id}"]`).value = "";
  }
  setSelectedPlayer("left");
  markerPositions = {};
  elements.clueText.value = "";
  savedSetupSnapshot = "";
  renderMarkers();
  validateSetup();
}

async function loadSetup(setup = undefined) {
  if (setup !== undefined) {
    applySetup(setup);
    return;
  }
  try {
    const result = await readResponse(await fetch("/api/session"));
    if (result.video) displayVideo(result.video);
    applySetup(result.setup);
  } catch (error) {
    setGlobalError(error.message);
  }
}

async function saveSetup() {
  if (!validateSetup()) return;
  elements.saveSetup.disabled = true;
  elements.setupStatus.textContent = "Saving setup…";
  try {
    const result = await readResponse(await fetch("/api/session", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_words: Object.fromEntries(PLAYERS.map((player) => [player.id, playerWord(player.id)])),
        marker_positions: markerPositions,
        clue_text: elements.clueText.value,
      }),
    }));
    savedSetupSnapshot = setupSnapshot();
    applySetup(result.setup);
  } catch (error) {
    elements.setupStatus.textContent = error.message;
    elements.setupStatus.classList.remove("ready");
  } finally {
    validateSetup();
  }
}

elements.chooseFile.addEventListener("click", showUploadPicker);
elements.replaceVideo.addEventListener("click", showUploadPicker);
elements.fileInput.addEventListener("change", () => {
  const [file] = elements.fileInput.files;
  if (file) uploadFile(file);
});

for (const eventName of ["dragenter", "dragover"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.add("dragging");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("dragging");
  });
}

elements.dropZone.addEventListener("drop", (event) => {
  const [file] = event.dataTransfer.files;
  if (file) uploadFile(file);
});

elements.continueToWords.addEventListener("click", () => {
  if (!video) return;
  setStep("words");
  validateSetup();
});
elements.uploadStep.addEventListener("click", () => setStep("upload"));
elements.wordsStep.addEventListener("click", () => {
  if (video) setStep("words");
});

document.querySelectorAll("[data-select-player]").forEach((button) => {
  button.addEventListener("click", () => setSelectedPlayer(button.dataset.selectPlayer));
});

document.querySelectorAll("[data-player-word]").forEach((input) => {
  input.addEventListener("input", () => {
    renderMarkers();
    validateSetup();
    if (setupSnapshot() !== savedSetupSnapshot) {
      elements.setupStatus.textContent = "Unsaved changes.";
    }
  });
});

elements.clueText.addEventListener("input", () => {
  validateSetup();
  if (setupSnapshot() !== savedSetupSnapshot) {
    elements.setupStatus.textContent = "Unsaved changes.";
  }
});

elements.videoStage.addEventListener("pointerdown", (event) => {
  const marker = event.target.closest("[data-marker-player]");
  if (marker) {
    draggingPlayer = marker.dataset.markerPlayer;
    elements.videoStage.setPointerCapture(event.pointerId);
    setMarkerPosition(draggingPlayer, event.clientX, event.clientY);
    event.preventDefault();
    return;
  }
  if (!video) return;
  setMarkerPosition(selectedPlayer, event.clientX, event.clientY);
});

elements.videoStage.addEventListener("pointermove", (event) => {
  if (draggingPlayer) {
    setMarkerPosition(draggingPlayer, event.clientX, event.clientY);
  }
});

function stopDragging() {
  draggingPlayer = null;
}

elements.videoStage.addEventListener("pointerup", stopDragging);
elements.videoStage.addEventListener("pointercancel", stopDragging);

elements.videoStage.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  const bounds = elements.videoStage.getBoundingClientRect();
  setMarkerPosition(
    selectedPlayer,
    bounds.left + bounds.width / 2,
    bounds.top + bounds.height / 2,
  );
});

elements.saveSetup.addEventListener("click", saveSetup);
window.addEventListener("resize", () => {
  if (video && !elements.wordsPanel.hidden) fitVideoStage(video);
});

loadSetup();
