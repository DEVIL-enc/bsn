/* ==========================================================================
   SECTION 1: APPLICATION STATE & DOM ELEMENT CACHE
   ========================================================================== */
const state = {
  library: null,
  activeTab: "ps4-owned",
  searchQuery: "",
  activeGame: null
};

const $ = (id) => document.getElementById(id);

const els = {
  app: $("minimalOledApp"),
  topRight: $("oledTopRight"),
  accountPreview: $("oledAccountPreview"),
  onlineId: $("oledAccountOnlineId"),
  tierBadge: $("oledAccountTierBadge"),
  btnLogout: $("btnOledLogout"),
  btnOpenInfo: $("btnOpenInfo"),
  infoModal: $("infoModal"),
  btnInfoModalClose: $("btnInfoModalClose"),

  controlSection: $("oledControlSection"),
  tokenInput: $("oledTokenInput"),
  btnTogglePass: $("btnOledTogglePass"),
  btnFetch: $("btnOledFetch"),
  btnHowTo: $("btnOledHowToReceive"),
  tutorialDrawer: $("oledTutorialDrawer"),

  btnToggleLogs: $("btnOledToggleLogs"),
  logsDrawer: $("oledLogsDrawer"),
  logsBadge: $("oledLogsStatusBadge"),
  logsEta: $("oledLogsEtaText"),
  progressBar: $("oledProgressBar"),
  logsStream: $("oledLogsStream"),

  gamesSection: $("oledGamesSection"),
  tabsNav: $("oledTabsNav"),
  searchContainer: $("oledSearchContainer"),
  gameSearch: $("oledGameSearch"),

  tabPsPlus: $("tabOledPsPlus"),
  panePsPlus: $("paneOledPsPlus"),
  psPlusTier: $("oledPsPlusTier"),
  psPlusStatus: $("oledPsPlusStatus"),
  psPlusCount: $("oledPsPlusCount"),
  psPlusAccount: $("oledPsPlusAccount"),
  psPlusPerks: $("oledPsPlusPerks"),
  psPlusStatusTag: $("oledPsPlusStatusTag"),

  counts: {
    "ps4-owned": $("oledCountPs4Owned"),
    "ps5-owned": $("oledCountPs5Owned"),
    "ps4-plus": $("oledCountPs4Plus"),
    "ps5-plus": $("oledCountPs5Plus")
  },
  panes: {
    "psplus": $("paneOledPsPlus"),
    "ps4-owned": $("paneOledPs4Owned"),
    "ps5-owned": $("paneOledPs5Owned"),
    "ps4-plus": $("paneOledPs4Plus"),
    "ps5-plus": $("paneOledPs5Plus")
  },
  lists: {
    "ps4-owned": $("listPs4Owned"),
    "ps5-owned": $("listPs5Owned"),
    "ps4-plus": $("listPs4Plus"),
    "ps5-plus": $("listPs5Plus")
  },

  footer: document.querySelector(".oled-footer"),
  btnOpenCopySimple: $("btnOpenCopySimple"),

  detailModal: $("gameDetailModal"),
  btnModalClose: $("btnModalClose"),
  modalCover: $("modalCoverImg"),
  modalPlatform: $("modalPlatformBadge"),
  modalLicense: $("modalLicenseBadge"),
  modalTitle: $("modalGameTitle"),
  modalTitleId: $("modalTitleId"),
  modalEntitlement: $("modalEntitlementId"),
  modalPlaytime: $("modalPlaytime"),
  modalPlayCount: $("modalPlayCount"),
  modalLastPlayed: $("modalLastPlayed"),
  modalDownloadable: $("modalDownloadable"),
  modalStoreLink: $("modalStoreLink"),
  btnCopyDetails: $("btnCopyDetails"),

  copyModal: $("copySimpleModal"),
  btnCopyModalClose: $("btnCopyModalClose"),
  btnCopyWithPlus: $("btnCopyWithPlus"),
  btnCopyWithoutPlus: $("btnCopyWithoutPlus"),
  copyWithPlusMeta: $("copyWithPlusMeta"),
  copyWithoutPlusMeta: $("copyWithoutPlusMeta"),

  toast: $("toastNotification"),
  preloader: $("sitePreloader")
};

