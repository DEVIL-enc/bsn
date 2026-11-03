# basex_bot.py  —  Python 3.11+ | python-telegram-bot 20.x
# pip install python-telegram-bot requests beautifulsoup4 aiofiles aiohttp
# BOT_TOKEN=xxx ADMIN_IDS=123,456 python basex_bot.py
# ─────────────────────────────────────────────────────────────────────────────
# v7.0 ULTRA — New Features:
#   ✅ Combo Deduplicator  — حذف التكرارات قبل الفحص
#   ✅ Combo Splitter      — تقسيم الملف الكبير إلى أجزاء
#   ✅ Proxy Tester        — اختبار البروكسيات قبل الفحص
#   ✅ Rich Hit Results    — نتائج مفصّلة لكل module
#       · Hotmail : inbox count, services found
#       · Xbox    : gamertag, gamerscore, gold/ultimate, games list
#       · PSN     : PSN ID, level, PS+, wallet
#       · Roblox  : username, Robux, premium, RAP
#       · Steam   : balance, games count, VAC status, level
#       · Fortnite: skins count, V-Bucks, battle pass, wins
# ─────────────────────────────────────────────────────────────────────────────

import os, sys, asyncio, logging, tempfile, time, json, zipfile, secrets, csv
from pathlib import Path
from datetime import datetime, timedelta
from io import BytesIO, StringIO

import aiofiles
import aiohttp

