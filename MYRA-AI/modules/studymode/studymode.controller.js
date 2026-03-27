const { sharedStudyModeService } = require("./studymode.service");

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(payload));
}

function readJsonBody(request) {
  return new Promise((resolve, reject) => {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
      if (body.length > 1_000_000) {
        reject(new Error("Payload too large"));
      }
    });
    request.on("end", () => {
      if (!body.trim()) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(new Error("Invalid JSON payload"));
      }
    });
    request.on("error", reject);
  });
}

async function getStatus(request, response) {
  sendJson(response, 200, sharedStudyModeService.getStatus());
}

async function startStudyMode(request, response) {
  try {
    const body = await readJsonBody(request);
    const duration = body.duration ?? body.durationMinutes ?? body.value ?? "";
    const payload = duration ? sharedStudyModeService.startStudyMode(duration) : sharedStudyModeService.requestActivation();
    sendJson(response, 200, payload);
  } catch (error) {
    sendJson(response, 400, { error: error.message });
  }
}

async function stopStudyMode(request, response) {
  try {
    const body = await readJsonBody(request);
    const passcode = String(body.passcode || "").trim();
    const payload = passcode
      ? sharedStudyModeService.stopStudyMode(passcode, { manual: true })
      : sharedStudyModeService.requestUnlock();
    sendJson(response, 200, payload);
  } catch (error) {
    sendJson(response, 400, { error: error.message });
  }
}

async function getLogs(request, response) {
  sendJson(response, 200, sharedStudyModeService.getLogs());
}

module.exports = {
  getLogs,
  getStatus,
  readJsonBody,
  sendJson,
  sharedStudyModeService,
  startStudyMode,
  stopStudyMode,
};