/* ==========================================================================
   SECTION 2: SANITIZATION & ARTWORK FALLBACK UTILITIES
   ========================================================================== */
function showToast(text, duration = 3000) {
  if (!els.toast) return;
  els.toast.textContent = text;
  els.toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => els.toast.classList.add("hidden"), duration);
}

function sanitizeUrl(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "data:" ? url : "";
  } catch {
    return "";
  }
}

function getArtworkFallback(title, platform) {
  const initials = (title || "PS")
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0] || "")
    .join("")
    .toUpperCase() || "PS";
  return `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300"><rect width="300" height="300" fill="%23111111"/><text x="150" y="145" font-family="sans-serif" font-size="34" font-weight="700" fill="white" text-anchor="middle">${encodeURIComponent(initials)}</text><text x="150" y="210" font-family="sans-serif" font-size="16" font-weight="700" fill="%23888888" text-anchor="middle">${encodeURIComponent(platform)}</text></svg>`;
}

function extractToken(raw) {
  let val = (raw || "").trim().replace(/^["']|["']$/g, "").trim();
  if (val.startsWith("{") && val.includes("npsso")) {
    try {
      const parsed = JSON.parse(val);
      if (parsed.npsso) val = parsed.npsso.trim();
    } catch {
      const match = val.match(/"npsso"\s*:\s*"([^"]+)"/);
      if (match) val = match[1].trim();
    }
  }
  return val;
}

function setViewMode(isLoggedIn) {
  if (isLoggedIn) {
    localStorage.setItem("psn_session_active", "true");
    els.app?.classList.remove("is-centered");
    els.controlSection?.classList.add("hidden");
    els.gamesSection?.classList.remove("hidden");
    els.accountPreview?.classList.remove("hidden");
    els.btnLogout?.classList.remove("hidden");
    els.footer?.classList.remove("hidden");
  } else {
    localStorage.removeItem("psn_session_active");
    els.app?.classList.add("is-centered");
    els.controlSection?.classList.remove("hidden");
    els.gamesSection?.classList.add("hidden");
    els.accountPreview?.classList.add("hidden");
    els.btnLogout?.classList.add("hidden");
    els.footer?.classList.add("hidden");
    if (els.tokenInput) els.tokenInput.value = "";
  }
}

/* ==========================================================================
   SECTION 3: ACCORDION DRAWERS & PROGRESS FEEDBACK
   ========================================================================== */
function toggleDrawer(drawer, button) {
  if (!drawer || !button) return;
  const isOpen = drawer.classList.toggle("open");
  const chevron = button.querySelector(".oled-chevron");
  if (chevron) chevron.classList.toggle("open", isOpen);
  button.setAttribute("aria-expanded", String(isOpen));
}

function logError(message, badgeText = "ERROR") {
  if (els.logsDrawer && !els.logsDrawer.classList.contains("open")) {
    toggleDrawer(els.logsDrawer, els.btnToggleLogs);
  }
  if (els.logsBadge) {
    els.logsBadge.textContent = badgeText.toUpperCase();
    els.logsBadge.className = "oled-mini-badge badge-error";
  }
  if (els.logsEta) {
    els.logsEta.textContent = badgeText.toLowerCase();
    els.logsEta.style.color = "#ef4444";
  }
  if (els.progressBar) {
    els.progressBar.className = "oled-progress-bar bar-error";
    els.progressBar.style.width = "100%";
  }
  if (els.logsStream) {
    const row = document.createElement("div");
    row.className = "log-line log-line-error";
    row.textContent = `[ERROR] ${message}`;
    els.logsStream.appendChild(row);
    els.logsStream.scrollTop = els.logsStream.scrollHeight;
  }
  if (els.tokenInput) {
    els.tokenInput.classList.remove("input-error");
    void els.tokenInput.offsetWidth;
    els.tokenInput.classList.add("input-error");
    els.tokenInput.focus();
  }
  showToast(message);
}

/* ==========================================================================
   SECTION 4: GAME LIST RENDERING & SQUASH-PROOF ROW CREATION
   ========================================================================== */
function filterList(games, query) {
  if (!query) return games;
  const q = query.toLowerCase();
  return games.filter(
    (g) =>
      g.name.toLowerCase().includes(q) ||
      g.titleId.toLowerCase().includes(q) ||
      g.entitlementId.toLowerCase().includes(q)
  );
}

function renderGameList(container, list) {
  if (!container) return;
  container.innerHTML = "";

  if (!list.length) {
    const empty = document.createElement("div");
    empty.className = "oled-empty-msg font-mono";
    empty.style.cssText = "padding: 12px; color: #555555; font-size: 0.78rem;";
    empty.textContent = "No matching titles found.";
    container.appendChild(empty);
    return;
  }

  for (const g of list) {
    const fallback = getArtworkFallback(g.name, g.platform);
    const coverUrl = sanitizeUrl(g.imageUrl) || fallback;

    const item = document.createElement("div");
    item.className = "oled-game-item";
    item.addEventListener("click", () => {
      item.classList.add("item-tapped");
      setTimeout(() => {
        item.classList.remove("item-tapped");
        inspectGame(g.titleId);
      }, 90);
    });

    const img = document.createElement("img");
    img.src = coverUrl;
    img.alt = g.name || "Game";
    img.className = "oled-game-icon";
    img.loading = "lazy";
    img.onerror = () => {
      img.onerror = null;
      img.src = fallback;
    };

    const main = document.createElement("div");
    main.className = "oled-game-main";

    const nameEl = document.createElement("div");
    nameEl.className = "oled-game-name";
    nameEl.title = g.name;
    nameEl.textContent = g.name;

    const subEl = document.createElement("div");
    subEl.className = "oled-game-sub font-mono";
    subEl.textContent = `${g.titleId || g.platform} • ${g.platform}`;

    main.append(nameEl, subEl);
    item.append(img, main);

    if (g.playtime) {
      const badge = document.createElement("span");
      badge.className = "oled-game-playtime";
      badge.textContent = g.playtime;
      item.appendChild(badge);
    }

    container.appendChild(item);
  }
}

/* ==========================================================================
   SECTION 5: TAB NAVIGATION & STATS DASHBOARD
   ========================================================================== */
function switchTab(tabKey) {
  state.activeTab = tabKey;

  document.querySelectorAll(".oled-tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.oledTab === tabKey);
  });

  Object.entries(els.panes).forEach(([key, pane]) => {
    if (pane) pane.classList.toggle("hidden", key !== tabKey);
  });

  if (els.searchContainer) {
    els.searchContainer.style.display = tabKey === "psplus" ? "none" : "block";
  }

  if (els.gameSearch) {
    const placeholders = {
      "ps4-owned": "filter PS4 owned titles...",
      "ps5-owned": "filter PS5 owned titles...",
      "ps4-plus": "filter PS4 PS+ titles...",
      "ps5-plus": "filter PS5 PS+ titles..."
    };
    els.gameSearch.placeholder = placeholders[tabKey] || "filter games...";
  }

  renderCurrentTab();
}