from telegram import (
    Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton,
    InputFile, ChatMember,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest, TelegramError

try:
    from basex_checker_gui import (
        load_combos, load_proxies, pick_proxy, make_writer,
        sanitize_filename, Writer, flag,
        run_hotmail_bg, run_xbox_bg, run_psn_bg,
        run_roblox_bg, run_steam_bg, run_fortnite_bg,
    )
except ImportError:
    sys.exit("❌  basex_checker_gui.py must be in the same directory")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
TOKEN        = os.environ.get("BOT_TOKEN", "7149909490:AAFQAEJgqDyOvRfX1T7boO-qYCWAGAsxAsg")
ADMIN_IDS    = [int(x) for x in os.environ.get("ADMIN_IDS", "1707478010").split(",") if x.strip().isdigit()]
SUPPORT      = "@BASE_XE"
CHANNEL_ID   = "@givewayess1"
CHANNEL_URL  = "https://t.me/givewayess1"
SUBS_FILE    = "subscriptions.json"
CODES_FILE   = "redeem_codes.json"
BANNED_FILE  = "banned_users.json"
BOT_VERSION  = "v7.0 ULTRA"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s │ %(levelname)s │ %(message)s")
log = logging.getLogger("basex")

_maintenance: bool = False

# ══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION STORE
# ══════════════════════════════════════════════════════════════════════════════
_subs_cache: dict = {}
_subs_lock: asyncio.Lock | None = None

def _get_lock() -> asyncio.Lock:
    global _subs_lock
    if _subs_lock is None:
        _subs_lock = asyncio.Lock()
    return _subs_lock

async def _init_subs():
    global _subs_cache, _subs_lock
    _subs_lock = asyncio.Lock()
    if os.path.exists(SUBS_FILE):
        try:
            async with aiofiles.open(SUBS_FILE) as f:
                raw = await f.read()
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                _subs_cache = parsed
        except Exception as exc:
            log.warning(f"_init_subs: {exc}")

async def _flush_subs():
    async with _get_lock():
        snapshot = dict(_subs_cache)
    async with aiofiles.open(SUBS_FILE, "w") as f:
        await f.write(json.dumps(snapshot, indent=2))

def get_sub(uid: int) -> dict | None:
    e = _subs_cache.get(str(uid))
    if not e:
        return None
    try:
        alive = datetime.fromisoformat(e["expires"]) > datetime.utcnow()
    except (ValueError, KeyError):
        return None
    return e if alive else None

async def add_sub(uid: int, plan_id: str, uname: str = "") -> dict:
    if plan_id not in PLANS:
        raise ValueError(f"Unknown plan_id: {plan_id!r}")
    p   = PLANS[plan_id]
    exp = datetime.utcnow() + timedelta(days=p["days"])
    e   = {
        "plan": plan_id, "label": p["label"], "badge": p["badge"],
        "expires": exp.isoformat(), "modules": list(p["modules"]),
        "threads_max": p["threads_max"], "username": uname,
        "activated": datetime.utcnow().isoformat(),
    }
    async with _get_lock():
        _subs_cache[str(uid)] = e
    await _flush_subs()
    return e

async def revoke_sub(uid: int):
    async with _get_lock():
        _subs_cache.pop(str(uid), None)
    await _flush_subs()

def days_left(e: dict) -> int:
    return max(0, (datetime.fromisoformat(e["expires"]) - datetime.utcnow()).days)

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

# ══════════════════════════════════════════════════════════════════════════════
# BANNED USERS
# ══════════════════════════════════════════════════════════════════════════════
_banned: set[int] = set()
_banned_lock: asyncio.Lock | None = None

def _get_banned_lock() -> asyncio.Lock:
    global _banned_lock
    if _banned_lock is None:
        _banned_lock = asyncio.Lock()
    return _banned_lock

async def _load_banned():
    global _banned
    if os.path.exists(BANNED_FILE):
        try:
            async with aiofiles.open(BANNED_FILE) as f:
                raw = await f.read()
            _banned = set(json.loads(raw))
        except Exception as exc:
            log.warning(f"_load_banned: {exc}")

async def _flush_banned():
    async with aiofiles.open(BANNED_FILE, "w") as f:
        await f.write(json.dumps(list(_banned)))

async def ban_user(uid: int):
    async with _get_banned_lock():
        _banned.add(uid)
    await _flush_banned()

async def unban_user(uid: int):
    async with _get_banned_lock():
        _banned.discard(uid)
    await _flush_banned()

def is_banned(uid: int) -> bool:
    return uid in _banned

# ══════════════════════════════════════════════════════════════════════════════
# REDEEM CODES
# ══════════════════════════════════════════════════════════════════════════════
_codes: dict = {}
_codes_lock: asyncio.Lock | None = None

def _get_codes_lock() -> asyncio.Lock:
    global _codes_lock
    if _codes_lock is None:
        _codes_lock = asyncio.Lock()
    return _codes_lock

async def _load_codes():
    global _codes
    if os.path.exists(CODES_FILE):
        try:
            async with aiofiles.open(CODES_FILE) as f:
                raw = await f.read()
            _codes = json.loads(raw)
        except Exception as exc:
            log.warning(f"_load_codes: {exc}")

async def _flush_codes():
    async with aiofiles.open(CODES_FILE, "w") as f:
        await f.write(json.dumps(_codes, indent=2))

async def create_code(plan_id: str, uses: int = 1) -> str:
    code = secrets.token_urlsafe(8).upper()
    async with _get_codes_lock():
        _codes[code] = {
            "plan": plan_id, "uses_left": uses,
            "used_by": [], "created": datetime.utcnow().isoformat()
        }
    await _flush_codes()
    return code

async def use_code(code: str, uid: int) -> dict | None:
    async with _get_codes_lock():
        c = _codes.get(code.upper())
        if not c or c["uses_left"] <= 0:
            return None
        if uid in c["used_by"]:
            return None
        c["uses_left"] -= 1
        c["used_by"].append(uid)
    await _flush_codes()
    return PLANS.get(c["plan"])

# ══════════════════════════════════════════════════════════════════════════════
# PLANS / MODULES
# ══════════════════════════════════════════════════════════════════════════════
PLANS = {
    "trial":    {"label":"Trial",    "days":1,     "modules":["hotmail"],                                          "threads_max":20,  "price":"Free",   "badge":"🆓"},
    "starter":  {"label":"Starter",  "days":30,    "modules":["hotmail","steam"],                                  "threads_max":50,  "price":"$9.99",  "badge":"⚡"},
    "pro":      {"label":"Pro",      "days":30,    "modules":["hotmail","xbox","steam","roblox"],                  "threads_max":150, "price":"$19.99", "badge":"💎"},
    "elite":    {"label":"Elite",    "days":30,    "modules":["hotmail","xbox","steam","roblox","psn","fortnite"], "threads_max":300, "price":"$34.99", "badge":"👑"},
    "lifetime": {"label":"Lifetime", "days":36500, "modules":["hotmail","xbox","steam","roblox","psn","fortnite"], "threads_max":500, "price":"$99.99", "badge":"♾️"},
}

MODULES = {
    "hotmail":  {"icon":"✉️",  "label":"Hotmail",  "runner": run_hotmail_bg},
    "xbox":     {"icon":"🎮",  "label":"Xbox",     "runner": run_xbox_bg},
    "psn":      {"icon":"🎯",  "label":"PSN",      "runner": run_psn_bg},
    "roblox":   {"icon":"🧩",  "label":"Roblox",   "runner": run_roblox_bg},
    "steam":    {"icon":"🖥️",  "label":"Steam",    "runner": run_steam_bg},
    "fortnite": {"icon":"⚡",  "label":"Fortnite", "runner": run_fortnite_bg},
}

# ══════════════════════════════════════════════════════════════════════════════
# HIT RESULT FORMATTERS  —  نتائج الفحص المفصّلة لكل module
# ══════════════════════════════════════════════════════════════════════════════
def _esc(s: str) -> str:
    for ch in r"\_*[]()~`>#+-=|{}.!":
        s = s.replace(ch, f"\\{ch}")
    return s

def _mask_email(email: str) -> str:
    """
    إخفاء الإيميل بشكل احترافي:
    abc@hotmail.com  →  a**@hotmail.com
    johnsmith@gmail.com  →  jo******@gmail.com
    """
    try:
        local, domain = email.rsplit("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "*"
        elif len(local) <= 4:
            masked_local = local[0] + "*" * (len(local) - 1)
        else:
            visible = max(2, len(local) // 4)
            masked_local = local[:visible] + "*" * (len(local) - visible)
        return f"{masked_local}@{domain}"
    except Exception:
        return "***@***.***"

def _mask_pass(password: str) -> str:
    """إخفاء كلمة المرور بالكامل بنجوم."""
    if not password:
        return "••••••••"
    length = len(password)
    if length <= 4:
        return "•" * length
    return "•" * length

def format_hit_hotmail(email: str, info: str) -> str:
    """
    info format (pipe-separated, all optional):
    inbox:42|services:Netflix,PayPal,Amazon|recovery:yes|country:US|pass:secret
    """
    parts    = dict(p.split(":", 1) for p in info.split("|") if ":" in p)
    inbox    = parts.get("inbox", "?")
    services = parts.get("services", "")
    recovery = parts.get("recovery", "")
    country  = parts.get("country", "")

    masked   = _mask_email(email)
    svc_line = f"\n│  📦 Services: `{_esc(services)}`" if services else ""
    rec_line = f"\n│  🔑 Recovery:  `{_esc(recovery)}`" if recovery else ""
    ctr_line = f"\n│  🌍 Country:   `{_esc(country)}`"  if country  else ""

    return (
        f"✅ *HIT ✦ Hotmail*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"│  📧 `{_esc(masked)}`\n"
        f"│  📥 Inbox: `{_esc(inbox)}` emails"
        f"{svc_line}{rec_line}{ctr_line}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 BaseX Checker {_esc(BOT_VERSION)}"
    )

def format_hit_xbox(email: str, info: str) -> str:
    """
    info: tag:CoolGamer|score:45000|sub:Xbox Game Pass Ultimate|games:Halo,COD,Forza|level:Gold
    """
    parts  = dict(p.split(":", 1) for p in info.split("|") if ":" in p)
    tag    = parts.get("tag", "Unknown")
    score  = parts.get("score", "?")
    sub    = parts.get("sub", "None")
    games  = parts.get("games", "")
    level  = parts.get("level", "")

    masked   = _mask_email(email)
    sub_icon = "♾️" if "Ultimate" in sub else ("🥇" if "Gold" in sub else ("🎮" if "Core" in sub else "🆓"))
    games_line = f"\n│  🕹  Games: `{_esc(games)}`"    if games else ""
    lvl_line   = f"\n│  🏆 Level: `{_esc(level)}`"     if level else ""

    return (
        f"✅ *HIT ✦ Xbox*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"│  📧 `{_esc(masked)}`\n"
        f"│  🎯 Gamertag: `{_esc(tag)}`\n"
        f"│  🎮 GamerScore: `{_esc(score)}`\n"
        f"│  {sub_icon} Sub: `{_esc(sub)}`"
        f"{games_line}{lvl_line}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 BaseX Checker {_esc(BOT_VERSION)}"
    )

def format_hit_psn(email: str, info: str) -> str:
    """
    info: psn:ProGamer99|level:250|sub:PS Plus Extra|wallet:$15.50|trophies:gold:5,silver:20
    """
    parts    = dict(p.split(":", 1) for p in info.split("|") if ":" in p)
    psn_id   = parts.get("psn", "Unknown")
    level    = parts.get("level", "?")
    sub      = parts.get("sub", "None")
    wallet   = parts.get("wallet", "")
    trophies = parts.get("trophies", "")

    masked      = _mask_email(email)
    sub_icon    = "🟡" if "Extra" in sub else ("🔵" if "Essential" in sub else ("🟣" if "Deluxe" in sub else "🆓"))
    wallet_line = f"\n│  💰 Wallet: `{_esc(wallet)}`"      if wallet   else ""
    troph_line  = f"\n│  🏆 Trophies: `{_esc(trophies)}`" if trophies else ""

    return (
        f"✅ *HIT ✦ PSN*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"│  📧 `{_esc(masked)}`\n"
        f"│  🎯 PSN ID: `{_esc(psn_id)}`\n"
        f"│  ⭐ Level: `{_esc(level)}`\n"
        f"│  {sub_icon} Sub: `{_esc(sub)}`"
        f"{wallet_line}{troph_line}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 BaseX Checker {_esc(BOT_VERSION)}"
    )

def format_hit_roblox(email: str, info: str) -> str:
    """
    info: user:CoolDude|robux:5000|premium:yes|rap:12000|badges:150
    """
    parts   = dict(p.split(":", 1) for p in info.split("|") if ":" in p)
    user    = parts.get("user", "Unknown")
    robux   = parts.get("robux", "0")
    premium = parts.get("premium", "no")
    rap     = parts.get("rap", "")
    badges  = parts.get("badges", "")

    masked     = _mask_email(email)
    prem_icon  = "⭐ Premium" if premium.lower() == "yes" else "🆓 Free"
    rap_line   = f"\n│  📈 RAP: `{_esc(rap)}`"       if rap    else ""
    badge_line = f"\n│  🏅 Badges: `{_esc(badges)}`" if badges else ""

    return (
        f"✅ *HIT ✦ Roblox*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"│  📧 `{_esc(masked)}`\n"
        f"│  👤 User: `{_esc(user)}`\n"
        f"│  💎 Robux: `{_esc(robux)}`\n"
        f"│  {prem_icon}"
        f"{rap_line}{badge_line}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 BaseX Checker {_esc(BOT_VERSION)}"
    )

def format_hit_steam(email: str, info: str) -> str:
    """
    info: balance:$24.50|games:320|level:75|vac:clean|country:US|hours:4500
    """
    parts   = dict(p.split(":", 1) for p in info.split("|") if ":" in p)
    balance = parts.get("balance", "$0")
    games   = parts.get("games", "?")
    level   = parts.get("level", "?")
    vac     = parts.get("vac", "?")
    country = parts.get("country", "")
    hours   = parts.get("hours", "")

    masked       = _mask_email(email)
    vac_icon     = "✅ Clean" if vac.lower() == "clean" else "⛔ VAC Ban"
    hours_line   = f"\n│  ⏱ Hours: `{_esc(hours)}`"      if hours   else ""
    country_line = f"\n│  🌍 Country: `{_esc(country)}`"  if country else ""

    return (
        f"✅ *HIT ✦ Steam*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"│  📧 `{_esc(masked)}`\n"
        f"│  💰 Balance: `{_esc(balance)}`\n"
        f"│  🎮 Games: `{_esc(games)}`\n"
        f"│  ⭐ Level: `{_esc(level)}`\n"
        f"│  🛡 VAC: {vac_icon}"
        f"{hours_line}{country_line}\n"
        f"└──────────────────────"
    )

def format_hit_fortnite(email: str, info: str) -> str:
    """
    info: skins:145|vbucks:2800|bp:yes|wins:320|level:210|rare:Renegade Raider,Black Knight
    """
    parts = dict(p.split(":", 1) for p in info.split("|") if ":" in p)
    skins  = parts.get("skins", "?")
    vbucks = parts.get("vbucks", "0")
    bp     = parts.get("bp", "no")
    wins   = parts.get("wins", "")
    level  = parts.get("level", "")
    rare   = parts.get("rare", "")

    bp_icon    = "🎫 Battle Pass" if bp.lower() == "yes" else "🆓 No BP"
    wins_line  = f"\n│  🏆 Wins: `{_esc(wins)}`"          if wins  else ""
    level_line = f"\n│  ⭐ Level: `{_esc(level)}`"         if level else ""
    rare_line  = f"\n│  💎 Rare: `{_esc(rare)}`"           if rare  else ""

    return (
        f"✅ *HIT — Fortnite*\n"
        f"┌ 📧 `{_esc(email)}`\n"
        f"│  👗 Skins: `{_esc(skins)}`\n"
        f"│  💎 V\\-Bucks: `{_esc(vbucks)}`\n"
        f"│  {bp_icon}"
        f"{wins_line}{level_line}{rare_line}\n"
        f"└──────────────────────"
    )

HIT_FORMATTERS = {
    "hotmail":  format_hit_hotmail,
    "xbox":     format_hit_xbox,
    "psn":      format_hit_psn,
    "roblox":   format_hit_roblox,
    "steam":    format_hit_steam,
    "fortnite": format_hit_fortnite,
}

def format_hit(module: str, email: str, info: str) -> str:
    formatter = HIT_FORMATTERS.get(module)
    if formatter:
        try:
            return formatter(email, info)
        except Exception as e:
            log.warning(f"format_hit({module}): {e}")
    return f"✅ *HIT*\n`{_esc(email)}`\n`{_esc(info)}`"

def format_2fa(email: str, module: str) -> str:
    icons = {"xbox":"🎮","psn":"🎯","steam":"🖥️","fortnite":"⚡","roblox":"🧩","hotmail":"✉️"}
    return (
        f"🔒 *2FA — {icons.get(module,'')} {_esc(module.title())}*\n"
        f"┌ 📧 `{_esc(email)}`\n"
        f"└ 🔐 Two\\-Factor Authentication enabled"
    )

# ══════════════════════════════════════════════════════════════════════════════
# PROXY TESTER
# ══════════════════════════════════════════════════════════════════════════════
TEST_URL     = "https://www.google.com"
PROXY_TIMEOUT = 8  # seconds

def _parse_proxy(line: str) -> str | None:
    """Convert proxy line to aiohttp-compatible URL string."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("http://") or line.startswith("https://") or line.startswith("socks5://"):
        return line
    parts = line.split(":")
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    if len(parts) == 4:
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return None

async def _test_one_proxy(session: aiohttp.ClientSession, proxy_url: str) -> tuple[str, float | None]:
    """Returns (proxy_url, latency_ms) or (proxy_url, None) on failure."""
    try:
        t0 = time.monotonic()
        async with session.get(TEST_URL, proxy=proxy_url,
                                timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT)) as resp:
            if resp.status < 400:
                return proxy_url, round((time.monotonic() - t0) * 1000, 1)
    except Exception:
        pass
    return proxy_url, None

async def test_proxies(proxy_file: str,
                       progress_cb=None,
                       concurrency: int = 50) -> tuple[list[str], list[str]]:
    """
    Test all proxies in file concurrently.
    Returns (alive_lines, dead_lines).
    progress_cb(done, total) called periodically.
    """
    with open(proxy_file, errors="ignore") as f:
        raw_lines = [l.strip() for l in f if l.strip()]

    parsed = [(line, _parse_proxy(line)) for line in raw_lines]
    valid  = [(orig, url) for orig, url in parsed if url]

    alive, dead = [], []
    sem   = asyncio.Semaphore(concurrency)
    total = len(valid)
    done  = [0]

    async def check_one(orig: str, url: str):
        async with sem:
            _, latency = await _test_one_proxy(session, url)
            if latency is not None:
                alive.append(orig)
            else:
                dead.append(orig)
            done[0] += 1
            if progress_cb and done[0] % 10 == 0:
                await progress_cb(done[0], total)

    connector = aiohttp.TCPConnector(ssl=False, limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        await asyncio.gather(*[check_one(o, u) for o, u in valid])

    return alive, dead

# ══════════════════════════════════════════════════════════════════════════════
# COMBO TOOLS
# ══════════════════════════════════════════════════════════════════════════════
def dedup_combo(input_path: str) -> tuple[str, int, int]:
    """
    Remove duplicate lines (case-insensitive on email part).
    Returns (output_path, original_count, unique_count).
    """
    seen   = set()
    unique = []
    total  = 0
    with open(input_path, errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            key = line.split(":")[0].lower() if ":" in line else line.lower()
            if key not in seen:
                seen.add(key)
                unique.append(line)

    out = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", prefix="dedup_", mode="w")
    out.write("\n".join(unique))
    out.close()
    return out.name, total, len(unique)

def split_combo(input_path: str, parts: int) -> list[str]:
    """
    Split combo file into N roughly equal parts.
    Returns list of temp file paths.
    """
    with open(input_path, errors="ignore") as f:
        lines = [l.strip() for l in f if l.strip()]

    chunk_size = max(1, len(lines) // parts + (1 if len(lines) % parts else 0))
    out_paths  = []

    for i in range(0, len(lines), chunk_size):
        chunk = lines[i:i + chunk_size]
        tmp   = tempfile.NamedTemporaryFile(delete=False, suffix=".txt",
                                             prefix=f"split_{i//chunk_size+1}_", mode="w")
        tmp.write("\n".join(chunk))
        tmp.close()
        out_paths.append(tmp.name)

    return out_paths

# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATION STATES
# ══════════════════════════════════════════════════════════════════════════════
(
    IDLE,
    AWAIT_COMBOS,
    AWAIT_PROXY,
    AWAIT_KW,
    RUNNING,
    ADMIN_GRANT,
    ADMIN_REVOKE,
    ADMIN_BAN,
    ADMIN_UNBAN,
    ADMIN_CODE_GEN,
    ADMIN_BROADCAST,
    AWAIT_REDEEM,
    AWAIT_SPLIT_PARTS,
    AWAIT_DEDUP_FILE,
    AWAIT_PROXY_TEST,
) = range(15)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION
# ══════════════════════════════════════════════════════════════════════════════
def sess(ud: dict) -> dict:
    ud.setdefault("module", None)
    ud.setdefault("combo_path", None)
    ud.setdefault("proxy_path", None)
    ud.setdefault("keywords", ["Steam","Netflix","PayPal","Amazon","Xbox"])
    ud.setdefault("threads", 50)
    ud.setdefault("stats", {})
    ud.setdefault("total", 0)
    ud.setdefault("results_dir", None)
    ud.setdefault("running", False)
    ud.setdefault("cancel", False)
    ud.setdefault("_last_stat_text", "")
    ud.setdefault("_broadcast_mode", None)
    ud.setdefault("_broadcast_target", "all")
    ud.setdefault("_pending_split_path", None)
    ud.setdefault("_pending_dedup_path", None)
    ud.setdefault("_pending_proxy_path", None)
    return ud

# ══════════════════════════════════════════════════════════════════════════════
# CHANNEL CHECK
# ══════════════════════════════════════════════════════════════════════════════
async def is_subscribed(bot: Bot, uid: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL_ID, uid)
        return m.status not in (ChatMember.LEFT, ChatMember.KICKED, ChatMember.BANNED)
    except Exception:
        return True

# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════
FOOTER = f"⚙️ {SUPPORT}  │  📢 {CHANNEL_URL}"
PM2    = ParseMode.MARKDOWN_V2

def pbar(done: int, total: int, w: int = 16) -> str:
    p   = done / total if total else 0
    fil = int(p * w)
    return f"{'█'*fil}{'░'*(w-fil)} {int(p*100):>3}%"

def home_text(sub: dict | None, uname: str) -> str:
    if sub:
        dl   = days_left(sub)
        mods = " ".join(MODULES[m]["icon"] for m in sub["modules"] if m in MODULES)
        bar  = pbar(PLANS[sub["plan"]]["days"] - dl, PLANS[sub["plan"]]["days"], 14)
        acct = (
            f"*{_esc(sub['badge'])} {_esc(sub['label'])}*\n"
            f"📅 Expires in *{dl} days*\n"
            f"🧵 Up to *{sub['threads_max']}* threads\n"
            f"📦 Modules: {mods}\n"
            f"`{bar}`"
        )
    else:
        acct = "⚠️ *No active subscription*\nClaim a free trial or view plans below\\."
    return (
        f"*BaseX Checker {_esc(BOT_VERSION)}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Welcome, *{_esc(uname)}*\n\n"
        f"{acct}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{_esc(FOOTER)}"
    )

def stat_text(stats: dict, total: int, label: str, module: str) -> str:
    done  = stats.get("done", 0)
    inbox = f"📥 Inbox  `{stats.get('inbox',0):,}`\n" if module == "hotmail" else ""
    return (
        f"*{_esc(label)}* — running\n"
        f"`{pbar(done, total)}`\n\n"
        f"✅ Hits    `{stats.get('hit',0):>6,}`\n"
        f"🔒 2FA     `{stats.get('2fa',0):>6,}`\n"
        f"❌ Bad     `{stats.get('bad',0):>6,}`\n"
        f"⚠️ Error   `{stats.get('err',0):>6,}`\n"
        f"{inbox}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 `{done:,}` / `{total:,}`  "
        f"🚀 `{stats.get('speed',0):,}` /min"
    )

def sub_card_text(sub: dict, uid: int) -> str:
    dl  = days_left(sub)
    exp = datetime.fromisoformat(sub["expires"]).strftime("%d %b %Y")
    act = datetime.fromisoformat(sub["activated"]).strftime("%d %b %Y")
    bar = pbar(PLANS[sub["plan"]]["days"] - dl, PLANS[sub["plan"]]["days"], 14)
    mods = "\n".join(
        f"{'✅' if m in sub['modules'] else '🔒'} {MODULES[m]['icon']} {_esc(MODULES[m]['label'])}"
        for m in MODULES
    )
    return (
        f"*{sub['badge']} {_esc(sub['label'])}* — 🟢 Active\n"
        f"📅 `{act}` → `{exp}` \\({dl} days left\\)\n"
        f"🧵 Up to *{sub['threads_max']}* threads\n"
        f"`{bar}`\n\n"
        f"*Modules:*\n{mods}"
    )

# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════
def kb_home(sub: dict | None) -> InlineKeyboardMarkup:
    rows = []
    if sub:
        allowed = sub["modules"]
        row = []
        for mid, m in MODULES.items():
            locked = mid not in allowed
            label  = f"{'🔒' if locked else m['icon']} {m['label']}"
            row.append(InlineKeyboardButton(label, callback_data=f"mod:{mid}"))
            if len(row) == 2: rows.append(row); row = []
        if row: rows.append(row)
        rows += [[
            InlineKeyboardButton("📋 My Sub",   callback_data="my_sub"),
            InlineKeyboardButton("📦 Plans",    callback_data="view_plans"),
            InlineKeyboardButton("🎟 Redeem",   callback_data="redeem"),
        ]]
    else:
        rows += [
            [InlineKeyboardButton("💎 View Plans",  callback_data="view_plans"),
             InlineKeyboardButton("🎟 Redeem Code", callback_data="redeem")],
            [InlineKeyboardButton("🎁 Claim Trial", callback_data="claim_trial")],
        ]
    rows.append([
        InlineKeyboardButton("🔧 Tools",    callback_data="tools_menu"),
        InlineKeyboardButton("📖 Help",     callback_data="help"),
        InlineKeyboardButton("📢 Channel",  url=CHANNEL_URL),
    ])
    return InlineKeyboardMarkup(rows)

def kb_tools() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Deduplicator",   callback_data="tool_dedup"),
         InlineKeyboardButton("✂️ Splitter",        callback_data="tool_split")],
        [InlineKeyboardButton("🌐 Proxy Tester",   callback_data="tool_proxy_test")],
        [InlineKeyboardButton("← Home",            callback_data="back_home")],
    ])

def kb_plans() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{p['badge']} {p['label']}  ·  {p['price']}",
                              callback_data=f"plan_info:{pid}")]
        for pid, p in PLANS.items() if pid != "trial"
    ]
    rows.append([InlineKeyboardButton("← Back", callback_data="back_home")])
    return InlineKeyboardMarkup(rows)

def kb_plan_info(pid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"💳 Purchase — Contact {SUPPORT}",
                             url=f"https://t.me/{SUPPORT.lstrip('@')}")
    ],[InlineKeyboardButton("← Plans", callback_data="view_plans")]])

def kb_threads(current: int, max_t: int) -> InlineKeyboardMarkup:
    opts = [t for t in [10, 25, 50, 100, 150, 200, 300, 500] if t <= max_t]
    rows, row = [], []
    for t in opts:
        mark = "✓ " if t == current else ""
        row.append(InlineKeyboardButton(f"{mark}{t}t", callback_data=f"threads:{t}"))
        if len(row) == 4: rows.append(row); row = []
    if row: rows.append(row)
    rows.append([
        InlineKeyboardButton("▶ Start Check", callback_data="start_check"),
        InlineKeyboardButton("✗ Cancel",      callback_data="back_home"),
    ])
    return InlineKeyboardMarkup(rows)

def kb_split_sizes() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("2 Parts",  callback_data="split:2"),
         InlineKeyboardButton("3 Parts",  callback_data="split:3"),
         InlineKeyboardButton("4 Parts",  callback_data="split:4")],
        [InlineKeyboardButton("5 Parts",  callback_data="split:5"),
         InlineKeyboardButton("10 Parts", callback_data="split:10"),
         InlineKeyboardButton("20 Parts", callback_data="split:20")],
        [InlineKeyboardButton("← Tools",  callback_data="tools_menu")],
    ])

def kb_cancel()    -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("■ Stop", callback_data="cancel_run")]])
def kb_back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Home", callback_data="back_home")]])
def kb_back_tools() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Tools", callback_data="tools_menu")]])
def kb_sub_dash()  -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="my_sub"),
         InlineKeyboardButton("📦 Plans",   callback_data="view_plans")],
        [InlineKeyboardButton(f"⚙️ Support {SUPPORT}",
                              url=f"https://t.me/{SUPPORT.lstrip('@')}")],
        [InlineKeyboardButton("← Home", callback_data="back_home")],
    ])
def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Grant",      callback_data="admin_grant"),
         InlineKeyboardButton("➖ Revoke",     callback_data="admin_revoke")],
        [InlineKeyboardButton("🎟 Gen Code",  callback_data="admin_code_gen"),
         InlineKeyboardButton("📋 Codes",     callback_data="admin_code_list")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
         InlineKeyboardButton("👥 List Subs", callback_data="admin_list")],
        [InlineKeyboardButton("🚫 Ban",       callback_data="admin_ban"),
         InlineKeyboardButton("✅ Unban",     callback_data="admin_unban")],
        [InlineKeyboardButton("📊 Stats",     callback_data="admin_stats"),
         InlineKeyboardButton("📤 Export",    callback_data="admin_export")],
        [InlineKeyboardButton("🔧 Maintenance", callback_data="admin_maintenance"),
         InlineKeyboardButton("← Home",       callback_data="back_home")],
    ])
def kb_broadcast() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Text",     callback_data="bc_type:text"),
         InlineKeyboardButton("🖼 Photo",    callback_data="bc_type:photo"),
         InlineKeyboardButton("📎 Document", callback_data="bc_type:doc")],
        [InlineKeyboardButton("👥 All users",   callback_data="bc_target:all"),
         InlineKeyboardButton("✅ Active subs", callback_data="bc_target:active")],
        [InlineKeyboardButton("← Admin",    callback_data="admin_panel")],
    ])

# ══════════════════════════════════════════════════════════════════════════════
# CORE HELPERS
# ══════════════════════════════════════════════════════════════════════════════
async def safe_edit(query, text: str, reply_markup=None):
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=PM2)
    except BadRequest:
        await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=PM2)

async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    if is_banned(uid) and not is_admin(uid):
        if update.message:
            await update.message.reply_text("🚫 *You have been banned\\.*", parse_mode=PM2)
        elif update.callback_query:
            await update.callback_query.answer("🚫 You are banned!", show_alert=True)
        return False
    if _maintenance and not is_admin(uid):
        if update.message:
            await update.message.reply_text("🔧 *Maintenance mode\\. Try later\\.*", parse_mode=PM2)
        elif update.callback_query:
            await update.callback_query.answer("🔧 Maintenance!", show_alert=True)
        return False
    if is_admin(uid):
        return True
    if not await is_subscribed(context.bot, uid):
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)
        ],[
            InlineKeyboardButton("✅ I Joined", callback_data="check_sub")
        ]])
        txt = (
            "⛔ *Access Denied*\n\nJoin the channel first\\.\n\n"
            f"📢 {_esc(CHANNEL_URL)}"
        )
        if update.message:
            await update.message.reply_text(txt, reply_markup=kb, parse_mode=PM2)
        elif update.callback_query:
            await safe_edit(update.callback_query, txt, kb)
            await update.callback_query.answer()
        return False
    return True

async def send_home(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> int:
    uid   = update.effective_user.id
    sub   = get_sub(uid)
    uname = update.effective_user.first_name or update.effective_user.username or "User"
    text  = home_text(sub, uname)
    kb    = kb_home(sub)
    if edit and update.callback_query:
        await safe_edit(update.callback_query, text, kb)
    else:
        msg = update.message or update.callback_query.message
        await msg.reply_text(text, reply_markup=kb, parse_mode=PM2)
    return IDLE

async def zip_and_send(bot: Bot, uid: int, rdir: str):
    rp    = Path(rdir)
    files = [f for f in rp.rglob("*") if f.is_file() and f.stat().st_size > 0]
    if not files:
        await bot.send_message(uid, "📭 No results generated\\.", parse_mode=PM2)
        return
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f.relative_to(rp.parent))
    buf.seek(0)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    await bot.send_document(uid, InputFile(buf, filename=f"basex_{ts}.zip"),
                            caption="✅ *Results ready*", parse_mode=PM2)

# ══════════════════════════════════════════════════════════════════════════════
# BROADCAST ENGINE
# ══════════════════════════════════════════════════════════════════════════════
async def do_broadcast(bot: Bot, admin_id: int, text: str,
                       target: str = "all",
                       photo_id: str | None = None,
                       doc_id:   str | None = None):
    now  = datetime.utcnow()
    uids = []
    for uid_s, v in _subs_cache.items():
        try:
            uid = int(uid_s)
        except ValueError:
            continue
        if target == "active":
            if datetime.fromisoformat(v.get("expires","2000-01-01")) <= now:
                continue
        uids.append(uid)
    if not uids:
        await bot.send_message(admin_id, "📭 No users to broadcast to\\.", parse_mode=PM2)
        return
    sent = failed = 0
    status_msg = await bot.send_message(
        admin_id, f"📢 *Broadcasting to {len(uids)} users\\.\\.\\.*", parse_mode=PM2)
    for i, uid in enumerate(uids, 1):
        try:
            if photo_id:
                await bot.send_photo(uid, photo_id, caption=text, parse_mode=PM2)
            elif doc_id:
                await bot.send_document(uid, doc_id, caption=text, parse_mode=PM2)
            else:
                await bot.send_message(uid, text, parse_mode=PM2)
            sent += 1
        except (Forbidden, BadRequest):
            failed += 1
        except TelegramError as e:
            log.warning(f"Broadcast {uid}: {e}"); failed += 1
        await asyncio.sleep(0.05)
        if i % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"📢 Broadcasting\\.\\.\\. `{i}/{len(uids)}`", parse_mode=PM2)
            except BadRequest:
                pass
    await status_msg.edit_text(
        f"✅ *Broadcast Done*\n📤 Sent `{sent}` \\| ❌ Failed `{failed}`",
        parse_mode=PM2)

# ══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sess(context.user_data)["cancel"] = False
    if not await guard(update, context): return IDLE
    return await send_home(update, context)

async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(f"🆔 *Your ID:* `{uid}`", parse_mode=PM2)

async def cmd_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard(update, context): return IDLE
    if context.args:
        return await _do_redeem(update, context, context.args[0])
    await update.message.reply_text(
        "🎟 *Redeem a Code*\n\nSend your code:",
        reply_markup=kb_back_home(), parse_mode=PM2)
    return AWAIT_REDEEM

async def _do_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str) -> int:
    uid  = update.effective_user.id
    plan = await use_code(code, uid)
    msg  = update.effective_message
    if plan is None:
        await msg.reply_text(
            "❌ *Invalid or already used code\\.*", parse_mode=PM2)
        return AWAIT_REDEEM
    pid = next((k for k, v in PLANS.items() if v == plan), None)
    if not pid:
        await msg.reply_text("❌ Plan error\\.", parse_mode=PM2)
        return IDLE
    sub = await add_sub(uid, pid, update.effective_user.username or "")
    await msg.reply_text(
        f"🎉 *Code Redeemed\\!*\n\n{sub_card_text(sub, uid)}\n\n"
        "Use /start to begin\\.", parse_mode=PM2)
    return IDLE

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    if not ud.get("running"):
        await update.message.reply_text("ℹ️ No active check\\. Use /start\\.", parse_mode=PM2)
        return
    mid = ud.get("module", "")
    await update.message.reply_text(
        stat_text(ud.get("stats", {}), ud.get("total", 0),
                  MODULES.get(mid, {}).get("label", ""), mid), parse_mode=PM2)

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud = context.user_data
    ud["cancel"] = True; ud["running"] = False
    await update.message.reply_text("⛔ Check cancelled\\. /start again\\.", parse_mode=PM2)
    return IDLE

async def cmd_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _maintenance
    if not is_admin(update.effective_user.id): return
    _maintenance = not _maintenance
    state = "🔧 ON" if _maintenance else "✅ OFF"
    await update.message.reply_text(f"Maintenance: *{state}*", parse_mode=PM2)

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied\\."); return IDLE
    return await _show_admin_panel(update, context)

async def _show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    subs   = _subs_cache
    now    = datetime.utcnow()
    active = sum(1 for v in subs.values()
                 if datetime.fromisoformat(v.get("expires","2000-01-01")) > now)
    text = (
        f"*🔧 Admin Panel — BaseX {_esc(BOT_VERSION)}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total    `{len(subs)}`\n"
        f"🟢 Active   `{active}`\n"
        f"🔴 Expired  `{len(subs)-active}`\n"
        f"🚫 Banned   `{len(_banned)}`\n"
        f"🎟 Codes    `{len(_codes)}`\n"
        f"🔧 Maint    `{'ON' if _maintenance else 'OFF'}`\n\n"
        f"{_esc(FOOTER)}"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=kb_admin(), parse_mode=PM2)
    else:
        await safe_edit(update.callback_query, text, kb_admin())
    return IDLE

# ══════════════════════════════════════════════════════════════════════════════
# TOOLS MENU CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════
async def cb_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    await safe_edit(q,
        "🔧 *Combo \\& Proxy Tools*\n\n"
        "🗑 *Deduplicator* — حذف التكرارات من الكومبو\n"
        "✂️ *Splitter* — تقسيم الكومبو إلى أجزاء\n"
        "🌐 *Proxy Tester* — اختبار البروكسيات وحذف الميتة\n\n"
        "_أرسل الملف لأي أداة مباشرة_",
        kb_tools())
    return IDLE

async def cb_tool_dedup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    await safe_edit(q,
        "🗑 *Combo Deduplicator*\n\n"
        "📤 أرسل ملف الكومبو \\(\\.txt\\)\n"
        "سيتم حذف التكرارات وإرجاع الملف النظيف\\.",
        kb_back_tools())
    return AWAIT_DEDUP_FILE

async def recv_dedup_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard(update, context): return IDLE
    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ أرسل ملف \\.txt", parse_mode=PM2)
        return AWAIT_DEDUP_FILE

    msg = await update.message.reply_text("⏳ *جاري حذف التكرارات\\.\\.\\.*", parse_mode=PM2)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", prefix="in_dedup_")
    await (await context.bot.get_file(doc.file_id)).download_to_drive(tmp.name)

    try:
        out_path, total, unique = dedup_combo(tmp.name)
        removed = total - unique
        removed_pct = round(removed / total * 100, 1) if total else 0

        await msg.edit_text(
            f"✅ *Deduplicator Done*\n\n"
            f"📊 Total lines:    `{total:,}`\n"
            f"✅ Unique:          `{unique:,}`\n"
            f"🗑 Removed:         `{removed:,}` \\(`{removed_pct}%`\\)\n\n"
            f"📤 Sending clean file\\.",
            parse_mode=PM2
        )
        with open(out_path, "rb") as f:
            await context.bot.send_document(
                update.effective_user.id,
                InputFile(f, filename=f"clean_{doc.file_name or 'combo.txt'}"),
                caption=f"🗑 *Deduped* — `{unique:,}` unique lines",
                parse_mode=PM2,
                reply_markup=kb_tools()
            )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{_esc(str(e))}`", parse_mode=PM2)

    return IDLE

async def cb_tool_split(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    await safe_edit(q,
        "✂️ *Combo Splitter*\n\n"
        "📤 أرسل ملف الكومبو \\(\\.txt\\) أولاً:",
        kb_back_tools())
    return AWAIT_SPLIT_PARTS

async def recv_split_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives combo file, then asks how many parts."""
    if not await guard(update, context): return IDLE
    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ أرسل ملف \\.txt", parse_mode=PM2)
        return AWAIT_SPLIT_PARTS

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", prefix="in_split_")
    await (await context.bot.get_file(doc.file_id)).download_to_drive(tmp.name)
    count = sum(1 for _ in open(tmp.name, errors="ignore"))
    sess(context.user_data)["_pending_split_path"] = tmp.name

    await update.message.reply_text(
        f"✅ ملف محمّل — `{count:,}` سطر\n\n"
        f"✂️ كم جزء تريد؟",
        reply_markup=kb_split_sizes(),
        parse_mode=PM2
    )
    return AWAIT_SPLIT_PARTS

async def cb_do_split(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    ud = sess(context.user_data)
    path = ud.get("_pending_split_path")
    if not path or not os.path.exists(path):
        await q.answer("❌ No file! Send a combo file first.", show_alert=True)
        return AWAIT_SPLIT_PARTS

    parts = int(q.data.split(":", 1)[1])
    msg   = await q.message.reply_text(f"⏳ *Splitting into {parts} parts\\.\\.\\.*", parse_mode=PM2)

    try:
        out_paths = split_combo(path, parts)
        total = sum(sum(1 for _ in open(p, errors="ignore")) for p in out_paths)
        await msg.edit_text(
            f"✅ *Split Complete*\n\n"
            f"📊 Parts: `{len(out_paths)}`\n"
            f"📝 Total lines: `{total:,}`\n\n"
            f"📤 Sending files\\.",
            parse_mode=PM2
        )
        for i, p in enumerate(out_paths, 1):
            lines_in_part = sum(1 for _ in open(p, errors="ignore"))
            with open(p, "rb") as f:
                await context.bot.send_document(
                    update.effective_user.id,
                    InputFile(f, filename=f"part_{i:02d}_of_{len(out_paths)}.txt"),
                    caption=f"✂️ Part `{i}/{len(out_paths)}` — `{lines_in_part:,}` lines",
                    parse_mode=PM2
                )
            await asyncio.sleep(0.3)
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{_esc(str(e))}`", parse_mode=PM2)

    ud["_pending_split_path"] = None
    return IDLE

async def cb_tool_proxy_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    await safe_edit(q,
        "🌐 *Proxy Tester*\n\n"
        "📤 أرسل ملف البروكسيات \\(\\.txt\\)\n\n"
        "*Formats accepted:*\n"
        "`ip:port`\n"
        "`ip:port:user:pass`\n"
        "`http://ip:port`\n\n"
        "سيختبر كل بروكسي ويرجع قائمة الحية فقط\\.",
        kb_back_tools())
    return AWAIT_PROXY_TEST

async def recv_proxy_test_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard(update, context): return IDLE
    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ أرسل ملف \\.txt", parse_mode=PM2)
        return AWAIT_PROXY_TEST

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", prefix="ptest_")
    await (await context.bot.get_file(doc.file_id)).download_to_drive(tmp.name)
    total_count = sum(1 for _ in open(tmp.name, errors="ignore"))

    status_msg = await update.message.reply_text(
        f"🌐 *Testing {total_count:,} proxies\\.\\.\\.*\n"
        f"`{'░'*16}   0%`\n\n"
        f"⏳ Please wait\\.",
        parse_mode=PM2
    )

    uid  = update.effective_user.id
    loop = asyncio.get_event_loop()

    async def progress_cb(done: int, total: int):
        bar = pbar(done, total)
        try:
            await status_msg.edit_text(
                f"🌐 *Testing proxies\\.\\.\\.*\n"
                f"`{bar}`\n\n"
                f"✅ Alive so far: checking\\.\\.\\.",
                parse_mode=PM2
            )
        except BadRequest:
            pass

    try:
        alive, dead = await test_proxies(tmp.name, progress_cb=progress_cb)
        alive_pct = round(len(alive) / total_count * 100, 1) if total_count else 0

        await status_msg.edit_text(
            f"✅ *Proxy Test Complete*\n\n"
            f"📊 Total:   `{total_count:,}`\n"
            f"🟢 Alive:   `{len(alive):,}` \\(`{alive_pct}%`\\)\n"
            f"🔴 Dead:    `{len(dead):,}`\n\n"
            f"📤 Sending alive proxies\\.",
            parse_mode=PM2
        )

        if alive:
            buf = BytesIO("\n".join(alive).encode())
            ts  = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            await context.bot.send_document(
                uid,
                InputFile(buf, filename=f"alive_proxies_{ts}.txt"),
                caption=(
                    f"🌐 *Alive Proxies*\n"
                    f"✅ `{len(alive):,}` / `{total_count:,}` \\(`{alive_pct}%`\\)"
                ),
                parse_mode=PM2,
                reply_markup=kb_tools()
            )
        else:
            await context.bot.send_message(uid, "❌ *No alive proxies found\\.*", parse_mode=PM2)

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: `{_esc(str(e))}`", parse_mode=PM2)

    return IDLE

# ══════════════════════════════════════════════════════════════════════════════
# NAV CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════
async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if await is_subscribed(context.bot, update.effective_user.id):
        await q.answer("✅ Access granted!", show_alert=True)
        return await send_home(update, context, edit=True)
    await q.answer("⛔ You haven't joined yet!", show_alert=True)
    return IDLE

async def cb_back_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    return await send_home(update, context, edit=True)

async def cb_my_sub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    uid = update.effective_user.id; sub = get_sub(uid)
    if not sub:
        await safe_edit(q,
            "⚠️ *No active subscription\\.*\n\nPurchase a plan\\.\n\n"
            f"{_esc(FOOTER)}", kb_plans())
    else:
        await safe_edit(q,
            f"📋 *My Subscription*\n\n{sub_card_text(sub, uid)}\n\n{_esc(FOOTER)}",
            kb_sub_dash())
    return IDLE

async def cb_claim_trial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    uid = update.effective_user.id
    if get_sub(uid):
        await q.answer("✅ You already have an active subscription!", show_alert=True)
        return IDLE
    sub = await add_sub(uid, "trial", update.effective_user.username or "")
    await safe_edit(q,
        f"🎁 *Trial Activated\\!*\n\n{sub_card_text(sub, uid)}\n\n"
        "1\\-day trial: Hotmail Inbox only\\.\n\n"
        f"{_esc(FOOTER)}",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("▶ Start Checking", callback_data="mod:hotmail")],
            [InlineKeyboardButton("💎 Upgrade Plan",  callback_data="view_plans")],
            [InlineKeyboardButton("← Home",           callback_data="back_home")],
        ]))
    return IDLE

