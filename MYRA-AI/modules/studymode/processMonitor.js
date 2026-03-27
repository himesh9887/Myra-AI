const { execFile } = require("child_process");

const SAFE_SYSTEM_PROCESSES = new Set([
  "applicationframehost.exe",
  "audiodg.exe",
  "backgroundtaskhost.exe",
  "conhost.exe",
  "csrss.exe",
  "ctfmon.exe",
  "dllhost.exe",
  "dwm.exe",
  "etdctrl.exe",
  "explorer.exe",
  "fontdrvhost.exe",
  "idle",
  "igfxem.exe",
  "lockapp.exe",
  "lsass.exe",
  "memory compression",
  "mmc.exe",
  "msmpeng.exe",
  "openconsole.exe",
  "registry",
  "runtimebroker.exe",
  "searchapp.exe",
  "searchhost.exe",
  "securityhealthservice.exe",
  "securityhealthsystray.exe",
  "secocl64.exe",
  "services.exe",
  "sgrmbroker.exe",
  "shellhost.exe",
  "shellexperiencehost.exe",
  "sihost.exe",
  "smartscreen.exe",
  "smss.exe",
  "spoolsv.exe",
  "startmenuexperiencehost.exe",
  "svchost.exe",
  "system",
  "system idle process",
  "taskhostw.exe",
  "textinputhost.exe",
  "useroobebroker.exe",
  "video.ui.exe",
  "widgetservice.exe",
  "widgets.exe",
  "wininit.exe",
  "winlogon.exe",
  "wlanext.exe",
  "wmiprvse.exe",
  "wudfhost.exe",
]);

const MYRA_SAFE_PROCESSES = new Set([
  "code.exe",
  "myra.exe",
  "myra-ai.exe",
  "node.exe",
  "python.exe",
  "pythonw.exe",
]);

const MANUAL_EXIT_SHELLS = new Set([
  "cmd.exe",
  "openconsole.exe",
  "powershell.exe",
  "pwsh.exe",
  "windowsterminal.exe",
]);

const KNOWN_DISTRACTION_PROCESSES = new Set([
  "brave.exe",
  "calc.exe",
  "discord.exe",
  "epicgameslauncher.exe",
  "firefox.exe",
  "gameloop.exe",
  "itunes.exe",
  "msteams.exe",
  "netflix.exe",
  "notepad.exe",
  "obs64.exe",
  "opera.exe",
  "opera_gx.exe",
  "robloxplayerbeta.exe",
  "slack.exe",
  "spotify.exe",
  "steam.exe",
  "telegram.exe",
  "vlc.exe",
  "whatsapp.exe",
  "whatsappdesktop.exe",
]);

const PROTECTED_WINDOW_PATTERNS = [
  /chatgpt/i,
  /localhost/i,
  /myra/i,
  /netcontrol/i,
  /visual studio code/i,
  /127\.0\.0\.1/i,
];

function normalizeProcessName(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function isVisibleWindowTitle(windowTitle) {
  const title = String(windowTitle || "").trim();
  return Boolean(title && title.toLowerCase() !== "n/a");
}

function parseCsvLine(line) {
  const fields = [];
  let current = "";
  let insideQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];

    if (char === '"') {
      if (insideQuotes && line[index + 1] === '"') {
        current += '"';
        index += 1;
      } else {
        insideQuotes = !insideQuotes;
      }
      continue;
    }

    if (char === "," && !insideQuotes) {
      fields.push(current);
      current = "";
      continue;
    }

    current += char;
  }

  fields.push(current);
  return fields.map((field) => field.trim());
}

function parseTasklistOutput(stdout) {
  return String(stdout || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const fields = parseCsvLine(line);
      return {
        imageName: normalizeProcessName(fields[0]),
        rawImageName: String(fields[0] || "").trim(),
        pid: Number(fields[1]) || 0,
        sessionName: String(fields[2] || "").trim(),
        status: String(fields[5] || "").trim(),
        userName: String(fields[6] || "").trim(),
        windowTitle: String(fields[8] || "").trim(),
      };
    })
    .filter((item) => item.imageName && item.pid > 0);
}