function renderCurrentTab() {
  if (!state.library?.games) return;
  const { games } = state.library;
  const q = (els.gameSearch?.value || state.searchQuery || "").trim();

  const groups = {
    "ps4-owned": games.filter((g) => !g.isPsPlus && g.platform === "PS4"),
    "ps5-owned": games.filter((g) => !g.isPsPlus && g.platform === "PS5"),
    "ps4-plus": games.filter((g) => g.isPsPlus && g.platform === "PS4"),
    "ps5-plus": games.filter((g) => g.isPsPlus && g.platform === "PS5")
  };

  if (groups[state.activeTab] && els.lists[state.activeTab]) {
    renderGameList(els.lists[state.activeTab], filterList(groups[state.activeTab], q));
  }
}

function renderDashboard() {
  if (!state.library) return;
  const { account, games } = state.library;

  if (els.onlineId) els.onlineId.textContent = (account.onlineId || "PLAYSTATION USER").toUpperCase();
  if (els.tierBadge) els.tierBadge.textContent = account.isPlusActive ? "PS PLUS" : "NO PLUS";

  if (els.psPlusTier) els.psPlusTier.textContent = account.isPlusActive ? "PlayStation Plus" : "No Active Membership";
  if (els.psPlusStatus) els.psPlusStatus.textContent = account.isPlusActive ? "Active" : "Inactive";
  if (els.psPlusCount) {
    const plusCount = games.filter((g) => g.isPsPlus).length;
    els.psPlusCount.textContent = `${plusCount} Titles`;
  }
  if (els.psPlusAccount) els.psPlusAccount.textContent = account.onlineId || "Unknown";
  if (els.psPlusPerks) {
    els.psPlusPerks.textContent = account.psPlusDescription || "Monthly Games, Online Multiplayer & Cloud Storage";
  }
  if (els.psPlusStatusTag) {
    els.psPlusStatusTag.textContent = account.isPlusActive ? "ACTIVE" : "INACTIVE";
    els.psPlusStatusTag.className = `oled-status-tag ${account.isPlusActive ? "status-active" : "status-inactive"}`;
  }

  const counts = {
    "ps4-owned": games.filter((g) => !g.isPsPlus && g.platform === "PS4").length,
    "ps5-owned": games.filter((g) => !g.isPsPlus && g.platform === "PS5").length,
    "ps4-plus": games.filter((g) => g.isPsPlus && g.platform === "PS4").length,
    "ps5-plus": games.filter((g) => g.isPsPlus && g.platform === "PS5").length
  };

  Object.entries(counts).forEach(([k, count]) => {
    if (els.counts[k]) els.counts[k].textContent = count;
  });

  switchTab(state.activeTab);
}

