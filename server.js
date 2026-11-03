/* ==========================================================================
   SECTION 1: IMPORTS & SERVER CONSTANTS
   ========================================================================== */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  exchangeNpssoForAccessCode,
  exchangeCodeForAccessToken,
  getProfileFromAccountId,
  getPurchasedGames,
  getUserPlayedGames
} from "psn-api";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 3000;
const PUBLIC_DIR = path.join(__dirname, "public");

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".ico": "image/x-icon"
};

/* ==========================================================================
   SECTION 2: SECURITY, RATE LIMITING & DEFENSIVE HEADERS
   ========================================================================== */
const rateLimits = new Map();
const RATE_WINDOW = 60 * 1000;
const RATE_MAX = 5;

function checkRateLimit(ip) {
  const now = Date.now();
  const entry = rateLimits.get(ip);
  if (!entry || now - entry.windowStart > RATE_WINDOW) {
    rateLimits.set(ip, { windowStart: now, count: 1 });
    return true;
  }
  entry.count++;
  return entry.count <= RATE_MAX;
}

setInterval(() => {
  const now = Date.now();
  for (const [ip, entry] of rateLimits) {
    if (now - entry.windowStart > RATE_WINDOW * 2) {
      rateLimits.delete(ip);
    }
  }
}, 5 * 60 * 1000).unref();

function sanitizeToken(input) {
  if (typeof input !== "string") return "";
  let token = input.trim().replace(/^["']|["']$/g, "").trim();
  if (token.startsWith("{") && token.includes("npsso")) {
    try {
      const parsed = JSON.parse(token);
      if (parsed.npsso) token = parsed.npsso.trim();
    } catch {}
    const match = token.match(/"npsso"\s*:\s*"([^"]+)"/);
    if (match) token = match[1].trim();
  }
  return token;
}

function applySecurityHeaders(res) {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("X-XSS-Protection", "1; mode=block");
  res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
  res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()");
  res.setHeader(
    "Content-Security-Policy",
    [
      "default-src 'self'",
      "script-src 'self'",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com",
      "img-src 'self' data: https://image.api.playstation.com https://store.playstation.com https://*.playstation.net",
      "connect-src 'self'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      "base-uri 'self'"
    ].join("; ")
  );
}

/* ==========================================================================
   SECTION 3: STRING SANITIZATION & PARSING UTILITIES
   ========================================================================== */
function parseDuration(isoDuration) {
  if (!isoDuration || typeof isoDuration !== "string") return null;
  const match = isoDuration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?/);
  if (!match) return null;
  const hours = Number(match[1] || 0);
  const minutes = Number(match[2] || 0);
  const total = (hours + minutes / 60).toFixed(1);
  return total > 0 ? `${total}h` : "<1h";
}

function escapeCsv(val) {
  if (val === null || val === undefined) return "";
  const str = String(val);
  return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
}

/* ==========================================================================
   SECTION 4: SONY PSN API ENGINE & PIPELINE
   ========================================================================== */
