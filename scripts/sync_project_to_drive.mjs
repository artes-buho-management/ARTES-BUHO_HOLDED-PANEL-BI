import { createSign } from "crypto";
import { promises as fs } from "fs";
import path from "path";

const DRIVE_SCOPE = "https://www.googleapis.com/auth/drive";
const TOKEN_URL = "https://oauth2.googleapis.com/token";
const DRIVE_API = "https://www.googleapis.com/drive/v3/files";
const DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files";
const FOLDER_MIME = "application/vnd.google-apps.folder";

const EXCLUDED_DIRS = new Set([
  ".git",
  "__pycache__",
  ".venv",
  "venv",
  "env",
  "node_modules",
  "reports_output",
]);

const EXCLUDED_FILES = new Set([
  ".env",
  "secrets.toml",
]);

function base64Url(input) {
  return Buffer.from(input)
    .toString("base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function contentTypeFor(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const map = {
    ".py": "text/x-python",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".toml": "text/plain",
    ".json": "application/json",
    ".yml": "text/yaml",
    ".yaml": "text/yaml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
  };
  return map[ext] || "application/octet-stream";
}

function parseFolderId(input) {
  if (!input) throw new Error("Falta DRIVE_TARGET_FOLDER_ID o URL.");
  if (!input.includes("drive.google.com")) return input.trim();
  const match = input.match(/\/folders\/([a-zA-Z0-9_-]+)/);
  if (!match) throw new Error("No se pudo extraer folderId del link de Drive.");
  return match[1];
}

async function readServiceAccount() {
  if (process.env.GOOGLE_SERVICE_ACCOUNT_JSON) {
    return JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_JSON);
  }

  if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
    const raw = await fs.readFile(process.env.GOOGLE_APPLICATION_CREDENTIALS, "utf8");
    return JSON.parse(raw);
  }

  const fallback = path.resolve(
    "C:/Users/elrub/Desktop/CARPETA CODEX/secrets/robot-codex-key-20260308-220232.json",
  );
  const raw = await fs.readFile(fallback, "utf8");
  return JSON.parse(raw);
}

async function getAccessToken(serviceAccount) {
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "RS256", typ: "JWT" };
  const claimSet = {
    iss: serviceAccount.client_email,
    scope: DRIVE_SCOPE,
    aud: TOKEN_URL,
    exp: now + 3600,
    iat: now,
  };

  const unsignedJwt = `${base64Url(JSON.stringify(header))}.${base64Url(JSON.stringify(claimSet))}`;
  const signer = createSign("RSA-SHA256");
  signer.update(unsignedJwt);
  const signature = signer.sign(serviceAccount.private_key);
  const jwt = `${unsignedJwt}.${base64Url(signature)}`;

  const body = new URLSearchParams({
    grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
    assertion: jwt,
  });

  const resp = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!resp.ok) {
    throw new Error(`Token error ${resp.status}: ${await resp.text()}`);
  }
  const data = await resp.json();
  return data.access_token;
}

async function driveList(token, query) {
  const url = new URL(DRIVE_API);
  url.searchParams.set("q", query);
  url.searchParams.set("fields", "files(id,name,mimeType,webViewLink)");
  url.searchParams.set("pageSize", "10");
  url.searchParams.set("supportsAllDrives", "true");
  url.searchParams.set("includeItemsFromAllDrives", "true");

  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    throw new Error(`Drive list error ${resp.status}: ${await resp.text()}`);
  }
  return resp.json();
}

async function findByNameInParent(token, name, parentId, mimeType = "") {
  const safe = name.replace(/'/g, "\\'");
  let q = `name='${safe}' and '${parentId}' in parents and trashed=false`;
  if (mimeType) q += ` and mimeType='${mimeType}'`;
  const data = await driveList(token, q);
  return data.files?.[0] || null;
}

async function createFolder(token, name, parentId) {
  const resp = await fetch(`${DRIVE_API}?supportsAllDrives=true`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name,
      mimeType: FOLDER_MIME,
      parents: [parentId],
    }),
  });
  if (!resp.ok) {
    throw new Error(`Create folder error ${resp.status}: ${await resp.text()}`);
  }
  return resp.json();
}

