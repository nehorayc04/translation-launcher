"""
plugins.community_compute - "מחשוב קהילתי" as a LAUNCHER PLUGIN.

This is the standalone Community-Compute worker (community_compute/desktop)
folded into the launcher's plugin system, so a volunteer does not install a
second program: they open the launcher they already have, turn the plugin on,
paste a free API key, and their machine starts translating community lines in
the background.

Split of responsibilities, same shape as save_backup.py / game_copilot.py:
  * THIS module is the stateless "kind" engine - the config shape, the pull
    loop, and the dispatch table `run_action()` that `plugins/engine.py`
    delegates to for `kind == "community_compute"`. It never touches Qt.
  * The loop runs on a plain daemon `threading.Thread` (NOT a QThread): the
    work is pure network + JSON, so it must not depend on the Qt shell and must
    keep running while the window is hidden in the tray.

Why this is a plugin and not "downloaded code": the launcher's plugin design
forbids executing anything fetched from the cloud (see plugins/__init__.py).
A background worker is genuine new code, so it ships INSIDE the app exactly
like save_backup and game_copilot, and only its metadata/UI can ever be
cloud-edited.

Privacy, unchanged from the standalone app and worth restating because this is
the whole reason volunteers trust it:
  * The provider API keys go through the OS keyring, never the plain-JSON
    plugin config, and are NEVER transmitted anywhere except to the provider
    the volunteer chose.
  * PULL model: the pool never connects to the volunteer, so it never learns
    their IP. Nothing about the machine is uploaded - only translated lines.
"""
from __future__ import annotations

import json
import logging

import ssl
import threading
import time
import urllib.error
import urllib.request
import uuid

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Control plane
# ─────────────────────────────────────────────────────────────
# The default pool. `base_override` in the config points the plugin at the
# SELF-HOSTED pool without shipping a new build - the one thing a live `config`
# reply cannot carry is its own address, so it has to be a setting.
# The pool endpoint. Deliberately NOT shown to volunteers: the workers.dev
# subdomain is derived from the Cloudflare ACCOUNT name, which carries the
# maintainer's personal handle. The UI shows "ברירת המחדל" instead, and the
# constant moves to a project-owned domain the moment one fronts the Worker.
#
# דור 3 (תשתית): Turso itself now hard-blocks reads (plan quota exceeded), so the
# Worker/Turso route above is DEAD; the queue moved to the self-hosted server on
# the Home Assistant machine (same secrets, byte-compatible /cc/* contract,
# reached via a Cloudflare Tunnel). `base_override` still lets a running
# volunteer point elsewhere without a rebuild.
CC_BASE = "https://pool.hebrew-translation-hub.com/cc"
CC_SECRET = "bff947baf4b340ec303dbabd377dd7aaa9f10ebc143ece3e"

# Live server tuning, refreshed from EVERY reply - so the operator retunes the
# whole fleet (heartbeat, batch size, caps) with no client rebuild.
SERVER_CONFIG = {"heartbeat_seconds": 300, "lease_ttl_seconds": 1200,
                 "batch_size": 50, "max_inflight": 300}

# Each provider carries its OWN how-to, in plain Hebrew - a volunteer who has
# never made an API key must not have to look anything up. The wording is the
# SAME as the Android app's guide (community_compute/android/lib/screens/keys.dart)
# so a user who set a key up on the phone recognises the steps here.
PROVIDERS = [
    {"id": "groq", "label": "Groq", "url": "https://console.groq.com/keys",
     "note": "המהיר והיציב ביותר - מומלץ להתחיל ממנו.",
     "steps": [
         "פתחו את console.groq.com והתחברו (אפשר עם Google או GitHub - חינם).",
         "בתפריט בצד לחצו על «API Keys».",
         "לחצו «Create API Key», תנו שם כלשהו ואשרו.",
         "העתיקו את המפתח שמופיע (מתחיל ב-gsk_) - הוא מוצג פעם אחת בלבד!",
         "הדביקו אותו בשדה שכאן ולחצו שמירה.",
     ]},
    {"id": "sambanova", "label": "SambaNova", "url": "https://cloud.sambanova.ai",
     "note": "דרגה חינמית לפיתוח - מהיר ואיכותי.",
     "steps": [
         "פתחו cloud.sambanova.ai והירשמו או התחברו (חינם).",
         "בתפריט לחצו על «APIs» / «API Keys».",
         "לחצו «Generate» / «Create» כדי ליצור מפתח חדש.",
         "העתיקו את המפתח שנוצר.",
         "הדביקו אותו בשדה שכאן ולחצו שמירה.",
     ]},
    {"id": "nim", "label": "NVIDIA NIM", "url": "https://build.nvidia.com",
     "note": "החינמי איטי ועמוס לפעמים - כדאי להוסיף גם Groq לצידו.",
     # אין צורך לבחור מודל - המפתח נוצר מהתפריט של חשבון המשתמש.
     "steps": [
         "פתחו build.nvidia.com והירשמו או התחברו עם חשבון NVIDIA (חינם).",
         "לחצו על סמל המשתמש בפינת האתר כדי לפתוח את התפריט הנפתח.",
         "בחרו בתפריט את האפשרות של מפתחות API («API Keys»).",
         "לחצו על יצירת מפתח חדש והעתיקו אותו (מתחיל ב-nvapi-).",
         "הדביקו אותו בשדה שכאן ולחצו שמירה.",
     ]},
]