async function runFetchPipeline(token, onProgress) {
  const startTime = Date.now();

  const emit = (payload) => {
    const elapsed = Math.max(1, Math.round((Date.now() - startTime) / 1000));
    const pct = payload.percent || 10;
    const estTotal = (elapsed / Math.max(pct, 5)) * 100;
    const remaining = pct >= 100 ? 0 : Math.max(0, Math.round(estTotal - elapsed));
    const etaText = remaining > 0 ? `~${remaining}s left` : "finishing...";

    onProgress({
      ...payload,
      elapsedSeconds: elapsed,
      remainingSeconds: remaining,
      etaText: `${etaText} (${elapsed}s elapsed)`
    });
  };

  emit({ step: 1, message: "Connecting to PlayStation OAuth gateway...", percent: 15 });

  const timeout = new Promise((_, reject) =>
    setTimeout(() => reject(new Error("Connection timed out after 3 seconds.")), 3000)
  );
  const accessCode = await Promise.race([exchangeNpssoForAccessCode(token), timeout]);

  emit({ step: 1, message: "Exchanging code for OAuth session...", percent: 25 });
  const auth = await exchangeCodeForAccessToken(accessCode);

  let accountId = null;
  try {
    const payload = JSON.parse(Buffer.from(auth.accessToken.split(".")[1], "base64").toString());
    accountId = payload.account_id || payload.sub;
  } catch {}

  emit({ step: 1, message: "Fetching account profile & PS Plus status...", percent: 38 });
  let profile = null;
  if (accountId) {
    try {
      profile = await getProfileFromAccountId(auth, accountId);
    } catch {}
  }

  const onlineId = profile?.onlineId || accountId || "PlayStation User";
  const realName = profile?.personalDetail
    ? `${profile.personalDetail.firstName || ""} ${profile.personalDetail.lastName || ""}`.trim()
    : "";
  const isPlus = profile?.isPlus === true;
  const avatarUrl =
    profile?.avatars?.find((a) => a.size === "xl" || a.size === "l")?.url || profile?.avatars?.[0]?.url || null;

  emit({ step: 2, message: "Fetching activity & playtime history...", percent: 50 });
  const playtimeMap = new Map();
  if (accountId) {
    try {
      let offset = 0;
      const limit = 100;
      while (offset < 300) {
        const res = await getUserPlayedGames(auth, accountId, { limit, offset });
        const titles = res?.titles || [];
        if (!titles.length) break;

        for (const item of titles) {
          if (item.titleId) {
            playtimeMap.set(item.titleId.toUpperCase(), {
              playtime: parseDuration(item.playDuration),
              playCount: item.playCount,
              lastPlayed: item.lastPlayedDateTime
            });
          }
        }
        if (titles.length < limit) break;
        offset += limit;
      }
    } catch {}
  }

  emit({ step: 3, message: "Retrieving digital titles from catalog...", percent: 65 });
  let allRawGames = [];
  let start = 0;
  const chunkSize = 100;

  while (true) {
    const res = await getPurchasedGames(auth, { size: chunkSize, start });
    const games = res?.data?.purchasedTitlesRetrieve?.games || [];
    if (!games.length) break;

    allRawGames = allRawGames.concat(games);
    emit({
      step: 3,
      message: `Retrieved ${allRawGames.length} titles...`,
      percent: Math.min(92, 65 + Math.round(allRawGames.length / 4.2))
    });

    if (games.length < chunkSize) break;
    start += chunkSize;
  }

  emit({ step: 4, message: "Categorizing licenses & entitlements...", percent: 96 });
  const normalized = allRawGames.map((g) => {
    const titleId = (g.titleId || "").toUpperCase();
    const activity = playtimeMap.get(titleId) || {};
    const isPsPlus = g.membership === "PS_PLUS";
    const platform = (g.platform || "OTHER").toUpperCase();

    return {
      name: g.name || "Unknown Title",
      platform,
      membership: g.membership || "NONE",
      isPsPlus,
      licenseType: isPsPlus ? "PS PLUS CLAIMED" : "OWNED DIGITAL PURCHASE",
      titleId: g.titleId || "",
      entitlementId: g.entitlementId || "",
      productId: g.productId || "",
      isActive: g.isActive ?? true,
      isDownloadable: g.isDownloadable ?? true,
      isPreOrder: g.isPreOrder ?? false,
      playtime: activity.playtime || null,
      playCount: activity.playCount || null,
      lastPlayed: activity.lastPlayed ? activity.lastPlayed.split("T")[0] : null,
      imageUrl: g.image?.url || null
    };
  });

  normalized.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));

  const ownedPS5 = normalized.filter((g) => !g.isPsPlus && g.platform === "PS5");
  const ownedPS4 = normalized.filter((g) => !g.isPsPlus && g.platform === "PS4");
  const ownedOther = normalized.filter((g) => !g.isPsPlus && g.platform !== "PS5" && g.platform !== "PS4");

  const plusPS5 = normalized.filter((g) => g.isPsPlus && g.platform === "PS5");
  const plusPS4 = normalized.filter((g) => g.isPsPlus && g.platform === "PS4");
  const plusOther = normalized.filter((g) => g.isPsPlus && g.platform !== "PS5" && g.platform !== "PS4");

  const totalOwned = ownedPS5.length + ownedPS4.length + ownedOther.length;
  const totalPlus = plusPS5.length + plusPS4.length + plusOther.length;

  const resultData = {
    fetchedAt: new Date().toISOString(),
    account: {
      onlineId,
      realName,
      avatarUrl,
      isPlusActive: isPlus,
      psPlusTier: isPlus ? "PS_PLUS" : "None",
      psPlusTierLabel: isPlus ? "PlayStation Plus" : "No Active Subscription",
      psPlusTierBadge: isPlus ? "PS PLUS" : "Inactive",
      psPlusDescription: isPlus
        ? "Monthly Games, Online Multiplayer, Exclusive Discounts & Cloud Storage"
        : ""
    },
    summary: {
      totalTitles: normalized.length,
      ownedPurchases: {
        total: totalOwned,
        ps5: ownedPS5.length,
        ps4: ownedPS4.length,
        other: ownedOther.length
      },
      psPlusEntitlements: {
        total: totalPlus,
        ps5: plusPS5.length,
        ps4: plusPS4.length,
        other: plusOther.length
      }
    },
    games: normalized
  };

  fs.writeFileSync(path.join(__dirname, "psn-game-library.json"), JSON.stringify(resultData, null, 2), "utf8");

  const csvHeaders = [
    "Name",
    "Platform",
    "License_Type",
    "Is_PS_Plus",
    "Title_ID",
    "Entitlement_ID",
    "Playtime",
    "Play_Count",
    "Last_Played",
    "Is_Active",
    "Is_Downloadable"
  ];

  const csvRows = normalized.map((g) => [
    escapeCsv(g.name),
    escapeCsv(g.platform),
    escapeCsv(g.licenseType),
    escapeCsv(g.isPsPlus ? "YES" : "NO"),
    escapeCsv(g.titleId),
    escapeCsv(g.entitlementId),
    escapeCsv(g.playtime || ""),
    escapeCsv(g.playCount ?? ""),
    escapeCsv(g.lastPlayed || ""),
    escapeCsv(g.isActive ? "YES" : "NO"),
    escapeCsv(g.isDownloadable ? "YES" : "NO")
  ].join(","));

  fs.writeFileSync(path.join(__dirname, "psn-game-library.csv"), [csvHeaders.join(","), ...csvRows].join("\r\n"), "utf8");

  emit({
    step: 4,
    message: `Sync complete: ${normalized.length} titles fetched.`,
    percent: 100,
    completed: true,
    data: resultData
  });

  return resultData;
}

