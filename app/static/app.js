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
  transcriptStep: document.querySelector("#transcript-step"),
  renderStep: document.querySelector("#render-step"),
  transcriptPanel: document.querySelector("#transcript-panel"),
  transcriptVideo: document.querySelector("#transcript-video"),
  transcriptContent: document.querySelector("#transcript-content"),
  transcriptionProgress: document.querySelector("#transcription-progress"),
  progressTitle: document.querySelector("#progress-title"),
  progressMessage: document.querySelector("#progress-message"),
  transcriptWords: document.querySelector("#transcript-words"),
  transcriptWordCount: document.querySelector("#transcript-word-count"),
  reviewList: document.querySelector("#review-list"),
  reviewCount: document.querySelector("#review-count"),
  reviewBlocker: document.querySelector("#review-blocker"),
  manualSelectHint: document.querySelector("#manual-select-hint"),
  acceptAll: document.querySelector("#accept-all"),
  startOver: document.querySelector("#start-over"),
  renderButton: document.querySelector("#render-button"),
  renderPanel: document.querySelector("#render-panel"),
  renderProgress: document.querySelector("#render-progress"),
  renderProgressTitle: document.querySelector("#render-progress-title"),
  renderProgressMessage: document.querySelector("#render-progress-message"),
  renderProgressBar: document.querySelector("#render-progress-bar"),
  renderContent: document.querySelector("#render-content"),
  finalVideo: document.querySelector("#final-video"),
  downloadOutput: document.querySelector("#download-output"),
  backToTranscript: document.querySelector("#back-to-transcript"),
};

let video = null;
let selectedPlayer = "left";
let markerPositions = {};
let draggingPlayer = null;
let savedSetupSnapshot = "";
let transcriptWords = [];
let reviewEntries = [];
let selectedEntryId = null;
let transcriptionRunning = false;
let renderingRunning = false;
let renderOutputReady = false;

function setGlobalError(message = "") {
  elements.globalError.textContent = message;
  elements.globalError.hidden = !message;
}

function setUploadStatus(message, isError = false) {
  elements.uploadStatus.textContent = message;
  elements.uploadStatus.classList.toggle("error", isError);
}

