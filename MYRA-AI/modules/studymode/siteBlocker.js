const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const HOSTS_MARKER_START = "# MYRA_STUDY_MODE_START";
const HOSTS_MARKER_END = "# MYRA_STUDY_MODE_END";

const SUPPORTED_BROWSERS = [
  {
    name: "Google Chrome",
    policyKey: "Google\\Chrome",
    processName: "chrome.exe",
  },
  {
    name: "Microsoft Edge",
    policyKey: "Microsoft\\Edge",
    processName: "msedge.exe",
  },
];

const DISTRACTION_HOSTS = [
  "bing.com",
  "discord.com",
  "facebook.com",
  "github.com",
  "google.com",
  "instagram.com",
  "linkedin.com",
  "netflix.com",
  "open.spotify.com",
  "primevideo.com",
  "reddit.com",
  "telegram.org",
  "twitter.com",
  "web.whatsapp.com",
  "www.bing.com",
  "www.discord.com",
  "www.facebook.com",
  "www.github.com",
  "www.google.com",
  "www.instagram.com",
  "www.linkedin.com",
  "www.netflix.com",
  "www.primevideo.com",
  "www.reddit.com",
  "www.telegram.org",
  "www.twitter.com",
  "www.x.com",
  "www.youtube.com",
  "x.com",
  "youtube.com",
  "youtu.be",
];

function normalizeSiteHost(value) {
  let raw = String(value || "").trim().toLowerCase();
  if (!raw) {
    return "";
  }

  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) {
    try {
      raw = new URL(raw).hostname.toLowerCase();
    } catch (error) {
      return "";
    }
  }

  raw = raw.replace(/^www\./, "");
  raw = raw.replace(/[/?#].*$/, "");
  if (raw.startsWith("[") && raw.endsWith("]")) {
    raw = raw.slice(1, -1);
  }
  if (!raw.includes("::")) {
    raw = raw.replace(/:\d+$/, "");
  }

  if (!raw) {
    return "";
  }
  if (raw === "localhost" || raw === "127.0.0.1" || raw === "::1") {
    return raw;
  }
  if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(raw)) {
    return raw;
  }
  if (/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(raw)) {
    return raw;
  }
  return "";
}

function expandAllowedSites(allowedSites = []) {
  const normalized = new Set([
    "chat.openai.com",
    "chatgpt.com",
    "localhost",
    "127.0.0.1",
    "::1",
  ]);

  for (const item of allowedSites) {
    const host = normalizeSiteHost(item);
    if (host) {
      normalized.add(host);
    }
  }

  if (normalized.has("chat.openai.com") || normalized.has("chatgpt.com")) {
    normalized.add("chat.openai.com");
    normalized.add("chatgpt.com");
  }

  return Array.from(normalized);
}

function addWildcardEntry(entries, value) {
  if (value) {
    entries.add(value);
  }
}

function addHostAllowEntries(entries, host) {
  if (!host) {
    return;
  }

  if (host === "localhost" || host === "127.0.0.1") {
    addWildcardEntry(entries, host);
    addWildcardEntry(entries, `${host}/*`);
    addWildcardEntry(entries, `http://${host}/*`);
    addWildcardEntry(entries, `https://${host}/*`);
    addWildcardEntry(entries, `http://${host}:*/*`);
    addWildcardEntry(entries, `https://${host}:*/*`);
    return;
  }

  if (host === "::1") {
    addWildcardEntry(entries, "[::1]");
    addWildcardEntry(entries, "[::1]/*");
    addWildcardEntry(entries, "http://[::1]/*");
    addWildcardEntry(entries, "https://[::1]/*");
    addWildcardEntry(entries, "http://[::1]:*/*");
    addWildcardEntry(entries, "https://[::1]:*/*");
    return;
  }

  addWildcardEntry(entries, host);
  addWildcardEntry(entries, `${host}/*`);
  addWildcardEntry(entries, `http://${host}/*`);
  addWildcardEntry(entries, `https://${host}/*`);
  if (!host.startsWith("www.")) {
    addWildcardEntry(entries, `www.${host}`);
    addWildcardEntry(entries, `http://www.${host}/*`);
    addWildcardEntry(entries, `https://www.${host}/*`);
  }
}