class ProcessMonitor {
  constructor({ onBlocked } = {}) {
    this.onBlocked = typeof onBlocked === "function" ? onBlocked : () => {};
    this._interval = null;
    this._allowedApps = new Set();
    this._protectedProcesses = new Set();
    this._protectedWindowPatterns = PROTECTED_WINDOW_PATTERNS.slice();
    this._killCooldowns = new Map();
  }

  start({ allowedApps = [], protectedProcesses = [], browserProcesses = [] } = {}) {
    this.stop();

    this._allowedApps = new Set(
      allowedApps.map((item) => normalizeProcessName(item)).filter(Boolean)
    );
    this._protectedProcesses = new Set([
      ...SAFE_SYSTEM_PROCESSES,
      ...MYRA_SAFE_PROCESSES,
      ...MANUAL_EXIT_SHELLS,
      ...this._allowedApps,
      ...protectedProcesses.map((item) => normalizeProcessName(item)).filter(Boolean),
      ...browserProcesses.map((item) => normalizeProcessName(item)).filter(Boolean),
      "taskkill.exe",
      "tasklist.exe",
    ]);
    this._killCooldowns.clear();

    this._poll();
    this._interval = setInterval(() => this._poll(), 2500);
  }

  stop() {
    if (this._interval) {
      clearInterval(this._interval);
      this._interval = null;
    }
    this._killCooldowns.clear();
  }

  isRunning() {
    return Boolean(this._interval);
  }

  _poll() {
    if (process.platform !== "win32") {
      return;
    }

    execFile("tasklist", ["/V", "/FO", "CSV", "/NH"], { windowsHide: true }, (error, stdout) => {
      if (error || !stdout) {
        return;
      }

      const processes = parseTasklistOutput(stdout);
      for (const processInfo of processes) {
        if (!this._isKillCandidate(processInfo)) {
          continue;
        }
        this._killProcess(processInfo);
      }
    });
  }

  _isKillCandidate(processInfo) {
    const imageName = processInfo.imageName;
    if (!imageName || this._protectedProcesses.has(imageName)) {
      return false;
    }

    if (!imageName.endsWith(".exe")) {
      return false;
    }

    if (SAFE_SYSTEM_PROCESSES.has(imageName) || MYRA_SAFE_PROCESSES.has(imageName)) {
      return false;
    }

    if (this._hasProtectedWindow(processInfo.windowTitle)) {
      return false;
    }

    if (KNOWN_DISTRACTION_PROCESSES.has(imageName)) {
      return true;
    }

    return isVisibleWindowTitle(processInfo.windowTitle);
  }

  _hasProtectedWindow(windowTitle) {
    const title = String(windowTitle || "").trim();
    if (!title) {
      return false;
    }
    return this._protectedWindowPatterns.some((pattern) => pattern.test(title));
  }

  _killProcess(processInfo) {
    const cooldownKey = `${processInfo.pid}:${processInfo.imageName}`;
    const now = Date.now();
    const lastAttempt = Number(this._killCooldowns.get(cooldownKey) || 0);
    if (now - lastAttempt < 5000) {
      return;
    }

    this._killCooldowns.set(cooldownKey, now);
    execFile(
      "taskkill",
      ["/F", "/PID", String(processInfo.pid)],
      { windowsHide: true },
      (error) => {
        if (!error) {
          this.onBlocked({
            imageName: processInfo.imageName,
            rawImageName: processInfo.rawImageName,
            pid: processInfo.pid,
            windowTitle: processInfo.windowTitle,
          });
        }
      }
    );
  }
}

module.exports = {
  MANUAL_EXIT_SHELLS,
  MYRA_SAFE_PROCESSES,
  ProcessMonitor,
  SAFE_SYSTEM_PROCESSES,
};