async def cb_view_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    blocks = []
    for pid, p in PLANS.items():
        if pid == "trial": continue
        mods = " ".join(MODULES[m]["icon"] for m in p["modules"] if m in MODULES)
        blocks.append(
            f"*{p['badge']} {_esc(p['label'])}* — `{p['price']}`\n"
            f"  ├ `{p['days']}d`  ·  up to `{p['threads_max']}` threads\n"
            f"  └ {mods}"
        )
    await safe_edit(q,
        f"💎 *Available Plans*\n\n" + "\n\n".join(blocks)
        + f"\n\n━━━━━━━━━━━━━━━━━━━━\nContact {_esc(SUPPORT)}\\.\n{_esc(FOOTER)}",
        kb_plans())
    return IDLE

async def cb_plan_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    pid = q.data.split(":", 1)[1]; p = PLANS.get(pid)
    if not p: await q.answer("Plan not found.", show_alert=True); return IDLE
    mods_list = "\n".join(
        f"{'✅' if m in p['modules'] else '🔒'} {MODULES[m]['icon']} {_esc(MODULES[m]['label'])}"
        for m in MODULES
    )
    await safe_edit(q,
        f"*{p['badge']} {_esc(p['label'])}*\n"
        f"💰 `{p['price']}`  ·  📅 `{p['days']} days`  ·  🧵 up to `{p['threads_max']}`\n\n"
        f"*Module Access:*\n{mods_list}\n\n"
        f"Contact {_esc(SUPPORT)}\\.\n{_esc(FOOTER)}",
        kb_plan_info(pid))
    return IDLE