_ENDPOINT = {
    "groq":      ("https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b"),
    "sambanova": ("https://api.sambanova.ai/v1/chat/completions", "Meta-Llama-3.3-70B-Instruct"),
    "nim":       ("https://integrate.api.nvidia.com/v1/chat/completions", "meta/llama-3.3-70b-instruct"),
}

PREFETCH_LINES = 20        # refill the local buffer once it drops below this
TRANSLATE_SLICE = 8        # lines handed to a provider per call
POLL_IDLE_S = 6
POLL_MAX_S = 60

_SSL = ssl.create_default_context()
# A real browser UA. Cloudflare (which fronts the pool AND every provider) blocks
# urllib's default with a bare 403 "error code: 1010" - no body, no explanation.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_KEYRING_SERVICE = "TranslationManagerCommunityCompute"


class NetworkError(Exception):
    """Transient - unreachable / timeout / 5xx. Buffer and retry."""


class ApiError(Exception):
    """The pool answered 4xx (bad secret, blocked, paused). A real answer."""


# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
def default_config() -> dict:
    return {
        "enabled": False,
        "worker_id": uuid.uuid4().hex[:12],
        "base_override": "",
        "lines_done": 0,
        "by_provider": {},
        # The buffers live in the config so a launcher restart never loses work
        # a volunteer already paid for with their own quota.
        "inbox": [],       # [{id, sys, target, src}]
        "outbox": {},      # {line_id: hebrew}
    }


# One writer lock for the whole module: `registry.set_config` REPLACES the
# config wholesale (it is not a merge), so every write here has to be a
# read-modify-write - and two of those racing would silently drop one side's
# fields (a translated line, or the user's key/base setting).
_cfg_lock = threading.RLock()


def _entry(pid: str) -> dict:
    """The install-state entry for this plugin ({} if not installed)."""
    from . import registry
    return (registry.installed() or {}).get(pid) or {}


def _meta(pid: str) -> dict:
    """The catalog entry (name/icon/version), independent of install state."""
    from . import registry
    return registry.by_id(pid) or {}


def _cfg(pid: str) -> dict:
    c = dict(default_config())
    c.update(_entry(pid).get("config") or {})
    if not c.get("worker_id"):
        c["worker_id"] = uuid.uuid4().hex[:12]
        _patch(pid, worker_id=c["worker_id"])
    return c


def _patch(pid: str, **fields) -> None:
    """Merge `fields` into the stored config (read-modify-write under the lock)."""
    from . import registry
    with _cfg_lock:
        cur = dict(_entry(pid).get("config") or {})
        cur.update(fields)
        registry.set_config(pid, cur)


def _base(pid: str) -> str:
    return (_cfg(pid).get("base_override") or "").strip().rstrip("/") or CC_BASE


# ─────────────────────────────────────────────────────────────
# API keys - OS keyring, never the plain-JSON plugin config
# ─────────────────────────────────────────────────────────────
def get_api_key(provider: str) -> str:
    try:
        import keyring
        return keyring.get_password(_KEYRING_SERVICE, provider) or ""
    except Exception:
        log.debug("community_compute: keyring read failed", exc_info=True)
        return ""


