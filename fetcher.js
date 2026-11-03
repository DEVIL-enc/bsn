import readline from "node:readline";
import { stdin as input, stdout as output } from "node:process";
import fs from "node:fs";
import {
  exchangeNpssoForAccessCode,
  exchangeCodeForAccessToken,
  getProfileFromAccountId,
  getPurchasedGames,
  getUserPlayedGames
} from "psn-api";

const rl = readline.createInterface({ input, output });
const prompt = (query) => new Promise((resolve) => rl.question(query, resolve));

function renderProgressBar(current, total, label = "Fetching games") {
  const width = 30;
  if (total > 0) {
    const pct = Math.min(1, current / total);
    const filled = Math.round(width * pct);
    const bar = "█".repeat(filled) + "░".repeat(width - filled);
    const pctText = `${Math.round(pct * 100)}%`.padStart(4);
    output.write(`\r[${bar}] ${pctText} | ${label} (${current}/${total})`);
  } else {
    const frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
    const frame = frames[current % frames.length];
    const filled = Math.min(width, Math.max(1, current % (width + 1)));
    const bar = "█".repeat(filled) + "░".repeat(width - filled);
    output.write(`\r${frame} [${bar}] | ${label} (${current} retrieved)`);
  }
}

function clearLine() {
  output.write("\r" + " ".repeat(85) + "\r");
}

function parseDuration(isoDuration) {
  if (!isoDuration || typeof isoDuration !== "string") return null;
  const match = isoDuration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?/);
  if (!match) return null;
  const hours = Number(match[1] || 0);
  const minutes = Number(match[2] || 0);
  const total = (hours + minutes / 60).toFixed(1);
  return total > 0 ? `${total}h` : "<1h";
}

