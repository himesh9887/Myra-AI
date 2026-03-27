const { executeNetControlCommand } = require("../../commands/netcontrol.commands");
const { NetControlService } = require("./netcontrol.service");

const service = new NetControlService();

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
  sendJson(response, 200, service.getNetworkStatus());
}

async function getWifi(request, response) {
  sendJson(response, 200, service.scanWifi());
}

async function toggleInternet(request, response) {
  try {
    const body = await readJsonBody(request);
    sendJson(response, 200, service.toggleInternet(body.state));
  } catch (error) {
    sendJson(response, 400, { error: error.message });
  }
}

async function blockWebsite(request, response) {
  try {
    const body = await readJsonBody(request);
    sendJson(response, 200, service.blockWebsite(body.site));
  } catch (error) {
    sendJson(response, 400, { error: error.message });
  }
}

async function startFocusMode(request, response) {
  try {
    const body = await readJsonBody(request);
    sendJson(
      response,
      200,
      service.startFocusMode(body.start, body.end, body.durationMinutes)
    );
  } catch (error) {
    sendJson(response, 400, { error: error.message });
  }
}

async function stopFocusMode(request, response) {
  sendJson(response, 200, service.stopFocusMode());
}

async function startStudyMode(request, response) {
  try {
    const body = await readJsonBody(request);
    const duration = body.duration ?? body.durationMinutes ?? body.value ?? "";
    const payload = duration ? service.startStudyMode(duration) : service.requestStudyModeStart();
    sendJson(response, 200, payload);
  } catch (error) {
    sendJson(response, 400, { error: error.message });
  }
}

async function stopStudyMode(request, response) {
  try {
    const body = await readJsonBody(request);
    const passcode = String(body.passcode || "").trim();
    const payload = passcode ? service.stopStudyMode(passcode) : service.requestStudyModeUnlock();
    sendJson(response, 200, payload);
  } catch (error) {
    sendJson(response, 400, { error: error.message });
  }
}

async function getLogs(request, response) {
  sendJson(response, 200, service.getLogs());
}

async function getVisionStatus(request, response) {
  sendJson(response, 200, service.getVisionStatus());
}

async function startVisionMonitoring(request, response) {
  sendJson(response, 200, service.startVisionMonitoring());
}

async function stopVisionMonitoring(request, response) {
  sendJson(response, 200, service.stopVisionMonitoring());
}

async function addLogEntry(request, response) {
  try {
    const body = await readJsonBody(request);
    sendJson(response, 200, service.addLog(body.message));
  } catch (error) {
    sendJson(response, 400, { error: error.message });
  }
}

async function executeCommand(request, response, context = {}) {
  try {
    const body = await readJsonBody(request);
    const result = executeNetControlCommand(body.command, {
      service,
      port: context.port,
      host: context.host,
    });
    sendJson(response, result.handled ? 200 : 404, result);
  } catch (error) {
    sendJson(response, 400, { error: error.message });
  }
}

module.exports = {
  addLogEntry,
  executeCommand,
  getLogs,
  getStatus,
  getVisionStatus,
  getWifi,
  readJsonBody,
  sendJson,
  service,
  startStudyMode,
  startVisionMonitoring,
  startFocusMode,
  stopStudyMode,
  stopVisionMonitoring,
  stopFocusMode,
  toggleInternet,
  blockWebsite,
};