function setStep(step) {
  const isUpload = step === "upload";
  const isWords = step === "words";
  const isTranscript = step === "transcript";
  const isRender = step === "render";
  elements.uploadPanel.hidden = !isUpload;
  elements.wordsPanel.hidden = !isWords;
  elements.transcriptPanel.hidden = !isTranscript;
  elements.renderPanel.hidden = !isRender;
  elements.uploadStep.classList.toggle("active", isUpload);
  elements.uploadStep.classList.toggle("complete", !isUpload);
  elements.wordsStep.classList.toggle("active", isWords);
  elements.wordsStep.classList.toggle("complete", isTranscript || isRender);
  elements.transcriptStep.classList.toggle("active", isTranscript);
  elements.transcriptStep.classList.toggle("complete", isRender);
  elements.renderStep.classList.toggle("active", isRender);
  elements.wordsStep.disabled = !video;
  elements.transcriptStep.disabled = (
    (!transcriptWords.length && !transcriptionRunning)
    || (transcriptWords.length > 0 && setupSnapshot() !== savedSetupSnapshot)
  );
  elements.transcriptStep.classList.toggle("unavailable", elements.transcriptStep.disabled);
  elements.renderStep.disabled = !renderOutputReady && !renderingRunning;
  elements.renderStep.classList.toggle("unavailable", elements.renderStep.disabled);
  elements.uploadStep.removeAttribute("aria-current");
  elements.wordsStep.removeAttribute("aria-current");
  elements.transcriptStep.removeAttribute("aria-current");
  elements.renderStep.removeAttribute("aria-current");
  const stepButton = isRender
    ? elements.renderStep
    : isTranscript
      ? elements.transcriptStep
      : isWords
        ? elements.wordsStep
        : elements.uploadStep;
  stepButton.setAttribute("aria-current", "step");
  const stepNumber = isRender ? "04" : isTranscript ? "03" : isWords ? "02" : "01";
  elements.stepCount.setAttribute("aria-label", `Step ${Number(stepNumber)} of 4`);
  elements.stepCount.querySelector(".step-count-number").textContent = stepNumber;
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
  elements.transcriptVideo.src = source;
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
    transcriptWords = [];
    reviewEntries = [];
    selectedEntryId = null;
    renderOutputReady = false;
    renderingRunning = false;
    elements.transcriptContent.hidden = true;
    elements.transcriptionProgress.hidden = true;
    elements.transcriptStep.disabled = true;
    elements.renderContent.hidden = true;
    elements.renderProgress.hidden = true;
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
  const isSaved = setupSnapshot() === savedSetupSnapshot;
  elements.saveSetup.disabled = !ready || transcriptionRunning;
  elements.transcribeButton.disabled = !ready || !isSaved || transcriptionRunning;
  elements.renderStep.disabled = !renderOutputReady && !renderingRunning;
  elements.renderStep.classList.toggle("unavailable", elements.renderStep.disabled);
  elements.transcriptStep.disabled = (
    (!transcriptWords.length && !transcriptionRunning)
    || (transcriptWords.length > 0 && !isSaved)
  );
  elements.transcriptStep.classList.toggle("unavailable", elements.transcriptStep.disabled);
  elements.setupStatus.classList.toggle("ready", ready);
  elements.setupStatusDot.classList.toggle("status-dot-muted", !ready);

  if (ready) {
    elements.setupStatus.textContent = isSaved
      ? "Setup saved for this session. Ready to transcribe."
      : "Setup is ready. Save it before starting transcription.";
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
    transcriptWords = result.transcript_words || [];
    reviewEntries = result.clue_entries || [];
    renderOutputReady = Boolean(result.output_ready);
    const job = result.processing_job;
    if (job?.state === "queued" || job?.state === "running") {
      if (job.kind === "render") {
        renderingRunning = true;
        renderRenderJob(job);
        setStep("render");
      } else {
        transcriptionRunning = true;
        renderJob(job);
        setStep("transcript");
      }
      watchProcessingJob(job.id, job.kind);
    } else if (renderOutputReady) {
      showRenderedVideo();
      setStep("render");
    } else if (result.transcription_info) {
      renderTranscript();
      setStep("transcript");
    } else {
      setStep("upload");
    }
  } catch (error) {
    setGlobalError(error.message);
  }
}

async function saveSetup() {
  if (!validateSetup()) return false;
  const setupChanged = setupSnapshot() !== savedSetupSnapshot;
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
    if (setupChanged) {
      transcriptWords = [];
      reviewEntries = [];
      selectedEntryId = null;
      renderOutputReady = false;
      elements.transcriptContent.hidden = true;
      elements.transcriptionProgress.hidden = true;
      elements.transcriptStep.disabled = true;
      elements.renderContent.hidden = true;
    }
    return true;
  } catch (error) {
    elements.setupStatus.textContent = error.message;
    elements.setupStatus.classList.remove("ready");
    return false;
  } finally {
    validateSetup();
  }
}

function formatTime(seconds) {
  return `${seconds.toFixed(2)}s`;
}

function renderJob(job) {
  elements.transcriptionProgress.hidden = false;
  elements.transcriptContent.hidden = true;
  elements.progressTitle.textContent = job.state === "failed"
    ? "Transcription could not finish"
    : "Transcription in progress";
  elements.progressMessage.textContent = job.message;
  elements.transcriptionProgress.classList.toggle("failed", job.state === "failed");
}