/* ==========================================================================
   SECTION 6: MODAL SYSTEM (INSPECTOR, EXPORT, ABOUT & FAQ)
   ========================================================================== */
function inspectGame(titleId) {
  const game = state.library?.games?.find((g) => g.titleId === titleId);
  if (!game) return;

  state.activeGame = game;

  const fallback = getArtworkFallback(game.name, game.platform);
  els.modalCover.src = sanitizeUrl(game.imageUrl) || fallback;
  els.modalCover.onerror = () => {
    els.modalCover.src = fallback;
  };

  els.modalTitle.textContent = game.name;
  els.modalPlatform.textContent = game.platform;
  els.modalPlatform.className = `ps-platform-tag ${game.platform === "PS5" ? "tag-ps5" : "tag-ps4"}`;

  els.modalLicense.textContent = game.isPsPlus ? "PLAYSTATION PLUS CLAIM" : "OWNED DIGITAL PURCHASE";
  els.modalLicense.className = `ps-license-tag ${game.isPsPlus ? "license-plus" : "license-owned"}`;

  els.modalTitleId.textContent = game.titleId || "N/A";
  els.modalEntitlement.textContent = game.entitlementId || "N/A";
  els.modalPlaytime.textContent = game.playtime ? `${game.playtime} (${game.playCount || 1} sessions)` : "Not recorded";
  els.modalPlayCount.textContent = game.playCount ? `${game.playCount} launches` : "—";
  els.modalLastPlayed.textContent = game.lastPlayed || "Never";
  els.modalDownloadable.textContent = game.isDownloadable ? "Active Entitlement" : "Inactive";

  const storeBase = "https://store.playstation.com/en-us";
  els.modalStoreLink.href = game.productId
    ? `${storeBase}/product/${encodeURIComponent(game.productId)}`
    : `${storeBase}/search/${encodeURIComponent(game.name)}`;

  els.detailModal?.classList.remove("hidden");
}

function closeModal(modal) {
  if (!modal || modal.classList.contains("hidden")) return;
  modal.classList.add("is-closing");
  setTimeout(() => {
    modal.classList.remove("is-closing");
    modal.classList.add("hidden");
  }, 200);
}