async def cb_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    await safe_edit(q, "🎟 *Redeem a Code*\n\nSend your code:", kb_back_home())
    return AWAIT_REDEEM

async def recv_redeem_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard(update, context): return IDLE
    return await _do_redeem(update, context, update.message.text.strip())

async def cb_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    await safe_edit(q,
        "📖 *BaseX Checker — Help*\n\n"
        "*Commands*\n"
        "`/start`       → Home menu\n"
        "`/status`      → Live progress\n"
        "`/cancel`      → Stop run\n"
        "`/redeem CODE` → Redeem a code\n"
        "`/myid`        → Your Telegram ID\n"
        "`/admin`       → Admin panel\n\n"
        "*Flow*\n"
        "1\\. Select module\n"
        "2\\. Upload combo \\(`email:pass`\\)\n"
        "3\\. Upload proxies or skip\n"
        "4\\. Keywords \\(Hotmail only\\)\n"
        "5\\. Pick threads → Start\n"
        "6\\. Live stats \\+ zip archive\n\n"
        "*Tools*\n"
        "🗑 Deduplicator — remove duplicates\n"
        "✂️ Splitter — split combo to parts\n"
        "🌐 Proxy Tester — test \\& filter proxies\n\n"
        f"{_esc(FOOTER)}",
        kb_back_home())
    return IDLE