/* ==========================================================================
   SECTION 5: HTTP ROUTER, SSE STREAM DISPATCHER & ASSETS
   ========================================================================== */
function getClientIp(req) {
  return req.headers["x-forwarded-for"]?.split(",")[0]?.trim() || req.socket?.remoteAddress || "127.0.0.1";
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const clientIp = getClientIp(req);

  applySecurityHeaders(res);

  const origin = req.headers.origin;
  if (origin) {
    const host = req.headers.host;
    const allowed = [`http://${host}`, `https://${host}`, `http://localhost:${PORT}`, `http://127.0.0.1:${PORT}`];
    if (allowed.includes(origin)) {
      res.setHeader("Access-Control-Allow-Origin", origin);
    }
  }
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // API endpoints
  if (url.pathname === "/api/library" && req.method === "GET") {
    const jsonPath = path.join(__dirname, "psn-game-library.json");
    if (!fs.existsSync(jsonPath)) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "No cached library found. Run fetch first." }));
      return;
    }
    try {
      const data = fs.readFileSync(jsonPath, "utf8");
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(data);
    } catch {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Failed to read library cache." }));
    }
    return;
  }

  if (url.pathname === "/api/fetch-stream" && req.method === "POST") {
    if (!checkRateLimit(clientIp)) {
      res.writeHead(429, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Too many requests. Please wait a minute before retrying." }));
      return;
    }

    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 2048) {
        req.destroy();
      }
    });

    req.on("end", async () => {
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive"
      });

      const send = (data) => res.write(`data: ${JSON.stringify(data)}\n\n`);

      try {
        const parsed = JSON.parse(body || "{}");
        const token = sanitizeToken(parsed.npsso);

        if (!token) {
          send({ error: "NPSSO token is required." });
          res.end();
          return;
        }

        if (token.length !== 64 || !/^[A-Za-z0-9]{64}$/.test(token)) {
          send({ error: "Invalid NPSSO token. It must be exactly 64 alphanumeric characters." });
          res.end();
          return;
        }

        await runFetchPipeline(token, send);
        res.end();
      } catch (err) {
        let msg = err.message || "Failed to fetch PlayStation library.";
        const lower = msg.toLowerCase();
        if (lower.includes("timed out") || lower.includes("enotfound") || lower.includes("econnrefused")) {
          msg = "Connection timed out. Sony PlayStation servers could not be reached.";
        } else if (lower.includes("unauthorized") || lower.includes("401") || lower.includes("403") || lower.includes("npsso")) {
          msg = "Invalid or expired NPSSO token. Please verify your token and try again.";
        }
        send({ error: msg });
        res.end();
      }
    });
    return;
  }

  if (url.pathname === "/api/download/csv" && req.method === "GET") {
    const csvPath = path.join(__dirname, "psn-game-library.csv");
    if (fs.existsSync(csvPath)) {
      res.writeHead(200, {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="psn-game-library.csv"'
      });
      fs.createReadStream(csvPath).pipe(res);
      return;
    }
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("CSV not found.");
    return;
  }

  if (url.pathname === "/api/download/json" && req.method === "GET") {
    const jsonPath = path.join(__dirname, "psn-game-library.json");
    if (fs.existsSync(jsonPath)) {
      res.writeHead(200, {
        "Content-Type": "application/json",
        "Content-Disposition": 'attachment; filename="psn-game-library.json"'
      });
      fs.createReadStream(jsonPath).pipe(res);
      return;
    }
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("JSON not found.");
    return;
  }

  // Static files
  const cleanPath = path.normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, "");
  let filePath = path.join(PUBLIC_DIR, cleanPath === "/" ? "index.html" : cleanPath);

  if (!path.resolve(filePath).startsWith(path.resolve(PUBLIC_DIR))) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      "Content-Type": MIME_TYPES[ext] || "application/octet-stream",
      "Cache-Control": "no-cache"
    });
    fs.createReadStream(filePath).pipe(res);
  } else {
    const indexPath = path.join(PUBLIC_DIR, "index.html");
    if (fs.existsSync(indexPath)) {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      fs.createReadStream(indexPath).pipe(res);
    } else {
      res.writeHead(404);
      res.end("Not Found");
    }
  }
});

/* ==========================================================================
   SECTION 6: SERVER INITIALIZATION & LIFECYCLE
   ========================================================================== */
server.listen(PORT, "0.0.0.0", () => {
  console.log(`Server running at http://localhost:${PORT}`);
});

