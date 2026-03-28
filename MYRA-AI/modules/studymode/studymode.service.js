const fs = require("fs");
const http = require("http");
const https = require("https");
const path = require("path");
const { spawn } = require("child_process");

const {
  MANUAL_EXIT_SHELLS,
  MYRA_SAFE_PROCESSES,
  ProcessMonitor,
} = require("./processMonitor");
const {
  SiteBlocker,
  expandAllowedSites,
  normalizeSiteHost,
} = require("./siteBlocker");
const { TimerManager } = require("./timerManager");
const {
  VisionRuntime,
  mergeState: mergeVisionRuntimeState,
} = require("../vision/vision.runtime");

const PRIMARY_ALLOWED_APPS = ["code.exe", "chrome.exe"];
const BROWSER_PROCESS_NAMES = new Set(["chrome.exe", "msedge.exe"]);
const CORE_PROTECTED_PROCESSES = Array.from(new Set([
  ...Array.from(MYRA_SAFE_PROCESSES),
  ...Array.from(MANUAL_EXIT_SHELLS),
]));
const CORE_ALLOWED_SITES = expandAllowedSites(["chat.openai.com", "localhost"]);
const MYRA_DASHBOARD_URL = String(process.env.MYRA_APP_URL || "http://localhost:3000").trim().replace(/\/+$/, "");
const NETCONTROL_DASHBOARD_URL = String(
  process.env.MYRA_APP_NETCONTROL_URL || `${MYRA_DASHBOARD_URL}/netcontrol`
).trim();
const NETCONTROL_DASHBOARD_FALLBACK_URL = `http://${process.env.MYRA_NETCONTROL_HOST || "127.0.0.1"}:${process.env.MYRA_NETCONTROL_PORT || "5127"}/dashboard/netcontrol`;
const STUDY_CHATGPT_URL = "https://chat.openai.com";
const WORKSPACE_OPEN_DELAY_MS = 1000;
const WORKSPACE_RETRY_DELAY_MS = 2000;
const VSCODE_LAUNCH_PATHS = [
  path.join(process.env.LocalAppData || "", "Programs", "Microsoft VS Code", "Code.exe"),
  path.join(process.env.ProgramFiles || "C:\\Program Files", "Microsoft VS Code", "Code.exe"),
  path.join(process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)", "Microsoft VS Code", "Code.exe"),
].filter(Boolean);
const DEFAULT_VISION_MONITOR = mergeVisionRuntimeState({
  active: false,
  manualDisabled: false,
  message: "Vision monitoring idle",
});

const DEFAULT_STATE = {
  studyMode: false,
  endTime: null,
  remainingSeconds: 0,
  allowedApps: [...PRIMARY_ALLOWED_APPS, "node.exe", "python.exe", "pythonw.exe"],
  protectedProcesses: CORE_PROTECTED_PROCESSES,
  allowedSites: CORE_ALLOWED_SITES,
  passcode: "1234",
  pendingAction: "",
  pendingPrompt: "",
  lastStartedAt: null,
  lastStoppedAt: null,
  browserProtection: {
    browserProtectionReady: false,
    hostsApplied: false,
    policiesApplied: false,
    policyTargets: [],
    supportedBrowserProcesses: [],
    lastError: "",
  },
  visionMonitor: DEFAULT_VISION_MONITOR,
  logs: [],
};

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function ensureDirectory(targetPath) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
}

function normalizeSite(value) {
  return normalizeSiteHost(value);
}

