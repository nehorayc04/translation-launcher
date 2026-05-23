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
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import eel
import requests

from translation_manager import downloads as _downloads
from translation_manager import game_mod as _game_mod
from translation_manager import mod_source as _mod_source
from translation_manager import paths as user_paths
from translation_manager import steam_apply as _steam_apply
from translation_manager import steam_mod as _steam_mod
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
from translation_manager.cp2077_language import (
    enable_arabic_slot as _cp2077_enable_arabic_slot,
    restore_language   as _cp2077_restore_language,
)

# Catalog id of the Cyberpunk 2077 entry. Hard-coded because the
# Arabic-slot flip is specific to that game's Hebrew mod and must
# never trigger for any other title.
_CP2077_ID = "cyberpunk"

# Installed launcher version. MUST stay in lock-step with
# installer.iss `#define AppVersion`. The in-app self-updater
# (get_launcher_update_info) compares this against the release feed.
LAUNCHER_VERSION = "1.1.0"

# Per-build identity, baked by build_exe.bat into translation_manager/
# _build_info.py (a fresh UTC timestamp every build). The version string
# stays "1.1.0" forever — re-released in place — so the self-updater can't
# tell two builds apart by version alone. BUILD_ID lets it: when the
# release feed carries a different build-id than this one, an update is
# offered even though the version is unchanged. Dev runs (no build step)
# have no _build_info.py → "dev", and the build-id check is skipped.
try:
    from translation_manager._build_info import BUILD_ID  # type: ignore[attr-defined]
except Exception:                                          # noqa: BLE001
    BUILD_ID = "dev"

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
REMOTE_CATALOG_URL  = "https://hebrew-translation-hub.vercel.app/api/games"
REMOTE_SOFTWARE_URL = "https://hebrew-translation-hub.vercel.app/api/software"
REMOTE_NEWS_URL     = "https://hebrew-translation-hub.vercel.app/api/news"
REMOTE_UPDATES_URL  = "https://hebrew-translation-hub.vercel.app/api/updates"
REMOTE_LAUNCHER_URL = "https://hebrew-translation-hub.vercel.app/api/launcher"
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


def _try_software_remote() -> list[dict] | None:
    """Fetch /api/software, drop entries that aren't flagged
    show_on_launcher. Returns None on any network/parse failure so SWR
    keeps serving the cached value."""
    data = _try_remote(REMOTE_SOFTWARE_URL)
    if data is None:
        return None
    return [s for s in data if s.get("showOnLauncher") is not False]


def _load_software() -> list[dict]:
    """Software catalog visible to the launcher. SWR-cached: instant
    return from disk, background refresh from /api/software."""
    data = swr_cache.swr("software", _try_software_remote, ttl=_REMOTE_CACHE_TTL)
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
    """SWR's background refresher / the idle poller call this when fresh
    data differs from the cached value. We forward it to the frontend's
    `cache_refreshed` handler (registered in frontend/public/eel-bindings.js).

    'games' and 'software' are re-enriched here with THIS machine's
    install/mod state: the SWR cache stores only the bare remote
    catalog, but the frontend's setGames()/setSoftware() expect the full
    enriched shape — pushing a bare row would silently drop every
    install/mod badge on a live update.

    Wrapped in try/except because the call is meaningless until the
    React app has connected — early firings before the websocket exists
    are just no-ops."""
    try:
        if kind == "games" and isinstance(data, list):
            data = _enrich_catalog(data)
        elif kind == "software" and isinstance(data, list):
            data = _enrich_software(data)
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


def _enrich_game_row(cg: dict) -> dict:
    """Enrich one bare catalog row with THIS machine's install path + mod
    state. Shared by _game_payload, get_all_games and the cache_refreshed
    push so every path emits an identical, fully-shaped game dict."""
    gid  = cg.get("id", "")
    base = _install_path(gid)
    cfg  = _config_for(gid)
    has_mod = cfg is not None and bool(cfg.mod_files)
    return {
        **cg,
        "install_path": str(base) if base else None,
        "is_installed": base is not None,
        "has_mod_support": has_mod,
        "mod_state": _mod_state(gid),
    }


def _game_payload(game_id: str) -> dict:
    """Catalog entry enriched with install path + mod state."""
    cg = _catalog_by_id(game_id)
    if cg is None:
        return {}
    return _enrich_game_row(cg)


# ═════════════════════════════════════════════════════════════
# @eel.expose — public API surface for the React frontend
# ═════════════════════════════════════════════════════════════
_AVAIL_RANK = {"available": 0, "in-progress": 1, "coming-soon": 2, "planned": 3}


def _enrich_catalog(items: list[dict]) -> list[dict]:
    """Bare remote catalog → sorted, install/mod-enriched list — the exact
    shape get_all_games() returns and the frontend's setGames() expects."""
    items_sorted = sorted(
        items,
        key=lambda g: (_AVAIL_RANK.get(g.get("availability", ""), 99),
                       g.get("titleEn", "")),
    )
    return [_enrich_game_row(g) for g in items_sorted if g.get("id")]


@eel.expose
def get_all_games() -> list[dict]:
    """Full catalog (sorted by availability) enriched with install + mod state."""
    return _enrich_catalog(_load_catalog())


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


def _mod_progress_cb(phase: str, pct: float, detail: str) -> None:
    """Forward a steam_mod / game_mod / mod_source progress tick to the
    React UI. The trailing () is what actually dispatches the eel call —
    same form as _push_download_progress / _push_cache_event. Wrapped so
    a UI hiccup can never crash the install worker."""
    try:
        eel.mod_install_progress(phase, round(pct, 1), detail)()  # type: ignore[attr-defined]
    except Exception:
        pass


