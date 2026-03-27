const fs = require("fs");
const path = require("path");

const DEFAULT_STATE = {
  internetEnabled: true,
  blockedSites: [],
  studyMode: false,
  studyUnlockPending: false,
  allowedSites: ["chat.openai.com"],
  allowedApps: ["code.exe"],
  passcode: "1234",
  focusMode: {
    active: false,
    start: null,
    end: null,
    startLabel: "",
    endLabel: "",
    remainingSeconds: 0,
    countdownLabel: "00:00",
    suggestion: "Best time to focus detected: 08:00 PM - 10:00 PM",
    protectedSites: ["youtube.com", "instagram.com", "facebook.com", "x.com"],
    lastStartedAt: null,
  },
  logs: [],
  lastUpdated: null,
};

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function ensureDirectory(targetPath) {
  const directory = path.dirname(targetPath);
  fs.mkdirSync(directory, { recursive: true });
}

function mergeState(rawState) {
  const incoming = rawState && typeof rawState === "object" ? rawState : {};
  const merged = deepClone(DEFAULT_STATE);

  merged.internetEnabled = incoming.internetEnabled !== false;
  merged.blockedSites = Array.isArray(incoming.blockedSites)
    ? incoming.blockedSites.map((item) => normalizeSite(item)).filter(Boolean)
    : [];
  merged.studyMode = incoming.studyMode === true;
  merged.studyUnlockPending = incoming.studyUnlockPending === true;
  merged.allowedSites = Array.isArray(incoming.allowedSites) && incoming.allowedSites.length
    ? incoming.allowedSites.map((item) => normalizeSite(item)).filter(Boolean)
    : deepClone(DEFAULT_STATE.allowedSites);
  merged.allowedApps = Array.isArray(incoming.allowedApps) && incoming.allowedApps.length
    ? incoming.allowedApps.map((item) => String(item || "").trim()).filter(Boolean)
    : deepClone(DEFAULT_STATE.allowedApps);
  merged.passcode = String(incoming.passcode || DEFAULT_STATE.passcode).trim() || DEFAULT_STATE.passcode;

  const focus = incoming.focusMode && typeof incoming.focusMode === "object" ? incoming.focusMode : {};
  merged.focusMode = {
    ...merged.focusMode,
    ...focus,
    protectedSites: Array.isArray(focus.protectedSites) && focus.protectedSites.length
      ? focus.protectedSites.map((item) => normalizeSite(item)).filter(Boolean)
      : deepClone(DEFAULT_STATE.focusMode.protectedSites),
  };

  merged.logs = Array.isArray(incoming.logs)
    ? incoming.logs.map((entry) => String(entry || "").trim()).filter(Boolean).slice(-120)
    : [];
  merged.lastUpdated = incoming.lastUpdated || null;
  return merged;
}

function loadState(statePath) {
  try {
    const payload = fs.readFileSync(statePath, "utf-8");
    return mergeState(JSON.parse(payload));
  } catch (error) {
    return deepClone(DEFAULT_STATE);
  }
}

function saveState(statePath, state) {
  ensureDirectory(statePath);
  const serialized = JSON.stringify(mergeState(state), null, 2);
  fs.writeFileSync(statePath, `${serialized}\n`, "utf-8");
}

function formatLogStamp(date = new Date()) {
  return date.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function appendLog(state, message) {
  const cleanMessage = String(message || "").trim();
  if (!cleanMessage) {
    return state;
  }

  const nextState = mergeState(state);
  nextState.logs.push(`[${formatLogStamp()}] ${cleanMessage}`);
  nextState.logs = nextState.logs.slice(-120);
  nextState.lastUpdated = new Date().toISOString();
  return nextState;
}

function normalizeSite(site) {
  const value = String(site || "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .replace(/[/?#].*$/, "")
    .replace(/\s+/g, "");

  if (!value || !/[a-z0-9.-]+\.[a-z]{2,}$/i.test(value)) {
    return "";
  }
  return value;
}

function randomInt(min, max) {
  const lower = Math.ceil(Number(min));
  const upper = Math.floor(Number(max));
  return Math.floor(Math.random() * (upper - lower + 1)) + lower;
}

function randomFloat(min, max, digits = 1) {
  const value = Math.random() * (Number(max) - Number(min)) + Number(min);
  return Number(value.toFixed(digits));
}

function formatMbps(value) {
  return `${Number(value || 0).toFixed(1)} Mbps`;
}

function formatCountdown(totalSeconds) {
  const safeSeconds = Math.max(0, Number(totalSeconds) || 0);
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function parseClockInput(value, reference = new Date()) {
  const raw = String(value || "").trim();
  if (!raw) {
    return null;
  }

  const match = raw.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$/i);
  if (!match) {
    return null;
  }

  let hours = Number(match[1]);
  const minutes = Number(match[2] || 0);
  const meridiem = String(match[3] || "").toLowerCase();

  if (minutes > 59 || hours > 23 || hours < 0) {
    return null;
  }

  if (meridiem) {
    if (hours > 12 || hours === 0) {
      return null;
    }
    if (meridiem === "pm" && hours !== 12) {
      hours += 12;
    }
    if (meridiem === "am" && hours === 12) {
      hours = 0;
    }
  }

  const parsed = new Date(reference);
  parsed.setHours(hours, minutes, 0, 0);
  return parsed;
}

function formatClockLabel(dateLike) {
  const date = dateLike instanceof Date ? dateLike : new Date(dateLike);
  return date.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sanitizeDuration(durationMinutes, fallback = 25) {
  const value = Number(durationMinutes);
  if (!Number.isFinite(value) || value <= 0) {
    return fallback;
  }
  return Math.min(240, Math.max(5, Math.round(value)));
}

function deriveFocusWindow({ start = "", end = "", durationMinutes = 25 } = {}) {
  const now = new Date();
  const effectiveStart = new Date(now);
  let effectiveEnd = parseClockInput(end, now);

  if (!effectiveEnd) {
    const requestedStart = parseClockInput(start, now);
    if (requestedStart) {
      effectiveEnd = new Date(
        now.getTime() + Math.max(5, Math.round((requestedStart.getTime() - now.getTime()) / 60000) + sanitizeDuration(durationMinutes, 25)) * 60000
      );
    }
  }

  if (!effectiveEnd) {
    effectiveEnd = new Date(now.getTime() + sanitizeDuration(durationMinutes, 25) * 60000);
  }

  if (effectiveEnd <= effectiveStart) {
    effectiveEnd = new Date(effectiveEnd.getTime() + 24 * 60 * 60 * 1000);
  }

  return {
    startAt: effectiveStart,
    endAt: effectiveEnd,
    startLabel: formatClockLabel(effectiveStart),
    endLabel: formatClockLabel(effectiveEnd),
  };
}

function getFocusSuggestion(date = new Date()) {
  const hour = date.getHours();
  if (hour < 11) {
    return "Best time to focus detected: 06:30 AM - 08:30 AM";
  }
  if (hour < 17) {
    return "Best time to focus detected: 02:00 PM - 04:00 PM";
  }
  return "Best time to focus detected: 08:00 PM - 10:00 PM";
}

module.exports = {
  DEFAULT_STATE,
  appendLog,
  deepClone,
  deriveFocusWindow,
  formatClockLabel,
  formatCountdown,
  formatMbps,
  getFocusSuggestion,
  loadState,
  mergeState,
  normalizeSite,
  randomFloat,
  randomInt,
  sanitizeDuration,
  saveState,
};
