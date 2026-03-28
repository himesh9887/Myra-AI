const API = {
  status: "/api/netcontrol/status",
  wifi: "/api/netcontrol/wifi",
  toggle: "/api/netcontrol/toggle",
  block: "/api/netcontrol/block",
  focusStart: "/api/netcontrol/focus/start",
  focusStop: "/api/netcontrol/focus/stop",
  studyStart: "/api/netcontrol/study/start",
  studyStop: "/api/netcontrol/study/stop",
  visionStart: "/api/netcontrol/vision/start",
  visionStop: "/api/netcontrol/vision/stop",
  logs: "/api/netcontrol/logs",
};

const elements = {
  backendPill: document.getElementById("backend-pill"),
  blockedSites: document.getElementById("blocked-sites"),
  blockButton: document.getElementById("block-site-button"),
  countdown: document.getElementById("countdown-value"),
  focusEnd: document.getElementById("focus-end"),
  focusStart: document.getElementById("focus-start"),
  focusStartButton: document.getElementById("focus-start-button"),
  focusStopButton: document.getElementById("focus-stop-button"),
  focusSuggestion: document.getElementById("focus-suggestion"),
  focusWindowLabel: document.getElementById("focus-window-label"),
  internetToggle: document.getElementById("internet-toggle"),
  logs: document.getElementById("log-output"),
  pingValue: document.getElementById("ping-value"),
  rescanWifi: document.getElementById("rescan-wifi"),
  siteInput: document.getElementById("site-input"),
  speedValue: document.getElementById("speed-value"),
  statusSubtitle: document.getElementById("status-subtitle"),
  statusValue: document.getElementById("status-value"),
  studyAllowList: document.getElementById("study-allow-list"),
  studyBlockedList: document.getElementById("study-blocked-list"),
  studyBrowserChip: document.getElementById("study-browser-chip"),
  studyDurationInput: document.getElementById("study-duration-input"),
  studyEndLabel: document.getElementById("study-end-label"),
  studyModeCopy: document.getElementById("study-mode-copy"),
  studyModeOffButton: document.getElementById("study-mode-off-button"),
  studyModeOnButton: document.getElementById("study-mode-on-button"),
  studyProcessChip: document.getElementById("study-process-chip"),
  studyProtectionCopy: document.getElementById("study-protection-copy"),
  studyRemainingValue: document.getElementById("study-remaining-value"),
  studyStatusChip: document.getElementById("study-status-chip"),
  studyStatusLine: document.getElementById("study-status-line"),
  studyUnlockHint: document.getElementById("study-unlock-hint"),
  toastStack: document.getElementById("toast-stack"),
  toggleLabel: document.getElementById("toggle-label"),
  visionDependencyCopy: document.getElementById("vision-dependency-copy"),
  visionFaceCopy: document.getElementById("vision-face-copy"),
  visionFaceValue: document.getElementById("vision-face-value"),
  visionFocusCopy: document.getElementById("vision-focus-copy"),
  visionFocusValue: document.getElementById("vision-focus-value"),
  visionNoiseCopy: document.getElementById("vision-noise-copy"),
  visionNoiseMeterFill: document.getElementById("vision-noise-meter-fill"),
  visionNoiseMeterLabel: document.getElementById("vision-noise-meter-label"),
  visionNoiseValue: document.getElementById("vision-noise-value"),
  visionPreviewCopy: document.getElementById("vision-preview-copy"),
  visionRuntimeCopy: document.getElementById("vision-runtime-copy"),
  visionRuntimeValue: document.getElementById("vision-runtime-value"),
  visionStartButton: document.getElementById("vision-start-button"),
  visionStatusChip: document.getElementById("vision-status-chip"),
  visionStopButton: document.getElementById("vision-stop-button"),
  visionWarningCopy: document.getElementById("vision-warning-copy"),
  visionWarningValue: document.getElementById("vision-warning-value"),
  wifiList: document.getElementById("wifi-list"),
  chartCanvas: document.getElementById("speed-chart"),
};

