const {
  sharedStudyModeService,
  looksLikeDuration,
  looksLikePasscode,
  parseDurationMinutes,
} = require("../modules/studymode/studymode.service");

const STUDY_MODE_PATTERN = "study\\s+mo(?:de|od)";

function getService(context = {}) {
  if (context.studyService && typeof context.studyService.getStatus === "function") {
    return context.studyService;
  }
  if (context.service && typeof context.service.getStudyModeService === "function") {
    return context.service.getStudyModeService();
  }
  return sharedStudyModeService;
}

function normalizeCommand(command) {
  return String(command || "")
    .trim()
    .split(/\s+/)
    .join(" ")
    .replace(/\bstudy\s+mood\b/gi, "study mode");
}

function extractInlineDuration(command) {
  const match = normalizeCommand(command).match(
    new RegExp(`^${STUDY_MODE_PATTERN}\\s+on(?:\\s+(?:for\\s+)?)?(.+)$`, "i")
  );
  if (!match) {
    return "";
  }
  const candidate = String(match[1] || "").trim();
  return looksLikeDuration(candidate) ? candidate : "";
}

function executeStudyModeCommand(command, context = {}) {
  const raw = normalizeCommand(command);
  if (!raw) {
    return { handled: false, message: "" };
  }

  const service = getService(context);
  const status = service.getStatus();

  if (/^force\s+stop\s+study\s+mode$/i.test(raw)) {
    const result = service.forceStopStudyMode();
    return {
      handled: true,
      requiresPasscode: false,
      message: result.message,
      data: result,
    };
  }

  if (status.studyUnlockPending && looksLikePasscode(raw)) {
    const result = service.stopStudyMode(raw, { manual: true });
    return {
      handled: true,
      requiresPasscode: Boolean(result.requiresPasscode),
      message: result.message,
      data: result,
    };
  }

  if (status.studyDurationPending && looksLikeDuration(raw)) {
    const minutes = parseDurationMinutes(raw);
    const result = service.startStudyMode(minutes || raw);
    return {
      handled: true,
      requiresDuration: Boolean(result.requiresDuration),
      message: result.message,
      data: result,
    };
  }

  if (new RegExp(`^${STUDY_MODE_PATTERN}\\s+on$`, "i").test(raw)) {
    const result = service.requestActivation();
    return {
      handled: true,
      requiresDuration: Boolean(result.requiresDuration),
      message: result.message,
      data: result,
    };
  }

  const inlineDuration = extractInlineDuration(raw);
  if (inlineDuration) {
    const result = service.startStudyMode(inlineDuration);
    return {
      handled: true,
      requiresDuration: Boolean(result.requiresDuration),
      message: result.message,
      data: result,
    };
  }

  if (new RegExp(`^${STUDY_MODE_PATTERN}\\s+off$`, "i").test(raw)) {
    const result = service.requestUnlock();
    return {
      handled: true,
      requiresPasscode: Boolean(result.requiresPasscode),
      message: result.message,
      data: result,
    };
  }

  if (status.studyUnlockPending && /^unlock$/i.test(raw)) {
    const result = service.requestUnlock();
    return {
      handled: true,
      requiresPasscode: Boolean(result.requiresPasscode),
      message: result.message,
      data: result,
    };
  }

  return {
    handled: false,
    message: "",
  };
}

module.exports = {
  STUDY_MODE_PATTERN,
  executeStudyModeCommand,
};
