const path = require("path");

const {
  appendLog,
  deriveFocusWindow,
  formatCountdown,
  formatMbps,
  getFocusSuggestion,
  loadState,
  mergeState,
  normalizeSite,
  randomFloat,
  randomInt,
  saveState,
} = require("./netcontrol.utils");
const { sharedStudyModeService } = require("../studymode/studymode.service");

class NetControlService {
  constructor(statePath = path.join(__dirname, "netcontrol.state.json")) {
    this.statePath = statePath;
    this.studyModeService = sharedStudyModeService;
  }

  getNetworkStatus() {
    const state = this._loadState();
    const studyStatus = this.studyModeService.getStatus();
    const internetEnabled = state.internetEnabled !== false;
    const studyMode = studyStatus.studyMode === true;
    const studyUnlockPending = studyStatus.studyUnlockPending === true;
    const speedValue = internetEnabled ? randomFloat(42, 186, 1) : 0;
    const pingValue = internetEnabled ? randomInt(14, 68) : 0;
    const effectiveBlockedSites = Array.from(
      new Set([
        ...state.blockedSites,
        ...(state.focusMode.active ? state.focusMode.protectedSites || [] : []),
      ])
    );

    return {
      status: internetEnabled ? "online" : "offline",
      speed: internetEnabled ? formatMbps(speedValue) : "0.0 Mbps",
      speedValue,
      ping: internetEnabled ? `${pingValue} ms` : "--",
      pingValue,
      internetEnabled,
      blockedSites: state.blockedSites,
      effectiveBlockedSites,
      studyMode,
      studyUnlockPending,
      studyDurationPending: Boolean(studyStatus.studyDurationPending),
      pendingAction: studyStatus.pendingAction || "",
      pendingPrompt: studyStatus.pendingPrompt || "",
      allowedSites: studyStatus.allowedSites,
      allowedApps: studyStatus.allowedApps,
      endTime: studyStatus.endTime || null,
      endLabel: studyStatus.endLabel || "--",
      remainingSeconds: studyStatus.remainingSeconds || 0,
      remainingLabel: studyStatus.remainingLabel || "00:00:00",
      browserProtection: studyStatus.browserProtection || {},
      visionMonitor: studyStatus.visionMonitor || {},
      studyLock: {
        ...(studyStatus.studyLock || {}),
        active: studyMode,
        status: studyMode ? "LOCKED" : "UNLOCKED",
      },
      focusMode: this._decorateFocusMode(state.focusMode),
      suggestion: state.focusMode.suggestion || getFocusSuggestion(),
      lastUpdated: state.lastUpdated,
    };
  }

  scanWifi() {
    return [
      { name: "JioFiber", strength: randomInt(76, 88), security: "WPA2" },
      { name: "Airtel_X", strength: randomInt(58, 70), security: "WPA3" },
      { name: "MYRA_Lab", strength: randomInt(48, 67), security: "WPA2/WPA3" },
      { name: "Cafe_Guest", strength: randomInt(24, 54), security: "Open" },
    ];
  }

  toggleInternet(nextState) {
    const desiredState = this._resolveBooleanState(nextState);
    const state = this._loadState();
    state.internetEnabled = desiredState;
    const actionMessage = desiredState ? "Internet enabled (simulated)" : "Internet disabled (simulated)";
    this._saveState(appendLog(state, actionMessage));
    return this.getNetworkStatus();
  }

  blockWebsite(site) {
    const normalizedSite = normalizeSite(site);
    if (!normalizedSite) {
      throw new Error("Please provide a valid website name.");
    }

    const state = this._loadState();
    if (!state.blockedSites.includes(normalizedSite)) {
      state.blockedSites.push(normalizedSite);
      state.blockedSites.sort();
      this._saveState(appendLog(state, `${normalizedSite} blocked`));
    } else {
      this._saveState(appendLog(state, `${normalizedSite} already present in block list`));
    }

    return {
      site: normalizedSite,
      blockedSites: this._loadState().blockedSites,
      status: "blocked",
    };
  }

  startFocusMode(start = "", end = "", durationMinutes = 25) {
    const state = this._loadState();
    const { startAt, endAt, startLabel, endLabel } = deriveFocusWindow({
      start,
      end,
      durationMinutes,
    });
    const remainingSeconds = Math.max(0, Math.round((endAt.getTime() - Date.now()) / 1000));

    state.focusMode = {
      ...state.focusMode,
      active: true,
      start: startAt.toISOString(),
      end: endAt.toISOString(),
      startLabel,
      endLabel,
      remainingSeconds,
      countdownLabel: formatCountdown(remainingSeconds),
      suggestion: getFocusSuggestion(startAt),
      lastStartedAt: new Date().toISOString(),
    };

    this._saveState(appendLog(state, "Focus mode started"));
    return this.getNetworkStatus();
  }