# ══════════════════════════════════════════════════════════════════════════════
# MODULE / COMBO / PROXY / KW / THREADS
# ══════════════════════════════════════════════════════════════════════════════
async def cb_module(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    uid = update.effective_user.id; sub = get_sub(uid)
    if not sub:
        await q.answer("❌ No active subscription!", show_alert=True); return IDLE
    mid = q.data.split(":", 1)[1]
    if mid not in sub["modules"]:
        await q.answer("🔒 This module requires a higher plan.", show_alert=True); return IDLE
    ud = sess(context.user_data)
    ud["module"] = mid; ud["combo_path"] = None; ud["proxy_path"] = None
    m = MODULES[mid]
    await safe_edit(q,
        f"{m['icon']} *{_esc(m['label'])}*\n\n"
        "*Step 1 — Combo File*\n"
        "Format: `email:password` one per line\n\n"
        "📤 Upload \\.txt or send local path\n\n"
        f"{_esc(FOOTER)}",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Dedup First", callback_data="tool_dedup")],
            [InlineKeyboardButton("✗ Cancel",       callback_data="back_home")],
        ]))
    return AWAIT_COMBOS

async def _combo_received(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          path: str, fname: str, size_kb: int, count: int) -> int:
    ud = sess(context.user_data); ud["combo_path"] = path
    await update.effective_message.reply_text(
        f"✅ *Combo received* — `{count:,}` lines \\(`{size_kb} KB`\\)\n\n"
        "*Step 2 — Proxy File*\n"
        "Upload proxies or skip\\.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Test Proxies First", callback_data="tool_proxy_test")],
            [InlineKeyboardButton("⚡ Skip — No Proxies",  callback_data="skip_proxy")],
            [InlineKeyboardButton("✗ Cancel",               callback_data="back_home")],
        ]),
        parse_mode=PM2,
    )
    return AWAIT_PROXY

