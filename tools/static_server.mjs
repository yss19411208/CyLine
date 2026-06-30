import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";

const port = Number.parseInt(process.argv[2] || "8080", 10);
const rootDirectory = resolve(process.argv[3] || "docs");

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp"
};

function resolveRequestPath(requestUrl) {
  const parsedUrl = new URL(requestUrl, `http://127.0.0.1:${port}`);
  let decodedPath = "";
  try {
    decodedPath = decodeURIComponent(parsedUrl.pathname);
  } catch {
    return null;
  }
  const relativePath = normalize(decodedPath).replace(/^([/\\])+/, "");
  const candidatePath = resolve(join(rootDirectory, relativePath || "index.html"));

  if (candidatePath !== rootDirectory && !candidatePath.startsWith(`${rootDirectory}${sep}`)) {
    return null;
  }

  if (existsSync(candidatePath) && statSync(candidatePath).isDirectory()) {
    return join(candidatePath, "index.html");
  }

  return candidatePath;
}

const server = createServer((request, response) => {
  const filePath = resolveRequestPath(request.url || "/");
  if (filePath === null || !existsSync(filePath) || !statSync(filePath).isFile()) {
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    response.end("Not found");
    return;
  }

  response.writeHead(200, {
    "content-type": contentTypes[extname(filePath).toLowerCase()] || "application/octet-stream"
  });
  createReadStream(filePath).pipe(response);
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Serving ${rootDirectory} at http://127.0.0.1:${port}/`);
});