@eel.expose
def apply_steam_translation() -> dict:
    """Install the Hebrew Steam translation.

    Cache-first: if the local cache is already populated, just enable it.
    On a cache miss, fetch the archive from the private GitHub repo via
    the Cloudflare Worker proxy (download → verify SHA-256 → extract),
    populate the cache, then enable."""
    if not _steam_mod.is_cached():
        try:
            extracted, version = _mod_source.fetch_and_extract(_mod_progress_cb)
        except _mod_source.IntegrityError as e:
            return {"ok": False, "error": f"כשל אימות שלמות הקובץ: {e}"}
        except _mod_source.ModSourceError as e:
            return {"ok": False, "error": f"כשל הורדה מ-GitHub: {e}"}
        try:
            r = _steam_mod.populate_cache(extracted, version)
        finally:
            # Always remove the temp dir (archive zip + extracted tree),
            # whether populate_cache succeeded or not — no clutter left.
            shutil.rmtree(extracted.parent, ignore_errors=True)
        if not r.get("ok"):
            return r
    return _steam_mod.enable(_mod_progress_cb)


@eel.expose
def get_steam_mod_state() -> dict:
    """{cached, enabled, version} — drives the AppsView button state machine."""
    return _steam_mod.status()


@eel.expose
def set_steam_mod_enabled(enabled: bool) -> dict:
    """Toggle the mod on/off — pure local file ops, no re-download."""
    if enabled:
        return _steam_mod.enable(_mod_progress_cb)
    return _steam_mod.disable(_mod_progress_cb)


@eel.expose
def clear_steam_mod_cache() -> dict:
    """Revert Steam to its originals and delete the local mod cache."""
    return _steam_mod.clear_cache()


# ─────────────────────────────────────────────────────────────
# Download-distributed GAME mods (e.g. Cyberpunk 2077).
# A game whose GameConfig carries a `mod_slug` is fetched through the
# Cloudflare Worker proxy and managed via translation_manager.game_mod:
#   download → cache → install → disable → clear-cache.
# Paid mods (catalog priceCents > 0) gate install on auth ownership.
# ─────────────────────────────────────────────────────────────
def _game_price_cents(game_id: str) -> int:
    cg = _catalog_by_id(game_id) or {}
    try:
        return int(cg.get("priceCents") or 0)
    except (TypeError, ValueError):
        return 0


@eel.expose
def get_game_mod_state(game_id: str) -> dict:
    """State for a download-distributed game mod (drives GameDetailPanel).
    {cached, installed, version, owned, priceCents, modSlug, hasPath}."""
    cfg   = _config_for(game_id)
    base  = _install_path(game_id)
    price = _game_price_cents(game_id)
    slug  = cfg.mod_slug if cfg else ""
    if not slug:
        return {
            "cached": False, "installed": False, "version": None,
            "owned": True, "priceCents": price, "modSlug": "",
            "hasPath": base is not None,
        }
    st = _game_mod.status(game_id, base, cfg.mod_files if cfg else [])
    # Free mods are always "owned"; paid mods consult the auth DRM check.
    owned = True if price <= 0 else auth_owns_game(game_id)
    return {
        **st,
        "owned":      owned,
        "priceCents": price,
        "modSlug":    slug,
        "hasPath":    base is not None,
    }


def _cp2077_disable_crash_reporter(game_root) -> None:
    """Rename bin\\x64\\REDEngineErrorReporter.exe → .bak.

    Running CP2077 in the Arabic locale slot fires CDPR's crash-reporter
    window on the engine's teardown when quitting — harmless (the
    session already ended, saves are safe) but ugly. With the reporter
    exe renamed the engine simply can't spawn it, so no window appears.
    This is the per-mod equivalent of the manual fix applied to the
    project's own game copy. Reversible — see the restore fn below."""
    if not game_root:
        return
    try:
        exe = Path(game_root) / "bin" / "x64" / "REDEngineErrorReporter.exe"
        bak = exe.with_name(exe.name + ".bak")
        if exe.is_file() and not bak.exists():
            exe.rename(bak)
            print("[cp2077] crash reporter disabled", flush=True)
    except OSError as e:                                # pragma: no cover
        print(f"[cp2077] disable crash reporter failed: {e}", flush=True)


def _cp2077_restore_crash_reporter(game_root) -> None:
    """Undo _cp2077_disable_crash_reporter — restore REDEngineErrorReporter.exe
    so removing the Hebrew mod leaves the game's crash reporting intact."""
    if not game_root:
        return
    try:
        exe = Path(game_root) / "bin" / "x64" / "REDEngineErrorReporter.exe"
        bak = exe.with_name(exe.name + ".bak")
        if bak.is_file() and not exe.exists():
            bak.rename(exe)
            print("[cp2077] crash reporter restored", flush=True)
    except OSError as e:                                # pragma: no cover
        print(f"[cp2077] restore crash reporter failed: {e}", flush=True)