def set_api_key(provider: str, key: str) -> bool:
    """Write, then READ BACK - a keyring backend can report success without
    actually persisting (a locked Credential vault), and a key that silently
    vanished looks exactly like a wrong key later."""
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, provider, (key or "").strip())
        return keyring.get_password(_KEYRING_SERVICE, provider) == (key or "").strip()
    except Exception:
        log.warning("community_compute: keyring write failed", exc_info=True)
        return False


def clear_api_key(provider: str) -> None:
    try:
        import keyring
        keyring.delete_password(_KEYRING_SERVICE, provider)
    except Exception:
        pass


def _keys() -> dict:
    return {p["id"]: get_api_key(p["id"]) for p in PROVIDERS
            if get_api_key(p["id"])}


# ─────────────────────────────────────────────────────────────
# Key import / export - the same convenience the standalone app has, so a
# volunteer sets a machine up once and moves the keys to the next one (or to
# their phone) instead of re-issuing them per device.
# ─────────────────────────────────────────────────────────────
_KEYS_FILENAME = "community-compute-keys.txt"


def _clip_get() -> str:
    """Read the Windows clipboard (raw Win32 - no Qt on this worker thread).

    Two things that silently return nothing if you skip them:
      * GetClipboardData returns a HANDLE - ctypes defaults a return to a 32-bit
        int, which TRUNCATES it on 64-bit and yields a null pointer.
      * OpenClipboard fails while another process holds the clipboard (Qt grabs
        it transiently right after our own copy), so it needs a short retry.
    """
    import ctypes
    try:
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        u32.GetClipboardData.restype = ctypes.c_void_p
        u32.GetClipboardData.argtypes = [ctypes.c_uint]
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        for _ in range(10):
            if u32.OpenClipboard(None):
                break
            time.sleep(0.05)
        else:
            return ""
        try:
            h = u32.GetClipboardData(13)              # CF_UNICODETEXT
            if not h:
                return ""
            p = k32.GlobalLock(h)
            if not p:
                return ""
            try:
                return ctypes.c_wchar_p(p).value or ""
            finally:
                k32.GlobalUnlock(h)
        finally:
            u32.CloseClipboard()
    except Exception:                                     # pragma: no cover
        log.debug("clipboard read failed", exc_info=True)
        return ""


def _clip_set(text: str) -> bool:
    try:
        from ..auth.manager import _clipboard_set
        return bool(_clipboard_set(text))
    except Exception:                                     # pragma: no cover
        log.debug("clipboard write failed", exc_info=True)
        return False


def export_text() -> str:
    """`provider=key` lines for every configured provider ("" if none)."""
    return "\n".join(f"{p['id']}={get_api_key(p['id'])}"
                      for p in PROVIDERS if get_api_key(p["id"]))


def parse_keys(text: str) -> dict:
    """Accept every shape a user might paste: a `provider=key` block, JSON, or a
    BARE key - a bare token is routed by its provider prefix, because someone
    copying one key out of a provider's console has no reason to know our
    format."""
    out: dict = {}
    txt = (text or "").strip()
    if not txt:
        return out
    if txt.startswith("{"):
        try:
            for k, v in (json.loads(txt) or {}).items():
                if k in _ENDPOINT and str(v).strip():
                    out[k] = str(v).strip()
            return out
        except Exception:
            pass
    for raw in txt.replace(",", "\n").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "=" in line or ":" in line:
            sep = "=" if "=" in line else ":"
            k, _, v = line.partition(sep)
            k, v = k.strip().lower(), v.strip().strip('"').strip("'")
            if k in _ENDPOINT and v:
                out[k] = v
                continue
        tok = line.strip().strip('"').strip("'")
        if len(tok) < 12 or " " in tok:
            continue
        if tok.startswith("gsk_"):
            out.setdefault("groq", tok)
        elif tok.startswith("nvapi-"):
            out.setdefault("nim", tok)
        else:
            out.setdefault("sambanova", tok)
    return out


