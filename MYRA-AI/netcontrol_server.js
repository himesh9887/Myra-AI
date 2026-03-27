const http = require("http");

const { handleNetControlRequest } = require("./modules/netcontrol/netcontrol.routes");

const HOST = process.env.MYRA_NETCONTROL_HOST || "127.0.0.1";
const PORT = Number(process.env.MYRA_NETCONTROL_PORT || 5127);

const server = http.createServer((request, response) => {
  handleNetControlRequest(request, response, {
    host: HOST,
    port: PORT,
  }).catch((error) => {
    response.writeHead(500, { "Content-Type": "application/json; charset=utf-8" });
    response.end(JSON.stringify({ error: error.message || "NetControl server error" }));
  });
});

server.keepAliveTimeout = 5000;
server.headersTimeout = 8000;

server.listen(PORT, HOST);

["SIGINT", "SIGTERM"].forEach((signal) => {
  process.on(signal, () => {
    server.close(() => process.exit(0));
  });
});