  stopFocusMode() {
    const state = this._loadState();
    state.focusMode = {
      ...state.focusMode,
      active: false,
      remainingSeconds: 0,
      countdownLabel: "00:00",
    };
    this._saveState(appendLog(state, "Focus mode stopped"));
    return this.getNetworkStatus();
  }

  getStudyModeService() {
    return this.studyModeService;
  }

  startStudyMode(duration) {
    return this.studyModeService.startStudyMode(duration);
  }

  requestStudyModeStart() {
    return this.studyModeService.requestActivation();
  }

  requestStudyModeUnlock() {
    return this.studyModeService.requestUnlock();
  }

  stopStudyMode(passcode = "") {
    return this.studyModeService.stopStudyMode(passcode, { manual: true });
  }

  startVisionMonitoring() {
    return this.studyModeService.startVisionMonitoring({
      manual: true,
      requireStudyMode: true,
      logOnSuccess: true,
    });
  }

  stopVisionMonitoring() {
    return this.studyModeService.stopVisionMonitoring({
      manual: true,
      requireStudyMode: true,
      logOnSuccess: true,
      preserveManualDisabled: true,
    });
  }

  getVisionStatus() {
    return this.studyModeService.getStatus().visionMonitor || {};
  }

  getLogs(limit = 60) {
    const state = this._loadState();
    const studyLogs = this.studyModeService.getLogs(limit).logs;
    const combined = [...state.logs, ...studyLogs].slice(-120);
    return {
      logs: combined.slice(-Math.max(1, Number(limit) || 60)),
      count: combined.length,
      lastUpdated: state.lastUpdated,
    };
  }

  addLog(message) {
    const state = this._loadState();
    this._saveState(appendLog(state, message));
    return this.getLogs();
  }

  getDashboardUrl(port = 5127, host = "127.0.0.1") {
    return `http://${host}:${port}/dashboard/netcontrol`;
  }

  _resolveBooleanState(nextState) {
    if (typeof nextState === "boolean") {
      return nextState;
    }

    const normalized = String(nextState || "")
      .trim()
      .toLowerCase();
    if (["on", "online", "true", "1", "enable", "enabled"].includes(normalized)) {
      return true;
    }
    if (["off", "offline", "false", "0", "disable", "disabled"].includes(normalized)) {
      return false;
    }
    return true;
  }

  _decorateFocusMode(focusMode) {
    const mode = mergeState({ focusMode }).focusMode;
    if (!mode.active || !mode.end) {
      return {
        ...mode,
        active: false,
        remainingSeconds: 0,
        countdownLabel: "00:00",
      };
    }

    const remainingSeconds = Math.max(0, Math.round((new Date(mode.end).getTime() - Date.now()) / 1000));
    return {
      ...mode,
      remainingSeconds,
      countdownLabel: formatCountdown(remainingSeconds),
    };
  }

  _loadState() {
    const state = loadState(this.statePath);
    const studyStatus = this.studyModeService.getStatus();
    state.studyMode = Boolean(studyStatus.studyMode);
    state.studyUnlockPending = Boolean(studyStatus.studyUnlockPending);
    state.allowedSites = Array.isArray(studyStatus.allowedSites) ? studyStatus.allowedSites : state.allowedSites;
    state.allowedApps = Array.isArray(studyStatus.allowedApps) ? studyStatus.allowedApps : state.allowedApps;
    const synced = this._syncFocusState(state);
    if (JSON.stringify(state) !== JSON.stringify(synced)) {
      this._saveState(synced);
    }
    return synced;
  }

  _saveState(state) {
    saveState(this.statePath, state);
  }

  _syncFocusState(state) {
    const nextState = mergeState(state);
    const focusMode = nextState.focusMode || {};
    if (!focusMode.active || !focusMode.end) {
      return nextState;
    }

    const remainingSeconds = Math.max(0, Math.round((new Date(focusMode.end).getTime() - Date.now()) / 1000));
    nextState.focusMode.remainingSeconds = remainingSeconds;
    nextState.focusMode.countdownLabel = formatCountdown(remainingSeconds);
    if (remainingSeconds > 0) {
      return nextState;
    }

    nextState.focusMode.active = false;
    nextState.focusMode.remainingSeconds = 0;
    nextState.focusMode.countdownLabel = "00:00";
    return appendLog(nextState, "Focus mode completed");
  }
}

module.exports = {
  NetControlService,
};