# ─────────────────────────────────────────────────────────────
# Control-plane calls
# ─────────────────────────────────────────────────────────────
def _cc(pid: str, op: str, body: dict, timeout: int = 45) -> dict:
    # 🔴 The User-Agent is NOT cosmetic: Cloudflare answers urllib's default
    # ("Python-urllib/3.x") with 403 "error code: 1010" on every request, so the
    # plugin could never reach the pool - and it surfaced as "no connection",
    # which reads as a network fault rather than a rejected client.
    req = urllib.request.Request(
        f"{_base(pid)}/{op}", data=json.dumps(body).encode(), method="POST",
        headers={"x-cc-secret": CC_SECRET, "Content-Type": "application/json",
                 "User-Agent": _UA})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_SSL))
    try:
        raw = opener.open(req, timeout=timeout).read().decode().strip()
    except urllib.error.HTTPError as e:
        if 500 <= e.code < 600:
            raise NetworkError(f"{op} {e.code}") from e
        raise ApiError(f"{op} {e.code}") from e
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as e:
        raise NetworkError(str(e)) from e
    m = json.loads(raw) if raw else {}
    if not isinstance(m, dict):
        return {}
    cfg = m.get("config")
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            if k in SERVER_CONFIG:
                try:
                    SERVER_CONFIG[k] = int(v)
                except (TypeError, ValueError):
                    pass
    return m


# ─────────────────────────────────────────────────────────────
# Providers - the volunteer's own key, called directly from this machine
# ─────────────────────────────────────────────────────────────
def _translate(provider: str, key: str, sysmsg: str, items: dict, timeout: int = 120) -> dict:
    """Ask ONE provider for {id: hebrew}. Returns {} on any failure."""
    url, model = _ENDPOINT[provider]
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sysmsg or "Translate to Hebrew."},
            {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        # Budget for the ids the model must echo verbatim + Hebrew at ~1 token
        # per character. A reasoning model also spends its thinking against this
        # ceiling, so an under-budget call comes back with an EMPTY answer.
        "max_tokens": min(4000, 1000 + sum(len(k) for k in items) // 2
                          + sum(len(v) for v in items.values()) * 2),
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 # Cloudflare 403s the default urllib UA on some providers.
                 "User-Agent": "Mozilla/5.0"})
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_SSL))
        raw = opener.open(req, timeout=timeout).read().decode()
        msg = json.loads(raw)["choices"][0]["message"]["content"] or ""
    except Exception:
        log.debug("community_compute: %s call failed", provider, exc_info=True)
        return {}
    txt = msg.strip()
    if txt.startswith("```"):
        txt = txt.split("```")[1] if "```" in txt[3:] else txt.strip("`")
        txt = txt.split("\n", 1)[-1] if txt.lower().startswith("json") else txt
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j <= i:
        return {}
    try:
        got = json.loads(txt[i:j + 1])
    except json.JSONDecodeError:
        return {}
    return {k: str(v) for k, v in got.items() if k in items and str(v).strip()}