const dashboardState = {
  chart: null,
  chartLabels: [],
  chartValues: [],
  focusMode: null,
  studyLock: null,
  visionMonitor: null,
};

function setDefaultFocusRange() {
  const now = new Date();
  const later = new Date(now.getTime() + 25 * 60 * 1000);
  elements.focusStart.value = now.toTimeString().slice(0, 5);
  elements.focusEnd.value = later.toTimeString().slice(0, 5);
}

function formatTimer(totalSeconds) {
  const safe = Math.max(0, Number(totalSeconds) || 0);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function showToast(message, tone = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${tone}`;
  toast.innerHTML = `<span class="toast-title">NetControl</span><span>${message}</span>`;
  elements.toastStack.appendChild(toast);
  window.setTimeout(() => {
    toast.remove();
  }, 3200);
}

function playToggleSound(enabled) {
  try {
    const context = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "triangle";
    oscillator.frequency.value = enabled ? 720 : 240;
    gain.gain.value = 0.04;
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.12);
  } catch (error) {
    console.debug("Toggle sound unavailable", error);
  }
}

function signalLevel(strength) {
  if (strength >= 76) {
    return 4;
  }
  if (strength >= 56) {
    return 3;
  }
  if (strength >= 36) {
    return 2;
  }
  return 1;
}

function renderWifi(networks) {
  elements.wifiList.classList.remove("scan-loader");
  elements.wifiList.innerHTML = "";

  networks.forEach((network) => {
    const item = document.createElement("div");
    item.className = "wifi-item";
    const level = signalLevel(Number(network.strength || 0));
    item.innerHTML = `
      <div class="wifi-meta">
        <strong>${network.name}</strong>
        <span>${network.security} | Strength ${network.strength}%</span>
      </div>
      <div class="signal-bars" aria-label="signal strength">
        ${[1, 2, 3, 4]
          .map((index) => `<span class="${index <= level ? "active" : ""}"></span>`)
          .join("")}
      </div>
    `;
    elements.wifiList.appendChild(item);
  });
}

function renderBlockedSites(status) {
  const effectiveSites = Array.isArray(status.effectiveBlockedSites) ? status.effectiveBlockedSites : [];
  elements.blockedSites.innerHTML = "";

  if (!effectiveSites.length) {
    elements.blockedSites.innerHTML = `<div class="site-chip"><strong>No blocked sites</strong><span>Focus shield standby</span></div>`;
    return;
  }

  effectiveSites.forEach((site) => {
    const chip = document.createElement("div");
    chip.className = "site-chip";
    const activeViaFocus = status.focusMode && Array.isArray(status.focusMode.protectedSites)
      ? status.focusMode.protectedSites.includes(site) && !(status.blockedSites || []).includes(site)
      : false;
    chip.innerHTML = `
      <strong>${site}</strong>
      <span>${activeViaFocus ? "Focus shield" : "Manual block"}</span>
    `;
    elements.blockedSites.appendChild(chip);
  });
}

function renderLogs(payload) {
  const logs = Array.isArray(payload.logs) ? payload.logs : [];
  elements.logs.classList.remove("scan-loader");
  elements.logs.innerHTML = "";

  if (!logs.length) {
    elements.logs.innerHTML = `<div class="log-line">[--:--] Waiting for NetControl activity...</div>`;
    return;
  }

  logs.slice(-18).forEach((entry) => {
    const line = document.createElement("div");
    line.className = "log-line";
    line.textContent = entry;
    elements.logs.appendChild(line);
  });
  elements.logs.scrollTop = elements.logs.scrollHeight;
}

function renderStudyMode(status) {
  const studyLock = status.studyLock || {};
  const active = Boolean(studyLock.active);
  const unlockPending = Boolean(studyLock.unlockPending);
  const durationPending = Boolean(studyLock.durationPending);
  const browserProtection = studyLock.browserProtection || {};
  const browserProtectionReady = Boolean(browserProtection.browserProtectionReady || browserProtection.policiesApplied);
  const policyTargets = Array.isArray(browserProtection.policyTargets) ? browserProtection.policyTargets : [];

  dashboardState.studyLock = {
    ...studyLock,
    active,
    remainingSeconds: Number(studyLock.remainingSeconds || status.remainingSeconds || 0),
  };

  elements.studyStatusChip.textContent = active ? "LOCKED" : durationPending ? "READY" : "UNLOCKED";
  elements.studyStatusChip.className = `mini-chip ${active ? "study-locked" : "study-unlocked"}`;
  elements.studyStatusLine.textContent = active
    ? "Status: LOCKED \uD83D\uDD12"
    : durationPending
      ? "Status: READY"
      : "Status: UNLOCKED";

  elements.studyRemainingValue.textContent = active
    ? studyLock.remainingLabel || formatTimer(dashboardState.studyLock.remainingSeconds)
    : "00:00:00";
  elements.studyEndLabel.textContent = active
    ? `Auto unlock at ${studyLock.endLabel || "--"}`
    : durationPending
      ? "Waiting for duration input"
      : "Auto unlock at --";

  elements.studyProcessChip.textContent = active ? "PROCESS WATCH ON" : "PROCESS WATCH OFF";
  elements.studyProcessChip.className = `mini-chip ${active ? "study-chip-live" : "study-unlocked"}`;
  elements.studyBrowserChip.textContent = active
    ? browserProtectionReady
      ? "WEB ALLOWLIST ON"
      : "WEB ALLOWLIST WARN"
    : "WEB ALLOWLIST OFF";
  elements.studyBrowserChip.className = `mini-chip ${active ? (browserProtectionReady ? "study-chip-live" : "study-chip-warning") : "study-unlocked"}`;

  if (active) {
    if (browserProtection.lastError && !browserProtectionReady) {
      elements.studyProtectionCopy.textContent = `Protection warning: ${browserProtection.lastError}`;
    } else if (browserProtectionReady) {
      elements.studyProtectionCopy.textContent = `${policyTargets.join(", ") || "Supported browsers"} are restricted to ChatGPT and localhost while other visible apps are monitored and closed.`;
    } else {
      elements.studyProtectionCopy.textContent = "Process lock is active. Browser allowlist needs Windows policy access to complete.";
    }
  } else {
    elements.studyProtectionCopy.textContent = "Ready to enforce local app and website lock.";
  }

  elements.studyModeCopy.textContent = active
    ? unlockPending
      ? "Passcode challenge active. MYRA, ChatGPT, and VS Code remain allowed."
      : "Only MYRA, ChatGPT, and VS Code are accessible. Everything else stays blocked until the timer ends or passcode unlock succeeds."
    : durationPending
      ? "Duration capture armed. Submit time to lock the system."
      : "Study lock is disengaged.";
  elements.studyUnlockHint.textContent = active || unlockPending
    ? 'Unlock requires the passcode. You can always say "study mode off".'
    : 'MYRA stays available. You can always say "study mode off".';

  const allowItems = Array.isArray(studyLock.allowedResources) && studyLock.allowedResources.length
    ? studyLock.allowedResources.map((item) => item.includes("&#x") ? item : `${item} &#x2705;`)
    : ["MYRA &#x2705;", "ChatGPT &#x2705;", "VS Code &#x2705;"];
  const blockedItems = Array.isArray(studyLock.blockedResources) && studyLock.blockedResources.length
    ? studyLock.blockedResources.map((item) => item.includes("&#x") ? item : `${item} &#x274C;`)
    : ["Everything else &#x274C;"];
  elements.studyAllowList.innerHTML = allowItems
    .map((item) => `<div class="study-list-item">${item}</div>`)
    .join("");
  elements.studyBlockedList.innerHTML = blockedItems
    .map((item) => `<div class="study-list-item study-list-item-danger">${item}</div>`)
    .join("");

  elements.studyDurationInput.disabled = active;
  elements.studyModeOnButton.disabled = active;
  elements.studyModeOffButton.disabled = !active && !unlockPending;
}

function renderVisionMonitor(status) {
  const vision = status.visionMonitor || {};
  const studyLock = status.studyLock || {};
  const studyActive = Boolean(studyLock.active);
  const monitorActive = Boolean(vision.active);
  const faceStatus = String(vision.faceStatus || "unavailable");
  const faceGuidance = String(vision.faceGuidance || "").trim();
  const focusStatus = String(vision.focusStatus || "unavailable");
  const noiseStatus = String(vision.noiseStatus || "unavailable");
  const warning = String(vision.warning || "none");
  const faceWarningActive = faceStatus === "missing" || warning === "Face not detected";
  const dependencies = vision.dependencies || {};
  const supports = vision.supports || {};
  const noisePercent = Math.max(0, Math.min(100, Number(vision.noisePercent || 0)));
  const missingDependencies = Object.entries(dependencies)
    .filter((entry) => entry[1] === false)
    .map((entry) => entry[0]);

  dashboardState.visionMonitor = {
    ...vision,
    active: monitorActive,
  };

  elements.visionStatusChip.textContent = monitorActive
    ? "LIVE"
    : studyActive
      ? "READY"
      : "IDLE";
  elements.visionStatusChip.className = `mini-chip ${monitorActive ? "study-chip-live" : studyActive ? "study-chip-warning" : "study-unlocked"}`;

  elements.visionFaceValue.textContent = faceStatus === "detected"
    ? "Detected ✅"
    : faceStatus === "missing"
      ? "Not Detected ❌"
      : "Unavailable";
  elements.visionFaceCopy.textContent = faceStatus === "detected"
    ? "Face is visible in front of the monitor."
    : faceStatus === "missing"
      ? `Face missing for ${Number(vision.faceMissingSeconds || 0).toFixed(1)}s.`
      : "Face detection waits for webcam access and OpenCV.";
  if (faceStatus === "detected") {
    elements.visionFaceValue.textContent = "Detected";
    elements.visionFaceCopy.textContent = "Face is clearly visible in front of the monitor.";
  } else if (faceStatus === "adjust") {
    elements.visionFaceValue.textContent = "Adjust Camera";
    elements.visionFaceCopy.textContent = faceGuidance
      ? `Face found, but not clear enough. Please ${faceGuidance}.`
      : "Face found, but not clear enough yet.";
  } else if (faceStatus === "missing") {
    elements.visionFaceValue.textContent = "Not Detected";
  }
  if (faceStatus === "detected") {
    elements.visionFaceValue.textContent = "Detected";
    elements.visionFaceCopy.textContent = "Face detection is working and your face is visible.";
  } else if (faceStatus === "missing") {
    elements.visionFaceValue.textContent = "Not Detected";
    elements.visionFaceCopy.textContent = `No face detected for ${Number(vision.faceMissingSeconds || 0).toFixed(1)}s.`;
  } else if (faceStatus === "adjust") {
    elements.visionFaceValue.textContent = "Detecting...";
    elements.visionFaceCopy.textContent = faceGuidance
      ? `Face found, but not clear yet. Please ${faceGuidance}.`
      : "Face found, but not clear yet.";
  } else if (faceStatus === "detecting") {
    elements.visionFaceValue.textContent = "Detecting...";
    elements.visionFaceCopy.textContent = "Camera is checking for your face.";
  } else {
    elements.visionFaceValue.textContent = monitorActive ? "Detecting..." : "Unavailable";
    elements.visionFaceCopy.textContent = "Face detection waits for camera and MediaPipe access.";
  }
  elements.visionFaceValue.classList.toggle("vision-alert-blink", faceWarningActive);
  elements.visionFaceCopy.classList.toggle("vision-copy-alert", faceWarningActive);

  elements.visionFocusValue.textContent = focusStatus === "focused"
    ? "Focused ✅"
    : focusStatus === "distracted"
      ? "Distracted ⚠️"
      : focusStatus === "unknown"
        ? "Checking..."
        : "Unavailable";
  elements.visionFocusCopy.textContent = focusStatus === "focused"
    ? "Gaze is aligned with the screen."
    : focusStatus === "distracted"
      ? `Looking away for ${Number(vision.focusAwaySeconds || 0).toFixed(1)}s.`
      : supports.eyeTracking
        ? "Waiting for a stable face to evaluate focus."
        : "Install MediaPipe to enable eye tracking.";

  elements.visionNoiseValue.textContent = noiseStatus === "noisy"
    ? "Noisy ⚠️"
    : noiseStatus === "quiet"
      ? "Quiet ✅"
      : "Unavailable";
  elements.visionNoiseCopy.textContent = noiseStatus === "noisy"
    ? "Disturbance is above the configured threshold."
    : noiseStatus === "quiet"
      ? "Realtime level is inside the quiet range."
      : "Install sounddevice and allow microphone access for live noise checks.";

  elements.visionNoiseMeterLabel.textContent = `${noisePercent.toFixed(0)}%`;
  elements.visionNoiseMeterFill.style.width = `${noisePercent}%`;
  elements.visionNoiseMeterFill.className = `vision-meter-fill ${noiseStatus === "noisy" ? "vision-meter-alert" : ""}`;

  elements.visionWarningValue.textContent = warning === "none" ? "none" : warning;
  elements.visionWarningCopy.textContent = warning === "none"
    ? "Voice alerts will speak only short focus prompts."
    : `Latest alert: ${warning}`;

  elements.visionRuntimeValue.textContent = vision.message || "Waiting";
  elements.visionRuntimeCopy.textContent = monitorActive
    ? "No images, video, or audio recordings are stored."
    : studyActive
      ? "Use the controls below to resume or pause realtime monitoring."
      : "Vision monitoring is armed by Study Mode.";

  elements.visionDependencyCopy.textContent = missingDependencies.length
    ? `Missing optional packages: ${missingDependencies.join(", ")}.`
    : "All vision monitor dependencies are available.";
  elements.visionPreviewCopy.textContent = Boolean(vision.previewAvailable)
    ? "Live webcam preview is available."
    : "Live webcam preview is optional and currently disabled for privacy-safe realtime monitoring.";

  elements.visionStartButton.disabled = !studyActive || monitorActive;
  elements.visionStopButton.disabled = !studyActive || !monitorActive;
}

function ensureChart() {
  if (dashboardState.chart || !window.Chart) {
    return;
  }

  dashboardState.chart = new window.Chart(elements.chartCanvas, {
    type: "line",
    data: {
      labels: dashboardState.chartLabels,
      datasets: [
        {
          label: "Speed",
          data: dashboardState.chartValues,
          borderColor: "#22c55e",
          backgroundColor: "rgba(34, 197, 94, 0.18)",
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointRadius: 0,
        },
      ],
    },
    options: {
      animation: {
        duration: 450,
      },
      maintainAspectRatio: false,
      responsive: true,
      plugins: {
        legend: {
          display: false,
        },
      },
      scales: {
        x: {
          ticks: {
            color: "#8fb6a2",
          },
          grid: {
            color: "rgba(143, 182, 162, 0.08)",
          },
        },
        y: {
          ticks: {
            color: "#8fb6a2",
          },
          grid: {
            color: "rgba(56, 189, 248, 0.08)",
          },
        },
      },
    },
  });
}

function renderFallbackCanvas() {
  const canvas = elements.chartCanvas;
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }

  const width = canvas.clientWidth || 600;
  const height = 250;
  canvas.width = width;
  canvas.height = height;
  context.clearRect(0, 0, width, height);

  context.strokeStyle = "rgba(56, 189, 248, 0.12)";
  context.lineWidth = 1;
  for (let step = 0; step < 5; step += 1) {
    const y = ((step + 1) / 6) * height;
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }

  const values = dashboardState.chartValues.slice(-16);
  if (!values.length) {
    return;
  }

  const maxValue = Math.max(...values, 50);
  context.strokeStyle = "#22c55e";
  context.lineWidth = 2.5;
  context.beginPath();
  values.forEach((value, index) => {
    const x = (index / Math.max(1, values.length - 1)) * width;
    const y = height - (value / maxValue) * (height - 18) - 9;
    if (index === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, y);
    }
  });
  context.stroke();
}