function renderTranscript() {
  elements.transcriptVideo.src = videoUrl();
  elements.transcriptionProgress.hidden = true;
  elements.transcriptContent.hidden = false;
  elements.transcriptWordCount.textContent = `${transcriptWords.length} WORDS`;
  elements.reviewCount.textContent = `${reviewEntries.length} CLUES`;

  elements.transcriptWords.replaceChildren();
  transcriptWords.forEach((word, index) => {
    const token = document.createElement("button");
    token.type = "button";
    token.className = "transcript-token";
    token.dataset.wordIndex = String(index);
    token.textContent = word.text;
    token.title = `${formatTime(word.start)} – ${formatTime(word.end)}`;
    if (reviewEntries.some((entry) => entry.token_start_index !== null
      && entry.token_end_index !== null
      && entry.token_start_index <= index
      && entry.token_end_index >= index)) {
      token.classList.add("matched");
    }
    elements.transcriptWords.append(token);
  });

  elements.reviewList.replaceChildren();
  reviewEntries.forEach((entry, index) => {
    const row = document.createElement("article");
    row.className = `review-entry confidence-${entry.confidence}`;
    if (selectedEntryId === entry.id) row.classList.add("selecting");

    const heading = document.createElement("div");
    heading.className = "review-entry-heading";
    const label = document.createElement("span");
    label.className = "review-entry-number";
    label.textContent = `CLUE ${String(index + 1).padStart(2, "0")}`;
    const confidence = document.createElement("span");
    confidence.className = `confidence-tag confidence-${entry.confidence}`;
    confidence.textContent = entry.confidence === "high"
      ? "MATCHED"
      : entry.confidence === "review"
        ? "CHECK MATCH"
        : "NOT FOUND";
    heading.append(label, confidence);

    const fields = document.createElement("div");
    fields.className = "review-fields";
    const clueInput = document.createElement("input");
    clueInput.type = "text";
    clueInput.value = entry.clue_word;
    clueInput.setAttribute("aria-label", `Edit clue ${index + 1}`);
    clueInput.dataset.entryId = entry.id;
    clueInput.dataset.reviewField = "clue_word";

    const playerSelect = document.createElement("select");
    playerSelect.setAttribute("aria-label", `Player for clue ${index + 1}`);
    playerSelect.dataset.entryId = entry.id;
    playerSelect.dataset.reviewField = "speaker";
    for (const player of PLAYERS) {
      const option = document.createElement("option");
      option.value = player.id;
      option.textContent = player.name;
      option.selected = entry.speaker === player.id;
      playerSelect.append(option);
    }
    fields.append(clueInput, playerSelect);

    const matchText = document.createElement("p");
    matchText.className = "match-text";
    matchText.textContent = entry.matched_text
      ? `Heard: “${entry.matched_text}”`
      : "No matching word was found in the transcript.";

    const timing = document.createElement("div");
    timing.className = "review-timing";
    const timeLabel = document.createElement("span");
    timeLabel.textContent = entry.display_time_seconds === null
      ? "Time not set"
      : `Display at ${formatTime(entry.display_time_seconds)}`;
    timing.append(timeLabel);

    if (entry.start !== null) {
      const seekButton = document.createElement("button");
      seekButton.type = "button";
      seekButton.className = "text-button";
      seekButton.textContent = "▶ Listen";
      seekButton.dataset.entryId = entry.id;
      seekButton.dataset.reviewAction = "seek";
      timing.append(seekButton);

      for (const direction of [-1, 1]) {
        const nudge = document.createElement("button");
        nudge.type = "button";
        nudge.className = "nudge-button";
        nudge.textContent = direction < 0 ? "−0.1s" : "+0.1s";
        nudge.setAttribute("aria-label", `${direction < 0 ? "Earlier" : "Later"} by 0.1 seconds`);
        nudge.dataset.entryId = entry.id;
        nudge.dataset.nudge = String(direction);
        timing.append(nudge);
      }
    }

    const actions = document.createElement("div");
    actions.className = "review-entry-actions";
    if (entry.confidence === "not_found") {
      const findButton = document.createElement("button");
      findButton.type = "button";
      findButton.className = "button button-secondary button-small";
      findButton.textContent = selectedEntryId === entry.id ? "Select a transcript word…" : "Find in transcript";
      findButton.dataset.entryId = entry.id;
      findButton.dataset.reviewAction = "select-word";
      actions.append(findButton);
    } else {
      const acceptButton = document.createElement("button");
      acceptButton.type = "button";
      acceptButton.className = "text-button";
      acceptButton.textContent = entry.review_status === "accepted" ? "Accepted ✓" : "Accept match";
      acceptButton.dataset.entryId = entry.id;
      acceptButton.dataset.reviewAction = "accept";
      actions.append(acceptButton);
    }
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "text-button delete-entry";
    deleteButton.textContent = "Delete";
    deleteButton.dataset.entryId = entry.id;
    deleteButton.dataset.reviewAction = "delete";
    actions.append(deleteButton);

    row.append(heading, fields, matchText, timing, actions);
    elements.reviewList.append(row);
  });

  const notFoundCount = reviewEntries.filter((entry) => entry.confidence === "not_found").length;
  const matchedCount = reviewEntries.filter(
    (entry) => entry.start !== null && entry.end !== null,
  ).length;
  elements.reviewBlocker.hidden = notFoundCount === 0 && matchedCount > 0;
  elements.reviewBlocker.textContent = notFoundCount > 0
    ? notFoundCount === 1
      ? "Find or delete the not-found clue before rendering."
      : `${notFoundCount} not-found clues must be found or deleted before rendering.`
    : "At least one clue needs a transcript match before rendering.";
  elements.renderButton.disabled = (
    notFoundCount > 0 || matchedCount === 0 || renderingRunning
  );
  elements.renderStep.disabled = !renderOutputReady && !renderingRunning;
  elements.renderStep.classList.toggle("unavailable", elements.renderStep.disabled);
  elements.acceptAll.disabled = !reviewEntries.some(
    (entry) => entry.confidence !== "not_found" && entry.review_status !== "accepted",
  );
  elements.transcriptStep.disabled = (
    (!transcriptWords.length && !transcriptionRunning)
    || (transcriptWords.length > 0 && setupSnapshot() !== savedSetupSnapshot)
  );
  elements.transcriptStep.classList.toggle("unavailable", elements.transcriptStep.disabled);
  elements.manualSelectHint.textContent = selectedEntryId
    ? "Select the matching word in the transcript below."
    : "Choose “Find in transcript” on a not-found clue, then select its spoken word below.";
}