function normalizeAppName(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function uniqueList(values, mapper = (item) => item) {
  const seen = new Set();
  const output = [];
  for (const item of values || []) {
    const normalized = mapper(item);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    output.push(normalized);
  }
  return output;
}

function ensureCoreList(values, requiredValues, mapper) {
  return uniqueList([...(values || []), ...(requiredValues || [])], mapper);
}

function mergeBrowserProtection(protection) {
  const incoming = protection && typeof protection === "object" ? protection : {};
  return {
    browserProtectionReady: Boolean(incoming.browserProtectionReady),
    hostsApplied: Boolean(incoming.hostsApplied),
    policiesApplied: Boolean(incoming.policiesApplied),
    policyTargets: uniqueList(
      Array.isArray(incoming.policyTargets) ? incoming.policyTargets : [],
      (item) => String(item || "").trim()
    ),
    supportedBrowserProcesses: uniqueList(
      Array.isArray(incoming.supportedBrowserProcesses) ? incoming.supportedBrowserProcesses : [],
      normalizeAppName
    ),
    lastError: String(incoming.lastError || "").trim(),
  };
}

function mergeVisionMonitorState(visionMonitor) {
  const incoming = visionMonitor && typeof visionMonitor === "object" ? visionMonitor : {};
  return mergeVisionRuntimeState({
    ...DEFAULT_VISION_MONITOR,
    ...incoming,
    manualDisabled: Boolean(incoming.manualDisabled),
  });
}

function mergeState(rawState) {
  const incoming = rawState && typeof rawState === "object" ? rawState : {};
  const merged = deepClone(DEFAULT_STATE);

  merged.studyMode = incoming.studyMode === true;
  merged.endTime = incoming.endTime || null;
  merged.remainingSeconds = Math.max(0, Number(incoming.remainingSeconds) || 0);
  merged.allowedApps = ensureCoreList(
    Array.isArray(incoming.allowedApps) && incoming.allowedApps.length ? incoming.allowedApps : DEFAULT_STATE.allowedApps,
    DEFAULT_STATE.allowedApps,
    normalizeAppName
  );
  merged.protectedProcesses = ensureCoreList(
    Array.isArray(incoming.protectedProcesses) && incoming.protectedProcesses.length
      ? incoming.protectedProcesses
      : DEFAULT_STATE.protectedProcesses,
    DEFAULT_STATE.protectedProcesses,
    normalizeAppName
  );
  merged.allowedSites = ensureCoreList(
    Array.isArray(incoming.allowedSites) && incoming.allowedSites.length ? incoming.allowedSites : DEFAULT_STATE.allowedSites,
    DEFAULT_STATE.allowedSites,
    normalizeSite
  );
  merged.passcode = String(incoming.passcode || DEFAULT_STATE.passcode).trim() || DEFAULT_STATE.passcode;
  merged.pendingAction = ["await_duration", "await_passcode"].includes(incoming.pendingAction)
    ? incoming.pendingAction
    : "";
  merged.pendingPrompt = String(incoming.pendingPrompt || "").trim();
  merged.lastStartedAt = incoming.lastStartedAt || null;
  merged.lastStoppedAt = incoming.lastStoppedAt || null;
  merged.browserProtection = mergeBrowserProtection(incoming.browserProtection);
  merged.visionMonitor = mergeVisionMonitorState(incoming.visionMonitor);
  merged.logs = Array.isArray(incoming.logs)
    ? incoming.logs.map((item) => String(item || "").trim()).filter(Boolean).slice(-200)
    : [];

  return merged;
}

function loadState(statePath) {
  try {
    return mergeState(JSON.parse(fs.readFileSync(statePath, "utf-8")));
  } catch (error) {
    return deepClone(DEFAULT_STATE);
  }
}

function saveState(statePath, state) {
  ensureDirectory(statePath);
  fs.writeFileSync(statePath, `${JSON.stringify(mergeState(state), null, 2)}\n`, "utf-8");
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
    return mergeState(state);
  }

  const nextState = mergeState(state);
  nextState.logs.push(`[${formatLogStamp()}] ${cleanMessage}`);
  nextState.logs = nextState.logs.slice(-200);
  return nextState;
}

function parseDurationMinutes(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) {
    return 0;
  }

  let minutes = 0;
  const hoursMatch = raw.match(/(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr|h)\b/);
  const minutesMatch = raw.match(/(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|min|m)\b/);

  if (hoursMatch) {
    minutes += Math.round(Number(hoursMatch[1]) * 60);
  }
  if (minutesMatch) {
    minutes += Math.round(Number(minutesMatch[1]));
  }

  if (!minutes && /^\d+$/.test(raw)) {
    minutes = Number(raw);
  }

  if (!minutes) {
    return 0;
  }

  return Math.min(12 * 60, Math.max(5, minutes));
}

function looksLikeDuration(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) {
    return false;
  }
  if (/^\d+$/.test(raw)) {
    return true;
  }
  return /(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr|h|minutes?|mins?|min|m)\b/.test(raw);
}

function looksLikePasscode(value) {
  const raw = String(value || "").trim();
  return /^(?:passcode\s*)?\d{4,8}$/i.test(raw);
}

function extractPasscode(value) {
  const match = String(value || "").trim().match(/^(?:passcode\s*)?(\d{4,8})$/i);
  return match ? match[1] : "";
}