# ─────────────────────────────────────────────────────────────
# The worker - ONE plain daemon thread per plugin id
# ─────────────────────────────────────────────────────────────
class _Worker(threading.Thread):
    def __init__(self, pid: str):
        super().__init__(daemon=True, name=f"cc-worker-{pid}")
        self.pid = pid
        self._alive = True
        self._online = False
        self._providers_ok = False
        self._enrolled = False
        self._blocked = False
        self._last_beat = 0.0
        self._started_at = time.time()
        self._stage = 0            # 0 pull · 1 translate · 2 check · 3 send
        self._busy = False
        self._note = ""
        self._session = 0
        self._lock = threading.Lock()

    # -- state helpers (the config IS the durable buffer)
    def _read(self) -> dict:
        return _cfg(self.pid)

    def _save(self, **patch) -> None:
        _patch(self.pid, **patch)

    def stop(self) -> None:
        self._alive = False

    def status(self) -> dict:
        c = self._read()
        return {
            "online": self._online, "blocked": self._blocked,
            "stage": self._stage, "busy": self._busy, "note": self._note,
            "inbox": len(c.get("inbox") or []), "outbox": len(c.get("outbox") or {}),
            "lines": int(c.get("lines_done") or 0), "session": self._session,
            "by_provider": dict(c.get("by_provider") or {}),
            "uptime": int(time.time() - self._started_at),
        }

    # -- the loop
    def run(self) -> None:
        backoff = POLL_IDLE_S
        while self._alive:
            try:
                self._tick()
            except Exception:                       # a background loop must never die
                log.exception("community_compute: tick failed")
                self._note = "שגיאה זמנית - ממשיך"
            if self._busy:
                backoff = POLL_IDLE_S
            else:
                backoff = min(backoff * 2, POLL_MAX_S)
            self._sleep(backoff)

        # graceful exit: push what we have, then hand the rest back to the pool
        try:
            self._flush()
            if self._enrolled:
                _cc(self.pid, "release", {"worker": self._read()["worker_id"]})
        except Exception:
            pass

    def _tick(self) -> None:
        c = self._read()
        keys = _keys()
        wid = c["worker_id"]

        if not keys:
            self._busy, self._stage = False, 0
            self._note = "צריך להוסיף מפתח מלפחות ספק אחד"
            return
        if self._blocked:
            self._busy = False
            self._note = "המכשיר נחסם על ידי המנהל"
            return

        # 0. enroll once
        if not self._enrolled:
            try:
                m = _cc(self.pid, "enroll", {"worker": wid, "platform": "windows"})
                self._blocked = m.get("blocked") is True
                self._enrolled, self._online = True, True
                self._last_beat = time.time()
            except NetworkError:
                self._online, self._busy = False, False
                self._note = "אין קשר לשרת - מנסה שוב"
                return
            except ApiError as e:
                self._busy = False
                self._note = "השרת דחה: " + str(e)[:60]
                return

        # 1. heartbeat on the SERVER's own live interval (one cheap write)
        beat = max(60, int(SERVER_CONFIG.get("heartbeat_seconds") or 300))
        if self._online and time.time() - self._last_beat >= beat:
            try:
                m = _cc(self.pid, "renew", {"worker": wid})
                if m.get("ok") is True:
                    self._last_beat = time.time()
                elif m.get("reenroll") is True:
                    self._enrolled = False          # the pool forgot us
                if m.get("blocked") is True:
                    self._blocked = True
            except NetworkError:
                self._online = False
            except ApiError:
                pass

        self._busy = False

        # 2. push whatever is already translated
        if (self._read().get("outbox") or {}):
            self._stage = 3
            self._flush()

        # 3. refill the buffer. The pool sizes the batch itself (it ignores our
        #    `max` on purpose) and already bounds us by max_inflight, so KEEP
        #    everything it hands over - slicing it would strand those lines,
        #    already leased to us, until the lease expires.
        c = self._read()
        if self._online and len(c.get("inbox") or []) < PREFETCH_LINES:
            self._stage = 0
            try:
                m = _cc(self.pid, "claim", {"worker": wid,
                                            "max": int(SERVER_CONFIG.get("batch_size") or 50)})
                if m.get("blocked") is True:
                    self._blocked = True
                lines = [{"id": str(r["id"]), "sys": r.get("sys") or "",
                          "target": r.get("target") or "", "src": r.get("src") or ""}
                         for r in (m.get("lines") or [])]
                if lines:
                    with self._lock:
                        cur = self._read()
                        have = {x["id"] for x in (cur.get("inbox") or [])}
                        done = set(cur.get("outbox") or {})
                        add = [x for x in lines if x["id"] not in have and x["id"] not in done]
                        self._save(inbox=(cur.get("inbox") or []) + add)
                    self._online = True
            except NetworkError:
                self._online = False
            except ApiError as e:
                self._note = "השרת דחה: " + str(e)[:60]

        # 4. translate a slice with the volunteer's OWN keys (needs no server)
        with self._lock:
            cur = self._read()
            inbox = list(cur.get("inbox") or [])
            slice_, rest = inbox[:TRANSLATE_SLICE], inbox[TRANSLATE_SLICE:]
            if slice_:
                self._save(inbox=rest)
        if not slice_:
            if not self._online:
                self._note = "אין קשר לשרת - ממתין וחוזר אוטומטית"
            else:
                self._note = "אין כרגע עבודה בתור"
            return

        self._stage, self._busy = 1, True
        sysmsg = slice_[0].get("sys") or ""
        items = {ln["id"]: ln.get("src") or "" for ln in slice_}
        out, used = {}, ""
        for prov, key in keys.items():             # first provider that answers wins
            out = _translate(prov, key, sysmsg, items)
            if out:
                used = prov
                break

        if not out:
            with self._lock:                       # never lose a line
                cur = self._read()
                self._save(inbox=slice_ + list(cur.get("inbox") or []))
            self._providers_ok = False
            self._note = "אין קשר לספקים - ממתין"
            return

        self._stage = 2
        self._providers_ok = True
        with self._lock:
            cur = self._read()
            ob = dict(cur.get("outbox") or {}); ob.update(out)
            bp = dict(cur.get("by_provider") or {})
            bp[used] = bp.get(used, 0) + len(out)
            missing = [ln for ln in slice_ if ln["id"] not in out]
            self._save(outbox=ob, by_provider=bp,
                       inbox=missing + list(cur.get("inbox") or []))
        self._stage = 3
        self._flush()
        self._note = "פעיל" if self._online else "פעיל - נאגר מקומית (השרת לא זמין)"

    def _flush(self) -> None:
        c = self._read()
        pending = dict(list((c.get("outbox") or {}).items())[:200])
        if not pending:
            return
        try:
            m = _cc(self.pid, "submit", {"worker": c["worker_id"], "out": pending})
            accepted = int(m.get("accepted") or 0)
            self._online = True
        except NetworkError:
            self._online = False        # pool down -> keep EVERYTHING buffered
            return
        except ApiError:
            accepted = 0                # refused ids are ones we no longer hold
        with self._lock:
            cur = self._read()
            ob = dict(cur.get("outbox") or {})
            for i in pending:
                ob.pop(i, None)
            self._save(outbox=ob,
                       lines_done=int(cur.get("lines_done") or 0) + accepted)
        self._session += accepted

    def _sleep(self, secs: float) -> None:
        end = time.time() + secs
        while self._alive and time.time() < end:
            time.sleep(0.25)


