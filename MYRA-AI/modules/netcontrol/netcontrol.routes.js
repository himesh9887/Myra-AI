const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const controller = require("./netcontrol.controller");
const studyController = require("../studymode/studymode.controller");

const DASHBOARD_ROOT = path.resolve(__dirname, "../../frontend/dashboard/netcontrol");

const STATIC_MIME_TYPES = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
};

function sendStatic(response, filePath) {
  try {
    const resolvedPath = path.resolve(filePath);
    if (!resolvedPath.startsWith(DASHBOARD_ROOT)) {
      controller.sendJson(response, 403, { error: "Forbidden" });
      return;
    }

    const extension = path.extname(resolvedPath).toLowerCase();
    const body = fs.readFileSync(resolvedPath);
    response.writeHead(200, {
      "Content-Type": STATIC_MIME_TYPES[extension] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    response.end(body);
  } catch (error) {
    controller.sendJson(response, 404, { error: "Resource not found" });
  }
}

async function handleNetControlRequest(request, response, context = {}) {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type");
  response.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");

  if (request.method === "OPTIONS") {
    response.writeHead(204);
    response.end();
    return;
  }

  const url = new URL(request.url, `http://${request.headers.host || "127.0.0.1"}`);
  const pathname = url.pathname;
  const routeKey = `${String(request.method || "GET").toUpperCase()} ${pathname}`;

  if (routeKey === "GET /dashboard/netcontrol" || routeKey === "GET /dashboard/netcontrol/") {
    sendStatic(response, path.join(DASHBOARD_ROOT, "netcontrol.html"));
    return;
  }

  if (pathname.startsWith("/frontend/dashboard/netcontrol/")) {
    const relativePath = pathname.replace("/frontend/dashboard/netcontrol/", "");
    sendStatic(response, path.join(DASHBOARD_ROOT, relativePath));
    return;
  }

  const routes = {
    "GET /api/netcontrol/status": controller.getStatus,
    "GET /api/netcontrol/wifi": controller.getWifi,
    "POST /api/netcontrol/toggle": controller.toggleInternet,
    "POST /api/netcontrol/block": controller.blockWebsite,
    "POST /api/netcontrol/focus/start": controller.startFocusMode,
    "POST /api/netcontrol/focus/stop": controller.stopFocusMode,
    "POST /api/netcontrol/study/start": controller.startStudyMode,
    "POST /api/netcontrol/study/stop": controller.stopStudyMode,
    "GET /api/netcontrol/vision/status": controller.getVisionStatus,
    "POST /api/netcontrol/vision/start": controller.startVisionMonitoring,
    "POST /api/netcontrol/vision/stop": controller.stopVisionMonitoring,
    "GET /api/netcontrol/logs": controller.getLogs,
    "POST /api/netcontrol/log": controller.addLogEntry,
    "POST /api/netcontrol/command": (req, res) => controller.executeCommand(req, res, context),
    "GET /api/studymode/status": studyController.getStatus,
    "POST /api/studymode/start": studyController.startStudyMode,
    "POST /api/studymode/stop": studyController.stopStudyMode,
    "GET /api/studymode/logs": studyController.getLogs,
  };

  const handler = routes[routeKey];
  if (!handler) {
    controller.sendJson(response, 404, { error: "NetControl route not found" });
    return;
  }

  await handler(request, response);
}

module.exports = {
  handleNetControlRequest,
};