function pushSpeedPoint(speedValue) {
  const stamp = new Date().toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  dashboardState.chartLabels.push(stamp);
  dashboardState.chartValues.push(Number(speedValue || 0));

  dashboardState.chartLabels = dashboardState.chartLabels.slice(-16);
  dashboardState.chartValues = dashboardState.chartValues.slice(-16);

  ensureChart();
  if (dashboardState.chart) {
    dashboardState.chart.data.labels = dashboardState.chartLabels;
    dashboardState.chart.data.datasets[0].data = dashboardState.chartValues;
    dashboardState.chart.update();
    return;
  }

  renderFallbackCanvas();
}

function renderStatus(status) {
  const online = status.status === "online";
  elements.backendPill.textContent = online ? "BACKEND LIVE" : "SIM OFFLINE";
  elements.statusValue.textContent = online ? "ONLINE" : "OFFLINE";
  elements.statusSubtitle.textContent = online
    ? "Simulation active and responsive"
    : "Traffic feed intentionally paused";
  elements.speedValue.textContent = status.speed || "0.0 Mbps";
  elements.pingValue.textContent = status.ping || "--";
  elements.internetToggle.checked = Boolean(status.internetEnabled);
  elements.toggleLabel.textContent = status.internetEnabled ? "Internet ON" : "Internet OFF";
  elements.focusSuggestion.textContent = status.suggestion || "Best time to focus detected soon.";

  renderBlockedSites(status);
  renderStudyMode(status);
  renderVisionMonitor(status);

  dashboardState.focusMode = status.focusMode || null;
  updateCountdowns();
  pushSpeedPoint(status.speedValue || 0);
}