function normalizeToken(raw) {
  let token = (raw || "").trim().replace(/^["']|["']$/g, "").trim();
  if (token.startsWith("{") && token.includes("npsso")) {
    try {
      const parsed = JSON.parse(token);
      if (parsed.npsso) return parsed.npsso.trim();
    } catch {}
    const match = token.match(/"npsso"\s*:\s*"([^"]+)"/);
    if (match) return match[1].trim();
  }
  return token;
}

function printGameTable(title, games) {
  console.log(`\n--- ${title} (${games.length} titles) ---`);
  if (!games.length) {
    console.log("  (None found)");
    return;
  }
  games.forEach((g, idx) => {
    const num = String(idx + 1).padStart(3, " ");
    const plat = `[${g.platform}]`.padEnd(7, " ");
    const playInfo = g.playtime ? `| Playtime: ${g.playtime}` : "";
    const titleIdInfo = g.titleId ? `(${g.titleId})` : "";
    console.log(` ${num}. ${plat} ${g.name} ${titleIdInfo} ${playInfo}`);
  });
}

function escapeCsv(val) {
  if (val === null || val === undefined) return "";
  const str = String(val);
  return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
}

async function main() {
  console.log("PSN Game Fetcher CLI v2.0\n");

  const args = process.argv.slice(2);
  let npsso = "";

  const tokenIdx = args.findIndex((a) => a === "--token" || a === "-t");
  if (tokenIdx !== -1 && args[tokenIdx + 1]) {
    npsso = args[tokenIdx + 1];
  } else if (process.env.NPSSO) {
    npsso = process.env.NPSSO;
  } else {
    npsso = await prompt("Enter your NPSSO token: ");
  }

  npsso = normalizeToken(npsso);
  rl.close();

  if (!npsso) {
    console.error("Error: No NPSSO token provided.");
    process.exitCode = 1;
    return;
  }

  try {
    console.log("Authenticating with PlayStation Network...");
    renderProgressBar(1, 4, "Exchanging NPSSO for access code");
    const accessCode = await exchangeNpssoForAccessCode(npsso);

    renderProgressBar(2, 4, "Exchanging code for OAuth tokens");
    const auth = await exchangeCodeForAccessToken(accessCode);

    let accountId = null;
    try {
      const payload = JSON.parse(Buffer.from(auth.accessToken.split(".")[1], "base64").toString());
      accountId = payload.account_id || payload.sub;
    } catch {}

    renderProgressBar(3, 4, "Fetching profile details");
    let profile = null;
    if (accountId) {
      try {
        profile = await getProfileFromAccountId(auth, accountId);
      } catch {}
    }

    renderProgressBar(4, 4, "Authentication complete");
    clearLine();

    const onlineId = profile?.onlineId || accountId || "PlayStation User";
    const realName = profile?.personalDetail
      ? `${profile.personalDetail.firstName || ""} ${profile.personalDetail.lastName || ""}`.trim()
      : "";
    const isPlus = profile?.isPlus === true;

    console.log("\nAccount Details:");
    console.log(`  Online ID : ${onlineId}`);
    if (realName) console.log(`  Name      : ${realName}`);
    console.log(`  PS Plus   : ${isPlus ? "Active" : "Inactive"}\n`);

    console.log("Fetching recent activity & playtime...");
    const playtimeMap = new Map();
    if (accountId) {
      try {
        let offset = 0;
        const limit = 100;
        let count = 0;
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
          count += titles.length;
          renderProgressBar(count, 0, "Scanning played activity");
          if (titles.length < limit) break;
          offset += limit;
        }
        clearLine();
        console.log(`Loaded activity for ${playtimeMap.size} titles.`);
      } catch {
        clearLine();
        console.log("Playtime data unavailable or private; skipping.");
      }
    }

    console.log("\nFetching digital purchases & entitlements...");
    let allRawGames = [];
    let start = 0;
    const chunkSize = 100;

    while (true) {
      renderProgressBar(allRawGames.length, 0, "Querying catalog");
      const res = await getPurchasedGames(auth, { size: chunkSize, start });
      const games = res?.data?.purchasedTitlesRetrieve?.games || [];
      if (!games.length) break;

      allRawGames = allRawGames.concat(games);
      renderProgressBar(allRawGames.length, 0, "Querying catalog");

      if (games.length < chunkSize) break;
      start += chunkSize;
    }
    clearLine();
    console.log(`Retrieved ${allRawGames.length} titles from catalog.`);

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

    printGameTable("OWNED PURCHASES — PS5", ownedPS5);
    printGameTable("OWNED PURCHASES — PS4", ownedPS4);
    if (ownedOther.length) printGameTable("OWNED PURCHASES — OTHER", ownedOther);

    printGameTable("PS PLUS ENTITLEMENTS — PS5", plusPS5);
    printGameTable("PS PLUS ENTITLEMENTS — PS4", plusPS4);
    if (plusOther.length) printGameTable("PS PLUS ENTITLEMENTS — OTHER", plusOther);

    const totalOwned = ownedPS5.length + ownedPS4.length + ownedOther.length;
    const totalPlus = plusPS5.length + plusPS4.length + plusOther.length;

    console.log("\nSummary:");
    console.log(`  Total titles       : ${normalized.length}`);
    console.log(`  Owned purchases    : ${totalOwned} (PS5: ${ownedPS5.length}, PS4: ${ownedPS4.length})`);
    console.log(`  PS Plus claims     : ${totalPlus} (PS5: ${plusPS5.length}, PS4: ${plusPS4.length})\n`);

    const jsonOutput = {
      fetchedAt: new Date().toISOString(),
      account: {
        onlineId,
        realName,
        isPlusActive: isPlus,
        psPlusTier: isPlus ? "PS_PLUS" : "None",
        psPlusTierLabel: isPlus ? "PlayStation Plus" : "No Active Subscription",
        psPlusTierBadge: isPlus ? "PS PLUS" : "Inactive"
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

    fs.writeFileSync("psn-game-library.json", JSON.stringify(jsonOutput, null, 2), "utf8");
    console.log("Saved JSON to psn-game-library.json");

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

    fs.writeFileSync("psn-game-library.csv", [csvHeaders.join(","), ...csvRows].join("\r\n"), "utf8");
    console.log("Saved CSV to psn-game-library.csv");
  } catch (error) {
    clearLine();
    console.error("\nFetch failed:", error?.message || error);
    console.error("Tip: Check that your NPSSO token is valid and not expired.");
    process.exitCode = 1;
  }
}

main();