function formatRemainingLabel(totalSeconds) {
  const safe = Math.max(0, Number(totalSeconds) || 0);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

function formatDurationLabel(minutes) {
  const safe = Math.max(0, Math.round(Number(minutes) || 0));
  const hours = Math.floor(safe / 60);
  const remainder = safe % 60;
  if (hours && remainder) {
    return `${hours} hour${hours === 1 ? "" : "s"} ${remainder} min`;
  }
  if (hours) {
    return `${hours} hour${hours === 1 ? "" : "s"}`;
  }
  return `${safe} min`;
}

function formatEndLabel(endTime) {
  if (!endTime) {
    return "--";
  }
  const date = new Date(endTime);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return date.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

class StudyModeService {
  constructor(
    statePath = path.join(__dirname, "state.json"),
    options = {}
  ) {
    this.statePath = statePath;
    this.workspaceRoot = path.resolve(options.workspaceRoot || path.join(__dirname, "..", ".."));
    this._blockLogCooldowns = new Map();
    this._expectedVisionStop = false;
    this._workspaceLaunchTimers = new Set();

    this.processMonitor = options.processMonitor || new ProcessMonitor({
      onBlocked: (payload) => this._handleBlockedProcess(payload),
    });
    this.siteBlocker = options.siteBlocker || new SiteBlocker({
      onLog: (message) => this.addLog(message),
    });
    this.timerManager = options.timerManager || new TimerManager({
      onTick: (remainingSeconds, endTime) => this._handleTick(remainingSeconds, endTime),
      onExpire: () => this._handleTimerExpire(),
    });
    this.visionRuntime = options.visionRuntime || new VisionRuntime({
      onStatus: (status) => this._handleVisionStatus(status),
      onEvent: (payload) => this._handleVisionEvent(payload),
      onExit: (payload) => this._handleVisionExit(payload),
      onError: (message) => this._handleVisionError(message),
    });

    this._resumeFromState();
  }

  getStatus() {
    const state = this._loadState();
    if (state.studyMode && state.endTime) {
      const remainingSeconds = Math.max(0, Math.round((new Date(state.endTime).getTime() - Date.now()) / 1000));
      if (remainingSeconds <= 0) {
        return this.stopStudyMode("", { manual: false, reason: "timer_expired" });
      }
      if (remainingSeconds !== state.remainingSeconds) {
        state.remainingSeconds = remainingSeconds;
        this._saveState(state);
      }
    }
    return this._buildPayload(this._loadState());
  }

  getLogs(limit = 80) {
    const state = this._loadState();
    const safeLimit = Math.max(1, Number(limit) || 80);
    return {
      logs: state.logs.slice(-safeLimit),
      count: state.logs.length,
      studyMode: state.studyMode,
      pendingAction: state.pendingAction,
    };
  }

  addLog(message) {
    const state = this._loadState();
    this._saveState(appendLog(state, message));
    return this.getLogs();
  }

  requestActivation() {
    const state = this._loadState();
    if (state.studyMode) {
      return {
        ...this._buildPayload(state),
        handled: true,
        requiresDuration: false,
        message: `Study mode already active. Remaining time ${formatRemainingLabel(state.remainingSeconds)}.`,
      };
    }

    state.pendingAction = "await_duration";
    state.pendingPrompt = "Enter duration (e.g., 2 hours, 30 minutes)";
    this._saveState(state);
    return {
      ...this._buildPayload(state),
      handled: true,
      requiresDuration: true,
      message: state.pendingPrompt,
    };
  }

  startStudyMode(durationInput) {
    const state = this._loadState();
    if (state.studyMode) {
      return {
        ...this._buildPayload(state),
        handled: true,
        requiresDuration: false,
        message: `Study mode already active. Remaining time ${formatRemainingLabel(state.remainingSeconds)}.`,
      };
    }

    const durationMinutes = typeof durationInput === "number"
      ? Math.min(12 * 60, Math.max(5, Math.round(durationInput)))
      : parseDurationMinutes(durationInput);

    if (!durationMinutes) {
      state.pendingAction = "await_duration";
      state.pendingPrompt = "Please enter valid duration (e.g., 10 minutes or 2 hours)";
      this._saveState(state);
      return {
        ...this._buildPayload(state),
        handled: true,
        requiresDuration: true,
        message: state.pendingPrompt,
      };
    }

    const protection = this.siteBlocker.start(state.allowedSites);
    if (!protection.browserProtectionReady) {
      this.siteBlocker.stop();
      const failedState = appendLog(
        {
          ...state,
          browserProtection: protection,
          pendingAction: "await_duration",
          pendingPrompt: "Enter duration (e.g., 2 hours, 30 minutes)",
        },
        "Study mode activation blocked because browser allowlist protection was unavailable"
      );
      this._saveState(failedState);
      return {
        ...this._buildPayload(failedState),
        handled: true,
        requiresDuration: true,
        message: "Study mode could not start safely because browser allowlist protection is unavailable. MYRA remains unlocked.",
      };
    }

    const endTime = new Date(Date.now() + durationMinutes * 60 * 1000);
    const monitorAllowedApps = this._resolveMonitorAllowedApps(state, protection);
    const protectedProcesses = this._resolveProtectedProcesses(state, protection);
    const browserRefresh = this._refreshManagedBrowsers();

    this.processMonitor.start({
      allowedApps: monitorAllowedApps,
      protectedProcesses,
      browserProcesses: protection.supportedBrowserProcesses,
    });
    this.timerManager.start(endTime.toISOString());
    const workspaceLaunch = this._launchStudyWorkspace();

    let nextState = {
      ...state,
      studyMode: true,
      endTime: endTime.toISOString(),
      remainingSeconds: durationMinutes * 60,
      pendingAction: "",
      pendingPrompt: "",
      lastStartedAt: new Date().toISOString(),
      protectedProcesses,
      browserProtection: protection,
      visionMonitor: mergeVisionMonitorState({
        ...state.visionMonitor,
        manualDisabled: false,
      }),
    };

    nextState = appendLog(nextState, `Study mode activated (${formatDurationLabel(durationMinutes)})`);
    nextState = appendLog(
      nextState,
      `Browser allowlist active: ${this._formatPolicyTargets(protection)} -> ChatGPT and localhost only`
    );
    if (browserRefresh.restarted.length) {
      nextState = appendLog(
        nextState,
        `${browserRefresh.restarted.join(", ")} restarted to apply study mode browser rules`
      );
    }
    if (browserRefresh.errors.length) {
      nextState = appendLog(nextState, `Browser refresh warning: ${browserRefresh.errors.join(" | ")}`);
    }
    if (workspaceLaunch.queued.length) {
      nextState = appendLog(nextState, `Study workspace launch queued: ${workspaceLaunch.queued.join(", ")}`);
    }
    nextState = appendLog(nextState, "MYRA dashboard and study mode off remain available");
    this._saveState(nextState);

    const visionResult = this.startVisionMonitoring({
      manual: false,
      requireStudyMode: true,
      logOnSuccess: true,
    });
    if (protection.lastError) {
      this.addLog(`Protection warning: ${protection.lastError}`);
    }
    if (visionResult && visionResult.warningMessage) {
      this.addLog(visionResult.warningMessage);
    }

    return {
      ...this._buildPayload(this._loadState()),
      handled: true,
      requiresDuration: false,
      message: `Study mode activated for ${formatDurationLabel(durationMinutes)}. Only MYRA, ChatGPT, and VS Code are accessible. Stay focused.`,
    };
  }

  requestUnlock() {
    const state = this._loadState();
    if (!state.studyMode) {
      state.pendingAction = "";
      state.pendingPrompt = "";
      this._saveState(state);
      return {
        ...this._buildPayload(state),
        handled: true,
        requiresPasscode: false,
        authorized: true,
        message: "Study mode is already disabled.",
      };
    }

    state.pendingAction = "await_passcode";
    state.pendingPrompt = "Enter passcode";
    this._saveState(state);
    return {
      ...this._buildPayload(state),
      handled: true,
      requiresPasscode: true,
      authorized: false,
      message: state.pendingPrompt,
    };
  }

  forceStopStudyMode() {
    return this.stopStudyMode("", {
      manual: false,
      reason: "force_stop",
    });
  }

  stopStudyMode(passcode = "", options = {}) {
    const manual = options.manual !== false;
    const reason = String(options.reason || "").trim().toLowerCase();
    const state = this._loadState();

    if (!state.studyMode) {
      state.pendingAction = "";
      state.pendingPrompt = "";
      this._saveState(state);
      return {
        ...this._buildPayload(state),
        handled: true,
        requiresPasscode: false,
        authorized: true,
        message: "Study mode is already disabled.",
      };
    }

    if (manual) {
      const expected = String(state.passcode || DEFAULT_STATE.passcode).trim();
      const provided = extractPasscode(passcode);
      if (!provided) {
        return this.requestUnlock();
      }
      if (provided !== expected) {
        const deniedState = appendLog(
          {
            ...state,
            pendingAction: "await_passcode",
            pendingPrompt: "Enter passcode",
          },
          "Unauthorized attempt blocked"
        );
        this._saveState(deniedState);
        return {
          ...this._buildPayload(deniedState),
          handled: true,
          requiresPasscode: true,
          authorized: false,
          message: "Incorrect passcode. Study mode remains locked.",
        };
      }
    }

    this._clearWorkspaceLaunchTimers();
    this.timerManager.stop();
    this.processMonitor.stop();
    const visionStopResult = this.stopVisionMonitoring({
      manual: false,
      requireStudyMode: false,
      logOnSuccess: false,
      preserveManualDisabled: false,
    });
    const protection = this.siteBlocker.stop();
    const browserRefresh = this._refreshManagedBrowsers();

    let stoppedState = {
      ...this._loadState(),
      studyMode: false,
      endTime: null,
      remainingSeconds: 0,
      pendingAction: "",
      pendingPrompt: "",
      lastStoppedAt: new Date().toISOString(),
      browserProtection: protection,
      visionMonitor: mergeVisionMonitorState({
        ...(visionStopResult && visionStopResult.data ? visionStopResult.data : {}),
        active: false,
        starting: false,
        manualDisabled: false,
      }),
    };

    stoppedState = appendLog(
      stoppedState,
      reason === "timer_expired"
        ? "Study session completed"
        : reason === "force_stop"
          ? "Study mode stopped by emergency override"
          : "Study mode stopped"
    );
    if (browserRefresh.restarted.length) {
      stoppedState = appendLog(
        stoppedState,
        `${browserRefresh.restarted.join(", ")} restarted after study mode unlock`
      );
    }
    if (browserRefresh.errors.length) {
      stoppedState = appendLog(stoppedState, `Browser refresh warning: ${browserRefresh.errors.join(" | ")}`);
    }
    if (protection.lastError) {
      stoppedState = appendLog(stoppedState, `Restore warning: ${protection.lastError}`);
    }
    this._saveState(stoppedState);

    return {
      ...this._buildPayload(this._loadState()),
      handled: true,
      requiresPasscode: false,
      authorized: true,
      message: reason === "timer_expired"
        ? "Study session completed. Good job Boss. Full access restored."
        : reason === "force_stop"
          ? "Study mode disabled."
        : "Study mode disabled. Full access restored.",
    };
  }

  startVisionMonitoring(options = {}) {
    const manual = options.manual !== false;
    const requireStudyMode = options.requireStudyMode !== false;
    const logOnSuccess = options.logOnSuccess !== false;
    const state = this._loadState();

    if (requireStudyMode && !state.studyMode) {
      return {
        ...this._buildPayload(state),
        handled: true,
        message: "Vision monitoring runs only during Study Mode.",
      };
    }

    if (!manual && state.visionMonitor.manualDisabled) {
      return {
        ...this._buildPayload(state),
        handled: true,
        message: "Vision monitoring is paused until you start it again.",
      };
    }

    if (this.visionRuntime.isRunning()) {
      const runningState = {
        ...state,
        visionMonitor: mergeVisionMonitorState({
          ...state.visionMonitor,
          ...this.visionRuntime.getStatus(),
          manualDisabled: false,
        }),
      };
      this._saveState(runningState);
      return {
        ...this._buildPayload(runningState),
        handled: true,
        message: "Vision monitoring is already active.",
      };
    }

    this._expectedVisionStop = false;
    this.visionRuntime.resetManualDisable();
    const result = this.visionRuntime.start();
    const startedState = {
      ...state,
      visionMonitor: mergeVisionMonitorState({
        ...state.visionMonitor,
        ...(result && result.state ? result.state : {}),
        manualDisabled: false,
      }),
    };
    this._saveState(startedState);

    if (logOnSuccess) {
      this.addLog("Vision system started");
    }

    let warningMessage = "";
    const dependencies = startedState.visionMonitor.dependencies || {};
    if (!dependencies.mediapipe || !dependencies.sounddevice) {
      const missing = [];
      if (!dependencies.mediapipe) {
        missing.push("MediaPipe");
      }
      if (!dependencies.sounddevice) {
        missing.push("sounddevice");
      }
      warningMessage = `Vision monitor running in fallback mode: missing ${missing.join(", ")}`;
    }

    return {
      ...this._buildPayload(this._loadState()),
      handled: true,
      warningMessage,
      message: manual
        ? "Vision monitoring started."
        : "Vision monitoring started for Study Mode.",
    };
  }

  stopVisionMonitoring(options = {}) {
    const manual = options.manual !== false;
    const requireStudyMode = options.requireStudyMode !== false;
    const logOnSuccess = options.logOnSuccess !== false;
    const preserveManualDisabled = options.preserveManualDisabled !== false;
    const state = this._loadState();

    if (requireStudyMode && !state.studyMode) {
      return {
        ...this._buildPayload(state),
        handled: true,
        data: state.visionMonitor,
        message: "Vision monitoring is already inactive.",
      };
    }

    this._expectedVisionStop = true;
    const runtimeResult = this.visionRuntime.stop({
      manual: manual && preserveManualDisabled,
    });

    const nextVisionState = mergeVisionMonitorState({
      ...state.visionMonitor,
      ...(runtimeResult && runtimeResult.state ? runtimeResult.state : {}),
      active: false,
      starting: false,
      manualDisabled: manual && preserveManualDisabled,
    });

    const nextState = {
      ...state,
      visionMonitor: nextVisionState,
    };
    this._saveState(nextState);

    if (manual && logOnSuccess) {
      this.addLog("Vision system stopped");
    }

    return {
      ...this._buildPayload(this._loadState()),
      handled: true,
      data: nextVisionState,
      message: manual
        ? "Vision monitoring stopped."
        : "Vision monitoring stopped.",
    };
  }

  isAwaitingDuration() {
    return this._loadState().pendingAction === "await_duration";
  }

  isAwaitingPasscode() {
    return this._loadState().pendingAction === "await_passcode";
  }

  looksLikeDuration(text) {
    return looksLikeDuration(text);
  }

  looksLikePasscode(text) {
    return looksLikePasscode(text);
  }

  _resumeFromState() {
    const state = this._loadState();
    if (!state.studyMode || !state.endTime) {
      return;
    }

    const remainingSeconds = Math.max(0, Math.round((new Date(state.endTime).getTime() - Date.now()) / 1000));
    if (remainingSeconds <= 0) {
      this.stopStudyMode("", { manual: false, reason: "timer_expired" });
      return;
    }

    const protection = this.siteBlocker.start(state.allowedSites);
    if (!protection.browserProtectionReady) {
      this.siteBlocker.stop();
      let resetState = {
        ...state,
        studyMode: false,
        endTime: null,
        remainingSeconds: 0,
        pendingAction: "",
        pendingPrompt: "",
        lastStoppedAt: new Date().toISOString(),
        browserProtection: protection,
      };
      resetState = appendLog(resetState, "Study mode disabled because browser protection could not resume");
      this._saveState(resetState);
      return;
    }

    const protectedProcesses = this._resolveProtectedProcesses(state, protection);
    const monitorAllowedApps = this._resolveMonitorAllowedApps(state, protection);
    const browserRefresh = this._refreshManagedBrowsers();
    const workspaceLaunch = this._launchStudyWorkspace();
    const resumedState = {
      ...state,
      remainingSeconds,
      protectedProcesses,
      browserProtection: protection,
    };
    let nextState = resumedState;
    if (browserRefresh.restarted.length) {
      nextState = appendLog(
        nextState,
        `${browserRefresh.restarted.join(", ")} restarted while restoring study mode browser rules`
      );
    }
    if (browserRefresh.errors.length) {
      nextState = appendLog(nextState, `Browser refresh warning: ${browserRefresh.errors.join(" | ")}`);
    }
    if (workspaceLaunch.queued.length) {
      nextState = appendLog(nextState, `Study workspace restore queued: ${workspaceLaunch.queued.join(", ")}`);
    }
    this._saveState(nextState);

    this.processMonitor.start({
      allowedApps: monitorAllowedApps,
      protectedProcesses,
      browserProcesses: protection.supportedBrowserProcesses,
    });
    this.timerManager.start(state.endTime);
    this.startVisionMonitoring({
      manual: false,
      requireStudyMode: true,
      logOnSuccess: false,
    });
  }

  _handleTick(remainingSeconds, endTime) {
    const state = this._loadState();
    if (!state.studyMode) {
      return;
    }

    state.remainingSeconds = Math.max(0, Number(remainingSeconds) || 0);
    state.endTime = endTime || state.endTime;
    this._saveState(state);
  }

  _handleTimerExpire() {
    this.stopStudyMode("", { manual: false, reason: "timer_expired" });
  }

  _handleBlockedProcess(payload) {
    const imageName = normalizeAppName(payload && payload.imageName);
    const displayName = String(
      payload && (payload.rawImageName || payload.imageName) ? (payload.rawImageName || payload.imageName) : imageName
    ).trim();
    if (!imageName) {
      return;
    }

    const now = Date.now();
    const lastBlockedAt = Number(this._blockLogCooldowns.get(imageName) || 0);
    if (now - lastBlockedAt < 4000) {
      return;
    }

    this._blockLogCooldowns.set(imageName, now);
    this.addLog(`${displayName} closed`);
  }

  _handleVisionStatus(status) {
    const state = this._loadState();
    const nextState = {
      ...state,
      visionMonitor: mergeVisionMonitorState({
        ...state.visionMonitor,
        ...status,
      }),
    };
    this._saveState(nextState);
  }

  _handleVisionEvent(payload) {
    const eventName = String(payload && payload.event ? payload.event : "").trim();
    if (!eventName) {
      return;
    }
    this.addLog(eventName);
  }

  _handleVisionExit(payload) {
    const state = this._loadState();
    const nextState = {
      ...state,
      visionMonitor: mergeVisionMonitorState({
        ...state.visionMonitor,
        ...(payload && payload.state ? payload.state : {}),
        active: false,
        starting: false,
      }),
    };
    this._saveState(nextState);

    if (!this._expectedVisionStop && state.studyMode) {
      this.addLog(`Vision monitor stopped unexpectedly: ${String(payload && payload.message ? payload.message : "unknown error")}`);
    }
    this._expectedVisionStop = false;
  }

  _handleVisionError(message) {
    const state = this._loadState();
    const nextState = {
      ...state,
      visionMonitor: mergeVisionMonitorState({
        ...state.visionMonitor,
        active: false,
        starting: false,
        lastError: String(message || "").trim(),
        message: String(message || "").trim(),
      }),
    };
    this._saveState(nextState);
    if (message) {
      this.addLog(`Vision monitor warning: ${message}`);
    }
  }

  _resolveProtectedProcesses(state, protection) {
    return uniqueList(
      [
        ...(Array.isArray(state.protectedProcesses) ? state.protectedProcesses : []),
        ...this._resolveMonitorAllowedApps(state, protection),
        ...(Array.isArray(protection.supportedBrowserProcesses) ? protection.supportedBrowserProcesses : []),
      ],
      normalizeAppName
    );
  }

  _resolveMonitorAllowedApps(state, protection) {
    const supportedBrowsers = new Set(
      (Array.isArray(protection.supportedBrowserProcesses) ? protection.supportedBrowserProcesses : [])
        .map((item) => normalizeAppName(item))
        .filter(Boolean)
    );

    return uniqueList(
      [
        ...(Array.isArray(state.allowedApps) ? state.allowedApps : []).filter((item) => {
          const normalized = normalizeAppName(item);
          if (!BROWSER_PROCESS_NAMES.has(normalized)) {
            return true;
          }
          return supportedBrowsers.has(normalized);
        }),
        ...Array.from(supportedBrowsers),
      ],
      normalizeAppName
    );
  }

  _formatPolicyTargets(protection) {
    const targets = Array.isArray(protection.policyTargets) ? protection.policyTargets : [];
    return targets.length ? targets.join(", ") : "Browser policy";
  }

  _refreshManagedBrowsers() {
    if (!this.siteBlocker || typeof this.siteBlocker.refreshBrowsers !== "function") {
      return {
        restarted: [],
        errors: [],
      };
    }
    const result = this.siteBlocker.refreshBrowsers({ restoreLastSession: true });
    return {
      restarted: Array.isArray(result && result.restarted) ? result.restarted : [],
      errors: Array.isArray(result && result.errors) ? result.errors : [],
    };
  }

  _launchStudyWorkspace() {
    this._clearWorkspaceLaunchTimers();

    const steps = [
      {
        name: "MYRA Dashboard",
        type: "browser",
        url: MYRA_DASHBOARD_URL,
        checkReady: true,
        maxAttempts: 3,
      },
      {
        name: "NetControl Dashboard",
        type: "browser",
        url: NETCONTROL_DASHBOARD_URL,
        retryUrl: NETCONTROL_DASHBOARD_FALLBACK_URL !== NETCONTROL_DASHBOARD_URL ? NETCONTROL_DASHBOARD_FALLBACK_URL : "",
        checkReady: true,
        maxAttempts: 3,
      },
      {
        name: "ChatGPT",
        type: "browser",
        url: STUDY_CHATGPT_URL,
        checkReady: false,
        maxAttempts: 2,
      },
      {
        name: "VS Code",
        type: "vscode",
        maxAttempts: 1,
      },
    ];

    steps.forEach((step, index) => {
      this._scheduleWorkspaceLaunch(step, index * WORKSPACE_OPEN_DELAY_MS, 0);
    });

    return {
      queued: steps.map((step) => step.name),
      errors: [],
    };
  }

  _scheduleWorkspaceLaunch(step, delayMs = 0, attemptNumber = 0) {
    const timer = setTimeout(() => {
      this._workspaceLaunchTimers.delete(timer);
      Promise.resolve(this._runWorkspaceLaunch(step, attemptNumber)).catch((error) => {
        this.addLog(`${step.name} launch error: ${error && error.message ? error.message : "unknown error"}`);
      });
    }, Math.max(0, Number(delayMs) || 0));
    this._workspaceLaunchTimers.add(timer);
  }

  _clearWorkspaceLaunchTimers() {
    for (const timer of this._workspaceLaunchTimers) {
      clearTimeout(timer);
    }
    this._workspaceLaunchTimers.clear();
  }

  async _runWorkspaceLaunch(step, attemptNumber = 0) {
    const currentStep = step && typeof step === "object" ? step : {};
    const name = String(currentStep.name || "workspace item").trim();
    const isRetry = attemptNumber > 0;
    const maxAttempts = Math.max(1, Number(currentStep.maxAttempts) || 1);
    const targetUrl = isRetry && currentStep.retryUrl ? currentStep.retryUrl : currentStep.url;

    this.addLog(`${isRetry ? "Retrying" : "Opening"} ${name}...`);

    let readiness = { ok: true };
    if (currentStep.type === "browser" && currentStep.checkReady && targetUrl) {
      readiness = await this._checkLocalUrlReady(targetUrl);
      if (!readiness.ok) {
        const detail = readiness.status
          ? `HTTP ${readiness.status}`
          : (readiness.error || "server not ready");
        this.addLog(`${name} not ready yet (${detail})`);
      }
    }

    const result = currentStep.type === "vscode"
      ? this._openVsCode()
      : this._openUrl(targetUrl);

    if (!result.ok) {
      this.addLog(`${name} launch failed: ${result.error || "launch failed"}`);
      if ((attemptNumber + 1) < maxAttempts) {
        this.addLog(`${name} retry scheduled in 2 seconds.`);
        this._scheduleWorkspaceLaunch(currentStep, WORKSPACE_RETRY_DELAY_MS, attemptNumber + 1);
      }
      return;
    }

    if (!readiness.ok && currentStep.checkReady && (attemptNumber + 1) < maxAttempts) {
      this.addLog(`${name} retry scheduled in 2 seconds.`);
      this._scheduleWorkspaceLaunch(currentStep, WORKSPACE_RETRY_DELAY_MS, attemptNumber + 1);
      return;
    }

    this.addLog(`${name} launch command sent.`);
  }

  _checkLocalUrlReady(url) {
    let parsed;
    try {
      parsed = new URL(String(url || "").trim());
    } catch (error) {
      return Promise.resolve({ ok: false, error: "invalid URL" });
    }

    const hostname = String(parsed.hostname || "").trim().toLowerCase();
    if (!["localhost", "127.0.0.1", "::1"].includes(hostname)) {
      return Promise.resolve({ ok: true, skipped: true });
    }

    const client = parsed.protocol === "https:" ? https : http;

    return new Promise((resolve) => {
      const request = client.request(parsed, { method: "GET", timeout: 1200 }, (response) => {
        const status = Number(response.statusCode) || 0;
        response.resume();
        resolve({
          ok: status >= 200 && status < 400,
          status,
        });
      });

      request.on("timeout", () => {
        request.destroy(new Error("timeout"));
      });
      request.on("error", (error) => {
        resolve({
          ok: false,
          error: error && error.message ? error.message : "connection failed",
        });
      });
      request.end();
    });
  }

  _openUrl(url) {
    if (process.platform === "win32") {
      return this._spawnDetached("cmd", ["/c", "start", "", String(url || "").trim()]);
    }
    return this._spawnDetached("xdg-open", [String(url || "").trim()]);
  }

  _openVsCode() {
    const workspaceTarget = this.workspaceRoot;

    let lastError = "VS Code executable not found";
    for (const executable of VSCODE_LAUNCH_PATHS) {
      const candidate = String(executable || "").trim();
      if (!candidate) {
        continue;
      }
      if ((candidate.includes("\\") || candidate.includes("/")) && !fs.existsSync(candidate)) {
        continue;
      }
      const result = this._spawnDetached(candidate, [workspaceTarget]);
      if (result.ok) {
        return result;
      }
      lastError = result.error || lastError;
    }

    if (process.platform === "win32") {
      const shellLaunch = this._spawnDetached("cmd", ["/c", "start", "", "code", workspaceTarget]);
      if (shellLaunch.ok) {
        return shellLaunch;
      }
      lastError = shellLaunch.error || lastError;
    } else {
      const cliLaunch = this._spawnDetached("code", [workspaceTarget]);
      if (cliLaunch.ok) {
        return cliLaunch;
      }
      lastError = cliLaunch.error || lastError;
    }

    return {
      ok: false,
      error: lastError,
    };
  }

  _spawnDetached(command, args = []) {
    try {
      const child = spawn(command, args, {
        detached: true,
        stdio: "ignore",
        windowsHide: true,
      });
      child.unref();
      return { ok: true, error: "" };
    } catch (error) {
      return {
        ok: false,
        error: error && error.message ? error.message : "launch failed",
      };
    }
  }

  _buildPayload(state) {
    const liveState = mergeState(state);
    const remainingSeconds = liveState.studyMode && liveState.endTime
      ? Math.max(0, Math.round((new Date(liveState.endTime).getTime() - Date.now()) / 1000))
      : 0;

    return {
      studyMode: liveState.studyMode,
      studyUnlockPending: liveState.pendingAction === "await_passcode",
      studyDurationPending: liveState.pendingAction === "await_duration",
      pendingAction: liveState.pendingAction,
      pendingPrompt: liveState.pendingPrompt,
      endTime: liveState.endTime,
      endLabel: formatEndLabel(liveState.endTime),
      remainingSeconds,
      remainingLabel: formatRemainingLabel(remainingSeconds),
      allowedApps: liveState.allowedApps,
      protectedProcesses: liveState.protectedProcesses,
      allowedSites: liveState.allowedSites,
      browserProtection: liveState.browserProtection,
      visionMonitor: liveState.visionMonitor,
      passcodeHint: "1234",
      logs: liveState.logs.slice(-80),
      studyLock: {
        active: liveState.studyMode,
        status: liveState.studyMode ? "LOCKED" : "UNLOCKED",
        safePanelTitle: "Study Mode Safe Panel",
        allowedApps: liveState.allowedApps,
        protectedProcesses: liveState.protectedProcesses,
        allowedSites: liveState.allowedSites,
        allowedResources: [
          "MYRA",
          "ChatGPT",
          "VS Code",
        ],
        blockedResources: ["Everything else"],
        blockedSummary: "Everything else",
        unlockCommand: "study mode off",
        dashboardAlwaysAvailable: true,
        manualExitPreserved: true,
        unlockPending: liveState.pendingAction === "await_passcode",
        durationPending: liveState.pendingAction === "await_duration",
        pendingPrompt: liveState.pendingPrompt,
        endTime: liveState.endTime,
        endLabel: formatEndLabel(liveState.endTime),
        remainingSeconds,
        remainingLabel: formatRemainingLabel(remainingSeconds),
        browserProtection: liveState.browserProtection,
        visionMonitor: liveState.visionMonitor,
      },
    };
  }

  _loadState() {
    return loadState(this.statePath);
  }

  _saveState(state) {
    saveState(this.statePath, state);
  }
}

const sharedStudyModeService = new StudyModeService();

module.exports = {
  DEFAULT_STATE,
  StudyModeService,
  appendLog,
  extractPasscode,
  formatDurationLabel,
  formatRemainingLabel,
  looksLikeDuration,
  looksLikePasscode,
  parseDurationMinutes,
  sharedStudyModeService,
};