def _run_game_mod_install(game_id: str) -> None:
    """Background worker: download (if needed) + install a game mod.

    Runs as a gevent GREENLET on the launcher's main hub (see
    download_and_install_game_mod for why a real thread is wrong here).
    Streams mod_install_progress ticks as it works and emits a terminal
    'done' / 'error' tick the GameDetailPanel watches for."""
    try:
        cfg  = _config_for(game_id)
        base = _install_path(game_id)
        if not _game_mod.is_cached(game_id):
            r = _game_mod.download_and_cache(game_id, cfg.mod_slug, _mod_progress_cb)
            if not r.get("ok"):
                _mod_progress_cb("error", 0, r.get("error") or "כשל בהורדת התרגום")
                return
        r = _game_mod.install(game_id, base, _mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהתקנת התרגום")
            return
        if game_id == _CP2077_ID:
            try:
                _cp2077_enable_arabic_slot()
            except Exception as e:                      # pragma: no cover
                print(f"[cp2077_language] enable failed: {e}", flush=True)
            _cp2077_disable_crash_reporter(base)
        _mod_progress_cb("done", 100, "ההתקנה הושלמה")
    except Exception as e:                              # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def download_and_install_game_mod(game_id: str) -> dict:
    """Kick off download+install and return at once. Progress + a
    terminal done/error tick stream over the mod_install_progress
    channel; the GameDetailPanel drives its bar from onModProgress."""
    cfg  = _config_for(game_id)
    base = _install_path(game_id)
    if cfg is None or not cfg.mod_slug:
        return {"ok": False, "error": "המשחק אינו נתמך להורדה אוטומטית"}
    if base is None:
        return {"ok": False, "error": "נתיב המשחק לא הוגדר — הגדר אותו תחילה בהגדרות"}
    # DRM gate — defense-in-depth; the UI gates too.
    if _game_price_cents(game_id) > 0 and not auth_owns_game(game_id):
        return {"ok": False, "error": "המשחק טרם נרכש"}

    # gevent GREENLET, NOT a real thread: eel's progress callback
    # (eel.mod_install_progress(...)()) is bound to the launcher's main
    # gevent hub — invoking it from a separate OS thread throws every
    # time, so nothing reaches the UI (the install still finishes, but
    # the bar sits at 0% and only a panel re-mount shows the result).
    # A greenlet shares the hub: requests cooperatively yields and every
    # progress tick — and the terminal 'done' — streams live.
    import gevent
    gevent.spawn(_run_game_mod_install, game_id)
    return {"ok": True, "started": True}


@eel.expose
def set_game_mod_installed(game_id: str, installed: bool) -> dict:
    """Toggle a cached game mod: install/reinstall (cache → game folder)
    or disable (remove from the game folder, keep the cache copy)."""
    cfg  = _config_for(game_id)
    base = _install_path(game_id)
    if cfg is None or not cfg.mod_slug or base is None:
        return {"ok": False, "error": "פעולה לא זמינה",
                "state": get_game_mod_state(game_id)}
    if installed:
        r = _game_mod.install(game_id, base, _mod_progress_cb)
        hook = _cp2077_enable_arabic_slot
    else:
        r = _game_mod.disable(game_id, base)
        hook = _cp2077_restore_language
    lang = None
    if r.get("ok") and game_id == _CP2077_ID:
        try:
            lang = hook()
        except Exception as e:                          # pragma: no cover
            print(f"[cp2077_language] toggle failed: {e}", flush=True)
            lang = {"ok": False, "error": str(e)}
        # Keep the crash-reporter rename in lock-step with the mod state.
        if installed:
            _cp2077_disable_crash_reporter(base)
        else:
            _cp2077_restore_crash_reporter(base)
    return {**r, "language": lang, "state": get_game_mod_state(game_id)}


@eel.expose
def clear_game_mod_cache(game_id: str) -> dict:
    """Remove a game mod entirely — from the game folder AND the launcher
    cache. A later install must re-download."""
    cfg  = _config_for(game_id)
    base = _install_path(game_id)
    # If CP2077's mod is currently active, restore the language slot +
    # the crash reporter before wiping the mod from the machine.
    if game_id == _CP2077_ID:
        st = _game_mod.status(game_id, base, cfg.mod_files if cfg else [])
        if st.get("installed"):
            try:
                _cp2077_restore_language()
            except Exception as e:                      # pragma: no cover
                print(f"[cp2077_language] restore (clear) failed: {e}", flush=True)
        _cp2077_restore_crash_reporter(base)
    r = _game_mod.clear_cache(game_id, base, cfg.mod_files if cfg else [])
    return {**r, "state": get_game_mod_state(game_id)}


@eel.expose
def open_purchase_page(game_id: str) -> dict:
    """Open the website's per-game checkout deep link in the user's
    default browser. The website's GamesPage component auto-opens the
    matching modal (one click away from PayPal). After payment the
    launcher re-checks ownership via the post-purchase burst poll in
    GameDetailPanel."""
    import webbrowser
    url = f"https://hebrew-translation-hub.vercel.app/games/{game_id}?buy=1"
    try:
        webbrowser.open(url)
        return {"ok": True, "url": url}
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


@eel.expose
def enable_mod_for(game_id: str) -> dict:
    cfg = _config_for(game_id)
    base = _install_path(game_id)
    if cfg is None or base is None:
        return {"ok": False, "error": "no config or install path", "state": _mod_state(game_id)}
    ok, count, err = enable_mod(cfg, base)
    lang_result = None
    # One-click install: flip CP2077 to the Arabic locale slot so the
    # Hebrew CR2W archive renders through CDPR's RTL/bidi pipeline.
    # Best-effort — failures degrade silently so they never block the
    # file-level mod operation that already succeeded above.
    if ok and game_id == _CP2077_ID:
        try:
            lang_result = _cp2077_enable_arabic_slot()
        except Exception as e:  # pragma: no cover — defensive
            print(f"[cp2077_language] enable failed: {e}", flush=True)
            lang_result = {"ok": False, "error": str(e)}
    return {
        "ok": ok, "count": count, "error": err, "state": _mod_state(game_id),
        "language": lang_result,
    }


@eel.expose
def disable_mod_for(game_id: str) -> dict:
    cfg = _config_for(game_id)
    base = _install_path(game_id)
    if cfg is None or base is None:
        return {"ok": False, "error": "no config or install path", "state": _mod_state(game_id)}
    ok, count, err = disable_mod(cfg, base)
    lang_result = None
    if ok and game_id == _CP2077_ID:
        try:
            lang_result = _cp2077_restore_language()
        except Exception as e:  # pragma: no cover — defensive
            print(f"[cp2077_language] restore (disable) failed: {e}", flush=True)
            lang_result = {"ok": False, "error": str(e)}
    return {
        "ok": ok, "count": count, "error": err, "state": _mod_state(game_id),
        "language": lang_result,
    }


@eel.expose
def uninstall_mod_for(game_id: str) -> dict:
    cfg = _config_for(game_id)
    base = _install_path(game_id)
    if cfg is None or base is None:
        return {"ok": False, "error": "no config or install path", "state": _mod_state(game_id)}
    ok, count, err = uninstall_mod(cfg, base)
    lang_result = None
    if ok and game_id == _CP2077_ID:
        try:
            lang_result = _cp2077_restore_language()
        except Exception as e:  # pragma: no cover — defensive
            print(f"[cp2077_language] restore (uninstall) failed: {e}", flush=True)
            lang_result = {"ok": False, "error": str(e)}
    return {
        "ok": ok, "count": count, "error": err, "state": _mod_state(game_id),
        "language": lang_result,
    }


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


def _enrich_software(items: list[dict]) -> list[dict]:
    """Tag each software row with THIS machine's install presence
    (`installed` / `installPath` / `installExe`), honouring the user's
    "forgotten" list. Works on COPIES so the bare SWR cache stays clean
    (mutating it in place would poison the poller's change-detection)."""
    from translation_manager import software_detector
    from translation_manager import launcher_prefs
    out = [dict(s) for s in items]
    presence = software_detector.scan_all([s.get("id", "") for s in out if s.get("id")])
    # Software ids the user "forgot" in Settings → report as not-installed
    # (path blanked) until the next full scan re-detects them.
    cleared = set(launcher_prefs.get_cleared_software())
    for s in out:
        sid = s.get("id")
        if isinstance(sid, str):
            if sid in cleared:
                s["installed"]   = False
                s["installPath"] = ""
                s["installExe"]  = ""
            else:
                info = presence.get(sid) or {}
                s["installed"]    = bool(info.get("installed"))
                s["installPath"]  = info.get("path") or ""
                s["installExe"]   = info.get("exe")  or ""
    return out


@eel.expose
def get_all_software() -> list[dict]:
    """Software catalog visible to the launcher. Returns the same shape
    as /api/software but filtered to entries flagged show_on_launcher.

    Every entry is enriched with a local-presence snapshot
    (`installed`, `path`, `exe`) from `software_detector.scan_all()`
    so the React side can render an "installed" chip without a
    separate round-trip on first paint."""
    return _enrich_software(_load_software())


@eel.expose
def scan_software() -> dict:
    """Full re-scan of installed software. Used by the "סרוק" button under
    the תוכנות tab — also clears any "forgotten" software paths so a
    cleared entry is re-detected and lands back under "מותקנות"."""
    from translation_manager import launcher_prefs
    launcher_prefs.clear_all_cleared_software()
    return {"software": get_all_software()}


@eel.expose
def clear_software_path(software_id: str) -> dict:
    """"Forget" a software's auto-detected install path. The entry shows
    as not-installed in the תוכנות catalog until the next full scan
    (scan_software) re-detects it. Drives the Settings "נקה" button."""
    from translation_manager import launcher_prefs
    launcher_prefs.add_cleared_software(software_id)
    return {"software": get_all_software()}


# ─────────────────────────────────────────────────────────────
# Launcher window/lifecycle prefs (close-to-tray + autostart)
# ─────────────────────────────────────────────────────────────
@eel.expose
def get_launcher_prefs() -> dict:
    """Snapshot consumed by the React frontend on boot. Drives:
       - first-launch close-behavior modal (when closeBehavior is null)
       - SettingsView toggles (keep-running-on-close, start-with-windows)
       - the static version label in the sidebar footer."""
    from translation_manager import autostart, launcher_prefs
    return {
        "closeBehavior": launcher_prefs.get_close_behavior(),       # "minimize" | "close" | None
        "startWithOs":   autostart.is_enabled(),
    }


@eel.expose
def set_close_behavior(behavior: str | None) -> dict:
    """Persist the close-behavior choice. `None` resets it (next launch
    will re-show the first-launch modal). Returns the fresh prefs
    snapshot so the React side can sync without a second call."""
    from translation_manager import autostart, launcher_prefs
    if behavior in ("minimize", "close"):
        ok = launcher_prefs.set_close_behavior(behavior)            # type: ignore[arg-type]
    elif behavior in (None, "", "null"):
        ok = launcher_prefs.clear_close_behavior()
    else:
        return {"ok": False, "error": f"invalid-behavior:{behavior!r}"}
    return {
        "ok": ok,
        "closeBehavior": launcher_prefs.get_close_behavior(),
        "startWithOs":   autostart.is_enabled(),
    }


@eel.expose
def set_start_with_os(enabled: bool) -> dict:
    """Write or remove the HKCU autostart Run-key entry. Mirrors the
    state into launcher_prefs.json so the UI stays in sync with the
    actual registry (in case a sysadmin removes the entry externally).
    """
    from translation_manager import autostart, launcher_prefs
    if enabled:
        ok, err = autostart.enable()
    else:
        ok, err = autostart.disable()
    launcher_prefs.set_start_with_os(autostart.is_enabled())
    return {
        "ok": ok,
        "error": err,
        "startWithOs":   autostart.is_enabled(),
        "closeBehavior": launcher_prefs.get_close_behavior(),
    }


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


# ─────────────────────────────────────────────────────────────
# Launcher self-update — in-app download + silent install.
# ─────────────────────────────────────────────────────────────
# The "הורדות ועדכונים" tab carries a persistent panel that checks the
# /api/launcher release feed, downloads the installer in-app with a
# live progress bar, verifies its SHA-256, then runs it silently
# (/VERYSILENT — no external wizard window). The installer's
# PrepareToInstall hook force-closes this process; its [Run] entry
# relaunches the freshly-installed version.

def _parse_version(v: str) -> tuple:
    """'v1.2.3' / '1.2.3' → (1, 2, 3). Non-numeric junk → 0."""
    cleaned = (v or "").strip().lstrip("vV")
    out: list[int] = []
    for part in cleaned.split(".")[:4]:
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out)