async function persistReview() {
  try {
    const result = await readResponse(await fetch("/api/review", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clue_entries: reviewEntries }),
    }));
    reviewEntries = result.clue_entries;
    renderOutputReady = Boolean(result.output_ready);
    setGlobalError();
    renderTranscript();
    return true;
  } catch (error) {
    setGlobalError(error.message);
    return false;
  }
}

async function loadTranscriptionResult() {
  const result = await readResponse(await fetch("/api/session"));
  transcriptWords = result.transcript_words || [];
  reviewEntries = result.clue_entries || [];
  renderOutputReady = Boolean(result.output_ready);
  renderTranscript();
}

function renderRenderJob(job) {
  elements.renderProgress.hidden = false;
  elements.renderContent.hidden = true;
  elements.renderProgressTitle.textContent = job.state === "failed"
    ? "Rendering could not finish"
    : "Rendering your video";
  elements.renderProgressMessage.textContent = job.message;
  elements.renderProgressBar.style.width = `${job.progress || 0}%`;
  elements.renderProgress.classList.toggle("failed", job.state === "failed");
}

function showRenderedVideo() {
  const source = `/api/output?session=${Date.now()}`;
  elements.finalVideo.src = source;
  elements.downloadOutput.href = source;
  elements.renderContent.hidden = false;
  elements.renderProgress.hidden = true;
  renderOutputReady = true;
  renderingRunning = false;
  elements.renderStep.disabled = false;
  elements.renderStep.classList.remove("unavailable");
}

async function watchProcessingJob(jobId, kind) {
  while (true) {
    try {
      const job = await readResponse(await fetch(`/api/jobs/${encodeURIComponent(jobId)}`));
      if (kind === "render") {
        renderRenderJob(job);
      } else {
        renderJob(job);
      }
      if (job.state === "completed") {
        if (kind === "render") {
          const session = await readResponse(await fetch("/api/session"));
          if (!session.output_ready) {
            throw new Error("The rendered video is not ready to play yet.");
          }
          showRenderedVideo();
          setStep("render");
        } else {
          await loadTranscriptionResult();
          transcriptionRunning = false;
          setStep("transcript");
        }
        validateSetup();
        return;
      }
      if (job.state === "failed") {
        if (kind === "render") {
          renderingRunning = false;
        } else {
          transcriptionRunning = false;
        }
        validateSetup();
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 700));
    } catch (error) {
      if (kind === "render") {
        renderingRunning = false;
        renderRenderJob({ state: "failed", message: error.message });
      } else {
        transcriptionRunning = false;
        renderJob({ state: "failed", message: error.message });
      }
      validateSetup();
      return;
    }
  }
}