async def recv_combos_doc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard(update, context): return IDLE
    doc = update.message.document
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", prefix="combos_")
    await (await context.bot.get_file(doc.file_id)).download_to_drive(tmp.name)
    count = sum(1 for _ in open(tmp.name, errors="ignore"))
    return await _combo_received(update, context, tmp.name,
                                 doc.file_name or "combo.txt",
                                 (doc.file_size or 0) // 1024, count)

async def recv_combos_path(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard(update, context): return IDLE
    p = update.message.text.strip()
    if not os.path.exists(p):
        await update.message.reply_text("❌ File not found\\. Upload the \\.txt\\.", parse_mode=PM2)
        return AWAIT_COMBOS
    count = sum(1 for _ in open(p, errors="ignore"))
    return await _combo_received(update, context, p, os.path.basename(p),
                                 os.path.getsize(p) // 1024, count)

async def recv_proxy_doc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard(update, context): return IDLE
    ud = sess(context.user_data); doc = update.message.document
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", prefix="proxies_")
    await (await context.bot.get_file(doc.file_id)).download_to_drive(tmp.name)
    count = sum(1 for _ in open(tmp.name, errors="ignore"))
    ud["proxy_path"] = tmp.name
    await update.message.reply_text(
        f"✅ *Proxies loaded* — `{count:,}` lines\\.", parse_mode=PM2)
    return await _after_proxy(update, context)

async def cb_skip_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    sess(context.user_data)["proxy_path"] = None
    await q.message.reply_text("⚡ *Running without proxies\\.*", parse_mode=PM2)
    return await _after_proxy(update, context)

async def _after_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ud    = sess(context.user_data); mid = ud["module"]
    sub   = get_sub(update.effective_user.id)
    max_t = sub["threads_max"] if sub else 50
    msg   = update.effective_message
    if mid == "hotmail":
        await msg.reply_text(
            f"*Step 3 — Keywords*\n"
            f"Defaults: `{_esc(', '.join(ud['keywords']))}`\n\n"
            "Send comma\\-separated keywords or keep defaults:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Keep Defaults", callback_data="skip_kw")],
                [InlineKeyboardButton("✗ Cancel",          callback_data="back_home")],
            ]),
            parse_mode=PM2,
        )
        return AWAIT_KW
    await msg.reply_text(
        f"*Step 3 — Thread Count*\n"
        f"Plan max: `{max_t}`  \\|  Current: `{ud['threads']}`",
        reply_markup=kb_threads(ud["threads"], max_t),
        parse_mode=PM2,
    )
    return IDLE

async def recv_kw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard(update, context): return IDLE
    ud = sess(context.user_data); sub = get_sub(update.effective_user.id)
    kws = [k.strip() for k in update.message.text.split(",") if k.strip()]
    ud["keywords"] = kws or ud["keywords"]
    max_t = sub["threads_max"] if sub else 50
    await update.message.reply_text(
        f"✅ Keywords: `{_esc(', '.join(ud['keywords']))}`\n\n"
        "*Step 4 — Thread Count*",
        reply_markup=kb_threads(ud["threads"], max_t),
        parse_mode=PM2,
    )
    return IDLE

async def cb_skip_kw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    ud = sess(context.user_data); sub = get_sub(update.effective_user.id)
    max_t = sub["threads_max"] if sub else 50
    await safe_edit(q,
        f"✅ Defaults: `{_esc(', '.join(ud['keywords']))}`\n\n"
        "*Step 4 — Thread Count*",
        kb_threads(ud["threads"], max_t))
    return IDLE

async def cb_threads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    ud = sess(context.user_data); sub = get_sub(update.effective_user.id)
    max_t = sub["threads_max"] if sub else 50
    t = int(q.data.split(":", 1)[1])
    if t > max_t:
        await q.answer(f"⛔ Plan max: {max_t} threads.", show_alert=True); return IDLE
    ud["threads"] = t
    try:
        await q.message.edit_reply_markup(reply_markup=kb_threads(t, max_t))
    except BadRequest:
        pass
    await q.answer(f"✅ Threads → {t}")
    return IDLE

