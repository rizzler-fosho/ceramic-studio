/**
 * ai_upload.js
 *
 * Handles the ceramic photo upload UX:
 *  1. Show a live preview of the first selected file
 *  2. Show a count badge when multiple files are selected
 *  3. Immediately POST the first image to Django's /api/analyze/ endpoint
 *  4. Claude returns { stage_guess, confidence, description, glaze_notes }
 *  5. Pre-fill the form fields with the AI response
 *  6. Briefly highlight the filled fields so the user notices them
 *  7. Show / hide the glaze-notes section based on the stage
 *
 * Variables injected by the Django template:
 *   ANALYZE_URL  – URL for the AI endpoint
 *   CSRF_TOKEN   – Django CSRF token
 *   PIECE_TITLE  – The piece title to pass to Claude
 */

(function () {
  "use strict";

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const fileInput       = document.getElementById("id_images");
  const imagePreview    = document.getElementById("image-preview");
  const uploadPrompt    = document.getElementById("upload-prompt");
  const dropZone        = document.getElementById("drop-zone");
  const countBadge      = document.getElementById("photo-count-badge");
  const countNum        = document.getElementById("photo-count-num");

  const aiStatus        = document.getElementById("ai-status");
  const aiThinking      = document.getElementById("ai-thinking");
  const aiDone          = document.getElementById("ai-done");
  const aiError         = document.getElementById("ai-error");
  const aiErrorMsg      = document.getElementById("ai-error-msg");
  const confidenceBadge = document.getElementById("confidence-badge");
  const confidenceValue = document.getElementById("confidence-value");

  const stageSelect     = document.getElementById("id_stage");
  const stageGlow       = document.getElementById("stage-glow");
  const descTextarea    = document.getElementById("id_description");
  const descGlow        = document.getElementById("desc-glow");
  const glazeSection    = document.getElementById("glaze-section");
  const glazeTextarea   = document.getElementById("id_glaze_notes");
  const glazeGlow       = document.getElementById("glaze-glow");

  // ── Glaze section visibility ───────────────────────────────────────────────
  function syncGlazeSection() {
    if (stageSelect.value === "glaze") {
      glazeSection.classList.remove("hidden");
    } else {
      glazeSection.classList.add("hidden");
    }
  }

  stageSelect.addEventListener("change", syncGlazeSection);
  syncGlazeSection();

  // ── Image preview + count badge ────────────────────────────────────────────
  function showPreview(file, totalCount) {
    const reader = new FileReader();
    reader.onload = function (e) {
      imagePreview.src = e.target.result;
      imagePreview.classList.remove("hidden");
      uploadPrompt.classList.add("hidden");
    };
    reader.readAsDataURL(file);

    if (totalCount > 1) {
      countNum.textContent = totalCount;
      countBadge.classList.remove("hidden");
    } else {
      countBadge.classList.add("hidden");
    }
  }

  // ── AI status helpers ─────────────────────────────────────────────────────
  function showThinking() {
    aiStatus.classList.remove("hidden");
    aiThinking.classList.remove("hidden");
    aiDone.classList.add("hidden");
    aiError.classList.add("hidden");
    confidenceBadge.classList.add("hidden");
  }

  function showDone(confidence) {
    aiThinking.classList.add("hidden");
    aiDone.classList.remove("hidden");
    aiDone.classList.add("flex");
    aiError.classList.add("hidden");

    if (confidence !== null && confidence !== undefined) {
      const pct = Math.round(confidence * 100);
      confidenceValue.textContent = pct + "%";
      confidenceBadge.classList.remove("hidden");
      confidenceBadge.classList.add("flex");
    }
  }

  function showError(msg) {
    aiThinking.classList.add("hidden");
    aiDone.classList.add("hidden");
    aiError.classList.remove("hidden");
    aiError.classList.add("flex");
    aiErrorMsg.textContent = msg || "AI analysis failed — please fill in the fields manually.";
  }

  // ── Glow animation helper ─────────────────────────────────────────────────
  function glowField(glowEl) {
    glowEl.classList.remove("hidden");
    setTimeout(() => glowEl.classList.add("hidden"), 2500);
  }

  // ── Fill form fields ──────────────────────────────────────────────────────
  function fillFields(data) {
    if (data.stage_guess) {
      stageSelect.value = data.stage_guess;
      stageSelect.dispatchEvent(new Event("change"));
      glowField(stageGlow);
    }
    if (data.description) {
      descTextarea.value = data.description;
      glowField(descGlow);
    }
    if (data.stage_guess === "glaze" && data.glaze_notes) {
      glazeTextarea.value = data.glaze_notes;
      glowField(glazeGlow);
    }
    showDone(data.confidence);
  }

  // ── Analyse first image via Claude ────────────────────────────────────────
  async function analyzeImage(file) {
    showThinking();

    const formData = new FormData();
    formData.append("image", file);
    formData.append("title", typeof PIECE_TITLE !== "undefined" ? PIECE_TITLE : "ceramic piece");
    formData.append("csrfmiddlewaretoken", typeof CSRF_TOKEN !== "undefined" ? CSRF_TOKEN : "");

    try {
      const response = await fetch(
        typeof ANALYZE_URL !== "undefined" ? ANALYZE_URL : "/my-collections/api/analyze/",
        {
          method: "POST",
          body: formData,
          headers: { "X-CSRFToken": typeof CSRF_TOKEN !== "undefined" ? CSRF_TOKEN : "" },
        }
      );

      if (!response.ok) throw new Error(`Server returned ${response.status}`);

      const data = await response.json();
      if (data.error) { showError(data.error); return; }
      fillFields(data);
    } catch (err) {
      console.error("AI analysis error:", err);
      showError("Could not reach the AI service. Please fill in the fields manually.");
    }
  }

  // ── File input change ─────────────────────────────────────────────────────
  fileInput.addEventListener("change", function () {
    const files = fileInput.files;
    if (!files.length) return;
    showPreview(files[0], files.length);
    analyzeImage(files[0]);
  });

  // ── Drag and drop ─────────────────────────────────────────────────────────
  dropZone.addEventListener("dragover", function (e) {
    e.preventDefault();
    dropZone.classList.add("border-clay", "bg-clay-light/10");
  });

  dropZone.addEventListener("dragleave", function () {
    dropZone.classList.remove("border-clay", "bg-clay-light/10");
  });

  dropZone.addEventListener("drop", function (e) {
    e.preventDefault();
    dropZone.classList.remove("border-clay", "bg-clay-light/10");

    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"));
    if (!droppedFiles.length) return;

    const dt = new DataTransfer();
    droppedFiles.forEach(f => dt.items.add(f));
    fileInput.files = dt.files;

    showPreview(droppedFiles[0], droppedFiles.length);
    analyzeImage(droppedFiles[0]);
  });
})();