_workers: dict[str, _Worker] = {}
_wlock = threading.Lock()


def sync(pid: str) -> None:
    """Start/stop this plugin's worker to match installed+enabled+config."""
    from . import registry
    ent = _entry(pid)
    want = bool(ent and ent.get("enabled")
                and (ent.get("config") or {}).get("enabled"))
    with _wlock:
        w = _workers.get(pid)
        if want and (w is None or not w.is_alive()):
            w = _Worker(pid)
            _workers[pid] = w
            w.start()
        elif not want and w is not None:
            w.stop()
            _workers.pop(pid, None)


def stop(pid: str) -> None:
    """Stop ONE plugin's worker regardless of its stored config - used when the
    plugin is pulled from the catalog, where `sync()` would keep it running
    because the local install-state still says enabled."""
    with _wlock:
        w = _workers.pop(pid, None)
    if w is not None:
        w.stop()


def stop_all(join_seconds: float = 0.0) -> None:
    """Ask every worker to stop. `join_seconds` waits for the graceful
    flush + release on app exit (a daemon thread would otherwise be killed
    mid-handoff and its lines would sit leased until they expire)."""
    with _wlock:
        ws = list(_workers.values())
        for w in ws:
            w.stop()
        _workers.clear()
    if join_seconds > 0:
        deadline = time.time() + join_seconds
        for w in ws:
            w.join(max(0.0, deadline - time.time()))


# ─────────────────────────────────────────────────────────────
# The state the declarative UI binds to
# ─────────────────────────────────────────────────────────────
_STAGE_TEXT = ["מבקש שורות חדשות מהמאגר", "מתרגם עם המפתחות שלך",
               "בודק תקינות ומבנה", "שולח את התוצאה"]