def _version_is_newer(latest: str, current: str) -> bool:
    try:
        return _parse_version(latest) > _parse_version(current)
    except Exception:
        return False


@eel.expose
def get_launcher_update_info() -> dict:
    """Check the release feed. Returns current-vs-latest version and
    whether an update is available. Network failures come back as a
    soft `error` string — the panel degrades gracefully, never throws.

    Update detection is version-OR-build: a higher version, OR the SAME
    version carrying a different build-id than this build. The launcher
    re-releases in place as v1.1.0, so without the build-id arm the
    self-updater would never fire on a re-released build."""
    info: dict = {
        "currentVersion":  LAUNCHER_VERSION,
        "latestVersion":   LAUNCHER_VERSION,
        "updateAvailable": False,
        "downloadUrl":     None,
        "sizeBytes":       0,
        "sizeMb":          0.0,
        "notes":           "",
        "sha256":          None,
        "currentBuildId":  BUILD_ID,
        "latestBuildId":   None,
        "error":           None,
    }
    try:
        r = requests.get(REMOTE_LAUNCHER_URL, timeout=REMOTE_TIMEOUT)
        if r.status_code == 204:
            return info                                  # no release marked current
        r.raise_for_status()
        data = r.json()
        latest = str(data.get("version") or "").strip()
        info["latestVersion"] = latest or LAUNCHER_VERSION
        info["downloadUrl"]   = data.get("downloadUrl")
        info["sizeBytes"]     = int(data.get("sizeBytes") or 0)
        info["sizeMb"]        = float(data.get("sizeMb") or 0.0)
        info["notes"]         = data.get("notes") or ""
        info["sha256"]        = data.get("sha256") or None
        server_build          = str(data.get("buildId") or "").strip()
        info["latestBuildId"] = server_build or None
        # Same version but a different build-id is still an update. Skipped
        # for a dev run (BUILD_ID == "dev") or when the feed has no build-id.
        build_differs = bool(
            server_build
            and BUILD_ID != "dev"
            and server_build != BUILD_ID
        )
        info["updateAvailable"] = bool(
            latest
            and data.get("downloadUrl")
            and (_version_is_newer(latest, LAUNCHER_VERSION) or build_differs)
        )
    except Exception as e:                               # pragma: no cover — network
        info["error"] = str(e)
    return info