function updateFocusCountdown() {
  const focusMode = dashboardState.focusMode;
  if (!focusMode || !focusMode.active) {
    elements.countdown.textContent = "00:00";
    elements.focusWindowLabel.textContent = "Ready to engage";
    return;
  }

  const remaining = Math.max(0, Number(focusMode.remainingSeconds || 0));
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  elements.countdown.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  elements.focusWindowLabel.textContent = `${focusMode.startLabel || "--"} to ${focusMode.endLabel || "--"}`;
  if (remaining > 0) {
    dashboardState.focusMode.remainingSeconds = remaining - 1;
  }
}

function updateStudyCountdown() {
  const studyLock = dashboardState.studyLock;
  if (!studyLock || !studyLock.active) {
    elements.studyRemainingValue.textContent = "00:00:00";
    return;
  }

  const remaining = Math.max(0, Number(studyLock.remainingSeconds || 0));
  elements.studyRemainingValue.textContent = formatTimer(remaining);
  if (remaining > 0) {
    dashboardState.studyLock.remainingSeconds = remaining - 1;
  }
}

function updateCountdowns() {
  updateFocusCountdown();
  updateStudyCountdown();
}

async function refreshStatus(showErrors = false) {
  try {
    const status = await fetchJson(API.status);
    renderStatus(status);
  } catch (error) {
    elements.backendPill.textContent = "BACKEND ERROR";
    if (showErrors) {
      showToast(error.message, "error");
    }
  }
}