# ══════════════════════════════════════════════════════════════════════════════
# START CHECK
# ══════════════════════════════════════════════════════════════════════════════
async def cb_start_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not await guard(update, context): return IDLE
    uid = update.effective_user.id; ud = sess(context.user_data)
    sub = get_sub(uid)
    if not sub:
        await q.answer("❌ No subscription!", show_alert=True); return IDLE
    if ud["running"]:
        await q.answer("⚠️ Already running!", show_alert=True); return IDLE
    if not ud["combo_path"]:
        await q.answer("❌ No combo file!", show_alert=True); return IDLE

    mid     = ud["module"]
    runner  = MODULES[mid]["runner"]
    mod_lbl = MODULES[mid]["label"]
    mod_ico = MODULES[mid]["icon"]
    writer, rdir = make_writer(mid)
    ud.update(
        results_dir=rdir,
        stats={"hit":0,"2fa":0,"bad":0,"err":0,"done":0,"speed":0,"inbox":0},
        total=0, running=True, cancel=False,
        _start=time.time(), _last_stat_text="",
    )

    smsg = await q.message.edit_text(
        f"*{mod_ico} {_esc(mod_lbl)}* — starting\\.\\.\\.\n\n"
        f"🧵 Threads: `{ud['threads']}`  \\|  "
        f"🌐 Proxies: `{'yes' if ud['proxy_path'] else 'no'}`\n\n"
        "⏳ Warming up\\.",
        reply_markup=kb_cancel(), parse_mode=PM2,
    )

    loop     = asyncio.get_event_loop()
    last_upd = [time.time()]
    INTERVAL = 4.0

    def cb_log(kind: str, email: str, info: str):
        if ud["cancel"]: return
        key = {"hit":"hit","2fa":"2fa","bad":"bad","err":"err"}.get(kind, "err")
        ud["stats"][key] = ud["stats"].get(key, 0) + 1
        if kind == "hit" and info.startswith("inbox:"):
            try:
                ud["stats"]["inbox"] = (
                    ud["stats"].get("inbox", 0) + int(info.split(":", 1)[1].split("|")[0])
                )
            except ValueError:
                pass
        # Send rich hit/2fa message to user
        if kind == "hit":
            rich = format_hit(mid, email, info)
            asyncio.run_coroutine_threadsafe(
                context.bot.send_message(uid, rich, parse_mode=PM2), loop
            )
        elif kind == "2fa":
            rich = format_2fa(email, mid)
            asyncio.run_coroutine_threadsafe(
                context.bot.send_message(uid, rich, parse_mode=PM2), loop
            )

    def cb_stat(stats: dict, total: int):
        if ud["cancel"]: return
        elapsed = time.time() - ud.get("_start", time.time())
        done    = stats.get("done", 0)
        stats["speed"] = int(done / (elapsed / 60)) if elapsed > 10 else 0
        if "inbox_found" in stats: stats["inbox"] = stats.pop("inbox_found")
        for k in ("hit","2fa","bad","err","done","speed","inbox"):
            if k in stats: ud["stats"][k] = stats[k]
        ud["total"] = total
        if time.time() - last_upd[0] < INTERVAL: return
        last_upd[0] = time.time()
        new_text = stat_text(ud["stats"], total, f"{mod_ico} {mod_lbl}", mid)
        if new_text == ud["_last_stat_text"]: return
        ud["_last_stat_text"] = new_text
        asyncio.run_coroutine_threadsafe(
            smsg.edit_text(new_text, reply_markup=kb_cancel(), parse_mode=PM2), loop
        )

    def cb_done(txt: str):
        ud["running"] = False
        async def _fin():
            final = (
                f"✅ *Check Complete — {mod_ico} {_esc(mod_lbl)}*\n\n"
                f"{stat_text(ud['stats'], ud['total'], f'{mod_ico} {mod_lbl}', mid)}"
            )
            await smsg.edit_text(final,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Home", callback_data="back_home")
                ]]),
                parse_mode=PM2,
            )
            await zip_and_send(context.bot, uid, rdir)
        asyncio.run_coroutine_threadsafe(_fin(), loop)

    kwargs = dict(
        combo_file=ud["combo_path"], proxy_file=ud["proxy_path"],
        threads=ud["threads"], writer=writer,
        cb_log=cb_log, cb_stat=cb_stat, cb_done=cb_done,
    )
    if mid == "hotmail": kwargs["keywords"] = ud["keywords"]
    loop.run_in_executor(None, lambda: (not ud["cancel"]) and runner(**kwargs))
    await q.answer("✅ Check started!")
    return RUNNING

async def cb_cancel_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer("Stopped.")
    ud = context.user_data; ud["cancel"] = True; ud["running"] = False
    mid = ud.get("module", "")
    lbl = MODULES.get(mid, {}).get("label", "Check")
    await q.message.edit_text(
        f"⛔ *Check Stopped — {_esc(lbl)}*\n\n"
        f"{stat_text(ud.get('stats',{}), ud.get('total',0), lbl, mid)}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Home", callback_data="back_home")
        ]]),
        parse_mode=PM2,
    )
    if ud.get("results_dir"):
        await zip_and_send(context.bot, update.effective_user.id, ud["results_dir"])
    return IDLE

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════
async def cb_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    return await _show_admin_panel(update, context)

async def cb_admin_grant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    pl = "\n".join(f"`{pid}` · {p['label']} · {p['days']}d"
                   for pid, p in PLANS.items())
    await safe_edit(q,
        f"➕ *Grant Subscription*\n\n{pl}\n\n"
        "Send: `user_id plan_id`\nExample: `123456789 elite`",
        kb_back_home())
    return ADMIN_GRANT

async def admin_do_grant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id): return IDLE
    parts = update.message.text.strip().split()
    if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in PLANS:
        await update.message.reply_text("❌ Format: `user_id plan_id`", parse_mode=PM2)
        return ADMIN_GRANT
    uid2, pid = int(parts[0]), parts[1]
    sub = await add_sub(uid2, pid)
    exp = datetime.fromisoformat(sub["expires"]).strftime("%d %b %Y")
    await update.message.reply_text(
        f"✅ *Granted* `{uid2}` — {_esc(sub['label'])} · `{exp}`",
        reply_markup=kb_admin(), parse_mode=PM2)
    try:
        await context.bot.send_message(uid2,
            f"🎉 *Subscription Activated\\!*\n\n{sub_card_text(sub, uid2)}\n\nUse /start\\.",
            parse_mode=PM2)
    except Exception: pass
    return IDLE

async def cb_admin_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    await safe_edit(q, "➖ *Revoke*\n\nSend `user_id`:", kb_back_home())
    return ADMIN_REVOKE

async def admin_do_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id): return IDLE
    if not update.message.text.strip().isdigit():
        await update.message.reply_text("❌ Valid user\\_id only\\.", parse_mode=PM2)
        return ADMIN_REVOKE
    uid2 = int(update.message.text.strip())
    await revoke_sub(uid2)
    await update.message.reply_text(
        f"✅ Revoked `{uid2}`", reply_markup=kb_admin(), parse_mode=PM2)
    try:
        await context.bot.send_message(uid2,
            f"⚠️ *Subscription revoked\\.*\n\nContact {_esc(SUPPORT)}\\.", parse_mode=PM2)
    except Exception: pass
    return IDLE

async def cb_admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    await safe_edit(q, "🚫 *Ban*\n\nSend `user_id`:", kb_back_home())
    return ADMIN_BAN

async def admin_do_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id): return IDLE
    if not update.message.text.strip().isdigit():
        await update.message.reply_text("❌ Valid user\\_id only\\.", parse_mode=PM2)
        return ADMIN_BAN
    uid2 = int(update.message.text.strip())
    await ban_user(uid2)
    await update.message.reply_text(f"🚫 Banned `{uid2}`", reply_markup=kb_admin(), parse_mode=PM2)
    try:
        await context.bot.send_message(uid2, "🚫 *You have been banned\\.*", parse_mode=PM2)
    except Exception: pass
    return IDLE

async def cb_admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    await safe_edit(q, "✅ *Unban*\n\nSend `user_id`:", kb_back_home())
    return ADMIN_UNBAN

async def admin_do_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id): return IDLE
    if not update.message.text.strip().isdigit():
        await update.message.reply_text("❌ Valid user\\_id only\\.", parse_mode=PM2)
        return ADMIN_UNBAN
    uid2 = int(update.message.text.strip())
    await unban_user(uid2)
    await update.message.reply_text(f"✅ Unbanned `{uid2}`", reply_markup=kb_admin(), parse_mode=PM2)
    return IDLE

async def cb_admin_code_gen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    pl = "  ".join(f"`{pid}`" for pid in PLANS)
    await safe_edit(q,
        f"🎟 *Generate Code*\n\nPlans: {pl}\n\n"
        "Send: `plan_id uses`\nExample: `elite 1`",
        kb_back_home())
    return ADMIN_CODE_GEN

async def admin_do_code_gen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id): return IDLE
    parts = update.message.text.strip().split()
    if not parts or parts[0] not in PLANS:
        await update.message.reply_text(
            "❌ Format: `plan_id [uses]`", parse_mode=PM2)
        return ADMIN_CODE_GEN
    pid  = parts[0]
    uses = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    code = await create_code(pid, uses)
    p    = PLANS[pid]
    await update.message.reply_text(
        f"🎟 *Code Generated\\!*\n\n"
        f"Code: `{code}`\n"
        f"Plan: *{p['badge']} {_esc(p['label'])}*\n"
        f"Uses: `{uses}`\n\n"
        f"Redeem: `/redeem {code}`",
        reply_markup=kb_admin(), parse_mode=PM2)
    return IDLE

async def cb_admin_code_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    if not _codes:
        await safe_edit(q, "📭 No codes yet\\.", kb_admin()); return IDLE
    lines = []
    for code, c in list(_codes.items())[-20:]:
        plan_lbl = PLANS.get(c["plan"], {}).get("label", c["plan"])
        lines.append(
            f"`{code}` · {_esc(plan_lbl)} · "
            f"{c['uses_left']} left / {len(c['used_by'])} used"
        )
    await safe_edit(q,
        f"🎟 *Codes* \\({len(_codes)} total\\)\n\n" + "\n".join(lines),
        kb_admin())
    return IDLE

async def cb_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    ud = sess(context.user_data)
    ud["_broadcast_mode"] = "text"; ud["_broadcast_target"] = "all"
    await safe_edit(q,
        "📢 *Broadcast*\n\n"
        "1\\. Choose type \\+ target\n"
        "2\\. Send the message\\.",
        kb_broadcast())
    return ADMIN_BROADCAST

async def cb_bc_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    ud = sess(context.user_data)
    ud["_broadcast_mode"] = q.data.split(":", 1)[1]
    await q.answer(f"Type: {ud['_broadcast_mode']}")
    return ADMIN_BROADCAST

async def cb_bc_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    ud = sess(context.user_data)
    ud["_broadcast_target"] = q.data.split(":", 1)[1]
    await q.answer(f"Target: {ud['_broadcast_target']}")
    return ADMIN_BROADCAST