def _emit_update_progress(phase: str, pct: float, detail: str) -> None:
    """Push one progress tick to the React self-update panel. Best-effort."""
    try:
        eel.launcher_update_progress(phase, round(float(pct), 1), detail)()  # type: ignore[attr-defined]
    except Exception:
        pass


def _run_launcher_update() -> None:
    """Background worker: download installer → verify SHA-256 → run it
    silently. Streams progress back through launcher_update_progress."""
    import hashlib
    import tempfile
    import time

    info = get_launcher_update_info()
    url = info.get("downloadUrl")
    if not url:
        _emit_update_progress("error", 0, info.get("error") or "אין קישור הורדה זמין")
        return

    expected_sha = (info.get("sha256") or "").strip().lower()
    total = int(info.get("sizeBytes") or 0)

    dest_dir = Path(tempfile.gettempdir()) / "translation-manager-update"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _emit_update_progress("error", 0, f"לא ניתן ליצור תיקיית הורדה: {e}")
        return
    installer = dest_dir / "TranslationManager-Setup-latest.exe"

    # ── Download with live progress ─────────────────────────────
    try:
        _emit_update_progress("download", 0, "מתחבר לשרת ההורדות…")
        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            if not total:
                total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            start = time.time()
            last_emit = 0.0
            with open(installer, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=262144):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    done += len(chunk)
                    now = time.time()
                    # Throttle UI pushes to ~5/sec so the bridge isn't flooded.
                    if now - last_emit >= 0.2:
                        last_emit = now
                        pct     = (done / total * 100) if total else 0.0
                        elapsed = max(0.001, now - start)
                        speed   = done / elapsed                       # bytes/sec
                        detail  = (
                            f"{done / 1048576:.1f} / {total / 1048576:.1f} MB"
                            f"  ·  {speed / 1048576:.1f} MB/s"
                        ) if total else f"{done / 1048576:.1f} MB"
                        _emit_update_progress("download", min(pct, 100.0), detail)
        _emit_update_progress("download", 100, "ההורדה הושלמה")
    except Exception as e:
        _emit_update_progress("error", 0, f"שגיאת הורדה: {e}")
        return

    # ── Verify SHA-256 (skip only if the feed carries no hash) ──
    if expected_sha:
        try:
            _emit_update_progress("verify", 0, "מאמת את תקינות הקובץ…")
            h = hashlib.sha256()
            with open(installer, "rb") as fh:
                for blk in iter(lambda: fh.read(1048576), b""):
                    h.update(blk)
            if h.hexdigest().lower() != expected_sha:
                _emit_update_progress(
                    "error", 0,
                    "אימות הקובץ נכשל — ההורדה כנראה פגומה. נסה שוב.",
                )
                return
            _emit_update_progress("verify", 100, "הקובץ אומת בהצלחה")
        except Exception as e:
            _emit_update_progress("error", 0, f"שגיאת אימות: {e}")
            return

    # ── Run the installer silently ──────────────────────────────
    # /VERYSILENT       — no wizard window at all
    # /SUPPRESSMSGBOXES — auto-answer prompts
    # /NORESTART        — never reboot the machine
    # The installer's PrepareToInstall hook taskkills THIS process
    # mid-wait; its [Run] entry then launches the new version.
    try:
        _emit_update_progress(
            "launch", 100,
            "מריץ את ההתקנה — האפליקציה תיסגר ותיפתח מחדש בגרסה החדשה…",
        )
        proc = subprocess.Popen(
            [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            close_fds=True,
        )
    except Exception as e:
        _emit_update_progress("error", 0, f"כשל בהפעלת קובץ ההתקנה: {e}")
        return

    # If the install proceeds, PrepareToInstall kills us during this
    # wait and we never return. If we DO return, the user declined the
    # UAC prompt (or the installer aborted) — surface it, stay alive.
    #
    # Cooperative poll instead of proc.wait() so the gevent hub keeps
    # serving the websocket + the catalog poller while the installer
    # works — otherwise the UI freezes for the full install duration on
    # the rare path where we DON'T get killed mid-wait.
    import gevent
    code: int | None = None
    while True:
        code = proc.poll()
        if code is not None:
            break
        gevent.sleep(0.3)
    _emit_update_progress(
        "error", 0,
        f"ההתקנה לא הושלמה — ייתכן שבוטלה בחלון ההרשאות (קוד {code}).",
    )


@eel.expose
def start_launcher_update() -> dict:
    """Kick the self-update on a gevent GREENLET so the eel RPC returns at
    once AND progress pushes work — eel.launcher_update_progress(...)()
    is bound to the main gevent hub; firing it from a separate OS thread
    silently drops every tick (that's the exact bug that left the
    download progress bar frozen at 0% for the entire transfer).
    `requests` is monkey-patched (socket/ssl/select) so its blocking
    .read()s cooperatively yield, and the greenlet doesn't pin the hub."""
    import gevent
    gevent.spawn(_run_launcher_update)
    return {"ok": True}


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
    """DRM check — fails closed on any error.

    Logs every call to launcher.log so a "the launcher thinks I own the
    game but I never paid" report can be diagnosed remotely: the log
    line shows the boolean result + the game id we checked. Pair with
    the more detailed log inside `auth.manager.owns_game` (user_id +
    HTTP status + row count returned)."""
    import logging
    log = logging.getLogger("launcher")
    if not _auth_available or _auth is None:
        log.info("auth_owns_game(%s) → False [auth unavailable]", game_id)
        return False
    try:
        result = bool(_auth.owns_game(str(game_id)))
        log.info("auth_owns_game(%s) → %s", game_id, result)
        return result
    except Exception as e:
        log.warning("auth_owns_game(%s) failed: %s", game_id, e)
        return False


@eel.expose
def auth_get_my_purchases() -> dict:
    """All 'completed' purchases for the signed-in user, with the joined
    game row embedded. Powers the launcher's Personal Area.

    Returns {"rows": list, "reason": str, "detail": str|None}. The
    reason lets the UI render a meaningful empty state instead of the
    old fail-closed `[]` that conflated "no purchases", "signed out",
    "expired token" and "network error" into the same screen."""
    import logging
    log = logging.getLogger("launcher")
    if not _auth_available or _auth is None:
        return {"rows": [], "reason": "signed-out", "detail": "auth-unavailable"}
    try:
        out = _auth.get_purchases()
        log.info("auth_get_my_purchases: reason=%s rows=%d",
                 out.get("reason"), len(out.get("rows") or []))
        return out
    except Exception as e:                              # pragma: no cover
        log.exception("auth_get_my_purchases failed")
        return {"rows": [], "reason": "error", "detail": str(e)}


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


# ─────────────────────────────────────────────────────────────
# Idle live-refresh poller.
# ─────────────────────────────────────────────────────────────
# swr()'s cache_refreshed push only fires as a SIDE-EFFECT of a frontend
# call (get_all_games on a component mount). Nothing re-triggers it on a
# timer — so without this greenlet the launcher UI only updated when the
# user left and re-entered a view. This loop re-fetches the dynamic
# catalogs every _POLL_INTERVAL seconds and hands them to
# swr_cache.put(), which diffs against the cache and pushes
# cache_refreshed ONLY when something actually changed → genuine live
# updates while the window is open, no spinner, no polling from React.
_POLL_INTERVAL = 60   # seconds


def _start_catalog_poller() -> None:
    """Spawn the idle live-refresh greenlet on the launcher's gevent hub.

    Runs as a GREENLET (not an OS thread): swr_cache.put → _push_cache_event
    → eel.cache_refreshed(...)() is bound to the main gevent hub and fails
    silently from a separate thread. The fetchers' `requests` calls yield
    cooperatively, so the loop never pins the websocket server."""
    import gevent
    import logging
    log = logging.getLogger("launcher")

    def _loop() -> None:
        while True:
            gevent.sleep(_POLL_INTERVAL)
            try:
                games = _fetch_catalog_live_first()
                if games is not None:
                    swr_cache.put("games", games)
                software = _try_software_remote()
                if software is not None:
                    swr_cache.put("software", software)
                news = _try_remote(REMOTE_NEWS_URL)
                if news is not None:
                    swr_cache.put("news", news)
                updates = _try_remote(REMOTE_UPDATES_URL)
                if updates is not None:
                    swr_cache.put("updates", updates)
                # Progress for whichever games the UI has already shown.
                for gid in swr_cache.progress_keys():
                    try:
                        swr_cache.put("progress", _fetch_progress(gid), sub_key=gid)
                    except Exception:                          # noqa: BLE001
                        pass
            except Exception:                                  # noqa: BLE001
                log.exception("[poller] tick failed")

    gevent.spawn(_loop)
    log.info("catalog poller started (every %ds)", _POLL_INTERVAL)


# ─────────────────────────────────────────────────────────────
# Single-instance guard (Windows).
# ─────────────────────────────────────────────────────────────
# Without a guard, a second instance (e.g. user clicks the Start-menu
# shortcut while the launcher is already running silently in the tray)
# would call eel.start → gevent tries to bind localhost:8765 → it's
# already bound → WinError 10048 surfaces as a fatal Python traceback
# in a console pop-up. Awful UX.
#
# Strategy:
#   1. CreateMutexW with a stable session-scoped name. If GetLastError
#      reports ERROR_ALREADY_EXISTS, another instance owns the mutex.
#   2. The non-owner signals a named auto-reset event "show me" and
#      exits cleanly with code 0 (no traceback).
#   3. The owner (first instance) spawns a daemon thread that waits on
#      the same event. When triggered, it follows the exact same code
#      path as the tray menu's "Open" item — `tray._relaunch_self()`
#      then `os._exit(0)`. That works for both --silent (no window) and
#      visible (existing window) starts: the next process boots
#      visible, bringing focus to the new Chromium window.
#
# We DELIBERATELY use ctypes (no pywin32 dep). PyInstaller ships
# ctypes by default, so there's nothing extra to bundle.
_INSTANCE_MUTEX_HANDLE = None      # kept alive for the process lifetime
_MUTEX_NAME            = "TranslationManagerLauncher_SingleInstance_v1"
_SHOW_EVENT_NAME       = "TranslationManagerLauncher_ShowEvent_v1"


def _acquire_single_instance_mutex() -> bool:
    """Returns True iff THIS process is the first / sole instance.

    Side effect on True: stashes the OS handle in a module global so
    Windows keeps the mutex alive until process exit. Caller must NOT
    close it.
    """
    if sys.platform != "win32":
        return True                                    # non-Windows: no-op
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return True                                    # ctypes broken: don't block boot
    global _INSTANCE_MUTEX_HANDLE
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype  = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle:
        return True                                    # CreateMutex failed → don't block boot
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _INSTANCE_MUTEX_HANDLE = handle
    return True


def _signal_show_to_existing_instance() -> None:
    """Open the named auto-reset event and SetEvent. The running
    instance's waiter wakes up, kills this orphan process, and relaunches
    itself visibly. Best-effort — failures are swallowed because we're
    about to sys.exit anyway."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenEventW.restype  = wintypes.HANDLE
        kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        EVENT_MODIFY_STATE = 0x0002
        h = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, _SHOW_EVENT_NAME)
        if h:
            kernel32.SetEvent(h)
            kernel32.CloseHandle(h)
    except Exception:
        pass


def _start_show_event_listener() -> None:
    """First-instance side: spawn a daemon thread that waits on the
    named event. When signaled, relaunch visibly + exit so the next
    process owns the screen."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import threading
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateEventW.restype  = wintypes.HANDLE
        kernel32.CreateEventW.argtypes = [
            ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR,
        ]
        # bManualReset=False (auto-reset), bInitialState=False (unsignalled)
        handle = kernel32.CreateEventW(None, False, False, _SHOW_EVENT_NAME)
        if not handle:
            return

        def _waiter() -> None:
            INFINITE = 0xFFFFFFFF
            while True:
                kernel32.WaitForSingleObject(handle, INFINITE)
                # Same code path as tray "Open": spawn a fresh visible
                # instance, then kill this one so Chromium hands input
                # focus to the new window.
                try:
                    from translation_manager import tray as _tray
                    # Close our Chrome --app subprocess FIRST so the
                    # relaunch doesn't end up with two launcher windows
                    # (Chrome children survive their parent on Windows).
                    _tray._kill_my_child_processes()
                    _tray._relaunch_self(restored=True)
                except Exception as e:                     # pragma: no cover
                    print(f"[single-instance] relaunch failed: {e}", flush=True)
                import os
                os._exit(0)

        t = threading.Thread(target=_waiter, daemon=True, name="show-event-listener")
        t.start()
    except Exception as e:                                 # pragma: no cover
        print(f"[single-instance] listener setup failed: {e}", flush=True)


def _on_window_closed(_page: str, _websockets: list) -> None:
    """Eel close_callback — fires the moment the Chromium window dies.

    Behaviour now depends on the user's persisted close preference:

      - "minimize" → the tray icon is already running; we do NOT exit.
                     eel.start() returns to main(), which then parks
                     the process until the tray's "Open" menu spawns
                     a fresh launcher instance.
      - "close" or unset → os._exit(0), same as before.

    We can't actually show a React modal HERE — by the time this fires
    the Chromium window is gone, so there's no UI to render on. The
    first-time preference modal is shown on launcher BOOT (when no
    preference exists yet); the saved choice then drives this callback
    silently on every subsequent close.
    """
    import logging
    import os
    from translation_manager import launcher_prefs
    log = logging.getLogger("launcher")
    pref = launcher_prefs.get_close_behavior()
    log.info("window closed — close_behavior=%r", pref)
    if pref == "minimize":
        log.info("close=minimize → process kept alive")
        print("[eel] Window closed → minimised to tray (process stays alive).", flush=True)
        return
    log.info("close=%r → os._exit(0)", pref)
    print("[eel] Window closed — exiting.", flush=True)
    os._exit(0)


def _setup_file_logging() -> None:
    """Route Python logging to ~/.translation_manager/launcher.log.

    The frozen build runs console=False, so without a file handler every
    log line — tray failures, the close-behavior decision, eel.start
    teardown — is lost. With it, a misbehaving close-to-tray leaves a
    diagnosable trail."""
    try:
        import logging
        log_path = Path.home() / ".translation_manager" / "launcher.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_path),
            filemode="a",
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            force=True,
        )
        logging.getLogger("launcher").info("──────── launcher boot ────────")
    except Exception:
        pass


