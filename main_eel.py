"""
Eel entry point — bridges the React frontend (in `frontend/`) to the existing
Python engine modules (translation_manager.{games_catalog, game_detector,
mod_logic, paths, config}).

Run in PROD mode (serves built React app):
    python main_eel.py

Run in DEV mode (frontend served by Vite on :5173, Eel just exposes the API):
    python main_eel.py --dev
"""

from __future__ import annotations

# ════════════════════════════════════════════════════════════════════
# CRITICAL: monkey-patch BEFORE any other runtime imports.
# ════════════════════════════════════════════════════════════════════
# Eel does NOT call gevent.monkey.patch_all() on its own. That left
# every socket call (HTTPS to Supabase, the loopback's handle_request,
# even Eel's own websocket accept) as native blocking calls running on
# the same OS thread as the gevent hub. Result: the hub stalls during
# every socket I/O, the React frontend hangs, and bridge calls like
# auth_abort_login can't dispatch — which is the entire history of the
# "Copy Link / Cancel button unresponsive" and "OAuth flow freezes
# right after the callback" bugs.
#
# We patch socket + ssl (and select, which is what http.server uses to
# wait for incoming connections). We DELIBERATELY DO NOT patch
# threading — the launcher's download manager and a few other modules
# use real OS threads for background work that must not be serialised
# behind the gevent hub. Threads created inside the auth path that
# DO need cooperative semantics use gevent.spawn / gevent.event
# explicitly, so they don't need monkey-patching either.
#
# `from __future__` MUST be the very first statement (Python language
# rule), so the patch lives on the line immediately after it; this is
# still before every runtime import below.
from gevent import monkey as _gevent_monkey
_gevent_monkey.patch_socket()
_gevent_monkey.patch_ssl()
_gevent_monkey.patch_select()

import argparse
import json
import os
import pathlib
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import eel
import requests

from translation_manager import downloads as _downloads
from translation_manager import paths as user_paths
from translation_manager import swr_cache
from translation_manager.config import GAMES as GAME_CONFIGS
from translation_manager.config import GameConfig
from translation_manager.game_detector import (
    cached as detected_cached,
    refresh_deep,
    refresh_quick,
)
from translation_manager.games_catalog import sorted_games as _bundled_games


from translation_manager.mod_logic import (
    STATE_NOT_AVAILABLE,
    STATE_NOT_INSTALLED,
    detect_state,
    disable_mod,
    enable_mod,
    uninstall_mod,
)

# Optional auth subsystem — if Supabase isn't configured (e.g. local
# dev without env vars), the bridge stays installed but every call
# returns a "not configured" error rather than crashing the launcher.
try:
    from translation_manager import auth as _auth
    _auth_available = True
    _auth_error: str | None = None
except Exception as e:  # pragma: no cover — defensive
    _auth = None
    _auth_available = False
    _auth_error = str(e)


# ─────────────────────────────────────────────────────────────
# Dynamic content layer  (Stale-While-Revalidate via swr_cache)
# ─────────────────────────────────────────────────────────────
# Catalog / news / updates / per-game progress all flow through the
# `swr_cache` module: hot calls return last-known-good data instantly
# (from memory, seeded on import from ~/.translation_manager/cache.json),
# and a background daemon refreshes from the live API. When fresh data
# differs from cached, swr_cache fires `eel.cache_refreshed(...)` to
# update the React UI without a reload.
ROOT = Path(__file__).parent
LOCAL_CATALOG_FILE = ROOT / "games.json"
LOCAL_NEWS_FILE    = ROOT / "news.json"
LOCAL_UPDATES_FILE = ROOT / "updates.json"
REMOTE_CATALOG_URL = "https://hebrew-translation-hub.vercel.app/api/games"
REMOTE_NEWS_URL    = "https://hebrew-translation-hub.vercel.app/api/news"
REMOTE_UPDATES_URL = "https://hebrew-translation-hub.vercel.app/api/updates"
REMOTE_TIMEOUT     = 3.0   # seconds — keep short so offline boot isn't slow
_REMOTE_CACHE_TTL  = 30    # in-memory hot-window. Below this, swr returns
                           # the cached value without firing a background
                           # refresh. Above it, return cached + refresh.