function buildAllowEntries(allowlist = []) {
  const entries = new Set();
  for (const host of allowlist) {
    addHostAllowEntries(entries, normalizeSiteHost(host));
  }
  return Array.from(entries);
}

class SiteBlocker {
  constructor({ onLog } = {}) {
    this.onLog = typeof onLog === "function" ? onLog : () => {};
    this.hostsPath = process.platform === "win32"
      ? path.join(process.env.SystemRoot || "C:\\Windows", "System32", "drivers", "etc", "hosts")
      : "/etc/hosts";
  }

  start(allowedSites = []) {
    const allowlist = expandAllowedSites(allowedSites);
    const result = {
      allowedSites: allowlist,
      browserProtectionReady: false,
      hostsApplied: false,
      policiesApplied: false,
      policyTargets: [],
      supportedBrowserProcesses: [],
      lastError: "",
    };

    try {
      this._applyHosts(allowlist);
      result.hostsApplied = true;
    } catch (error) {
      result.lastError = error.message;
      this.onLog(`Hosts blocker warning: ${error.message}`);
    }

    try {
      const policyResult = this._applyBrowserPolicies(allowlist);
      result.policiesApplied = policyResult.policiesApplied;
      result.policyTargets = policyResult.policyTargets;
      result.supportedBrowserProcesses = policyResult.supportedBrowserProcesses;
      result.browserProtectionReady = policyResult.browserProtectionReady;
      if (!result.browserProtectionReady && !result.lastError) {
        result.lastError = "Browser allowlist policies could not be applied.";
      }
    } catch (error) {
      result.lastError = result.lastError || error.message;
      this.onLog(`Browser policy warning: ${error.message}`);
    }

    return result;
  }

  stop() {
    const result = {
      browserProtectionReady: false,
      hostsApplied: false,
      policiesApplied: false,
      policyTargets: [],
      supportedBrowserProcesses: [],
      lastError: "",
    };

    try {
      this._removeHosts();
      result.hostsApplied = true;
    } catch (error) {
      result.lastError = error.message;
      this.onLog(`Hosts restore warning: ${error.message}`);
    }

    try {
      const policyResult = this._clearBrowserPolicies();
      result.policiesApplied = policyResult.policiesApplied;
      result.policyTargets = policyResult.policyTargets;
      result.supportedBrowserProcesses = policyResult.supportedBrowserProcesses;
    } catch (error) {
      result.lastError = result.lastError || error.message;
      this.onLog(`Browser policy restore warning: ${error.message}`);
    }

    return result;
  }

  _applyHosts(allowlist) {
    const current = fs.existsSync(this.hostsPath)
      ? fs.readFileSync(this.hostsPath, "utf-8")
      : "";
    const cleaned = this._stripManagedSection(current);
    const allowSet = new Set(allowlist.map((item) => normalizeSiteHost(item)).filter(Boolean));
    const blockedHosts = DISTRACTION_HOSTS.filter((host) => !allowSet.has(normalizeSiteHost(host)));
    const managedBody = [
      HOSTS_MARKER_START,
      ...blockedHosts.map((host) => `127.0.0.1 ${host}`),
      HOSTS_MARKER_END,
      "",
    ].join("\n");
    const prefix = cleaned.trimEnd();
    const nextContent = prefix ? `${prefix}\n\n${managedBody}` : managedBody;
    fs.writeFileSync(this.hostsPath, nextContent, "utf-8");
  }

  _removeHosts() {
    if (!fs.existsSync(this.hostsPath)) {
      return;
    }
    const current = fs.readFileSync(this.hostsPath, "utf-8");
    const cleaned = this._stripManagedSection(current).trimEnd();
    fs.writeFileSync(this.hostsPath, cleaned ? `${cleaned}\n` : "", "utf-8");
  }