def get_state(pid: str) -> dict:
    from . import registry
    ent = _meta(pid)
    c = _cfg(pid)
    w = _workers.get(pid)
    st = w.status() if w else {
        "online": False, "blocked": False, "stage": 0, "busy": False, "note": "",
        "inbox": len(c.get("inbox") or []), "outbox": len(c.get("outbox") or {}),
        "lines": int(c.get("lines_done") or 0), "session": 0,
        "by_provider": dict(c.get("by_provider") or {}), "uptime": 0,
    }
    keys = {p["id"]: bool(get_api_key(p["id"])) for p in PROVIDERS}
    n_keys = sum(1 for v in keys.values() if v)
    running = bool(c.get("enabled")) and w is not None and w.is_alive()

    if st["blocked"]:
        head = "נחסם"
    elif not n_keys:
        head = "דרוש מפתח API אחד"
    elif not c.get("enabled"):
        head = "כבוי"
    elif st["busy"]:
        head = "פעיל · " + _STAGE_TEXT[min(3, int(st["stage"]))]
    elif not st["online"]:
        # Show the worker's OWN reason when it has one. A rejected client (the
        # server answered, and said no) is a completely different problem from an
        # unreachable one, and collapsing both into "no connection" is what sent
        # this bug hunt after the network instead of the request.
        head = st["note"] or "אין קשר לשרת"
    else:
        head = st["note"] or "ממתין לעבודה"

    up = st["uptime"]
    up_txt = ("—" if not running or up <= 0 else
              f"{up // 3600} שע' {(up % 3600) // 60} דק'" if up >= 3600 else
              f"{max(1, up // 60)} דק'")

    return {
        "entitled": True,
        "enabled": bool(c.get("enabled")),
        "statusText": head,
        "running": running,
        "online": st["online"],
        "hasKeys": n_keys > 0,
        "nKeys": n_keys,
        # The select needs {value,label}; the list needs its own row shape. Two
        # different consumers of the same data, so BOTH are provided explicitly
        # rather than making one shape do double duty (which silently renders an
        # empty dropdown).
        "providerOptions": [{"value": p["id"], "label": p["label"]} for p in PROVIDERS],
        # One card per provider: its own paste field + its own how-to. `steps` is
        # data, so the guide can be corrected from the cloud catalog with no rebuild.
        "keyRows": [{"id": p["id"], "label": p["label"], "url": p["url"],
                     "has": keys[p["id"]], "note": p["note"], "steps": p["steps"],
                     "mark": "מפתח שמור ✓" if keys[p["id"]] else "אין מפתח"}
                    for p in PROVIDERS],
        "linesDone": st["lines"],
        "linesDisplay": f"{st['lines']:,}",
        "pending": st["outbox"],
        "buffered": st["inbox"],
        "uptimeDisplay": up_txt,
        # A short line UNDER the status that tells the volunteer what to do next -
        # a status alone ("כבוי") does not.
        "heroHint": ("המכשיר אינו מקבל עבודה כרגע" if st["blocked"] else
                     "הוסיפו מפתח חינמי מספק אחד כדי להתחיל" if not n_keys else
                     "הפעילו את המתג והמחשב יתחיל לתרגם ברקע" if not c.get("enabled") else
                     "רץ ברקע - אפשר לסגור את החלון, התוסף ממשיך" if st["online"] else
                     "העבודה נאגרת ותישלח כשהחיבור יחזור"),
        "queueDisplay": f"{st['inbox'] + st['outbox']:,}",
        "queueCaption": (f"{st['outbox']:,} ממתינות לשליחה" if st["outbox"]
                         else "שורות שנמשכו למחשב"),
        # The caption UNDER the uptime number has to describe the uptime, not the
        # server's batch sizes (that belongs in the advanced box).
        "connText": ("מחובר לשרת" if running and st["online"] else
                     "אין קשר לשרת - נאגר מקומית" if running else "כבוי"),
        "workerId": (c.get("worker_id") or "")[:8] or "—",
        # A LABEL, never the raw URL - the default host is not the volunteer's
        # business and it carries a private subdomain.
        "serverLabel": (c.get("base_override") or "").strip() or "ברירת המחדל של הפרויקט",
        "isCustomServer": bool((c.get("base_override") or "").strip()),
        "baseOverride": c.get("base_override", ""),
        "serverInfo": (f"פעימה כל {SERVER_CONFIG['heartbeat_seconds'] // 60} דק' · "
                       f"מנה {SERVER_CONFIG['batch_size']} שורות · "
                       f"תקרה {SERVER_CONFIG['max_inflight']}"),
        "byProviderText": " · ".join(f"{k}: {v:,}" for k, v in
                                     (st["by_provider"] or {}).items()) or "—",
        "version": (ent.get("version") or ""),
    }


# ─────────────────────────────────────────────────────────────
# Actions (the declarative UI's dispatch table)
# ─────────────────────────────────────────────────────────────
def _ok(pid: str, **extra) -> dict:
    return {"ok": True, "state": get_state(pid), **extra}