API_BASE = "https://hebrew-translation-hub.vercel.app"


def _has_any_cache() -> bool:
    """True if the SWR cache already has at least one entry on disk."""
    p = pathlib.Path.home() / ".translation_manager" / "cache.json"
    if not p.exists():
        return False
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(raw.get("entries"))


def _ping_api(timeout: float = 3.0) -> bool:
    try:
        r = requests.get(f"{API_BASE}/api/games", timeout=timeout)
        return r.ok
    except requests.RequestException:
        return False


def _show_no_internet_dialog() -> None:
    """Tk-based blocking dialog. Used only when the launcher cannot start
    its cache from the network on first run."""
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "אין חיבור לאינטרנט",
        "להפעלה הראשונה של מנהל התרגומים נדרש חיבור לאינטרנט "
        "כדי להוריד את הקטלוג המעודכן (משחקים, חדשות, תמונות).\n\n"
        "אנא התחבר לאינטרנט ופתח שוב את האפליקציה.",
    )
    root.destroy()


def _try_remote(url: str) -> list[dict] | None:
    """GET a remote JSON list. Returns None on any failure (network, parse, …).
    SWR treats None as 'no update — keep cached value'."""
    try:
        r = requests.get(url, timeout=REMOTE_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
    except (requests.RequestException, ValueError):
        pass
    return None


def _shape_supabase_game(row: dict, owned_ids: set[str]) -> dict:
    """Snake-case DB row → camelCase shape consumed by the React frontend
    (matches the website's /api/games response 1:1 so the frontend
    doesn't have to branch on data source)."""
    gid = row.get('id') or ''
    return {
        'id':              gid,
        'titleEn':         row.get('title_en') or '',
        'titleHe':         row.get('title_he') or '',
        'version':         row.get('version') or '—',
        'versionLabel':    row.get('version_label') or '',
        'status':          row.get('status') or 'final',
        'cover':           row.get('cover_url'),
        'theme_key':       row.get('theme_key') or 'default',   # legacy snake
        'themeKey':        row.get('theme_key') or 'default',   # new camel
        'availability':    row.get('availability') or 'planned',
        'progress':        row.get('progress'),
        'downloadUrl':     row.get('download_url'),
        'tagline':         row.get('tagline') or '',
        'description':     row.get('description') or '',
        'next':            bool(row.get('next_up')),
        'featured':        bool(row.get('featured')),
        'sortOrder':       row.get('sort_order') or 1000,
        # New: ownership flag for the DRM gate. Always present (false when
        # signed out or not purchased) so the frontend can branch cleanly.
        'owned':           gid in owned_ids,
    }


def _try_supabase_catalog() -> list[dict] | None:
    """Live games catalog straight from Supabase REST. Bypasses the
    website's CDN-cached /api/games (60s s-maxage) so admin edits show
    up within one SWR window. Fails closed → caller falls through to
    /api/games → bundled games.json on absolute offline cold boot.

    Auth-aware: if the launcher has a valid stored access token, also
    queries user_purchases and tags each game with `owned`. If the user
    is signed out (or the token is expired and refresh fails), the
    games table is anon-readable so we still get the catalog — every
    `owned` is just `false`."""
    if not _auth_available or _auth is None:
        return None
    try:
        from translation_manager.auth.config import load_config, AuthConfigError
        from translation_manager.auth.storage import TokenStore
    except Exception:                                              # pragma: no cover
        return None
    try:
        cfg = load_config()
    except AuthConfigError:
        return None

    # Optional Bearer — present iff there's a non-expired access token.
    headers = {'apikey': cfg.anon_key, 'Accept': 'application/json'}
    access_token: str | None = None
    try:
        tok = TokenStore().load()
        if tok and tok.access_token and not tok.is_expired():
            access_token = tok.access_token
            headers['Authorization'] = f'Bearer {access_token}'
    except Exception:
        access_token = None

    # 1) Games — anon-readable; auth optional.
    try:
        r = requests.get(
            cfg.rest_url + '/games',
            headers=headers,
            params={'select': '*', 'order': 'sort_order.asc'},
            timeout=REMOTE_TIMEOUT,
        )
        if not r.ok:
            return None
        rows = r.json()
        if not isinstance(rows, list):
            return None
    except (requests.RequestException, ValueError):
        return None

    # 2) Owned game IDs (only when signed in). RLS scopes to auth.uid().
    #    A failure here is non-fatal — we just don't tag ownership.
    owned_ids: set[str] = set()
    if access_token:
        try:
            r2 = requests.get(
                cfg.rest_url + '/user_purchases',
                headers=headers,
                params={'select': 'game_id', 'status': 'eq.completed'},
                timeout=REMOTE_TIMEOUT,
            )
            if r2.ok:
                purchases = r2.json()
                if isinstance(purchases, list):
                    owned_ids = {p['game_id'] for p in purchases if isinstance(p, dict) and p.get('game_id')}
        except (requests.RequestException, ValueError):
            pass

    return [_shape_supabase_game(row, owned_ids) for row in rows if isinstance(row, dict)]


def _fetch_catalog_live_first() -> list[dict] | None:
    """SWR fetch closure: try live Supabase first (instant admin reflection),
    then the website /api/games (CDN-cached, slightly stale), and let SWR
    fall through to the bundled JSON if both return None."""
    data = _try_supabase_catalog()
    if data is not None:
        return data
    return _try_remote(REMOTE_CATALOG_URL)


def _load_catalog() -> list[dict]:
    """SWR-cached catalog. On absolute cold start (no disk cache, no
    bundled file, no network) falls back to the dataclasses bundled
    inside the launcher binary itself."""
    data = swr_cache.swr("games", _fetch_catalog_live_first,
                         ttl=_REMOTE_CACHE_TTL)
    if data is None:
        data = [asdict(g) for g in _bundled_games()]
    return data


def _load_news() -> list[dict]:
    data = swr_cache.swr("news", lambda: _try_remote(REMOTE_NEWS_URL),
                         ttl=_REMOTE_CACHE_TTL)
    return data if data is not None else []


def _load_updates() -> list[dict]:
    data = swr_cache.swr("updates", lambda: _try_remote(REMOTE_UPDATES_URL),
                         ttl=_REMOTE_CACHE_TTL)
    return data if data is not None else []


def _force_refresh(kind: str, url: str) -> str:
    """Synchronous force-refresh used by `refresh_catalog`. Returns a
    source label ("remote" | "cache" | "none") for the status toast."""
    remote = _try_remote(url)
    if remote is not None:
        swr_cache.put(kind, remote)
        return "remote"
    return "cache" if swr_cache.peek(kind) is not None else "none"


def _push_cache_event(kind: str, data, sub_key) -> None:
    """SWR's background refresher calls this when fresh data differs from
    the cached value. We forward it to the frontend's `cache_refreshed`
    handler (registered in frontend/public/eel-bindings.js). Wrapped in
    try/except because the call is meaningless until the React app has
    connected — early background firings before the websocket exists
    will just be no-ops."""
    try:
        eel.cache_refreshed(kind, data, sub_key)()         # type: ignore[attr-defined]
    except Exception:
        pass


swr_cache.configure(
    push_cb=_push_cache_event,
)


def _catalog_by_id(game_id: str) -> dict | None:
    for g in _load_catalog():
        if g.get("id") == game_id:
            return g
    return None


# ─────────────────────────────────────────────────────────────
# Resolve the game's effective install path:
#   1) explicit user override (paths.json)
#   2) launcher-detected cache
#   3) None
# ─────────────────────────────────────────────────────────────
def _install_path(game_id: str) -> Path | None:
    custom = user_paths.get(game_id)
    if custom:
        return custom
    return detected_cached().get(game_id)


# Find the GameConfig (mod-file definition) by catalog id.
# Not every catalog game has a config — only the few with actual mods do.
def _config_for(game_id: str) -> GameConfig | None:
    for cfg in GAME_CONFIGS.values():
        if cfg.internal_id == game_id:
            return cfg
    return None


def _mod_state(game_id: str) -> str:
    """Strict state resolution. NEVER returns UNKNOWN — we always know enough
    to pick a correct UI action:
       no GameConfig OR empty mod_files  → NOT_AVAILABLE  (package not authored)
       install dir not detected          → NOT_INSTALLED  (ready to install)
       files inspected on disk           → ACTIVE / DISABLED / NOT_INSTALLED
    """
    cfg = _config_for(game_id)
    if cfg is None or not cfg.mod_files:
        return STATE_NOT_AVAILABLE
    base = _install_path(game_id)
    if base is None:
        return STATE_NOT_INSTALLED
    return detect_state(cfg, base)


def _game_payload(game_id: str) -> dict:
    """Catalog entry enriched with install path + mod state."""
    cg = _catalog_by_id(game_id)
    if cg is None:
        return {}
    base = _install_path(game_id)
    cfg  = _config_for(game_id)
    has_mod = cfg is not None and bool(cfg.mod_files)
    return {
        **cg,
        "install_path": str(base) if base else None,
        "is_installed": base is not None,
        "has_mod_support": has_mod,
        "mod_state": _mod_state(game_id),
    }


# ═════════════════════════════════════════════════════════════
# @eel.expose — public API surface for the React frontend
# ═════════════════════════════════════════════════════════════
_AVAIL_RANK = {"available": 0, "in-progress": 1, "coming-soon": 2, "planned": 3}


@eel.expose
def get_all_games() -> list[dict]:
    """Full catalog (sorted by availability) enriched with install + mod state."""
    items = _load_catalog()
    items_sorted = sorted(
        items,
        key=lambda g: (_AVAIL_RANK.get(g.get("availability", ""), 99),
                       g.get("titleEn", "")),
    )
    return [_game_payload(g["id"]) for g in items_sorted if "id" in g]


@eel.expose
def get_news() -> list[dict]:
    """News / changelog items for the home screen."""
    return _load_news()


@eel.expose
def refresh_catalog() -> dict:
    """Force a synchronous remote re-fetch of all dynamic sources. Bypasses
    the SWR TTL. Returns per-source labels ('remote' | 'cache' | 'none')
    so the React toast can tell the user whether the network worked."""
    catalog_source = _force_refresh("games",   REMOTE_CATALOG_URL)
    news_source    = _force_refresh("news",    REMOTE_NEWS_URL)
    updates_source = _force_refresh("updates", REMOTE_UPDATES_URL)
    return {
        "games":          get_all_games(),
        "news":           get_news(),
        "updates":        list_updates(),
        "catalog_source": catalog_source,
        "news_source":    news_source,
        "updates_source": updates_source,
    }


@eel.expose
def get_game(game_id: str) -> dict:
    return _game_payload(game_id)


@eel.expose
def scan_quick() -> dict:
    """Fast registry-only scan. (Kept for internal use; UI exposes deep only.)
    Persistence is handled inside game_detector.refresh_quick itself."""
    refresh_quick()
    return {"games": get_all_games(), "found": len(detected_cached())}


@eel.expose
def scan_deep() -> dict:
    """Walk every fixed drive looking for known game folders.
    Results are persisted to ~/.translation_manager/detected_games.json so
    the next launch starts pre-populated."""
    refresh_deep()
    return {"games": get_all_games(), "found": len(detected_cached())}


@eel.expose
def set_custom_path(game_id: str, path: str | None) -> dict:
    user_paths.set_path(game_id, path or None)
    return _game_payload(game_id)


@eel.expose
def clear_custom_path(game_id: str) -> dict:
    user_paths.set_path(game_id, None)
    return _game_payload(game_id)


@eel.expose
def enable_mod_for(game_id: str) -> dict:
    cfg = _config_for(game_id)
    base = _install_path(game_id)
    if cfg is None or base is None:
        return {"ok": False, "error": "no config or install path", "state": _mod_state(game_id)}
    ok, count, err = enable_mod(cfg, base)
    return {"ok": ok, "count": count, "error": err, "state": _mod_state(game_id)}


@eel.expose
def disable_mod_for(game_id: str) -> dict:
    cfg = _config_for(game_id)
    base = _install_path(game_id)
    if cfg is None or base is None:
        return {"ok": False, "error": "no config or install path", "state": _mod_state(game_id)}
    ok, count, err = disable_mod(cfg, base)
    return {"ok": ok, "count": count, "error": err, "state": _mod_state(game_id)}


@eel.expose
def uninstall_mod_for(game_id: str) -> dict:
    cfg = _config_for(game_id)
    base = _install_path(game_id)
    if cfg is None or base is None:
        return {"ok": False, "error": "no config or install path", "state": _mod_state(game_id)}
    ok, count, err = uninstall_mod(cfg, base)
    return {"ok": ok, "count": count, "error": err, "state": _mod_state(game_id)}


@eel.expose
def launch_game(game_id: str) -> dict:
    """Find the game's executable and spawn it. Returns the exe path or error."""
    cfg = _config_for(game_id)
    base = _install_path(game_id)
    if base is None:
        return {"ok": False, "error": "install path not set"}

    # Preferred: the validation_file from config (it's the real exe).
    exe: Path | None = None
    if cfg and cfg.validation_file:
        candidate = base / cfg.validation_file
        if candidate.exists():
            exe = candidate

    # Fallback: largest .exe in bin/x64 or bin/ or root.
    if exe is None:
        for sub in ("bin/x64", "bin", "."):
            d = base / sub
            if not d.exists():
                continue
            exes = sorted(d.glob("*.exe"), key=lambda p: p.stat().st_size, reverse=True)
            if exes:
                exe = exes[0]
                break

    if exe is None:
        return {"ok": False, "error": "executable not found"}

    try:
        subprocess.Popen([str(exe)], cwd=str(exe.parent))
        return {"ok": True, "exe": str(exe)}
    except OSError as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────
# Downloads — wire downloads.py into Eel.
# The progress callback runs on the worker thread; eel.* is thread-safe
# (the underlying gevent websocket handles cross-thread dispatch).
# ─────────────────────────────────────────────────────────────
def _push_download_progress(item_id: str, pct: float, speed_text: str, state: str) -> None:
    try:
        eel.update_download_progress(item_id, pct, speed_text, state)()  # type: ignore[attr-defined]
    except Exception:
        pass


_downloads.set_progress_callback(_push_download_progress)


@eel.expose
def list_updates() -> list[dict]:
    return _load_updates()


# ─────────────────────────────────────────────────────────────
# Live progress proxy — same data the public website displays.
# Pulls /api/progress?game=<id> via the SWR cache so the launcher's
# HomeView renders the universal ProgressDashboard instantly from the
# last-known-good snapshot, with a quiet background refresh.
# ─────────────────────────────────────────────────────────────
PROGRESS_API_BASE = "https://hebrew-translation-hub.vercel.app/api/progress"


def _fetch_progress(game_id: str) -> dict | None:
    """Single-shot fetch used by SWR. Returns:
       - dict on 200 with a JSON object body
       - None on 404 / non-dict body  (legitimately "no data" — cached as null)
       - raises on network / parse error          (SWR keeps the cached value)
    """
    r = requests.get(
        f"{PROGRESS_API_BASE}?game={game_id}",
        headers={"Accept": "application/json"},
        timeout=REMOTE_TIMEOUT,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else None


@eel.expose
def get_live_progress(game_id: str) -> dict | None:
    if not game_id:
        return None
    return swr_cache.swr("progress",
                         lambda: _fetch_progress(game_id),
                         sub_key=game_id,
                         ttl=30.0)


@eel.expose
def start_download(item_id: str) -> dict:
    """Resolve the item from the dynamic updates catalog, then hand it to the
    downloads engine. Lookup happens here (in main_eel) so downloads.py stays
    pure execution and doesn't need to know the source-of-truth."""
    item = next((u for u in _load_updates() if u.get("id") == item_id), None)
    if item is None:
        return {"ok": False, "error": "unknown item"}
    return _downloads.start(item)


@eel.expose
def cancel_download(item_id: str) -> dict:
    return _downloads.cancel(item_id)


@eel.expose
def open_folder(path: str) -> dict:
    """Open a folder in Windows Explorer."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": "path does not exist"}
    try:
        os.startfile(str(p))  # type: ignore[attr-defined]
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}


# ═════════════════════════════════════════════════════════════
# Auth bridge — Supabase OAuth (Google) + DRM ownership check
# ═════════════════════════════════════════════════════════════
#
# These four functions are the entire frontend-facing surface of the
# auth subsystem. Everything else (PKCE, loopback HTTP, token
# refresh, keyring storage) lives behind translation_manager.auth.
#
# All four return JSON-serializable dicts so the React frontend can
# treat them uniformly: `{ ok: bool, ... }` for actions, and the
# user object directly for `auth_me()` (or None).
#
# `auth_login()` is BLOCKING for as long as the user takes to
# complete the browser flow. Eel runs each exposed function on a
# worker thread, so this doesn't freeze the UI — but we cap the
# wait at 180 s so a forgotten browser tab doesn't pin a thread.

@eel.expose
def auth_login() -> dict:
    """Open browser → wait for OAuth callback → store tokens → return user.

    The blocking call (`_auth.login()`, which can sit on a
    threading.Event for up to 180 s waiting for the loopback callback)
    runs on a NATIVE OS thread so it never pins the Eel/gevent
    websocket loop. The handler greenlet then polls cooperatively via
    `gevent.sleep` while waiting on the OS thread's done-event.

    Why this matters: Eel's websocket transport runs on gevent. Without
    monkey-patching (Eel does not patch by default), `threading.Event`
    is the native blocking primitive — `event.wait()` from a greenlet
    halts the entire gevent loop, which means a second Eel call
    (`auth_abort_login`) cannot dispatch until the first returns. The
    user clicks "בטל וחזור" and nothing happens for 180 s. Running the
    blocker in an OS thread and polling cooperatively breaks the
    deadlock — gevent stays alive, the abort bridge fires instantly."""
    if not _auth_available or _auth is None:
        return {"ok": False, "error": f"auth-unavailable: {_auth_error or 'module not loaded'}"}

    # CRITICAL: run the blocking login() inside a GREENLET, not a native
    # OS thread. Eel/bottle_websocket invokes gevent.monkey.patch_all(),
    # which replaces the stdlib socket with a gevent-cooperative one.
    # That patched socket REQUIRES a gevent hub in the current thread to
    # dispatch I/O — the hub only exists on the thread the gevent event
    # loop runs on. Spawning a native threading.Thread moves the
    # subsequent requests.get/post calls off the hub-bearing thread, so
    # the first HTTPS read silently deadlocks (the auth_debug.log gets
    # stuck right between "storing initial tokens" and "fetching user
    # profile", i.e. exactly at the next outbound HTTPS read).
    #
    # gevent.spawn keeps the work in the hub's thread. The Eel handler
    # waits on a gevent.AsyncResult which yields cooperatively, so the
    # websocket loop keeps dispatching other Eel calls (including
    # auth_abort_login) while we wait — same UX guarantees as the
    # threading version was supposed to have, without the deadlock.
    import gevent                                                                 # type: ignore[import-not-found]
    from gevent.event import AsyncResult                                          # type: ignore[import-not-found]

    result_box: AsyncResult = AsyncResult()

    def _worker() -> None:
        try:
            user = _auth.login()
            result_box.set({"ok": True, "user": user})
        except _auth.AuthError as e:
            result_box.set({"ok": False, "error": str(e)})
        except BaseException as e:                                                # noqa: BLE001
            # BaseException catches KeyboardInterrupt / SystemExit /
            # GreenletExit / etc. so even an exotic crash resolves the
            # AsyncResult — the Eel handler returns a clean error
            # instead of leaving the React Promise unresolved forever.
            result_box.set({
                "ok":    False,
                "error": f'unexpected: {type(e).__name__}: {e}',
            })

    greenlet = gevent.spawn(_worker)

    # Outer safety cap. _auth.login()'s internal timeout is 180 s; this
    # 200 s wrap is belt-and-braces in case something exotic eats both
    # success AND failure paths inside the greenlet. AsyncResult.get
    # yields cooperatively to the gevent hub, so the websocket loop
    # stays responsive — auth_abort_login dispatches normally while we
    # wait, identical UX to a non-blocking handler.
    try:
        return result_box.get(timeout=200.0)
    except gevent.Timeout:
        try:
            greenlet.kill(block=False)
        except Exception:
            pass
        return {
            "ok":    False,
            "error": "Login did not complete within 200s. Try again.",
        }


@eel.expose
def auth_me() -> dict | None:
    """Return the cached user (refreshing token if needed) or None."""
    if not _auth_available or _auth is None:
        return None
    try:
        return _auth.me()
    except Exception:
        return None


@eel.expose
def auth_logout() -> dict:
    """Local sign-out — clears the OS keyring entry."""
    if not _auth_available or _auth is None:
        return {"ok": True}  # already effectively signed out
    try:
        _auth.logout()
        return {"ok": True}
    except Exception as e:  # pragma: no cover
        return {"ok": False, "error": str(e)}


@eel.expose
def auth_owns_game(game_id: str) -> bool:
    """DRM check — fails closed on any error."""
    if not _auth_available or _auth is None:
        return False
    try:
        return bool(_auth.owns_game(str(game_id)))
    except Exception:
        return False


@eel.expose
def auth_get_my_purchases() -> list[dict]:
    """All 'completed' purchases for the signed-in user, with the
    joined game row embedded. Powers the launcher's Personal Area.
    Returns [] when signed out or on any error (fail-closed)."""
    if not _auth_available or _auth is None:
        return []
    try:
        return _auth.get_purchases()
    except Exception as e:                              # pragma: no cover
        print(f"[auth_get_my_purchases] failed: {e}", flush=True)
        return []


@eel.expose
def auth_get_my_votes() -> list[str]:
    """Game-ids the signed-in user has voted for. Powers the votes
    count + "voted" markers in the launcher's Personal Area. Returns
    [] when signed out or on any error."""
    if not _auth_available or _auth is None:
        return []
    try:
        return _auth.get_votes()
    except Exception as e:                              # pragma: no cover
        print(f"[auth_get_my_votes] failed: {e}", flush=True)
        return []


@eel.expose
def auth_get_authorize_url() -> str | None:
    """Return the URL of the in-flight Google OAuth attempt so the
    AuthModal can offer a "copy link" affordance — useful when the OS
    default browser opened the wrong Chrome profile and the user wants
    to paste the URL into a different profile instead. Returns None
    when no attempt is active. The URL embeds a PKCE challenge that
    only this process can redeem, so sharing it with the user is
    safe."""
    if not _auth_available or _auth is None:
        return None
    try:
        return _auth.get_last_authorize_url()
    except Exception:
        return None


@eel.expose
def auth_abort_login() -> dict:
    """Tear down any in-flight Google OAuth attempt RIGHT NOW so the
    next login() call can rebind port 8085 immediately.

    Without this, the user clicking "בטל וחזור" only resets the React
    UI — the Python loopback HTTP server keeps blocking in
    await_code() for the full 180s timeout, holding port 8085 and
    queueing every subsequent Eel auth_login call behind it. That's
    what produced the "multi-window stacking" bug.

    Returns { ok: true, aborted: bool }. aborted=False means there
    was no active listener (idempotent / nothing to do)."""
    if not _auth_available or _auth is None:
        return {"ok": False, "error": "auth-unavailable"}
    try:
        aborted = bool(_auth.abort_login())
        return {"ok": True, "aborted": aborted}
    except Exception as e:                                                    # pragma: no cover
        return {"ok": False, "error": f"unexpected: {e}"}


# Email/password bridges — keep the entire credential flow inside the
# launcher UI without bouncing through the system browser. Tokens land
# in the OS keyring the same way as the OAuth flow, so me() / owns_game
# / sign-out are agnostic about which entry point was used.

@eel.expose
def auth_signin_password(email: str, password: str) -> dict:
    if not _auth_available or _auth is None:
        return {"ok": False, "error": f"auth-unavailable: {_auth_error or 'module not loaded'}"}
    if not email or not password:
        return {"ok": False, "error": "missing-credentials"}
    try:
        user = _auth.signin_with_password(str(email), str(password))
        return {"ok": True, "user": user}
    except _auth.AuthError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:                                                    # pragma: no cover
        return {"ok": False, "error": f"unexpected: {e}"}


@eel.expose
def auth_signup_password(email: str, password: str, full_name: str = "") -> dict:
    if not _auth_available or _auth is None:
        return {"ok": False, "error": f"auth-unavailable: {_auth_error or 'module not loaded'}"}
    if not email or not password:
        return {"ok": False, "error": "missing-credentials"}
    try:
        user = _auth.signup_with_password(str(email), str(password), str(full_name or ""))
        # `confirmed=True` means a session was returned and stored; the
        # UI should treat it like a successful sign-in. `False` means
        # the project requires email confirmation — UI shows "check
        # your inbox" and stays signed out.
        return {"ok": True, "user": user, "confirmed": bool(user.get("confirmed", False))}
    except _auth.AuthError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:                                                    # pragma: no cover
        return {"ok": False, "error": f"unexpected: {e}"}


# ═════════════════════════════════════════════════════════════
# Boot
# ═════════════════════════════════════════════════════════════
ROOT = Path(__file__).parent
FRONTEND_DIST = ROOT / "frontend" / "dist"


def _on_window_closed(_page: str, _websockets: list) -> None:
    """Eel close_callback. Force-exits the Python process the moment the
    last websocket dies — otherwise Chromium's --app subprocess can linger
    for several seconds as a black leftover window. os._exit(0) skips
    atexit handlers, which is what we want: every persistence point
    (games.json, detected_games.json, paths.json) already writes-through
    on each mutation, so there's nothing left to flush at shutdown."""
    import os
    print("[eel] Window closed — exiting.", flush=True)
    os._exit(0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true",
                    help="Skip frontend serving — assume Vite dev server on :5173")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    # game_detector seeds its cache from disk at import time (no work to do
    # here). We deliberately do NOT run an automatic scan on boot — the user
    # owns scanning via the explicit "Full Drive Scan" button.

    if not _has_any_cache() and not _ping_api():
        _show_no_internet_dialog()
        sys.exit(1)

    if args.dev:
        # Vite dev mode — Eel only serves /eel.js + JSON-RPC; the React app
        # runs on http://localhost:5173 with `npm run dev`.
        eel.init(str(FRONTEND_DIST if FRONTEND_DIST.exists() else ROOT / "frontend"))
        print(f"[eel] DEV mode — Vite frontend at http://localhost:5173, "
              f"Eel API on :{args.port}")
        try:
            eel.start({"port": 5173}, mode=None, host="localhost", port=args.port,
                      block=True, suppress_error=True,
                      close_callback=_on_window_closed)
        except (SystemExit, KeyboardInterrupt):
            pass
    else:
        if not FRONTEND_DIST.exists():
            print(f"[eel] frontend/dist/ not built. Run: cd frontend && npm run build")
            sys.exit(2)
        eel.init(str(FRONTEND_DIST))
        print(f"[eel] PROD mode — serving {FRONTEND_DIST}")
        # Hardening flags so the Chrome --app window doesn't feel like a browser:
        #   --disable-features=Translate,TranslateUI  : kill the "translate this page" bar
        #   --no-first-run / --no-default-browser-check : silence Chromium nags
        #   --disable-pinch                            : laptop trackpads can't pinch-zoom
        #   --overscroll-history-navigation=0          : no back/forward swipe gesture
        #   --disable-background-mode                  : Chrome doesn't linger after close
        #   --disable-features=AutofillServerCommunication : no autofill chatter
        # (`--disable-context-menu` is not a real Chromium flag — the React
        #  layer handles right-click suppression instead.)
        chrome_flags = [
            "--disable-features=Translate,TranslateUI,AutofillServerCommunication",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-pinch",
            "--overscroll-history-navigation=0",
            "--disable-background-mode",
        ]
        try:
            eel.start("index.html", size=(1400, 900), port=args.port,
                      mode="chrome", block=True,
                      cmdline_args=chrome_flags,
                      disable_cache=True,
                      close_callback=_on_window_closed)
        except (SystemExit, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    main()