async function ensureFolder(token, name, parentId) {
  const existing = await findByNameInParent(token, name, parentId, FOLDER_MIME);
  if (existing) return existing;
  return createFolder(token, name, parentId);
}

async function uploadFileMultipart(token, filePath, parentId, overwrite = true) {
  const fileName = path.basename(filePath);
  const mimeType = contentTypeFor(filePath);
  const existing = await findByNameInParent(token, fileName, parentId);
  const fileBytes = await fs.readFile(filePath);

  const boundary = `batch_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  const metadata = existing
    ? { name: fileName }
    : { name: fileName, parents: [parentId] };

  const part1 =
    `--${boundary}\r\n` +
    `Content-Type: application/json; charset=UTF-8\r\n\r\n` +
    `${JSON.stringify(metadata)}\r\n`;
  const part2Header =
    `--${boundary}\r\n` +
    `Content-Type: ${mimeType}\r\n\r\n`;
  const closing = `\r\n--${boundary}--`;

  const body = Buffer.concat([
    Buffer.from(part1, "utf8"),
    Buffer.from(part2Header, "utf8"),
    fileBytes,
    Buffer.from(closing, "utf8"),
  ]);

  let url = `${DRIVE_UPLOAD_API}?uploadType=multipart&supportsAllDrives=true`;
  let method = "POST";
  if (existing && overwrite) {
    url = `${DRIVE_UPLOAD_API}/${existing.id}?uploadType=multipart&supportsAllDrives=true`;
    method = "PATCH";
  } else if (existing && !overwrite) {
    return { status: "skipped", id: existing.id, name: fileName };
  }

  const resp = await fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": `multipart/related; boundary=${boundary}`,
    },
    body,
  });
  if (!resp.ok) {
    throw new Error(`Upload error ${resp.status} (${fileName}): ${await resp.text()}`);
  }
  const data = await resp.json();
  return { status: existing ? "updated" : "created", id: data.id, name: fileName };
}

async function syncDirectory(token, localDir, driveParentId) {
  const entries = await fs.readdir(localDir, { withFileTypes: true });
  const sorted = entries.sort((a, b) => a.name.localeCompare(b.name));

  for (const entry of sorted) {
    if (entry.name.startsWith(".") && entry.name !== ".streamlit") continue;
    if (entry.isDirectory() && EXCLUDED_DIRS.has(entry.name)) continue;
    if (entry.isFile() && EXCLUDED_FILES.has(entry.name)) continue;

    const fullPath = path.join(localDir, entry.name);
    if (entry.isDirectory()) {
      const childFolder = await ensureFolder(token, entry.name, driveParentId);
      await syncDirectory(token, fullPath, childFolder.id);
      continue;
    }
    if (entry.isFile()) {
      const result = await uploadFileMultipart(token, fullPath, driveParentId, true);
      console.log(`${result.status.toUpperCase()}: ${entry.name}`);
    }
  }
}

async function main() {
  const targetInput =
    process.env.DRIVE_TARGET_FOLDER_ID ||
    process.argv[2] ||
    "https://drive.google.com/drive/folders/REPLACE_WITH_ID?usp=drive_link";

  const targetFolderId = parseFolderId(targetInput);
  const projectRoot = process.cwd();
  const serviceAccount = await readServiceAccount();
  const token = await getAccessToken(serviceAccount);

  const projectFolderName = path.basename(projectRoot);
  const projectFolder = await ensureFolder(token, projectFolderName, targetFolderId);
  await syncDirectory(token, projectRoot, projectFolder.id);

  console.log("SYNC_OK");
  console.log(`Drive folder: https://drive.google.com/drive/folders/${projectFolder.id}`);
}

main().catch((err) => {
  console.error("SYNC_ERROR");
  console.error(err?.message || err);
  process.exit(1);
});