def run_action(pid: str, action: str, args: dict | None = None) -> dict:
    from . import registry
    args = args or {}

    if action == "get_state":
        return _ok(pid)

    # Mutating actions require an installed plugin - installing IS the gate.
    if not registry.is_installed(pid):
        return {"ok": False, "error": "התוסף אינו מותקן"}

    if action == "set_enabled" or action == "toggle":
        want = bool(args.get("value")) if "value" in args else not bool(_cfg(pid).get("enabled"))
        if want and not _keys():
            return {"ok": False, "error": "צריך להוסיף מפתח מלפחות ספק אחד לפני ההפעלה",
                    "state": get_state(pid)}
        _patch(pid, enabled=want)
        sync(pid)
        return _ok(pid)

    if action == "export_keys":
        txt = export_text()
        if not txt:
            return {"ok": False, "error": "אין מפתחות לייצוא"}
        where = str(args.get("to") or "clipboard")
        if where == "file":
            from . import engine as _eng
            folder = _eng.pick_folder("בחרו לאן לשמור את קובץ המפתחות")
            if not folder:
                return {"ok": True, "state": get_state(pid)}      # cancelled
            import os
            path = os.path.join(folder, _KEYS_FILENAME)
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(txt + "\n")
            except OSError as e:
                return {"ok": False, "error": f"השמירה נכשלה: {e}"}
            return _ok(pid, status=f"המפתחות נשמרו ל-{path}")
        if not _clip_set(txt):
            return {"ok": False, "error": "ההעתקה ללוח נכשלה"}
        return _ok(pid, status="המפתחות הועתקו ללוח")

    if action == "import_keys":
        src = str(args.get("from") or "clipboard")
        if src == "file":
            from . import engine as _eng
            path = _eng.pick_file("בחרו קובץ מפתחות")
            if not path:
                return {"ok": True, "state": get_state(pid)}      # cancelled
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError as e:
                return {"ok": False, "error": f"הקריאה נכשלה: {e}"}
        else:
            text = str(args.get("text") or "") or _clip_get()
        found = parse_keys(text)
        if not found:
            return {"ok": False, "error": "לא נמצאו מפתחות בטקסט"}
        saved = [p for p, k in found.items() if set_api_key(p, k)]
        if not saved:
            return {"ok": False, "error": "שמירת המפתחות נכשלה"}
        names = ", ".join(next(q["label"] for q in PROVIDERS if q["id"] == p) for p in saved)
        return _ok(pid, status=f"נטענו מפתחות: {names}")

    if action == "set_api_key":
        prov, key = str(args.get("provider") or ""), str(args.get("key") or "").strip()
        if prov not in _ENDPOINT:
            return {"ok": False, "error": "ספק לא מוכר"}
        if not key:
            return {"ok": False, "error": "לא הוזן מפתח"}
        if not set_api_key(prov, key):
            return {"ok": False, "error": "שמירת המפתח נכשלה (מחסן הסיסמאות של Windows לא זמין)"}
        return _ok(pid, status="המפתח נשמר מוצפן במחשב הזה")

    if action == "clear_api_key":
        clear_api_key(str(args.get("provider") or ""))
        if not _keys():                       # no key left -> nothing to run on
            _patch(pid, enabled=False)
            sync(pid)
        return _ok(pid)

    if action == "set_base":
        url = str(args.get("url") or "").strip()
        if url and not url.startswith(("http://", "https://")):
            return {"ok": False, "error": "הכתובת חייבת להתחיל ב-http:// או https://"}
        _patch(pid, base_override=url)
        with _wlock:                          # re-enroll against the new pool
            w = _workers.get(pid)
            if w:
                w._enrolled = False
        return _ok(pid, status="כתובת השרת עודכנה")

    if action == "test":
        try:
            m = _cc(pid, "stats", {})
            return _ok(pid, status=(f"השרת עונה · פתוחות {m.get('open', '?')} · "
                                    f"הושלמו {m.get('done', '?')} · "
                                    f"מכשירים {m.get('workers', '?')}"))
        except NetworkError as e:
            return {"ok": False, "error": f"אין קשר לשרת: {str(e)[:80]}", "state": get_state(pid)}
        except ApiError as e:
            return {"ok": False, "error": f"השרת דחה: {str(e)[:80]}", "state": get_state(pid)}

    if action == "open_url":
        url = str(args.get("url") or "")
        if url.startswith(("http://", "https://")):
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass
        return _ok(pid)

    return {"ok": False, "error": f"פעולה לא מוכרת: {action}"}