function generateSimpleList(withPlus) {
  if (!state.library?.games) return { text: "", count: 0 };
  const pool = withPlus ? state.library.games : state.library.games.filter((g) => !g.isPsPlus);

  const ps4 = [];
  const ps5 = [];
  const other = [];

  for (const g of pool) {
    const title = (g.name || "").trim();
    if (!title) continue;
    const plat = (g.platform || "PS4").trim().toUpperCase();
    if (plat === "PS4") ps4.push(title);
    else if (plat === "PS5") ps5.push(title);
    else other.push(title);
  }

  const sortAlphabetical = (arr) => [...new Set(arr)].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  const sortedPs4 = sortAlphabetical(ps4);
  const sortedPs5 = sortAlphabetical(ps5);
  const sortedOther = sortAlphabetical(other);

  const sections = [];
  if (sortedPs4.length) sections.push(["PS4", ...sortedPs4].join("\n"));
  if (sortedPs5.length) sections.push(["PS5", ...sortedPs5].join("\n"));
  if (sortedOther.length) sections.push(["OTHER", ...sortedOther].join("\n"));

  return {
    text: sections.join("\n\n"),
    count: sortedPs4.length + sortedPs5.length + sortedOther.length
  };
}

async function copySimpleList(withPlus) {
  const { text, count } = generateSimpleList(withPlus);
  if (!count) {
    showToast("No games found to copy.");
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }

  showToast(`Copied ${count} titles (${withPlus ? "with PS+" : "owned only"}) to clipboard!`);
  closeModal(els.copyModal);
}

/* ==========================================================================
   SECTION 7: REAL-TIME SSE STREAM LISTENER
   ========================================================================== */