async function startTranscription() {
  if (!await saveSetup()) return;
  transcriptionRunning = true;
  transcriptWords = [];
  reviewEntries = [];
  selectedEntryId = null;
  renderOutputReady = false;
  elements.transcriptContent.hidden = true;
  elements.renderContent.hidden = true;
  renderJob({ state: "queued", message: "Starting transcription…" });
  setStep("transcript");
  validateSetup();
  try {
    const job = await readResponse(await fetch("/api/transcription", { method: "POST" }));
    watchProcessingJob(job.id, "transcription");
  } catch (error) {
    transcriptionRunning = false;
    renderJob({ state: "failed", message: error.message });
    validateSetup();
  }
}

async function startRender() {
  renderingRunning = true;
  renderRenderJob({ state: "queued", progress: 0, message: "Starting rendering…" });
  elements.renderButton.disabled = true;
  setStep("render");
  validateSetup();
  try {
    const job = await readResponse(await fetch("/api/render", { method: "POST" }));
    watchProcessingJob(job.id, "render");
  } catch (error) {
    renderingRunning = false;
    renderRenderJob({ state: "failed", message: error.message });
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
elements.transcriptStep.addEventListener("click", () => {
  if (transcriptWords.length || transcriptionRunning) setStep("transcript");
});
elements.renderStep.addEventListener("click", () => {
  if (renderOutputReady || renderingRunning) setStep("render");
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
elements.transcribeButton.addEventListener("click", startTranscription);
elements.renderButton.addEventListener("click", startRender);
elements.startOver.addEventListener("click", () => setStep("words"));
elements.backToTranscript.addEventListener("click", () => setStep("transcript"));
elements.acceptAll.addEventListener("click", async () => {
  reviewEntries = reviewEntries.map((entry) => (
    entry.confidence === "not_found"
      ? entry
      : { ...entry, review_status: "accepted" }
  ));
  await persistReview();
});

elements.reviewList.addEventListener("change", async (event) => {
  const field = event.target.closest("[data-review-field]");
  if (!field) return;
  const entry = reviewEntries.find((item) => item.id === field.dataset.entryId);
  if (!entry) return;
  entry[field.dataset.reviewField] = field.value;
  await persistReview();
});

elements.reviewList.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  const entry = reviewEntries.find((item) => item.id === button.dataset.entryId);
  if (button.dataset.reviewAction === "select-word" && entry) {
    selectedEntryId = entry.id;
    renderTranscript();
    return;
  }
  if (button.dataset.reviewAction === "seek" && entry && entry.start !== null) {
    elements.transcriptVideo.currentTime = entry.start;
    return;
  }
  if (button.dataset.reviewAction === "accept" && entry) {
    entry.review_status = "accepted";
  } else if (button.dataset.reviewAction === "delete" && entry) {
    reviewEntries = reviewEntries.filter((item) => item.id !== entry.id);
    if (selectedEntryId === entry.id) selectedEntryId = null;
  } else if (button.dataset.nudge && entry) {
    entry.time_nudge_seconds = Number(
      (entry.time_nudge_seconds + Number(button.dataset.nudge) * 0.1).toFixed(1),
    );
  } else {
    return;
  }
  await persistReview();
});

elements.transcriptWords.addEventListener("click", async (event) => {
  const token = event.target.closest("[data-word-index]");
  if (!token) return;
  const index = Number(token.dataset.wordIndex);
  const word = transcriptWords[index];
  if (!word) return;
  elements.transcriptVideo.currentTime = word.start;
  if (!selectedEntryId) return;

  const entry = reviewEntries.find((item) => item.id === selectedEntryId);
  if (!entry) {
    selectedEntryId = null;
    renderTranscript();
    return;
  }
  entry.token_start_index = index;
  entry.token_end_index = index;
  entry.manual_match = true;
  entry.review_status = "accepted";
  selectedEntryId = null;
  await persistReview();
});

window.addEventListener("resize", () => {
  if (video && !elements.wordsPanel.hidden) fitVideoStage(video);
});

loadSetup();
