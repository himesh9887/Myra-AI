const { NetControlService } = require("../modules/netcontrol/netcontrol.service");
const { executeStudyModeCommand } = require("./studymode.commands");

const sharedService = new NetControlService();

function formatWifiSummary(networks) {
  return networks
    .map((item) => `${item.name} (${item.strength}% ${item.security})`)
    .join(", ");
}

function summarizeLogs(logs) {
  if (!logs.length) {
    return "Boss, NetControl logs abhi quiet hain.";
  }
  return logs.slice(-5).join(" | ");
}

function summarizeVisionStatus(visionMonitor = {}) {
  const face = visionMonitor.faceStatus || "unavailable";
  const focus = visionMonitor.focusStatus || "unavailable";
  const noise = visionMonitor.noiseStatus || "unavailable";
  const warning = visionMonitor.warning && visionMonitor.warning !== "none"
    ? ` Warning: ${visionMonitor.warning}.`
    : "";
  return `Face ${face}, focus ${focus}, noise ${noise}.${warning}`.trim();
}

function extractFocusPayload(command) {
  const raw = String(command || "");
  const durationMatch = raw.match(/(\d{1,3})\s*(?:min|mins|minutes)/i);
  const rangeMatch = raw.match(/(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|-)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)/i);
  return {
    durationMinutes: durationMatch ? Number(durationMatch[1]) : 25,
    start: rangeMatch ? rangeMatch[1] : "",
    end: rangeMatch ? rangeMatch[2] : "",
  };
}

function getService(context = {}) {
  return context.service instanceof NetControlService ? context.service : sharedService;
}

const NETCONTROL_COMMANDS = [
  {
    key: "check_network",
    pattern: /^(?:check|show)\s+(?:the\s+)?network(?:\s+status)?$|^(?:internet|wifi|network)\s+(?:status|speed|ping)(?:\s+batao)?$/i,
    handler: (command, context) => {
      const service = getService(context);
      const status = service.getNetworkStatus();
      service.addLog("Network status inspected");
      return {
        handled: true,
        message: `Boss, network ${status.status} hai. Speed ${status.speed} aur ping ${status.ping} dikh raha hai.`,
        data: status,
      };
    },
  },
  {
    key: "scan_wifi",
    pattern: /^(?:scan|show)\s+wifi$|^wifi\s+scan$/i,
    handler: (command, context) => {
      const service = getService(context);
      const networks = service.scanWifi();
      service.addLog("WiFi scan completed");
      return {
        handled: true,
        message: `Boss, nearby WiFi mil gaye: ${formatWifiSummary(networks)}.`,
        data: networks,
      };
    },
  },
  {
    key: "internet_off",
    pattern: /^internet\s+off$/i,
    handler: (command, context) => {
      const service = getService(context);
      service.toggleInternet(false);
      return {
        handled: true,
        message: "Boss, internet simulation off kar diya. Real connection touch nahi kiya gaya.",
      };
    },
  },
  {
    key: "internet_on",
    pattern: /^internet\s+on$/i,
    handler: (command, context) => {
      const service = getService(context);
      service.toggleInternet(true);
      return {
        handled: true,
        message: "Boss, internet simulation dubara online hai.",
      };
    },
  },
  {
    key: "block_site",
    pattern: /^block\s+site\s+(.+)$/i,
    handler: (command, context) => {
      const service = getService(context);
      const match = String(command).match(/^block\s+site\s+(.+)$/i);
      const result = service.blockWebsite(match ? match[1] : "");
      return {
        handled: true,
        message: `Boss, ${result.site} ko NetControl block list me daal diya.`,
        data: result,
      };
    },
  },
  {
    key: "start_focus_mode",
    pattern: /^start\s+focus\s+mode(?:\s+.*)?$/i,
    handler: (command, context) => {
      const service = getService(context);
      const payload = extractFocusPayload(command);
      const status = service.startFocusMode(payload.start, payload.end, payload.durationMinutes);
      return {
        handled: true,
        message: `Boss, focus mode live hai till ${status.focusMode.endLabel || "soon"}. ${status.suggestion}`,
        data: status,
      };
    },
  },
  {
    key: "stop_focus_mode",
    pattern: /^stop\s+focus\s+mode$/i,
    handler: (command, context) => {
      const service = getService(context);
      service.stopFocusMode();
      return {
        handled: true,
        message: "Boss, focus mode stop kar diya. Block shield bhi relax kar diya gaya.",
      };
    },
  },
  {
    key: "show_logs",
    pattern: /^show\s+logs$/i,
    handler: (command, context) => {
      const service = getService(context);
      const logs = service.getLogs().logs;
      return {
        handled: true,
        message: summarizeLogs(logs),
        data: logs,
      };
    },
  },
  {
    key: "start_vision_monitoring",
    pattern: /^(?:start|enable)\s+vision\s+monitor(?:ing)?$/i,
    handler: (command, context) => {
      const service = getService(context);
      const result = service.startVisionMonitoring();
      return {
        handled: true,
        message: result.message || "Vision monitoring started.",
        data: result,
      };
    },
  },
  {
    key: "stop_vision_monitoring",
    pattern: /^(?:stop|disable)\s+vision\s+monitor(?:ing)?$/i,
    handler: (command, context) => {
      const service = getService(context);
      const result = service.stopVisionMonitoring();
      return {
        handled: true,
        message: result.message || "Vision monitoring stopped.",
        data: result,
      };
    },
  },
  {
    key: "vision_monitor_status",
    pattern: /^(?:show|check)\s+vision\s+monitor(?:ing)?(?:\s+status)?$/i,
    handler: (command, context) => {
      const service = getService(context);
      const status = service.getVisionStatus();
      return {
        handled: true,
        message: `Boss, ${summarizeVisionStatus(status)}`,
        data: status,
      };
    },
  },
  {
    key: "open_dashboard",
    pattern: /^(?:open|show|launch)\s+netcontrol\s+dashboard$/i,
    handler: (command, context) => {
      const service = getService(context);
      const port = Number(context.port || 5127);
      const host = String(context.host || "127.0.0.1");
      service.addLog("NetControl dashboard opened");
      return {
        handled: true,
        message: "Boss, NetControl dashboard browser ke liye ready hai.",
        openUrl: service.getDashboardUrl(port, host),
      };
    },
  },
];

function executeNetControlCommand(command, context = {}) {
  const raw = String(command || "")
    .trim()
    .split(/\s+/)
    .join(" ")
    .replace(/\bstudy\s+mood\b/gi, "study mode");
  if (!raw) {
    return { handled: false, message: "" };
  }

  const service = getService(context);
  const studyResult = executeStudyModeCommand(raw, {
    ...context,
    service,
    studyService: typeof service.getStudyModeService === "function" ? service.getStudyModeService() : undefined,
  });
  if (studyResult && studyResult.handled) {
    return studyResult;
  }

  const matched = NETCONTROL_COMMANDS.find((item) => item.pattern.test(raw));
  if (!matched) {
    return {
      handled: false,
      message: "Boss, NetControl command thoda aur clearly bolo.",
    };
  }

  return matched.handler(raw, context);
}

module.exports = {
  NETCONTROL_COMMANDS,
  executeNetControlCommand,
};