async function refreshWifi(showErrors = false) {
  try {
    const wifi = await fetchJson(API.wifi);
    renderWifi(wifi);
  } catch (error) {
    if (showErrors) {
      showToast(error.message, "error");
    }
  }
}

async function refreshLogs(showErrors = false) {
  try {
    const logs = await fetchJson(API.logs);
    renderLogs(logs);
  } catch (error) {
    if (showErrors) {
      showToast(error.message, "error");
    }
  }
}

async function refreshDashboard(showErrors = false) {
  await Promise.all([refreshStatus(showErrors), refreshWifi(showErrors), refreshLogs(showErrors)]);
}

async function handleInternetToggle() {
  try {
    const response = await fetchJson(API.toggle, {
      method: "POST",
      body: JSON.stringify({
        state: elements.internetToggle.checked,
      }),
    });
    playToggleSound(Boolean(response.internetEnabled));
    renderStatus(response);
    await refreshLogs();
    showToast(response.internetEnabled ? "Internet simulation enabled." : "Internet simulation disabled.");
  } catch (error) {
    elements.internetToggle.checked = !elements.internetToggle.checked;
    showToast(error.message, "error");
  }
}

async function handleBlockSite() {
  const site = elements.siteInput.value.trim();
  if (!site) {
    showToast("Enter a site before blocking it.", "error");
    return;
  }

  try {
    await fetchJson(API.block, {
      method: "POST",
      body: JSON.stringify({ site }),
    });
    elements.siteInput.value = "";
    await refreshDashboard();
    showToast(`Blocked ${site} in NetControl.`);
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function handleStartFocus() {
  try {
    const payload = {
      start: elements.focusStart.value,
      end: elements.focusEnd.value,
    };
    const response = await fetchJson(API.focusStart, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderStatus(response);
    await refreshLogs();
    showToast("Focus mode activated.");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function handleStopFocus() {
  try {
    const response = await fetchJson(API.focusStop, {
      method: "POST",
      body: JSON.stringify({}),
    });
    renderStatus(response);
    await refreshLogs();
    showToast("Focus mode stopped.");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function handleStartStudyMode() {
  const duration = elements.studyDurationInput.value.trim();
  if (!duration) {
    showToast("Enter a duration like 2 hours or 30 min.", "error");
    elements.studyDurationInput.focus();
    return;
  }

  try {
    const response = await fetchJson(API.studyStart, {
      method: "POST",
      body: JSON.stringify({ duration }),
    });
    renderStudyMode(response);
    elements.studyDurationInput.value = "";
    await refreshDashboard();
    showToast(response.message || "Study mode activated.");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function handleStopStudyMode() {
  const studyLock = dashboardState.studyLock || {};
  if (!studyLock.active && !studyLock.unlockPending) {
    showToast("Study mode is already disabled.");
    return;
  }

  const passcode = window.prompt("Enter passcode to disable study mode", "");
  if (passcode === null) {
    return;
  }

  try {
    const response = await fetchJson(API.studyStop, {
      method: "POST",
      body: JSON.stringify({ passcode }),
    });
    renderStudyMode(response);
    await refreshDashboard();
    showToast(response.message, response.authorized === false ? "error" : "info");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function handleStartVisionMonitoring() {
  try {
    const response = await fetchJson(API.visionStart, {
      method: "POST",
      body: JSON.stringify({}),
    });
    await refreshDashboard();
    showToast(response.message || "Vision monitoring started.");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function handleStopVisionMonitoring() {
  try {
    const response = await fetchJson(API.visionStop, {
      method: "POST",
      body: JSON.stringify({}),
    });
    await refreshDashboard();
    showToast(response.message || "Vision monitoring stopped.");
  } catch (error) {
    showToast(error.message, "error");
  }
}

function bindEvents() {
  elements.internetToggle.addEventListener("change", handleInternetToggle);
  elements.blockButton.addEventListener("click", handleBlockSite);
  elements.siteInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      handleBlockSite();
    }
  });
  elements.focusStartButton.addEventListener("click", handleStartFocus);
  elements.focusStopButton.addEventListener("click", handleStopFocus);
  elements.studyModeOnButton.addEventListener("click", handleStartStudyMode);
  elements.studyModeOffButton.addEventListener("click", handleStopStudyMode);
  elements.visionStartButton.addEventListener("click", handleStartVisionMonitoring);
  elements.visionStopButton.addEventListener("click", handleStopVisionMonitoring);
  elements.studyDurationInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      handleStartStudyMode();
    }
  });
  elements.rescanWifi.addEventListener("click", () => refreshWifi(true));
}

async function initialize() {
  setDefaultFocusRange();
  bindEvents();
  await refreshDashboard(true);
  window.setInterval(updateCountdowns, 1000);
  window.setInterval(() => refreshStatus(false), 4000);
  window.setInterval(() => refreshWifi(false), 5000);
  window.setInterval(() => refreshLogs(false), 5000);
}

initialize();