  _stripManagedSection(text) {
    const pattern = new RegExp(`${HOSTS_MARKER_START}[\\s\\S]*?${HOSTS_MARKER_END}\\s*`, "g");
    return String(text || "").replace(pattern, "").trimEnd();
  }

  _applyBrowserPolicies(allowlist) {
    if (process.platform !== "win32") {
      return {
        browserProtectionReady: false,
        policiesApplied: false,
        policyTargets: [],
        supportedBrowserProcesses: [],
      };
    }

    const allowEntries = buildAllowEntries(allowlist);
    const policyTargets = [];
    const supportedBrowserProcesses = [];
    const errors = [];

    for (const browser of SUPPORTED_BROWSERS) {
      try {
        this._writeBrowserPolicy(browser, allowEntries);
        policyTargets.push(browser.name);
        supportedBrowserProcesses.push(browser.processName);
      } catch (error) {
        errors.push(`${browser.name}: ${error.message}`);
      }
    }

    if (errors.length) {
      this.onLog(`Browser policy warning: ${errors.join(" | ")}`);
    }

    return {
      browserProtectionReady: supportedBrowserProcesses.length > 0,
      policiesApplied: supportedBrowserProcesses.length > 0,
      policyTargets,
      supportedBrowserProcesses,
    };
  }

  _clearBrowserPolicies() {
    if (process.platform !== "win32") {
      return {
        policiesApplied: false,
        policyTargets: [],
        supportedBrowserProcesses: [],
      };
    }

    const policyTargets = [];
    const supportedBrowserProcesses = [];
    for (const browser of SUPPORTED_BROWSERS) {
      try {
        this._deleteBrowserPolicy(browser);
        policyTargets.push(browser.name);
        supportedBrowserProcesses.push(browser.processName);
      } catch (error) {
        this.onLog(`Browser policy restore warning: ${browser.name}: ${error.message}`);
      }
    }

    return {
      policiesApplied: supportedBrowserProcesses.length > 0,
      policyTargets,
      supportedBrowserProcesses,
    };
  }

  _writeBrowserPolicy(browser, allowEntries) {
    const baseKey = `HKCU\\Software\\Policies\\${browser.policyKey}`;
    this._runReg(["add", baseKey, "/f"]);
    this._deleteRegKey(`${baseKey}\\URLBlocklist`);
    this._deleteRegKey(`${baseKey}\\URLAllowlist`);
    this._runReg(["add", `${baseKey}\\URLBlocklist`, "/f"]);
    this._runReg(["add", `${baseKey}\\URLAllowlist`, "/f"]);
    this._runReg(["add", `${baseKey}\\URLBlocklist`, "/v", "1", "/t", "REG_SZ", "/d", "*", "/f"]);

    allowEntries.forEach((entry, index) => {
      this._runReg([
        "add",
        `${baseKey}\\URLAllowlist`,
        "/v",
        String(index + 1),
        "/t",
        "REG_SZ",
        "/d",
        entry,
        "/f",
      ]);
    });
  }

  _deleteBrowserPolicy(browser) {
    const baseKey = `HKCU\\Software\\Policies\\${browser.policyKey}`;
    this._deleteRegKey(`${baseKey}\\URLBlocklist`);
    this._deleteRegKey(`${baseKey}\\URLAllowlist`);
  }

  _deleteRegKey(key) {
    try {
      this._runReg(["delete", key, "/f"], { stdio: "ignore" });
    } catch (error) {
      return;
    }
  }

  _runReg(args, options = {}) {
    return execFileSync("reg", args, {
      windowsHide: true,
      ...options,
    });
  }
}

module.exports = {
  SiteBlocker,
  buildAllowEntries,
  expandAllowedSites,
  normalizeSiteHost,
};
