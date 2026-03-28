const path = require("path");
const readline = require("readline");
const { spawn } = require("child_process");

function buildDefaultState() {
  return {
    active: false,
    starting: false,
    available: false,
    manualDisabled: false,
    faceDetected: false,
    faceProperlyVisible: false,
    faceReady: false,
    faceGuidance: "",
    faceStatus: "detecting",
    focus: null,
    focusStatus: "unavailable",
    noiseLevel: 0,
    noisePercent: 0,
    noiseAlert: false,
    noiseStatus: "unavailable",
    warning: "none",
    event: "",
    message: "Vision monitoring idle",
    previewAvailable: false,
    webcamAvailable: false,
    microphoneAvailable: false,
    voiceAlertsEnabled: false,
    dependencies: {
      opencv: false,
      mediapipe: false,
      numpy: false,
      sounddevice: false,
      pyttsx3: false,
    },
    supports: {
      faceDetection: false,
      eyeTracking: false,
      noiseDetection: false,
      voiceAlerts: false,
    },
    lastUpdated: null,
    lastError: "",
  };
}

function mergeState(nextState) {
  const base = buildDefaultState();
  const incoming = nextState && typeof nextState === "object" ? nextState : {};
  return {
    ...base,
    ...incoming,
    faceDetected: incoming.faceDetected === true,
    faceProperlyVisible: incoming.faceProperlyVisible === true,
    faceReady: incoming.faceReady === true,
    faceGuidance: String(incoming.faceGuidance || ""),
    faceStatus: String(incoming.faceStatus || base.faceStatus),
    dependencies: {
      ...base.dependencies,
      ...(incoming.dependencies && typeof incoming.dependencies === "object" ? incoming.dependencies : {}),
    },
    supports: {
      ...base.supports,
      ...(incoming.supports && typeof incoming.supports === "object" ? incoming.supports : {}),
    },
  };
}

class VisionRuntime {
  constructor(options = {}) {
    this.scriptPath = options.scriptPath || path.join(__dirname, "vision.service.py");
    this.configPath = options.configPath || path.join(__dirname, "config.json");
    this.pythonCommand = options.pythonCommand || process.env.MYRA_PYTHON_BIN || "python";
    this.onStatus = typeof options.onStatus === "function" ? options.onStatus : () => {};
    this.onEvent = typeof options.onEvent === "function" ? options.onEvent : () => {};
    this.onExit = typeof options.onExit === "function" ? options.onExit : () => {};
    this.onError = typeof options.onError === "function" ? options.onError : () => {};
    this._child = null;
    this._stdout = null;
    this._stderrBuffer = [];
    this._state = buildDefaultState();
  }

  start() {
    if (this.isRunning()) {
      return {
        started: true,
        state: this.getStatus(),
      };
    }

    const args = ["-u", this.scriptPath, "--config", this.configPath];
    const child = spawn(this.pythonCommand, args, {
      cwd: path.dirname(this.scriptPath),
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
      },
    });

    this._child = child;
    this._state = mergeState({
      ...this._state,
      active: true,
      starting: true,
      manualDisabled: false,
      message: "Vision monitor starting...",
      lastError: "",
      lastUpdated: new Date().toISOString(),
    });

    this._stdout = readline.createInterface({
      input: child.stdout,
      crlfDelay: Infinity,
    });
    this._stdout.on("line", (line) => this._handleStdoutLine(line));

    child.stderr.on("data", (chunk) => {
      const text = String(chunk || "").trim();
      if (!text) {
        return;
      }
      this._stderrBuffer.push(text);
      this._stderrBuffer = this._stderrBuffer.slice(-10);
    });

    child.on("error", (error) => {
      const message = error && error.message ? error.message : "Vision monitor failed to start";
      this._state = mergeState({
        ...this._state,
        active: false,
        starting: false,
        lastError: message,
        message,
        lastUpdated: new Date().toISOString(),
      });
      this.onError(message);
    });

    child.on("close", (code, signalName) => {
      const stderrMessage = this._stderrBuffer.join(" | ").trim();
      const message = stderrMessage || (code === 0 ? "Vision monitor stopped" : `Vision monitor exited (${code || signalName || "unknown"})`);
      this._state = mergeState({
        ...this._state,
        active: false,
        starting: false,
        message,
        lastError: code === 0 ? "" : message,
        lastUpdated: new Date().toISOString(),
      });
      this._child = null;
      this._stdout = null;
      this._stderrBuffer = [];
      this.onExit({
        code,
        signal: signalName,
        message,
        state: this.getStatus(),
      });
    });

    return {
      started: true,
      state: this.getStatus(),
    };
  }

  stop({ manual = true } = {}) {
    if (manual) {
      this._state = mergeState({
        ...this._state,
        manualDisabled: true,
        message: "Vision monitor stopped",
      });
    }

    if (!this.isRunning()) {
      this._state = mergeState({
        ...this._state,
        active: false,
        starting: false,
        lastUpdated: new Date().toISOString(),
      });
      return {
        stopped: true,
        state: this.getStatus(),
      };
    }

    const child = this._child;
    try {
      child.kill("SIGTERM");
    } catch (error) {
      return {
        stopped: false,
        state: this.getStatus(),
      };
    }

    return {
      stopped: true,
      state: this.getStatus(),
    };
  }

  resetManualDisable() {
    this._state = mergeState({
      ...this._state,
      manualDisabled: false,
      lastUpdated: new Date().toISOString(),
    });
  }

  isRunning() {
    return Boolean(this._child && !this._child.killed);
  }

  getStatus() {
    return mergeState(this._state);
  }

  _handleStdoutLine(line) {
    const clean = String(line || "").trim();
    if (!clean) {
      return;
    }

    let payload = null;
    try {
      payload = JSON.parse(clean);
    } catch (error) {
      return;
    }

    if (!payload || typeof payload !== "object") {
      return;
    }

    const status = mergeState({
      ...this._state,
      ...payload,
      active: payload.active !== false,
      available: Boolean(payload.supports || payload.dependencies),
      starting: false,
      lastUpdated: new Date().toISOString(),
      lastError: payload.type === "error" ? String(payload.message || "Vision monitor error") : this._state.lastError,
    });

    this._state = status;
    this.onStatus(status);

    const eventMessage = String(payload.event || "").trim();
    if (eventMessage) {
      this.onEvent({
        event: eventMessage,
        status,
      });
    }
  }
}

module.exports = {
  VisionRuntime,
  buildDefaultState,
  mergeState,
};