async function startSync(rawToken) {
  const token = extractToken(rawToken);

  if (!token) {
    logError("Please enter your 64-character PlayStation NPSSO token.", "token empty");
    return;
  }
  if (token.length !== 64 || !/^[A-Za-z0-9]{64}$/.test(token)) {
    logError("Invalid token format: NPSSO token must be 64 alphanumeric characters.", "wrong token");
    return;
  }

  if (els.logsBadge) {
    els.logsBadge.className = "oled-mini-badge";
    els.logsBadge.textContent = "CONNECTING";
  }
  if (els.logsEta) {
    els.logsEta.style.color = "";
    els.logsEta.textContent = "starting...";
  }
  if (els.progressBar) {
    els.progressBar.className = "oled-progress-bar";
    els.progressBar.style.width = "5%";
  }
  els.tokenInput?.classList.remove("input-error");

  if (els.logsDrawer && !els.logsDrawer.classList.contains("open")) {
    toggleDrawer(els.logsDrawer, els.btnToggleLogs);
  }
  if (els.logsStream) {
    els.logsStream.innerHTML = '<div class="log-line">[START] Connecting to PlayStation Network...</div>';
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);

  try {
    const res = await fetch("/api/fetch-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ npsso: token }),
      signal: controller.signal
    });

    if (!res.ok) {
      clearTimeout(timer);
      const json = await res.json().catch(() => ({}));
      throw new Error(json.error || `Server responded with ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      clearTimeout(timer);
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop();

      for (const chunk of chunks) {
        if (!chunk.startsWith("data: ")) continue;
        const text = chunk.slice(6).trim();
        if (!text) continue;

        const data = JSON.parse(text);
        if (data.error) throw new Error(data.error);

        if (els.progressBar && data.percent !== undefined) {
          els.progressBar.style.width = `${data.percent}%`;
        }
        if (els.logsBadge) {
          els.logsBadge.textContent = `${data.percent || 0}%`;
        }
        if (els.logsEta && data.etaText) {
          els.logsEta.textContent = data.etaText;
        }
        if (els.logsStream && data.message) {
          const row = document.createElement("div");
          row.className = "log-line";
          row.textContent = `[STEP ${data.step || 1}] ${data.message}`;
          els.logsStream.appendChild(row);
          els.logsStream.scrollTop = els.logsStream.scrollHeight;
        }

        if (data.completed && data.data) {
          state.library = data.data;
          showToast("PlayStation library synced successfully!");

          if (els.logsBadge) {
            els.logsBadge.textContent = "SYNCED";
            els.logsBadge.className = "oled-mini-badge badge-success";
          }
          if (els.logsEta) {
            els.logsEta.textContent = "complete";
            els.logsEta.style.color = "#22c55e";
          }
          if (els.progressBar) {
            els.progressBar.style.width = "100%";
          }

          setTimeout(() => {
            setViewMode(true);
            renderDashboard();
          }, 350);
        }
      }
    }
  } catch (err) {
    clearTimeout(timer);
    const msg = err.name === "AbortError"
      ? "Connection timed out. Sony PlayStation servers could not be reached."
      : err.message || "Failed to fetch library.";
    logError(msg);
  }
}

/* ==========================================================================
   SECTION 8: EVENT LISTENERS & LIFECYCLE HYDRATION
   ========================================================================== */
function bindEvents() {
  els.btnHowTo?.addEventListener("click", () => toggleDrawer(els.tutorialDrawer, els.btnHowTo));
  els.btnToggleLogs?.addEventListener("click", () => toggleDrawer(els.logsDrawer, els.btnToggleLogs));

  els.btnTogglePass?.addEventListener("click", () => {
    if (!els.tokenInput) return;
    els.tokenInput.type = els.tokenInput.type === "password" ? "text" : "password";
  });

  els.btnFetch?.addEventListener("click", () => startSync(els.tokenInput?.value));
  els.tokenInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") startSync(els.tokenInput?.value);
  });

  els.btnLogout?.addEventListener("click", () => {
    setViewMode(false);
    showToast("Logged out.");
  });

  els.tabsNav?.addEventListener("click", (e) => {
    const btn = e.target.closest(".oled-tab-btn");
    if (btn?.dataset.oledTab) switchTab(btn.dataset.oledTab);
  });

  els.gameSearch?.addEventListener("input", (e) => {
    state.searchQuery = e.target.value;
    renderCurrentTab();
  });

  els.btnOpenCopySimple?.addEventListener("click", () => {
    if (!state.library?.games?.length) {
      showToast("Please fetch your library first.");
      return;
    }
    const withPlus = state.library.games.length;
    const withoutPlus = state.library.games.filter((g) => !g.isPsPlus).length;
    if (els.copyWithPlusMeta) els.copyWithPlusMeta.textContent = `${withPlus} titles (includes ${withPlus - withoutPlus} PS+ claims)`;
    if (els.copyWithoutPlusMeta) els.copyWithoutPlusMeta.textContent = `${withoutPlus} owned purchases only`;
    els.copyModal?.classList.remove("hidden");
  });

  els.btnCopyWithPlus?.addEventListener("click", () => copySimpleList(true));
  els.btnCopyWithoutPlus?.addEventListener("click", () => copySimpleList(false));

  els.btnCopyDetails?.addEventListener("click", () => {
    if (!state.activeGame) return;
    const g = state.activeGame;
    const text = `${g.name} [${g.platform}]\nTitle ID: ${g.titleId || "N/A"}\nLicense: ${g.isPsPlus ? "PlayStation Plus" : "Owned"}\nPlaytime: ${g.playtime || "N/A"}`;
    navigator.clipboard.writeText(text).then(() => showToast("Copied specs to clipboard!"));
  });

  els.btnModalClose?.addEventListener("click", () => closeModal(els.detailModal));
  els.detailModal?.addEventListener("click", (e) => {
    if (e.target === els.detailModal) closeModal(els.detailModal);
  });

  els.btnCopyModalClose?.addEventListener("click", () => closeModal(els.copyModal));
  els.copyModal?.addEventListener("click", (e) => {
    if (e.target === els.copyModal) closeModal(els.copyModal);
  });

  els.btnOpenInfo?.addEventListener("click", () => {
    els.infoModal?.classList.remove("hidden");
  });
  els.btnInfoModalClose?.addEventListener("click", () => closeModal(els.infoModal));
  els.infoModal?.addEventListener("click", (e) => {
    if (e.target === els.infoModal) closeModal(els.infoModal);
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeModal(els.detailModal);
      closeModal(els.copyModal);
      closeModal(els.infoModal);
    }
  });
}

async function init() {
  bindEvents();

  try {
    const res = await fetch("/api/library");
    if (res.ok) {
      state.library = await res.json();
      renderDashboard();
      setViewMode(localStorage.getItem("psn_session_active") === "true");
    } else {
      setViewMode(false);
    }
  } catch {
    setViewMode(false);
  }

  if (els.preloader) {
    setTimeout(() => {
      els.preloader.classList.add("fade-out");
      setTimeout(() => els.preloader.remove(), 500);
    }, 300);
  }
}

document.addEventListener("DOMContentLoaded", init);