async def recv_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id): return IDLE
    ud     = sess(context.user_data)
    msg    = update.message
    mode   = ud.get("_broadcast_mode", "text")
    target = ud.get("_broadcast_target", "all")
    text      = msg.caption or msg.text or ""
    photo_id  = msg.photo[-1].file_id if mode == "photo" and msg.photo else None
    doc_id    = msg.document.file_id  if mode == "doc"   and msg.document else None
    if mode == "text" and not msg.text:
        await msg.reply_text("❌ Send text for text broadcast\\.", parse_mode=PM2)
        return ADMIN_BROADCAST
    await msg.reply_text(f"📢 Broadcasting to *{_esc(target)}*\\.\\.\\.", parse_mode=PM2)
    asyncio.create_task(
        do_broadcast(context.bot, update.effective_user.id, text, target, photo_id, doc_id))
    return IDLE

async def cb_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    subs = _subs_cache; now = datetime.utcnow()
    if not subs:
        await safe_edit(q, "📭 No subscriptions\\.", kb_admin()); return IDLE
    lines = []
    for uid_s, v in list(subs.items())[:20]:
        alive = datetime.fromisoformat(v.get("expires","2000-01-01")) > now
        dl    = max(0,(datetime.fromisoformat(v.get("expires","2000-01-01"))-now).days)
        icon  = "🟢" if alive else "🔴"
        uname = f"@{v['username']}" if v.get("username") else uid_s
        lines.append(f"{icon} `{uid_s}` · {v['badge']} {_esc(v['label'])} · {dl}d · {_esc(uname)}")
    await safe_edit(q,
        f"👥 *Subscriptions* \\({len(subs)}\\)\n\n" + "\n".join(lines), kb_admin())
    return IDLE

async def cb_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    subs = _subs_cache; now = datetime.utcnow()
    plan_counts: dict[str,int] = {}
    active = expired = 0
    for v in subs.values():
        alive = datetime.fromisoformat(v.get("expires","2000-01-01")) > now
        if alive:
            active += 1
            plan_counts[v["plan"]] = plan_counts.get(v["plan"],0) + 1
        else: expired += 1
    plan_lines = "\n".join(
        f"{PLANS[p]['badge']} {_esc(PLANS[p]['label']):<12} · `{c}`"
        for p, c in sorted(plan_counts.items(), key=lambda x: -x[1])
    ) or "None"
    await safe_edit(q,
        f"📊 *Stats*\n\n"
        f"👥 Total   `{len(subs)}`\n"
        f"🟢 Active  `{active}`\n"
        f"🔴 Expired `{expired}`\n"
        f"🚫 Banned  `{len(_banned)}`\n"
        f"🎟 Codes   `{len(_codes)}`\n\n"
        f"*By plan:*\n{plan_lines}", kb_admin())
    return IDLE

async def cb_admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    buf = StringIO()
    w   = csv.writer(buf)
    w.writerow(["uid","username","plan","label","activated","expires","modules","threads_max"])
    for uid_s, v in _subs_cache.items():
        w.writerow([uid_s, v.get("username",""), v.get("plan",""), v.get("label",""),
                    v.get("activated",""), v.get("expires",""),
                    "|".join(v.get("modules",[])), v.get("threads_max","")])
    buf.seek(0)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    await context.bot.send_document(
        update.effective_user.id,
        InputFile(BytesIO(buf.getvalue().encode()), filename=f"subs_{ts}.csv"),
        caption="📤 *Subscriptions Export*", parse_mode=PM2)
    return IDLE

async def cb_admin_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    global _maintenance
    q = update.callback_query; await q.answer()
    if not is_admin(update.effective_user.id):
        await q.answer("❌ Denied", show_alert=True); return IDLE
    _maintenance = not _maintenance
    state = "🔧 ON" if _maintenance else "✅ OFF"
    await q.answer(f"Maintenance: {state}", show_alert=True)
    return await _show_admin_panel(update, context)

# ══════════════════════════════════════════════════════════════════════════════
# APP WIRING
# ══════════════════════════════════════════════════════════════════════════════
def _nav_handlers() -> list:
    return [
        CallbackQueryHandler(cb_back_home,          pattern="^back_home$"),
        CallbackQueryHandler(cb_check_sub,          pattern="^check_sub$"),
        CallbackQueryHandler(cb_my_sub,             pattern="^my_sub$"),
        CallbackQueryHandler(cb_claim_trial,        pattern="^claim_trial$"),
        CallbackQueryHandler(cb_view_plans,         pattern="^view_plans$"),
        CallbackQueryHandler(cb_plan_info,          pattern=r"^plan_info:"),
        CallbackQueryHandler(cb_help,               pattern="^help$"),
        CallbackQueryHandler(cb_redeem,             pattern="^redeem$"),
        CallbackQueryHandler(cb_module,             pattern=r"^mod:"),
        CallbackQueryHandler(cb_threads,            pattern=r"^threads:"),
        CallbackQueryHandler(cb_start_check,        pattern="^start_check$"),
        CallbackQueryHandler(cb_skip_proxy,         pattern="^skip_proxy$"),
        CallbackQueryHandler(cb_skip_kw,            pattern="^skip_kw$"),
        # Tools
        CallbackQueryHandler(cb_tools_menu,         pattern="^tools_menu$"),
        CallbackQueryHandler(cb_tool_dedup,         pattern="^tool_dedup$"),
        CallbackQueryHandler(cb_tool_split,         pattern="^tool_split$"),
        CallbackQueryHandler(cb_tool_proxy_test,    pattern="^tool_proxy_test$"),
        CallbackQueryHandler(cb_do_split,           pattern=r"^split:"),
        # Admin
        CallbackQueryHandler(cb_admin_panel,        pattern="^admin_panel$"),
        CallbackQueryHandler(cb_admin_grant,        pattern="^admin_grant$"),
        CallbackQueryHandler(cb_admin_revoke,       pattern="^admin_revoke$"),
        CallbackQueryHandler(cb_admin_ban,          pattern="^admin_ban$"),
        CallbackQueryHandler(cb_admin_unban,        pattern="^admin_unban$"),
        CallbackQueryHandler(cb_admin_code_gen,     pattern="^admin_code_gen$"),
        CallbackQueryHandler(cb_admin_code_list,    pattern="^admin_code_list$"),
        CallbackQueryHandler(cb_admin_broadcast,    pattern="^admin_broadcast$"),
        CallbackQueryHandler(cb_admin_list,         pattern="^admin_list$"),
        CallbackQueryHandler(cb_admin_stats,        pattern="^admin_stats$"),
        CallbackQueryHandler(cb_admin_export,       pattern="^admin_export$"),
        CallbackQueryHandler(cb_admin_maintenance,  pattern="^admin_maintenance$"),
        CallbackQueryHandler(cb_bc_type,            pattern=r"^bc_type:"),
        CallbackQueryHandler(cb_bc_target,          pattern=r"^bc_target:"),
    ]

def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    nav = _nav_handlers()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start",  cmd_start),
            CommandHandler("admin",  cmd_admin),
            CommandHandler("redeem", cmd_redeem),
            *nav,
        ],
        states={
            IDLE:          nav,
            AWAIT_COMBOS:  [
                MessageHandler(filters.Document.ALL,                  recv_combos_doc),
                MessageHandler(filters.TEXT & ~filters.COMMAND,       recv_combos_path),
                *nav,
            ],
            AWAIT_PROXY:   [
                MessageHandler(filters.Document.ALL,                  recv_proxy_doc),
                *nav,
            ],
            AWAIT_KW:      [
                MessageHandler(filters.TEXT & ~filters.COMMAND,       recv_kw),
                *nav,
            ],
            RUNNING:       [
                CallbackQueryHandler(cb_cancel_run, pattern="^cancel_run$"),
                *nav,
            ],
            AWAIT_REDEEM:  [
                MessageHandler(filters.TEXT & ~filters.COMMAND,       recv_redeem_text),
                *nav,
            ],
            # ── Tools states ────────────────────────────────────────────
            AWAIT_DEDUP_FILE:  [
                MessageHandler(filters.Document.ALL,                  recv_dedup_file),
                *nav,
            ],
            AWAIT_SPLIT_PARTS: [
                MessageHandler(filters.Document.ALL,                  recv_split_file),
                *nav,
            ],
            AWAIT_PROXY_TEST:  [
                MessageHandler(filters.Document.ALL,                  recv_proxy_test_file),
                *nav,
            ],
            # ── Admin states ─────────────────────────────────────────────
            ADMIN_GRANT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_do_grant),   *nav],
            ADMIN_REVOKE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_do_revoke),  *nav],
            ADMIN_BAN:     [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_do_ban),     *nav],
            ADMIN_UNBAN:   [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_do_unban),   *nav],
            ADMIN_CODE_GEN:[MessageHandler(filters.TEXT & ~filters.COMMAND, admin_do_code_gen),*nav],
            ADMIN_BROADCAST:[
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
                    recv_broadcast_msg,
                ),
                CallbackQueryHandler(cb_bc_type,   pattern=r"^bc_type:"),
                CallbackQueryHandler(cb_bc_target, pattern=r"^bc_target:"),
                *nav,
            ],
        },
        fallbacks=[
            CommandHandler("start",  cmd_start),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("admin",  cmd_admin),
        ],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("admin",       cmd_admin),       group=1)
    app.add_handler(CommandHandler("status",      cmd_status),      group=1)
    app.add_handler(CommandHandler("cancel",      cmd_cancel),      group=1)
    app.add_handler(CommandHandler("myid",        cmd_myid),        group=1)
    app.add_handler(CommandHandler("maintenance", cmd_maintenance),  group=1)
    app.add_handler(CommandHandler("redeem",      cmd_redeem),      group=1)
    return app


async def _post_init(app: Application):
    await _init_subs()
    await _load_banned()
    await _load_codes()
    log.info(
        f"BaseX {BOT_VERSION} ready — "
        f"{len(_subs_cache)} subs, {len(_banned)} banned, {len(_codes)} codes"
    )


if __name__ == "__main__":
    log.info(f"BaseX Bot {BOT_VERSION} — starting")
    app = build_app()
    app.post_init = _post_init
    app.run_polling(drop_pending_updates=True)