def main() -> None:
    _setup_file_logging()
    import logging
    _log = logging.getLogger("launcher")

    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true",
                    help="Skip frontend serving — assume Vite dev server on :5173")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--silent", action="store_true",
                    help="Boot hidden in the system tray (no Chromium window). "
                         "Used by the autostart Run-key entry when the app launches at "
                         "Windows logon — user explicitly opts in via the settings toggle.")
    ap.add_argument("--restored", action="store_true",
                    help="This launch is a restore from a still-running tray "
                         "instance (tray 'Open' / single-instance re-signal), NOT "
                         "a genuine cold start. Skips the refresh-on-open: the disk "
                         "cache is shown instantly and the idle poller keeps it live.")
    args = ap.parse_args()

    # Tray-restore: the previous instance was alive, so the disk cache is
    # recent. Mark it hot so the first get_all_games() serves it instantly
    # without a refresh-on-open. A genuine cold start skips this and still
    # refreshes. Either way the idle poller keeps the UI live afterwards.
    if args.restored:
        try:
            swr_cache.touch_all()
        except Exception:                                       # noqa: BLE001
            pass
    else:
        # Cold start (genuine fresh boot, NOT a tray restore) — force a
        # synchronous catalog refresh so the first paint shows fresh data
        # instead of whatever was on disk from the previous session. Bg
        # network failure is non-fatal: swr still serves the cached value
        # via the normal background-refresh path.
        try:
            games_data = _fetch_catalog_live_first()
            if games_data is not None:
                swr_cache.put("games", games_data, push=False)
            sw_data = _try_software_remote()
            if sw_data is not None:
                swr_cache.put("software", sw_data, push=False)
        except Exception:                                       # noqa: BLE001
            pass

    # Single-instance guard. If another instance already owns the named
    # mutex, signal it to show its window and exit THIS process cleanly.
    # Otherwise: install the named-event listener so the next time the
    # user clicks the Start-menu shortcut, the running instance hears
    # about it instead of port 8765 colliding into a Python traceback.
    if not _acquire_single_instance_mutex():
        print("[boot] Another launcher instance is running — signalling it to show.", flush=True)
        _signal_show_to_existing_instance()
        sys.exit(0)
    _start_show_event_listener()

    # Tray icon — always spawn it, regardless of how main() reaches eel.start.
    # The tray is the lifeline for both --silent boots (no main window at
    # all) and minimize-to-tray (window closes, tray stays).
    from translation_manager import tray as _tray
    _tray_ok = _tray.start(title="Translation Manager")
    _log.info("tray.start() returned %r", _tray_ok)

    # game_detector seeds its cache from disk at import time (no work to do
    # here). We deliberately do NOT run an automatic scan on boot — the user
    # owns scanning via the explicit "Full Drive Scan" button.

    if not _has_any_cache() and not _ping_api():
        _show_no_internet_dialog()
        sys.exit(1)

    # --silent boot (Windows autostart). No Chromium window opens — the
    # process sits with just the tray icon until the user double-clicks
    # it. The tray callback relaunches us WITHOUT --silent so the second
    # run opens normally.
    if args.silent:
        print("[boot] --silent — tray-only mode, no main window.", flush=True)
        import time
        while True:
            time.sleep(3600)

    # Idle live-refresh — runs on the gevent hub once eel.start() spins it
    # up. Spawned here (after the --silent early-return) so it only exists
    # for a real window session.
    _start_catalog_poller()

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
        except Exception:
            # Any other eel teardown error must NOT crash main() — fall
            # through to the park check so close-to-tray still works.
            _log.exception("eel.start() raised")
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
        except Exception:
            # Any other eel teardown error must NOT crash main() — fall
            # through to the park check so close-to-tray still works.
            _log.exception("eel.start() raised")

    # Reached when eel.start() returns (the window closed and the eel
    # server stopped). If the user picked "minimize to tray" we park the
    # process here so the tray icon stays alive; otherwise main() returns
    # and the process exits.
    from translation_manager import launcher_prefs
    _behavior = launcher_prefs.get_close_behavior()
    _log.info("eel.start() returned — close_behavior=%r", _behavior)
    if _behavior == "minimize":
        _log.info("parking process in tray (close-to-tray)")
        print("[boot] Parked in tray after window close.", flush=True)
        import time
        while True:
            time.sleep(3600)
    _log.info("main() returning — process will exit")


if __name__ == "__main__":
    main()
