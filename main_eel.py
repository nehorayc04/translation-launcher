"""
Translation Manager backend module - 44 RPC functions + 4 push channels
that drive the React frontend.

Role under the current architecture (Qt-shell, post-migration):
  * main_qt.py is the production entry point.
  * main_qt.py installs translation_manager.qt_shell.eel_shim into
    sys.modules['eel'] BEFORE importing this file, which makes every
    `@eel.expose` here a no-op decorator and routes `eel.<push>(...)()`
    calls into Qt Signals on the Bridge object. The function bodies
    below are reused 1:1.
  * Bridge slots in qt_shell/bridge.py delegate to these functions
    directly - this file remains the single source of truth for what
    the launcher RPC surface does.

Legacy Eel entry point (kept working for reference / emergencies):
  PROD mode (serves built React app):
      python main_eel.py
  DEV mode (Vite on :5173, Eel just exposes the API):
      python main_eel.py --dev
  When run as `python main_eel.py`, `import eel` resolves to the real
  Eel package (no shim is installed), the @eel.expose decorators
  register normally, and main() opens Eel's Chromium window.
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
# auth_abort_login can't dispatch - which is the entire history of the
# "Copy Link / Cancel button unresponsive" and "OAuth flow freezes
# right after the callback" bugs.
#
# We patch socket + ssl (and select, which is what http.server uses to
# wait for incoming connections). We DELIBERATELY DO NOT patch
# threading - the launcher's download manager and a few other modules
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
import time
from dataclasses import asdict
from pathlib import Path

import eel
import requests

from translation_manager import crash_reporter as _crash
from translation_manager import downloads as _downloads
from translation_manager import game_mod as _game_mod
from translation_manager import mod_source as _mod_source
from translation_manager import offline_bundle as _offline_bundle
from translation_manager import paths as user_paths
from translation_manager import steam_apply as _steam_apply
from translation_manager import steam_mod as _steam_mod
from translation_manager import virtualdj_mod as _vdj
from translation_manager import borderless_gaming_mod as _bg
from translation_manager import signalrgb_mod as _srgb
from translation_manager import swr_cache
from translation_manager.config import GAMES as GAME_CONFIGS
from translation_manager.config import GameConfig
from translation_manager.game_detector import (
    cached as detected_cached,
    find_exe as _find_exe,
    refresh_deep,
    refresh_quick,
    root_from_exe as _root_from_exe,
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
from translation_manager import game_language as _game_language
from translation_manager import spiderman2_mod as _sm2
from translation_manager import watchdogs2_mod as _wd2
from translation_manager import gtav_mod as _gtav
from translation_manager import gowr_mod as _gowr
from translation_manager import hogwarts_legacy_mod as _hl
from translation_manager import witcher3_mod as _w3
from translation_manager import plague_tale_requiem_mod as _pt

# Catalog id of Marvel's Spider-Man 2 - the only title applied via the native
# DAT1/TOC patcher (Insomniac engine), distinct from the CP2077-style
# download-and-copy mods.
_SM2_ID = "spiderman2"

# Catalog id of Watch Dogs 2 - applied via the native FAT5 fat-redirect patcher
# (Ubisoft Disrupt engine), distinct again from both the CP2077 download-mod and
# the SM2 TOC patcher. Activation is in-game (Written Language = Arabic).
_WD2_ID = "watchdogs2"
# The bundled WD2 payload's version (shipped in assets/watchdogs2/). Surfaced as
# the installed version; bump it when the bundled files are refreshed.
_WD2_BUNDLED_VERSION = "1.0.0-beta.4"
# Worker slug: the WD2 native applier DOWNLOADS the latest payload from here
# (the published mod zip carries the exact 3 files it needs) so new versions
# reach users WITHOUT a launcher rebuild; the bundled files are the offline
# fallback. Same model as SM2.
_WD2_SLUG = "watchdogs2-hebrew"

# Catalog id of the Cyberpunk 2077 entry. Hard-coded because the
# Arabic-slot flip is specific to that game's Hebrew mod and must
# never trigger for any other title.
_CP2077_ID = "cyberpunk"

# Catalog id of Anno 1800. A download-distributed mod like CP2077, but its
# payload is a LOOSE-FILE mod that deploys into %Documents%\Anno 1800\mods\
# (see GameConfig.documents_subdir + _deploy_root), and its post-install hook
# sets the in-game text language to English.
_ANNO_ID = "anno1800"

# Catalog id of Grand Theft Auto V. Applied via the native OpenIV-free RPF7
# read-modify-write (gtav_mod, vendored rpf7_writer): edits the user's existing
# OPEN `mods\` folder, preserving every other mod byte-exact. A clean install
# with no mods folder is GUIDED through a one-time OpenIV setup (the launcher
# can't decrypt the vanilla - Legacy-2025 NG keys).
_GTAV_ID = "gtav"
_GTAV_BUNDLED_VERSION = "1.0.0-beta.2"
# Worker slug: the GTA applier downloads the CURRENT payload pair (Hebrew +
# vanilla-English, one archive) from here, so a new mod version reaches users with
# no launcher rebuild; the bundled zips are the offline / server-down fallback.
_GTAV_SLUG = "gtav-hebrew"

# Catalog id of God of War: Ragnarök. Applied via a native SINGLE-FILE swap of the
# Arabic-slot localization WAD (gowr_mod): back up the original OUTSIDE the game,
# atomically replace exec\wad\pc_le\r_lang_ar.wad with our bundled Hebrew build -
# only that one file is ever touched, and revert restores the exact original.
# Activation is in-game (Settings → Text Language = العربية). id == the Supabase
# games row + the game_detector key.
_GOWR_ID = "gowragnarok"
_GOWR_BUNDLED_VERSION = "1.0.0-beta.1"
# Worker slug: GoWR native applier downloads the latest r_lang_ar.wad from here
# (server-side updates, no rebuild); bundled WAD = offline fallback.
_GOWR_SLUG = "godofwar-ragnarok-hebrew"

# ── Three DOWNLOAD-ONLY native appliers (mod not bundled - fetched from the
# Worker once published; nothing to install until then). id == the Supabase
# games.id + the game_detector key. Deploy mechanism per game:
#   Hogwarts Legacy  - additive UE4 override pak into Phoenix\…\Paks\~mods\
#                      (pakchunk0 untouched); activation in-game Text=Arabic.
#   The Witcher 3    - non-destructive Mods\modHebrew overlay; activation Text=Arabic
#                      (scriptable via game_language: user.settings TextLanguage).
#   Plague Tale: Req - overwrite TRTEXT\tt23.pc(+.IGN) + FONT\ENGLISH.DPC, originals
#                      backed up in the launcher cache; activation in-game Text=Arabic.
_HL_ID = "hogwarts"
_HL_SLUG = "hogwarts-legacy-hebrew"
_W3_ID = "witcher3"
_W3_SLUG = "witcher3-hebrew"
_PT_ID = "plague-tale-requiem"
_PT_SLUG = "plague-tale-requiem-hebrew"

# Installed launcher SemVer core. MUST stay in lock-step with
# installer.iss `#define AppVersion`. The in-app self-updater
# (get_launcher_update_info) compares this against the release feed.
# Maturity is carried SEPARATELY by LAUNCHER_CHANNEL - the UI joins them
# for display ("1.0.0" + "dev" → "v1.0.0-dev"), the same way Chrome / VS
# Code keep a clean version number plus a channel. Never bake the channel
# into this string: the version comparator treats it as pure semver.
LAUNCHER_VERSION = "1.2.0"

# Maturity channel of THIS build: dev | canary | beta | stable. Shown in the
# launcher UI (Settings) next to the version and used by the website's download
# page to decide visibility (dev/canary are developer-only). Set per-build -
# bump to "beta"/"stable" when the launcher graduates, then rebuild.
LAUNCHER_CHANNEL = "beta"

# Per-build identity, baked by build_exe.bat into translation_manager/
# _build_info.py (a fresh UTC timestamp every build). The version string
# stays constant across dev re-releases - re-released in place - so the
# self-updater can't tell two builds apart by version alone. BUILD_ID lets
# it: when the
# release feed carries a different build-id than this one, an update is
# offered even though the version is unchanged. Dev runs (no build step)
# have no _build_info.py → "dev", and the build-id check is skipped.
try:
    from translation_manager._build_info import BUILD_ID  # type: ignore[attr-defined]
except Exception:                                          # noqa: BLE001
    BUILD_ID = "dev"

# Dev build counter - baked by build_exe.bat (increments every build). Shown
# everywhere as the FULL launcher version v<ver>-<channel>.<DEV_BUILD>
# (e.g. v1.0.0-dev.7). A dev run with no build step (or an older build) has no
# DEV_BUILD → 0, and the ".N" suffix is simply omitted.
try:
    from translation_manager._build_info import DEV_BUILD  # type: ignore[attr-defined]
except Exception:                                          # noqa: BLE001
    DEV_BUILD = 0

# Optional auth subsystem - if Supabase isn't configured (e.g. local
# dev without env vars), the bridge stays installed but every call
# returns a "not configured" error rather than crashing the launcher.
try:
    from translation_manager import auth as _auth
    _auth_available = True
    _auth_error: str | None = None
except Exception as e:  # pragma: no cover - defensive
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
REMOTE_CATALOG_URL  = "https://hebrew-translation-hub.com/api/games"
REMOTE_SOFTWARE_URL = "https://hebrew-translation-hub.com/api/software"
REMOTE_NEWS_URL     = "https://hebrew-translation-hub.com/api/news"
REMOTE_UPDATES_URL  = "https://hebrew-translation-hub.com/api/updates"
REMOTE_LAUNCHER_URL = "https://hebrew-translation-hub.com/api/launcher"
REMOTE_TIMEOUT     = 3.0   # seconds - keep short so offline boot isn't slow
_REMOTE_CACHE_TTL  = 30    # in-memory hot-window. Below this, swr returns
                           # the cached value without firing a background
                           # refresh. Above it, return cached + refresh.
API_BASE = "https://hebrew-translation-hub.com"


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
    SWR treats None as 'no update - keep cached value'."""
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
        'version':         row.get('version') or '-',
        'versionLabel':    row.get('version_label') or '',
        # the GAME/SOFTWARE version this mod was built/tested against - shown as
        # "גרסת משחק/תוכנה תואמת" in the detail panel. Read via select=* so it
        # flows once the `game_version` column exists; '' → the row is hidden.
        'gameVersion':     row.get('game_version') or '',
        'status':          row.get('status') or 'final',
        'cover':           row.get('cover_url'),
        # Steam-style wide background banner + transparent logo (served from
        # Supabase storage, NOT bundled - keeps the install small). Optional;
        # the GameDetailPanel falls back to a blurred cover / the title text.
        'bannerUrl':       row.get('banner_url'),
        'logoUrl':         row.get('logo_url'),
        'theme_key':       row.get('theme_key') or 'default',   # legacy snake
        'themeKey':        row.get('theme_key') or 'default',   # new camel
        'availability':    row.get('availability') or 'planned',
        'progress':        row.get('progress'),
        'downloadUrl':     row.get('download_url'),
        'tagline':         row.get('tagline') or '',
        'description':     row.get('description') or '',
        'next':            bool(row.get('next_up')),
        'featured':        bool(row.get('featured')),
        # NOTE: `or 1000` would be WRONG here - sort_order=0 (the first/featured
        # game, e.g. Cyberpunk) is falsy and would collapse to 1000, sorting it
        # LAST. Only a genuinely-missing value falls back.
        'sortOrder':       1000 if row.get('sort_order') is None else row.get('sort_order'),
        # Critical for the DRM gate. Missing this column makes
        # `_game_price_cents()` return 0 for every game, which collapses
        # `if price > 0 and not owns(...)` to False - i.e. any user can
        # install any paid mod without owning it. Build G fix after a
        # bypass was caught in the wild: the catalog response had every
        # field EXCEPT priceCents because this mapping skipped it.
        'priceCents':      int(row.get('price_cents') or 0),
        # New: ownership flag for the DRM gate. Always present (false when
        # signed out or not purchased) so the frontend can branch cleanly.
        'owned':           gid in owned_ids,
        # Versioning system - release maturity stage (alpha|beta|rc|stable) +
        # the latest "what's new". Mirrors the website's /api/games shape.
        'releaseStage':    row.get('release_stage') or 'stable',
        'changelog':       row.get('changelog') or '',
        # SOFTWARE flag (VirtualDJ…). Software rows live in the SAME `games`
        # table; this is what routes them to the תוכנות library instead of the
        # games one. WITHOUT it `_load_catalog()`'s filter is blind and a
        # software title shows up in BOTH libraries - and, worse, the price
        # lookup for the DRM gate can't find its row.
        'isSoftware':      bool(row.get('is_software') or False),
        # Admin "show on launcher" toggle. Honoured for GAMES too (not just
        # software): _games_only drops rows where this is explicitly False, so an
        # admin can hide a game from every launcher. None/absent → shown (default).
        'showOnLauncher':  row.get('show_on_launcher') is not False,
        # OPTIONAL server-side detection hints. When the admin fills these on a
        # NEW game's row, every installed launcher can find that game on disk
        # WITHOUT an app update (game_detector.register_patterns merges them at
        # runtime). Absent columns simply yield [] - nothing breaks.
        'detectFolders':   row.get('detect_folders') or [],
        'detectExes':      row.get('detect_exes') or [],
    }


def _try_supabase_catalog() -> list[dict] | None:
    """Live games catalog straight from Supabase REST. Bypasses the
    website's CDN-cached /api/games (60s s-maxage) so admin edits show
    up within one SWR window. Fails closed → caller falls through to
    /api/games → bundled games.json on absolute offline cold boot.

    Auth-aware: if the launcher has a valid stored access token, also
    queries user_purchases and tags each game with `owned`. If the user
    is signed out (or the token is expired and refresh fails), the
    games table is anon-readable so we still get the catalog - every
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

    # Optional Bearer - present iff there's a non-expired access token.
    headers = {'apikey': cfg.anon_key, 'Accept': 'application/json'}
    access_token: str | None = None
    try:
        tok = TokenStore().load()
        if tok and tok.access_token and not tok.is_expired():
            access_token = tok.access_token
            headers['Authorization'] = f'Bearer {access_token}'
    except Exception:
        access_token = None

    # 1) Games - anon-readable; auth optional.
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
    #    A failure here is non-fatal - we just don't tag ownership.
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
    """SWR-cached catalog of GAMES. On absolute cold start (no disk cache, no
    bundled file, no network) falls back to the dataclasses bundled inside the
    launcher binary itself.

    SOFTWARE rows (VirtualDJ…) live in the SAME `games` table flagged
    `isSoftware` - they belong to the "תוכנות" library, never the games one."""
    data = swr_cache.swr("games", _fetch_catalog_live_first,
                         ttl=_REMOTE_CACHE_TTL)
    if data is None:
        # OFFLINE PACKAGE before the compiled-in catalog: the bundle's snapshot
        # was taken from the LIVE site when it was built, so it knows about games
        # added after this exe was compiled. The bundled dataclasses stay as the
        # last-resort cold-start fallback.
        try:
            snap = _offline_bundle.catalog_games()
        except Exception:                               # pragma: no cover
            snap = None
        data = snap if snap else [asdict(g) for g in _bundled_games()]
    # Belt AND braces: honour the flag, and also exclude anything the software
    # catalog claims. A row cached by an OLDER build (before the shape carried
    # `isSoftware`) has no flag at all - without the id check it would keep
    # showing up in the games library until the cache expires.
    # FUTURE-PROOFING: a catalog row may carry its own detection hints
    # (detectFolders / detectExes). Merging them here means a brand-new game
    # added on the website becomes DETECTABLE on every installed launcher
    # immediately - no rebuild, no update. Additive + idempotent; never raises.
    try:
        from translation_manager import game_detector as _gd
        _gd.register_patterns(data)
        # Same idea for the save-backup plugin: a catalog row may carry
        # `savePaths`, so a new game's save location is known WITHOUT an update.
        from translation_manager.plugins import save_backup as _sb
        _sb.register_known(data)
    except Exception:                                   # pragma: no cover
        pass

    return _games_only(data)


def _games_only(data: list[dict]) -> list[dict]:
    """Drop SOFTWARE rows from a RAW catalog feed.

    The `games` SWR key caches the feed VERBATIM (it carries software rows too -
    `_try_software_remote` builds the software catalog by filtering the very same
    response), so EVERY consumer of that cached payload must apply this filter.
    `_load_catalog` does it on the read path; the SWR background PUSH must do it
    too, or a refresh pushes software into the games library."""
    soft_ids = {s.get("id") for s in _load_software()}
    # `showOnLauncher is not False` honours the admin "hide from launcher" toggle
    # for GAMES (None/absent = shown, so the bundled offline catalog is unaffected).
    return [g for g in data
            if not g.get("isSoftware") and g.get("id") not in soft_ids
            and g.get("showOnLauncher") is not False]


def _load_news() -> list[dict]:
    data = swr_cache.swr("news", lambda: _try_remote(REMOTE_NEWS_URL),
                         ttl=_REMOTE_CACHE_TTL)
    return data if data is not None else []


def _load_updates() -> list[dict]:
    data = swr_cache.swr("updates", lambda: _try_remote(REMOTE_UPDATES_URL),
                         ttl=_REMOTE_CACHE_TTL)
    return data if data is not None else []


def _try_software_remote() -> list[dict] | None:
    """SOFTWARE catalog = the rows of the SAME live `/api/games` feed flagged
    `isSoftware` (VirtualDJ…). They keep the FULL game shape, so the launcher
    renders them with the very same GameCard / GameDetailPanel as a game -
    only the library they live in differs. One admin panel drives both."""
    data = _try_remote(REMOTE_CATALOG_URL)
    if data is None:
        return None
    return [g for g in data
            if g.get("isSoftware") and g.get("showOnLauncher") is not False]


def _load_software() -> list[dict]:
    """Software catalog visible to the launcher. SWR-cached: instant
    return from disk, background refresh from /api/software. Falls back to
    the BUNDLED catalog (Steam + VirtualDJ) when the remote feed is
    empty/retired - the translation FILES still come from the cloud, only
    the catalog metadata is bundled."""
    from translation_manager.software_catalog import sorted_software
    data = swr_cache.swr("software", _try_software_remote, ttl=_REMOTE_CACHE_TTL)
    return data if data else sorted_software()


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
    enriched shape - pushing a bare row would silently drop every
    install/mod badge on a live update.

    Wrapped in try/except because the call is meaningless until the
    React app has connected - early firings before the websocket exists
    are just no-ops."""
    try:
        if kind == "games" and isinstance(data, list):
            # The cached `games` payload is the RAW feed (software rows included),
            # so filter EXACTLY like the _load_catalog read path - otherwise a
            # background refresh pushes VirtualDJ & co into the games library.
            data = _enrich_catalog(_games_only(data))
        elif kind == "software" and isinstance(data, list):
            # SAME enrichment/shape as get_all_software() (is_installed / mod_state /
            # currentLanguage) so a pushed update matches what the software view reads.
            data = _enrich_catalog(data)
        eel.cache_refreshed(kind, data, sub_key)()         # type: ignore[attr-defined]
    except Exception:
        pass


swr_cache.configure(
    push_cb=_push_cache_event,
)


def _catalog_by_id(game_id: str) -> dict | None:
    """The catalog row for an id - GAMES first, then SOFTWARE.

    `_load_catalog()` deliberately drops the `isSoftware` rows (they have their
    own library tab), so a software id would resolve to None here. That matters
    for MONEY: `_game_price_cents()` reads this row, and a missing row means
    price 0 → the paid-mod DRM gate collapses to "free for everyone". So the
    lookup must span both halves of the catalog.
    """
    for g in _load_catalog():
        if g.get("id") == game_id:
            return g
    try:
        for s in _load_software():
            if s.get("id") == game_id:
                return s
    except Exception:                                   # pragma: no cover
        pass
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


def _documents_dir() -> Path:
    """The user's real Documents folder. Reads the Windows known-folder
    ('Personal') from the registry so a OneDrive-redirected Documents is
    honoured - the loose-file mod MUST land where the game's mod loader
    reads. Falls back to ~/Documents (what the mod's own builder uses)."""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as k:
            val, _ = winreg.QueryValueEx(k, "Personal")
            if val:
                return Path(os.path.expandvars(str(val)))
    except Exception:                                    # pragma: no cover
        pass
    return Path.home() / "Documents"


def _deploy_root(game_id: str) -> Path | None:
    """Where a download-distributed mod's FILES go.

    For a normal game this is the detected game folder (`_install_path`).
    For a loose-file Documents mod (GameConfig.documents_subdir set, e.g.
    Anno 1800) it is %Documents%\\<documents_subdir>, independent of where
    the game itself is installed. Identical to `_install_path` for every
    other game, so the well-tested copy-into-game-folder path is untouched."""
    cfg = _config_for(game_id)
    sub = getattr(cfg, "documents_subdir", "") if cfg else ""
    if sub:
        return _documents_dir() / sub
    base = _install_path(game_id)
    # A package whose payload is FLAT but belongs in a fixed sub-folder of the
    # game (Corsair Cove's two pak stubs live in CorsairCove\Content\Paks).
    deep = getattr(cfg, "deploy_subdir", "") if cfg else ""
    return (base / deep) if (base and deep) else base


def _anno1800_set_language_english() -> None:
    """Best-effort: set Anno 1800's in-game TEXT language to English so the
    Hebrew (which the mod ships in the English slot) renders. Edits the
    `"TextLanguage":"..."` key in %Documents%\\Anno 1800\\config\\engine.ini,
    leaving AudioLanguage alone. Idempotent; never raises. The user still
    toggles the language once in-game for the full atlas re-bake (see the UI
    note) - this just removes the 'pick English first' step."""
    try:
        ini = _documents_dir() / "Anno 1800" / "config" / "engine.ini"
        if not ini.is_file():
            return
        text = ini.read_text(encoding="utf-8", errors="replace")
        import re
        new = re.sub(r'("TextLanguage"\s*:\s*")[^"]*(")',
                     r"\1English\2", text, count=1)
        if new != text:
            ini.write_text(new, encoding="utf-8")
    except Exception:                                    # pragma: no cover
        pass


def _anno1800_deploy_data4(base) -> dict:
    """Deploy the Hebrew-injected maindata `data4.rda` into the Anno game folder
    (the English-slot build needs it for the cold-boot pre-baked atlas). The mod
    archive carries data4.rda at the cache root; back up the user's original
    OUTSIDE the game and drop ours in. No-op if the payload has no data4
    (an older loose-only archive) - the loose mod still works via Korean/English-toggle."""
    try:
        if base is None:
            return {"ok": True, "skipped": "no game path"}
        from translation_manager import anno1800_data4 as _d4
        src = _game_mod.cache_dir(_ANNO_ID) / "data4.rda"
        return _d4.deploy(base, src, str(_native_backup_dir(_ANNO_ID)))
    except Exception as e:                                # pragma: no cover
        return {"ok": False, "error": f"data4: {e}"}


def _anno1800_revert_data4(base) -> dict:
    """Restore the user's original maindata data4.rda (Anno uninstall)."""
    try:
        from translation_manager import anno1800_data4 as _d4
        return _d4.revert(base, str(_native_backup_dir(_ANNO_ID)))
    except Exception as e:                                # pragma: no cover
        return {"ok": False, "error": f"data4: {e}"}


# Find the GameConfig (mod-file definition) by catalog id.
# Not every catalog game has a config - only the few with actual mods do.
def _config_for(game_id: str) -> GameConfig | None:
    for cfg in GAME_CONFIGS.values():
        if cfg.internal_id == game_id:
            return cfg
    return None


def _mod_state(game_id: str) -> str:
    """Strict state resolution. NEVER returns UNKNOWN - we always know enough
    to pick a correct UI action:
       no GameConfig OR empty mod_files  → NOT_AVAILABLE  (package not authored)
       install dir not detected          → NOT_INSTALLED  (ready to install)
       files inspected on disk           → ACTIVE / DISABLED / NOT_INSTALLED
    """
    # Spider-Man 2 has no GameConfig (it's applied via the native TOC patcher,
    # not the copy-into-folder flow) - resolve its state from the applier so
    # the library buckets it under "active translation" once installed.
    # VirtualDJ (software): state comes purely from the local applier cache -
    # the translation is one loose file under %LOCALAPPDATA%.
    if game_id == _VDJ_ID:
        try:
            st = _vdj.status()
            if st.get("enabled"):
                return "ACTIVE"
            if st.get("cached"):
                return "DISABLED"
        except Exception:                               # pragma: no cover
            pass
        return STATE_NOT_INSTALLED
    # Borderless Gaming (software): same shape - everything lives in %APPDATA%.
    if game_id == _BG_ID:
        try:
            st = _bg.status()
            if st.get("enabled"):
                return "ACTIVE"
            if st.get("cached"):
                return "DISABLED"
        except Exception:                               # pragma: no cover
            pass
        return STATE_NOT_INSTALLED
    # SignalRGB (software): state from the local applier cache + the live exe.
    if game_id == _SRGB_ID:
        try:
            st = _srgb.status()
            if st.get("enabled"):
                return "ACTIVE"
            if st.get("cached"):
                return "DISABLED"
        except BaseException:                           # pragma: no cover
            # BaseException, NOT Exception: status() reconciles against the exe
            # by running the DOWNLOADED package's patch_exe, which can
            # `raise SystemExit(...)` on an unrecognised exe layout. A SystemExit
            # here would otherwise kill the whole launcher at boot (no traceback,
            # no crash report). Fail safe to "not installed".
            pass
        return STATE_NOT_INSTALLED
    if game_id == _SM2_ID:
        base = _install_path(game_id)
        if base is None:
            return STATE_NOT_INSTALLED
        try:
            return "ACTIVE" if _sm2.is_applied(base) else STATE_NOT_INSTALLED
        except Exception:                               # pragma: no cover
            return STATE_NOT_INSTALLED
    # Watch Dogs 2: native FAT5 patcher - state resolves from our backup
    # marker (in the launcher cache), not from a GameConfig.
    if game_id == _WD2_ID:
        if _install_path(game_id) is None:
            return STATE_NOT_INSTALLED
        try:
            return "ACTIVE" if _wd2.is_applied(str(_wd2_backup_dir())) else STATE_NOT_INSTALLED
        except Exception:                               # pragma: no cover
            return STATE_NOT_INSTALLED
    # GTA V: native OpenIV-free RPF7 applier - state from our backup marker.
    if game_id == _GTAV_ID:
        if _install_path(game_id) is None:
            return STATE_NOT_INSTALLED
        try:
            return "ACTIVE" if _gtav.is_applied(str(_gtav_backup_dir())) else STATE_NOT_INSTALLED
        except Exception:                               # pragma: no cover
            return STATE_NOT_INSTALLED
    # God of War: Ragnarök: native single-file WAD swap - state from our backup
    # marker + a content check that the live WAD is our Hebrew build.
    if game_id == _GOWR_ID:
        base = _install_path(game_id)
        if base is None:
            return STATE_NOT_INSTALLED
        try:
            # Same content check get_gowr_mod_state does: the sha RECORDED at
            # install (the downloaded WAD). No payload ships in the installer, so
            # the bundled sha is only a legacy fallback for pre-download installs.
            sha = _gowr_state().get("sha") or _gowr_bundled_sha()
            return ("ACTIVE" if _gowr.is_applied(str(_gowr_backup_dir()), base, sha)
                    else STATE_NOT_INSTALLED)
        except Exception:                               # pragma: no cover
            return STATE_NOT_INSTALLED
    # Hogwarts Legacy / Witcher 3 / Plague Tale: Requiem - download-only native
    # appliers; state resolves from the applier's own is_applied check.
    if game_id == _HL_ID:
        base = _install_path(game_id)
        try:
            return "ACTIVE" if base is not None and _hl.is_applied(base) else STATE_NOT_INSTALLED
        except Exception:                               # pragma: no cover
            return STATE_NOT_INSTALLED
    if game_id == _W3_ID:
        base = _install_path(game_id)
        try:
            return "ACTIVE" if base is not None and _w3.is_applied(base) else STATE_NOT_INSTALLED
        except Exception:                               # pragma: no cover
            return STATE_NOT_INSTALLED
    if game_id == _PT_ID:
        base = _install_path(game_id)
        try:
            return ("ACTIVE" if base is not None and _pt.is_applied(
                str(_native_backup_dir(_PT_ID)), base, _native_state(_PT_ID).get("key_sha"))
                    else STATE_NOT_INSTALLED)
        except Exception:                               # pragma: no cover
            return STATE_NOT_INSTALLED
    cfg = _config_for(game_id)
    if cfg is None or not cfg.mod_files:
        return STATE_NOT_AVAILABLE
    base = _install_path(game_id)
    if base is None:
        return STATE_NOT_INSTALLED
    # For a loose-file Documents mod (Anno) the files live under _deploy_root
    # (%Documents%\…), not the game folder; detect_state inspects there.
    return detect_state(cfg, _deploy_root(game_id) or base)


# ── SOFTWARE (VirtualDJ …) resolution ────────────────────────
# Software is NOT in the game path cache and has no GameConfig, so every
# game-path helper returns None for it. These three resolve it through
# `software_detector` instead (a user override in paths.json still wins).
def _is_software(game_id: str) -> bool:
    return bool((_catalog_by_id(game_id) or {}).get("isSoftware"))


def _software_detect(game_id: str) -> dict:
    """{installed, path (DIR), exe (full path), source} - never raises."""
    try:
        from translation_manager import software_detector
        return software_detector.scan_all([game_id]).get(game_id) or {}
    except Exception:                                   # pragma: no cover
        return {}


def _software_install_path(game_id: str) -> Path | None:
    custom = user_paths.get(game_id)
    if custom:
        return custom
    p = _software_detect(game_id).get("path")
    return Path(p) if p else None


def _vdj_install_path() -> Path | None:
    return _software_install_path(_VDJ_ID)


def _enrich_game_row(cg: dict) -> dict:
    """Enrich one bare catalog row with THIS machine's install path + mod
    state. Shared by _game_payload, get_all_games and the cache_refreshed
    push so every path emits an identical, fully-shaped game dict."""
    gid  = cg.get("id", "")
    # Software (VirtualDJ …) resolves via software_detector AND honours the
    # "forgotten" list (Settings → נקה) - a cleared software id reports as
    # not-installed until the next full scan re-detects it. (A game path uses
    # the detected/override cache and is never in the software cleared-list.)
    if cg.get("isSoftware"):
        from translation_manager import launcher_prefs as _lp
        base = None if gid in set(_lp.get_cleared_software()) else _software_install_path(gid)
    else:
        base = _install_path(gid)
    cfg  = _config_for(gid)
    # SM2 + WD2 are moddable via their native appliers even without a GameConfig.
    has_mod = (cfg is not None and bool(cfg.mod_files)) or gid in (_SM2_ID, _WD2_ID, _GTAV_ID, _GOWR_ID, _HL_ID, _W3_ID, _PT_ID, _VDJ_ID, _BG_ID, _SRGB_ID)
    # Current in-game TEXT language (interface + subtitles) for the few
    # titles the launcher can read - shown per-game in the UI. Cheap: a
    # plain dict miss for unsupported games, a ~1-5ms registry/settings
    # read for the supported ones (spiderman2 / cyberpunk). `installed`
    # is irrelevant to the live `current` reading, so skip resolving it.
    current_language = None
    try:
        if _game_language.is_supported(gid):
            ls = _game_language.get_state(gid, installed=None)
            if ls.get("supported"):
                current_language = ls.get("current")
    except Exception:                                   # pragma: no cover
        current_language = None
    # Full EXE path for the Settings field: the exact exe the user picked (if
    # any), else auto-derived from the detected folder + the known exe name.
    # None → the UI shows the folder path. install_path (the ROOT) is unchanged,
    # so every applier keeps writing into the game folder.
    exe_path = user_paths.get_exe(gid)
    if not exe_path and base is not None and not cg.get("isSoftware"):
        exe_path = _find_exe(gid, base)
    return {
        **cg,
        "install_path": str(base) if base else None,
        "exe_path": exe_path,
        "is_installed": base is not None,
        "has_mod_support": has_mod,
        "mod_state": _mod_state(gid),
        "currentLanguage": current_language,
    }


def _game_payload(game_id: str) -> dict:
    """Catalog entry enriched with install path + mod state."""
    cg = _catalog_by_id(game_id)
    if cg is None:
        return {}
    return _enrich_game_row(cg)


# ═════════════════════════════════════════════════════════════
# @eel.expose - public API surface for the React frontend
# ═════════════════════════════════════════════════════════════
_AVAIL_RANK = {"available": 0, "in-progress": 1, "coming-soon": 2, "planned": 3}


def _enrich_catalog(items: list[dict]) -> list[dict]:
    """Bare remote catalog → sorted, install/mod-enriched list - the exact
    shape get_all_games() returns and the frontend's setGames() expects."""
    items_sorted = sorted(
        items,
        key=lambda g: (_AVAIL_RANK.get(g.get("availability", ""), 99),
                       g.get("titleEn", "")),
    )
    out: list[dict] = []
    for g in items_sorted:
        if not g.get("id"):
            continue
        try:
            out.append(_enrich_game_row(g))
        except BaseException as e:
            # SYSTEMIC SAFETY NET (catch BaseException, NOT Exception). Enriching
            # ONE row reads that game/software's install + mod state, and for the
            # software appliers (SignalRGB / Borderless) that runs DOWNLOADED
            # in-process code which can `raise SystemExit(...)`. SystemExit is a
            # BaseException, so `except Exception` missed it → one bad row
            # silently TERMINATED the whole launcher at boot, with no traceback
            # and no crash report (the interpreter never runs the crash_reporter
            # excepthook for SystemExit). Never again: skip-and-degrade per row -
            # log it, REPORT it to the admin site, and show the bare row so its
            # card still renders instead of the whole catalog (or the app) dying.
            gid = g.get("id", "")
            try:
                __import__("logging").getLogger("launcher").warning(
                    "enrich failed for %s - %r (row shown un-enriched)", gid, e)
            except Exception:
                pass
            _event("enrich_failed", f"{type(e).__name__}: {e!r}",
                   source="catalog", code="enrich", severity="warn", game=gid)
            out.append(g)
    return out


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
    """Set the game's install location. `path` may be the game FOLDER or the
    full EXE path (from the 'choose file' dialog). When it's an exe we store the
    game ROOT the appliers need (derived by walking up to the game's own folder)
    AND remember the exact exe for display. The appliers all validate their
    target, so an unexpected root fails with a clear message, never corruption."""
    if path:
        p = Path(path)
        if p.is_file() and p.suffix.lower() == ".exe":
            cfg   = _config_for(game_id)
            vfile = getattr(cfg, "validation_file", "") if cfg else ""
            root  = _root_from_exe(game_id, str(p), vfile or None)
            user_paths.set_path(game_id, str(root) if root else str(p.parent))
            user_paths.set_exe(game_id, str(p))
        else:                                            # a folder (typed or legacy)
            user_paths.set_path(game_id, str(p))
            user_paths.set_exe(game_id, None)            # drop a stale picked exe
    else:
        user_paths.set_path(game_id, None)
        user_paths.set_exe(game_id, None)
    return _game_payload(game_id)


@eel.expose
def clear_custom_path(game_id: str) -> dict:
    user_paths.set_path(game_id, None)
    user_paths.set_exe(game_id, None)
    return _game_payload(game_id)


def _event(kind: str, message: str = "", *, source: str = "", code: str = "",
           severity: str = "error", **extra) -> None:
    """Fire a handled-event report (anonymous, silent, opt-in-gated). A thin
    wrapper so call sites stay one-liners and a reporter failure never leaks."""
    try:
        _crash.report_event(kind, message, source=source, code=code,
                            severity=severity, extra=extra or None)
    except Exception:
        pass


# The game whose install worker is currently running, so a handled install
# failure can be ATTRIBUTED in the crash dashboard. A raw "[WinError 2]" with no
# game id was un-diagnosable in the field; set by each _run_*_install worker.
_CUR_INSTALL_GAME: list[str] = [""]


def _bounded(fn, timeout_s: float, default=None):
    """Run fn() on a daemon thread; return `default` if it does not finish in
    time. The thread keeps running - a first-time multi-GB is_applied() content
    hash finishes in the background and warms its memo, so the NEXT poll is fast.
    This bounds a single get_mod_updates item so one slow file-hash can never
    blow the bridge slot's 180 s guard (real field report: the whole update sweep
    timed out on a native mod's first post-update hash)."""
    import threading as _th
    box: dict = {}

    def _w() -> None:
        try:
            box["v"] = fn()
        except Exception:
            box["v"] = default

    t = _th.Thread(target=_w, daemon=True)
    t.start()
    t.join(timeout_s)
    return box.get("v", default)


# An extra listener for the SAME tick stream, used by the headless --mod CLI
# (Big Launch). It is a plain list so a caller can install one without importing
# anything Qt/eel, and it is invoked defensively — a broken sink must never take
# down an install that is already writing to a game folder.
_MOD_PROGRESS_SINK: list = []


def set_mod_progress_sink(fn) -> None:
    """Route every mod-install tick to `fn` as well as to the UI."""
    _MOD_PROGRESS_SINK.clear()
    if fn is not None:
        _MOD_PROGRESS_SINK.append(fn)


def _mod_progress_cb(phase: str, pct: float, detail: str) -> None:
    """Forward a steam_mod / game_mod / mod_source progress tick to the
    React UI. The trailing () is what actually dispatches the eel call -
    same form as _push_download_progress / _push_cache_event. Wrapped so
    a UI hiccup can never crash the install worker.

    An "error" phase = a handled install/apply failure → report it silently
    (opt-in gated) so field install failures surface in the dashboard. The
    `detail` is a Hebrew user message; PII is scrubbed by the reporter."""
    if phase == "error":
        _event("install_error", detail, source="mod_install", severity="error",
               game=_CUR_INSTALL_GAME[0] or "")
    for _sink in list(_MOD_PROGRESS_SINK):
        try:
            _sink({"phase": phase, "pct": round(pct, 1), "message": detail})
        except Exception:
            pass
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
            # whether populate_cache succeeded or not - no clutter left.
            shutil.rmtree(extracted.parent, ignore_errors=True)
        if not r.get("ok"):
            return r
    return _steam_mod.enable(_mod_progress_cb)


@eel.expose
def get_steam_mod_state() -> dict:
    """{cached, enabled, version} - drives the AppsView button state machine."""
    return _steam_mod.status()


@eel.expose
def set_steam_mod_enabled(enabled: bool) -> dict:
    """Toggle the mod on/off - pure local file ops, no re-download."""
    if enabled:
        return _steam_mod.enable(_mod_progress_cb)
    return _steam_mod.disable(_mod_progress_cb)


@eel.expose
def clear_steam_mod_cache() -> dict:
    """Revert Steam to its originals and delete the local mod cache."""
    return _steam_mod.clear_cache()


# ─────────────────────────────────────────────────────────────
# VirtualDJ 2026 Hebrew - same lifecycle as Steam. Files from the CLOUD
# (Worker slug `virtualdj-hebrew` → GitHub release), NOT bundled.
# ─────────────────────────────────────────────────────────────
_VDJ_ID   = "virtualdj"
_VDJ_SLUG = "virtualdj-hebrew"


# Titles whose ownership was CONFIRMED (owned=True) at least once this session.
# Ownership is permanent per account, so a later transient network blip (which
# makes auth_owns_game fail-closed to False) must NOT re-lock a confirmed buyer.
_owned_confirmed: set[str] = set()


def _owns_confirm(game_id: str) -> bool:
    """auth_owns_game + remember a confirmed purchase for the session."""
    owned = auth_owns_game(game_id)
    if owned:
        _owned_confirmed.add(game_id)
    return owned


# Short-lived ownership memo for the READ path (see _owns_ui).
_OWNS_CACHE: dict[str, tuple[float, bool]] = {}
_OWNS_TTL_YES = 600.0     # a purchase does not expire
_OWNS_TTL_NO  = 1.5       # short - the post-purchase burst poller runs every 3s


def _owns_ui(game_id: str) -> bool:
    """Ownership for a UI/STATE read, memoized.

    `auth.owns_game` is an UNCACHED HTTPS round-trip, and opening a paid game's
    panel asks for it TWICE - once from `get_game_mod_state` (header chips) and
    once from the game's own native state RPC - so the panel blocked on two
    sequential network calls before it could paint its buttons. That is a real
    part of the "the screen fills in in stages" feel.

    A positive answer is cached long (ownership is permanent per account); a
    negative one only ~1.5s, which collapses the duplicate calls of a single
    panel open while still letting the 3s post-purchase burst poller flip the
    CTA promptly. Cleared on every sign-in/sign-out alongside _owned_confirmed.

    ⚠️ Install GATES do not use this - they call `auth_owns_game` directly, so
    no gate is ever decided by a cached value.
    """
    now = time.monotonic()
    hit = _OWNS_CACHE.get(game_id)
    if hit is not None and now - hit[0] < (_OWNS_TTL_YES if hit[1] else _OWNS_TTL_NO):
        return hit[1]
    owned = auth_owns_game(game_id)
    _OWNS_CACHE[game_id] = (now, owned)
    if owned:
        _owned_confirmed.add(game_id)
    return owned


def _vdj_owned() -> bool:
    """DRM gate - a paid software mod installs only for a buyer. Free → always."""
    return True if _game_price_cents(_VDJ_ID) <= 0 else _owns_confirm(_VDJ_ID)


def _run_vdj_install() -> None:
    """Background worker: download (cloud) → cache → enable, streaming progress
    and ALWAYS ending on a terminal done/error tick - the same contract every
    game applier honours, and what the UI waits on to clear the progress bar.
    (Running it inline on the RPC thread froze the window and left the bar
    spinning forever, because no terminal tick was ever emitted.)"""
    try:
        if not _vdj_owned():
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        if not _vdj.is_cached():
            try:
                extracted, version = _mod_source.fetch_and_extract(_mod_progress_cb, slug=_VDJ_SLUG)
            except _mod_source.IntegrityError as e:
                _mod_progress_cb("error", 0, f"כשל אימות שלמות הקובץ: {e}")
                return
            except _mod_source.ModSourceError as e:
                _mod_progress_cb("error", 0, f"כשל הורדה: {e}")
                return
            try:
                r = _vdj.populate_cache(extracted, version)
            finally:
                shutil.rmtree(extracted.parent, ignore_errors=True)
            if not r.get("ok"):
                _mod_progress_cb("error", 0, r.get("error") or "כשל בהתקנה")
                return
        r = _vdj.enable(_mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהתקנה")
            return
        # Follow the mod: pick the Arabic slot so the UI comes up in Hebrew.
        try:
            _game_language.set_mode(_VDJ_ID, "hebrew", installed=True)
        except Exception:                               # pragma: no cover
            pass
        _mod_progress_cb("done", 100,
            'הותקן! ב-VirtualDJ: Options → Language → "עברית" (חריץ הערבית).')
    except Exception as e:                              # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def apply_virtualdj_translation() -> dict:
    """Kick off the VirtualDJ install on a background worker. Progress + a
    terminal done/error tick stream over mod_install_progress."""
    if not _vdj_owned():
        return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
    import gevent
    gevent.spawn(_run_vdj_install)
    return {"ok": True, "started": True}


@eel.expose
def get_virtualdj_mod_state() -> dict:
    """{cached, enabled, version, owned, priceCents} - drives the VirtualDJ CTA
    (the paid-mod gate needs owned/priceCents, same as a paid game mod)."""
    st = _vdj.status()
    price = _game_price_cents(_VDJ_ID)
    st["priceCents"] = price
    st["owned"] = True if price <= 0 else _owns_confirm(_VDJ_ID)
    return st


@eel.expose
def set_virtualdj_mod_enabled(enabled: bool) -> dict:
    """Toggle the mod on/off - pure local file ops, no re-download."""
    if enabled:
        if not _vdj_owned():
            return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
        return _vdj.enable(_mod_progress_cb)
    return _vdj.disable(_mod_progress_cb)


@eel.expose
def clear_virtualdj_mod_cache() -> dict:
    """Revert VirtualDJ to its original and delete the local mod cache."""
    return _vdj.clear_cache()


# ─────────────────────────────────────────────────────────────
# Borderless Gaming Hebrew - FREE software mod, cloud payload
# (Worker slug `borderless-gaming-hebrew` → GitHub release).
#
# Two surfaces: the app interface (a real added `he-IL` locale) and the effect
# editor, whose text lives inside the .slang shader sources and therefore has to
# be applied to the COMPILED EFFECT CACHE - see borderless_gaming_mod for why.
# Everything lands in %APPDATA%; the Steam folder is never touched.
# ─────────────────────────────────────────────────────────────
_BG_ID   = "borderless-gaming"
_BG_SLUG = "borderless-gaming-hebrew"


def _bg_install_path() -> Path | None:
    return _software_install_path(_BG_ID)


def _bg_effects_dir() -> Path | None:
    """<install>\\effects - the parameter anchors are read from the shaders."""
    base = _bg_install_path()
    if not base:
        return None
    d = Path(base) / "effects"
    return d if d.is_dir() else None


def _bg_owned() -> bool:
    return True if _game_price_cents(_BG_ID) <= 0 else _owns_confirm(_BG_ID)


def _run_bg_install() -> None:
    """Background worker: download (cloud) → cache → enable, always ending on a
    terminal done/error tick."""
    try:
        if not _bg_owned():
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        if not _bg.is_cached():
            try:
                extracted, version = _mod_source.fetch_and_extract(_mod_progress_cb, slug=_BG_SLUG)
            except _mod_source.IntegrityError as e:
                _mod_progress_cb("error", 0, f"כשל אימות שלמות הקובץ: {e}")
                return
            except _mod_source.ModSourceError as e:
                _mod_progress_cb("error", 0, f"כשל הורדה: {e}")
                return
            try:
                r = _bg.populate_cache(extracted, version)
            finally:
                shutil.rmtree(extracted.parent, ignore_errors=True)
            if not r.get("ok"):
                _mod_progress_cb("error", 0, r.get("error") or "כשל בהתקנה")
                return
        r = _bg.enable(_mod_progress_cb, effects_dir=_bg_effects_dir())
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהתקנה")
            return
        # The effect editor is only compiled after the app has run once; say so
        # instead of leaving the user wondering why half of it is still English.
        if r.get("effectStrings"):
            _mod_progress_cb("done", 100, "הותקן! פתחו מחדש את Borderless Gaming.")
        else:
            _mod_progress_cb("done", 100,
                "הותקן! הפעילו את Borderless Gaming פעם אחת, סגרו, "
                "ולחצו שוב על התקנה כדי לתרגם גם את עורך האפקטים.")
    except Exception as e:                              # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def apply_borderless_gaming_translation() -> dict:
    """Kick off the Borderless Gaming install on a background worker."""
    if not _bg_owned():
        return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
    import gevent
    gevent.spawn(_run_bg_install)
    return {"ok": True, "started": True}


@eel.expose
def get_borderless_gaming_mod_state() -> dict:
    """{cached, enabled, version, owned, priceCents} - drives the card CTA."""
    st = _bg.status()
    price = _game_price_cents(_BG_ID)
    st["priceCents"] = price
    st["owned"] = True if price <= 0 else _owns_confirm(_BG_ID)
    return st


@eel.expose
def set_borderless_gaming_mod_enabled(enabled: bool) -> dict:
    """Toggle the mod on/off - pure local file ops, no re-download."""
    if enabled:
        if not _bg_owned():
            return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
        return _bg.enable(_mod_progress_cb, effects_dir=_bg_effects_dir())
    return _bg.disable(_mod_progress_cb)


@eel.expose
def clear_borderless_gaming_mod_cache() -> dict:
    """Revert Borderless Gaming and delete the local mod cache."""
    return _bg.clear_cache()


# ─────────────────────────────────────────────────────────────
# SignalRGB Hebrew - software, cloud-first (Worker slug `signalrgb-hebrew`).
# The mod package's own install.py applies FOUR surfaces + the registry locale;
# this side downloads it and runs deploy()/revert() in-process.
# ─────────────────────────────────────────────────────────────
_SRGB_ID   = "signalrgb"
_SRGB_SLUG = "signalrgb-hebrew"


def _srgb_owned() -> bool:
    """DRM gate - a paid software mod installs only for a buyer. Free → always."""
    return True if _game_price_cents(_SRGB_ID) <= 0 else _owns_confirm(_SRGB_ID)


def _run_srgb_install() -> None:
    """Background worker: download (cloud) → cache → enable, always ending on a
    terminal done/error tick (the contract the UI waits on)."""
    try:
        if not _srgb_owned():
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        # Pull the package if it's MISSING or STALE - a newer version may have
        # been published since we cached (e.g. a fix for a new SignalRGB
        # release). Without this the stale cache is used forever and the update
        # never reaches the user (this is why a published beta.2 kept installing
        # the cached beta.1).
        need_dl = not _srgb.is_cached()
        if not need_dl:
            try:
                mf = _bounded(lambda: _mod_source.fetch_manifest(slug=_SRGB_SLUG), 8.0, None)
                latest = (mf or {}).get("version")
                cached = _srgb.read_state().get("version")
                if latest and latest != cached:
                    need_dl = True
            except Exception:                           # offline / manifest error
                pass                                    # -> use the cache we have
        if need_dl:
            try:
                extracted, version = _mod_source.fetch_and_extract(_mod_progress_cb, slug=_SRGB_SLUG)
            except _mod_source.IntegrityError as e:
                _mod_progress_cb("error", 0, f"כשל אימות שלמות הקובץ: {e}")
                return
            except _mod_source.ModSourceError as e:
                _mod_progress_cb("error", 0, f"כשל הורדה: {e}")
                return
            try:
                r = _srgb.populate_cache(extracted, version)
            finally:
                shutil.rmtree(extracted.parent, ignore_errors=True)
            if not r.get("ok"):
                _mod_progress_cb("error", 0, r.get("error") or "כשל בהתקנה")
                return
        r = _srgb.enable(_mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהתקנה")
            return
        _mod_progress_cb("done", 100,
            "הותקן! הפעילו מחדש את SignalRGB - הוא כבר בעברית.")
    except Exception as e:                              # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def apply_signalrgb_translation() -> dict:
    """Kick off the SignalRGB install on a background worker."""
    if not _srgb_owned():
        return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
    import gevent
    gevent.spawn(_run_srgb_install)
    return {"ok": True, "started": True}


@eel.expose
def get_signalrgb_mod_state() -> dict:
    """{cached, enabled, version, owned, priceCents} - drives the card CTA."""
    st = _srgb.status()
    price = _game_price_cents(_SRGB_ID)
    st["priceCents"] = price
    st["owned"] = True if price <= 0 else _owns_confirm(_SRGB_ID)
    return st


@eel.expose
def set_signalrgb_mod_enabled(enabled: bool) -> dict:
    """Toggle the mod on/off - re-applies or reverts (no re-download)."""
    if enabled:
        if not _srgb_owned():
            return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
        return _srgb.enable(_mod_progress_cb)
    return _srgb.disable(_mod_progress_cb)


@eel.expose
def clear_signalrgb_mod_cache() -> dict:
    """Revert SignalRGB and delete the local mod cache."""
    return _srgb.clear_cache()


@eel.expose
def restart_signalrgb() -> dict:
    """Close SignalRGB and relaunch it so a just-applied translation loads.
    The Hebrew .qm is read at SignalRGB startup, so the app must restart for
    the translation to take effect - fired by the 'restart now?' prompt the
    launcher shows after a successful install."""
    import subprocess as _sp
    import time as _t
    try:
        _sp.run(["taskkill", "/F", "/IM", "SignalRgb.exe"],
                capture_output=True, timeout=15)
    except Exception:                                   # pragma: no cover
        pass                                            # not running / can't kill
    _t.sleep(1.2)                                       # let the single-instance lock release
    return launch_game(_SRGB_ID)                        # reuses the software exe resolution + WinError-740 handling


# ─────────────────────────────────────────────────────────────
# Download-distributed GAME mods (e.g. Cyberpunk 2077).
# A game whose GameConfig carries a `mod_slug` is fetched through the
# Cloudflare Worker proxy and managed via translation_manager.game_mod:
#   download → cache → install → disable → clear-cache.
# Paid mods (catalog priceCents > 0) gate install on auth ownership.
# ─────────────────────────────────────────────────────────────
def _game_price_cents(game_id: str) -> int:
    # `priceCents` = the live/shaped catalog; `price_cents` = the offline bundled
    # dataclass (asdict). Read BOTH so a paid title stays gated even on the cold
    # bundled fallback (a missing key would be 0 = free-for-everyone DRM hole).
    cg = _catalog_by_id(game_id) or {}
    try:
        return int(cg.get("priceCents") or cg.get("price_cents") or 0)
    except (TypeError, ValueError):
        return 0


def _owned_fields(game_id: str) -> dict:
    """`{priceCents, owned}` - the two keys EVERY purchase-aware CTA reads.

    The panel draws the "רכישה - ₪N" button from `priceCents > 0 && !owned`, and
    the "✓ נרכש" chip from `priceCents > 0 && owned`. The NATIVE appliers
    (W3/HL/PT/GoWR/WD2/SM2) returned neither key, so on a paid native title the
    buy button could not render at all - and the chip, fed by
    `get_game_mod_state`'s slug-less branch which hardcoded `owned: True`, lied
    "✓ נרכש" to an account that never bought it. Price comes from the LIVE
    catalog, so a title that turns paid is reflected without a rebuild; a free
    mod short-circuits to owned=True with no network call.
    """
    price = _game_price_cents(game_id)
    return {"priceCents": price,
            "owned": True if price <= 0 else _owns_ui(game_id)}


@eel.expose
def get_game_mod_state(game_id: str) -> dict:
    """State for a download-distributed game mod (drives GameDetailPanel).
    {cached, installed, version, owned, priceCents, modSlug, hasPath}."""
    cfg   = _config_for(game_id)
    base  = _install_path(game_id)
    price = _game_price_cents(game_id)
    slug  = cfg.mod_slug if cfg else ""
    if not slug:
        # No mod_slug = a NATIVE applier (W3/HL/PT/GoWR/WD2/SM2/GTAV). This branch
        # still feeds the header chips, so `owned` must be the REAL answer: it was
        # hardcoded True, which painted "✓ נרכש" on a paid title the account never
        # bought. The install state itself comes from the game's own state RPC.
        return {
            "cached": False, "installed": False, "version": None,
            **_owned_fields(game_id), "modSlug": "",
            "hasPath": base is not None,
        }
    st = _game_mod.status(game_id, _deploy_root(game_id), cfg.mod_files if cfg else [])
    # Free mods are always "owned"; paid mods consult the auth DRM check (memoized
    # for the read path - the install gate still asks the server directly).
    owned = True if price <= 0 else _owns_ui(game_id)
    return {
        **st,
        "owned":      owned,
        "priceCents": price,
        "modSlug":    slug,
        "hasPath":    base is not None,
    }


def _native_latest_version(slug: str, fallback: str) -> str:
    """Latest published version of a native mod = its Worker/GitHub manifest
    version. This is what lets a native applier (SM2/WD2/GoWR) offer a server-side
    update WITHOUT a launcher rebuild - the install path downloads that version
    from the Worker (bundled payload = offline fallback). Soft-fails to the bundled
    version string when offline / the slug isn't deployed yet."""
    try:
        v = _mod_source.fetch_manifest(slug=slug).get("version")
        return v or fallback
    except Exception:                                   # pragma: no cover
        return fallback


def _native_update_status(game_id: str) -> dict | None:
    """Update status for a NATIVE-applier mod (no mod_slug). SM2/WD2/GoWR compare
    the installed version against the Worker manifest (server-side updates, no
    rebuild); GTAV compares against the BUNDLED payload version (no Worker slug yet,
    so this lights up after the launcher updates itself, prompting a re-apply).
    Returns {installed, installedVersion, latestVersion, updateAvailable} or None
    for a non-native game. Soft-fails (never raises)."""
    if game_id == _SM2_ID:
        st = get_spiderman2_mod_state()
        iv = st.get("version")
        latest = None
        try:
            latest = _mod_source.fetch_manifest(slug=_SM2_SLUG).get("version")
        except Exception:                              # pragma: no cover
            latest = None
        upd = bool(st.get("installed")) and bool(latest) and _offer_update(_SM2_ID, latest, iv)
        return {"installed": bool(st.get("installed")), "installedVersion": iv,
                "latestVersion": latest, "updateAvailable": bool(upd)}
    if game_id == _WD2_ID:
        st = get_watchdogs2_mod_state()
        latest = _native_latest_version(_WD2_SLUG, _WD2_BUNDLED_VERSION)
    elif game_id == _GTAV_ID:
        st = get_gtav_mod_state()
        latest = _native_latest_version(_GTAV_SLUG, _GTAV_BUNDLED_VERSION)
    elif game_id == _GOWR_ID:
        st = get_gowr_mod_state()
        latest = _native_latest_version(_GOWR_SLUG, _GOWR_BUNDLED_VERSION)
    elif game_id == _HL_ID:
        st = get_hogwarts_mod_state()
        latest = _native_latest_version(_HL_SLUG, st.get("version") or "")
    elif game_id == _W3_ID:
        st = get_witcher3_mod_state()
        latest = _native_latest_version(_W3_SLUG, st.get("version") or "")
    elif game_id == _PT_ID:
        st = get_plaguetale_mod_state()
        latest = _native_latest_version(_PT_SLUG, st.get("version") or "")
    else:
        return None
    iv = st.get("version")
    upd = bool(st.get("installed")) and _offer_update(game_id, latest, iv)
    return {"installed": bool(st.get("installed")), "installedVersion": iv,
            "latestVersion": latest, "updateAvailable": bool(upd)}


def _with_offline_update(game_id: str, installed: bool,
                         installed_version: str | None, res: dict) -> dict:
    """Fold the OFFLINE-package signal into an update-check result.

    On a machine with no internet the normal (server) check finds nothing, so a
    newer version carried by a pre-built offline package would be INVISIBLE.
    Comparing the APPLIED version against the bundled one is purely local, which
    is what makes an offline update discoverable at all. `updateSource` tells the
    UI which wording to use ("עדכון" vs "עדכון אופליין").
    """
    res.setdefault("updateSource", "network" if res.get("updateAvailable") else "")
    if not installed:
        return res
    try:
        ob = _offline_bundle.offline_update(game_id, installed_version, _version_is_newer)
    except Exception:                                   # pragma: no cover
        return res
    if not ob:
        return res
    # Respect the same beta opt-in the network path uses.
    if not _offer_update(game_id, ob["version"], installed_version):
        return res
    # Both sources have something → the NEWER one wins (usually the server).
    net_v = res.get("latestVersion") if res.get("updateAvailable") else None
    if net_v and not _version_is_newer(ob["version"], net_v):
        return res
    res["updateAvailable"] = True
    res["latestVersion"]   = ob["version"]
    res["updateSource"]    = "offline"
    return res


@eel.expose
def check_game_mod_update(game_id: str) -> dict:
    """Is a newer translation-mod version available than the installed one?
    Lightweight - fetches ONLY the manifest (no archive). The Qt bridge runs
    this off the GUI thread so the network call never freezes the panel. Handles
    BOTH download-distributed mods (mod_slug) and native appliers (SM2/WD2/GTAV).
    {ok, supported, kind, installed, installedVersion, latestVersion, updateAvailable, error}."""
    if game_id in (_SM2_ID, _WD2_ID, _GTAV_ID, _GOWR_ID, _HL_ID, _W3_ID, _PT_ID):
        ns = _native_update_status(game_id) or {}
        return _with_offline_update(game_id, bool(ns.get("installed")),
                                    ns.get("installedVersion"),
               {"ok": True, "supported": True, "kind": "native",
                "installed":        bool(ns.get("installed")),
                "installedVersion": ns.get("installedVersion"),
                "latestVersion":    ns.get("latestVersion"),
                "updateAvailable":  bool(ns.get("updateAvailable")), "error": ""})
    cfg = _config_for(game_id)
    if cfg is None or not cfg.mod_slug:
        return {"ok": True, "supported": False, "updateAvailable": False}
    st   = _game_mod.status(game_id, _deploy_root(game_id), cfg.mod_files)
    installed = bool(st.get("installed"))
    # The version APPLIED to the game (not the one sitting in the cache) - an
    # offline package may have seeded a newer payload into the cache already.
    iv = _game_mod.applied_version(game_id) or st.get("version")
    try:
        latest = _mod_source.fetch_manifest(slug=cfg.mod_slug).get("version")
    except Exception as e:                              # pragma: no cover
        # OFFLINE: no server answer, but a bundle may still carry something new.
        return _with_offline_update(game_id, installed, iv,
               {"ok": False, "supported": True, "kind": "download", "installed": installed,
                "installedVersion": iv, "latestVersion": None,
                "updateAvailable": False, "error": str(e)})
    upd = bool(installed) and _offer_update(game_id, latest, iv)
    return _with_offline_update(game_id, installed, iv,
           {"ok": True, "supported": True, "kind": "download", "installed": installed,
            "installedVersion": iv, "latestVersion": latest,
            "updateAvailable": upd, "error": ""})


@eel.expose
def get_mod_updates() -> list:
    """Every download-distributed translation mod that is INSTALLED and has a
    newer version available - drives the Downloads/Updates screen's mod
    section. One lightweight manifest GET per configured mod."""
    out:  list[dict] = []
    seen: set[str]   = set()
    # Overall TIME BUDGET. This fans out one network manifest GET per installed
    # mod (~10-15 of them, sequentially), so on a slow/blocked network the
    # accumulated waits used to blow past the bridge's slot guard and CRASH the
    # app (real report: "get_mod_updates did not return within 120.0s"). Stop
    # early and return what we already found - an update check is advisory and
    # never worth a hang. (mod_source.MANIFEST_TIMEOUT caps each single GET.)
    #
    # The other half of the cost is per-game STATE: a native applier's
    # is_applied() may hash a multi-GB game file. That is memoised by file
    # identity (see gowr_mod._SHA_MEMO) so it is paid at most once per file
    # version instead of on every poll - which is what actually caused the
    # "did not return within 120/180s" reports. The budget below still bounds
    # the fan-out; it is checked BETWEEN items, so one slow item can overrun it
    # (the bridge slot fails safe with an empty list rather than crashing).
    import time as _t
    _t0, _BUDGET_S = _t.monotonic(), 30.0
    for cfg in GAME_CONFIGS.values():
        if _t.monotonic() - _t0 > _BUDGET_S:
            break
        gid = cfg.internal_id
        if not cfg.mod_slug or gid in seen:
            continue
        seen.add(gid)
        try:
            # Cap this single item: _game_mod.status() may hash a multi-GB game
            # file for a content is_applied() check. Bounded so one slow item can
            # never overrun the whole sweep (fails safe: skip this game's row).
            st   = _bounded(lambda: _game_mod.status(gid, _deploy_root(gid), cfg.mod_files),
                            8.0, {}) or {}
            if not st.get("installed"):
                continue
            iv     = _game_mod.applied_version(gid) or st.get("version")
            latest, source = None, ""
            try:
                # Bound the network manifest GET too. requests' own timeout does
                # NOT reliably cap a stalled TLS handshake / DNS / byte-drip, so a
                # single hung GET here (the one slow call in this loop that was NOT
                # wrapped) could overrun the whole sweep past the 180 s slot guard
                # - the between-item budget is only checked BEFORE an item, never
                # during it (real recurring report: get_mod_updates did not return
                # within 180 s). Same per-item cap as the status hash above.
                mf     = _bounded(lambda: _mod_source.fetch_manifest(slug=cfg.mod_slug), 8.0, None)
                latest = (mf or {}).get("version")
                if latest and _offer_update(gid, latest, iv):
                    source = "network"
            except Exception:                          # offline → the bundle may still have one
                latest = None
            if not source:
                r = _with_offline_update(gid, True, iv,
                                         {"updateAvailable": False, "latestVersion": latest})
                if r.get("updateAvailable"):
                    latest, source = r.get("latestVersion"), "offline"
            if source:
                cg = _catalog_by_id(gid) or {}
                out.append({
                    "gameId":           gid,
                    "titleEn":          cg.get("titleEn") or cfg.name,
                    "titleHe":          cg.get("titleHe") or cfg.name,
                    "installedVersion": iv,
                    "latestVersion":    latest,
                    "kind":             "download",
                    "updateSource":     source,
                })
        except Exception:                              # pragma: no cover
            continue
    # Native-applier mods (no mod_slug): SM2 (GitHub manifest) + WD2/GTAV
    # (bundled - a newer bundle arrives via a launcher self-update). These DON'T
    # install via download_and_install_game_mod, so the row carries kind=native
    # and the UI dispatches to the right install RPC.
    for gid in (_SM2_ID, _WD2_ID, _GTAV_ID, _GOWR_ID, _HL_ID, _W3_ID, _PT_ID):
        if _t.monotonic() - _t0 > _BUDGET_S:
            break
        if gid in seen:
            continue
        seen.add(gid)
        try:
            # Same per-item cap: a native applier's state read (SM2/GoWR) does a
            # content hash of a multi-GB game file. Bound it so a first-time hash
            # can't blow the 180 s slot guard - it warms its memo in the bg.
            ns = _bounded(lambda: _native_update_status(gid), 8.0, None) or {}
            # Same offline fold as the download loop: with no internet the
            # server check is silent, but a pre-built package may carry a
            # newer payload that is already on disk.
            ns = _with_offline_update(gid, bool(ns.get("installed")),
                                      ns.get("installedVersion"), dict(ns))
            if ns.get("updateAvailable"):
                cg  = _catalog_by_id(gid) or {}
                cfg = _config_for(gid)
                out.append({
                    "gameId":           gid,
                    "titleEn":          cg.get("titleEn") or (cfg.name if cfg else gid),
                    "titleHe":          cg.get("titleHe") or (cfg.name if cfg else gid),
                    "installedVersion": ns.get("installedVersion"),
                    "latestVersion":    ns.get("latestVersion"),
                    "kind":             "native",
                    "updateSource":     ns.get("updateSource") or "network",
                })
        except Exception:                              # pragma: no cover
            continue
    return out


@eel.expose
def get_update_prefs() -> dict:
    """Mod-update preferences for the Settings screen: {betaChannel,
    betaOverrides}. (Silent auto-update was removed - updates are always
    surfaced as an in-app + Windows notification, never installed silently.)"""
    from translation_manager import launcher_prefs as _p
    ov = _p.load().get("mod_beta_overrides")
    return {
        "betaChannel":   _p.get_beta_channel(),
        "betaOverrides": ov if isinstance(ov, dict) else {},
    }


@eel.expose
def set_update_prefs(beta_channel=None) -> dict:
    """Set the global beta-channel opt-in."""
    from translation_manager import launcher_prefs as _p
    if beta_channel is not None:
        _p.set_beta_channel(bool(beta_channel))
    return get_update_prefs()


@eel.expose
def notify_os(title: str, body: str) -> bool:
    """Show a native Windows notification (tray balloon/toast). No-op on the
    Eel dev build (no system tray); under the Qt shell the bridge's own
    notify_os Slot handles it (this function is only hit via the Eel
    transport). Best-effort - never raises."""
    return True


# ── Custom frameless title-bar window controls (Eel transport stubs) ──
# The Qt build routes these through the bridge (which drives the real window);
# on the Eel dev build there is no Qt window, so these are safe no-ops and the
# frontend title bar stays hidden (window_is_frameless → False).
@eel.expose
def restart_app() -> bool:
    """Qt build: the bridge slot relaunches the real window. Eel dev build has no
    process to restart cleanly → no-op (the UI just closes its restart prompt)."""
    return False
@eel.expose
def window_is_frameless() -> bool: return False
@eel.expose
def window_is_maximized() -> bool: return False
@eel.expose
def window_minimize() -> None: return None
@eel.expose
def window_toggle_maximize() -> bool: return False
@eel.expose
def window_close() -> None: return None
@eel.expose
def window_start_drag() -> None: return None
@eel.expose
def window_start_resize(edge: str) -> None: return None

# ── "ביג-לאנץ" console shell (Eel transport stubs) ──
# The Qt bridge owns the real window state; under the Eel dev build the shell
# still RENDERS (open http://localhost:8000/#big) - it just can't drive a
# borderless-fullscreen native window, so these are honest no-ops.
_BIG_LAUNCH_REQUESTED = False


def set_big_launch_requested(on: bool) -> None:
    """Called by main_qt.py when the process was started with --big, so the
    frontend can tell 'booted straight into the console shell' from 'switched
    into it at runtime'. Plain module state; never raises."""
    global _BIG_LAUNCH_REQUESTED
    _BIG_LAUNCH_REQUESTED = bool(on)


@eel.expose
def big_launch_requested() -> bool: return bool(_BIG_LAUNCH_REQUESTED)
@eel.expose
def set_big_launch(on: bool) -> bool: return False


# ── "ביג-לאנץ" as a SEPARATE EXE (the Steam / Big-Picture shape) ──
# Two shells, two executables: TranslationManager.exe is the desktop launcher,
# BigLaunch.exe is the 10ft console shell. Each can start on its own, and each
# can hand off to the other - BigLaunch calls back via the hebrewhub:// deep
# link, and this is the launcher -> console direction.

def _big_launch_exe() -> "str | None":
    """Locate BigLaunch.exe. Next to the running exe when installed, or the
    dev publish folder. Returns None rather than raising - a missing console
    shell must never break the desktop launcher."""
    import os, sys
    from pathlib import Path
    cands = []
    try:
        if getattr(sys, "frozen", False):
            cands.append(Path(sys.executable).resolve().parent / "BigLaunch.exe")
        here = Path(__file__).resolve().parent
        cands += [here / "dist_biglaunch" / "BigLaunch.exe",
                  here / "biglaunch" / "bin" / "Release" / "net8.0-windows"
                       / "win-x64" / "publish" / "BigLaunch.exe"]
    except Exception:
        return None
    for p in cands:
        try:
            if p.is_file():
                return str(p)
        except Exception:
            continue
    return None


@eel.expose
def big_launch_available() -> bool:
    """Is the console shell installed on this machine?"""
    return _big_launch_exe() is not None and _dotnet_desktop_ok()


def _dotnet_desktop_ok() -> bool:
    """Is a .NET 8+ Desktop Runtime present? BigLaunch.exe is published
    framework-dependent (a self-contained build would add ~150 MB to an installer
    that was just trimmed), so the runtime is a real prerequisite. Checking the
    shared-framework folder is cheap and needs no registry or subprocess.
    Fails OPEN - if the layout is ever unreadable we let the launch attempt
    proceed rather than hide a working shell behind a bad probe."""
    import os
    from pathlib import Path
    try:
        roots = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "dotnet",
                 Path(os.environ.get("DOTNET_ROOT", "")) if os.environ.get("DOTNET_ROOT") else None]
        for r in roots:
            if not r:
                continue
            d = r / "shared" / "Microsoft.WindowsDesktop.App"
            if not d.is_dir():
                continue
            for v in d.iterdir():
                major = v.name.split(".", 1)[0]
                if major.isdigit() and int(major) >= 8:
                    return True
        return False
    except Exception:
        return True


@eel.expose
def open_big_launch() -> dict:
    """Start BigLaunch.exe. Detached, non-elevated, and never fatal."""
    import subprocess
    from pathlib import Path
    exe = _big_launch_exe()
    if not exe:
        return {"ok": False, "error": "ביג-לאנץ׳ אינו מותקן במחשב הזה"}
    if not _dotnet_desktop_ok():
        # Without this the failure is SILENT: BigLaunch.exe is framework-dependent,
        # so on a machine with no .NET 8 Desktop Runtime it exits immediately while
        # Popen still succeeds - the user clicks and nothing happens, forever.
        return {"ok": False,
                "error": "כדי להפעיל את ביג-לאנץ׳ צריך להתקין את .NET 8 Desktop Runtime"}
    try:
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP - the console shell must
        # outlive the launcher, exactly like Steam's Big Picture.
        subprocess.Popen([exe], cwd=str(Path(exe).parent),
                         creationflags=0x00000008 | 0x00000200,
                         close_fds=True)
        return {"ok": True}
    except Exception as e:                                    # pragma: no cover
        log.warning("open_big_launch failed: %s", e)
        return {"ok": False, "error": "פתיחת ביג-לאנץ׳ נכשלה"}
@eel.expose
def app_quit() -> None: return None
@eel.expose
def get_custom_titlebar() -> bool:
    from translation_manager import launcher_prefs as _p
    try: return bool(_p.get_custom_titlebar())
    except Exception: return True   # real default is True (frameless on)
@eel.expose
def set_custom_titlebar(enabled: bool) -> bool:
    from translation_manager import launcher_prefs as _p
    try: return bool(_p.set_custom_titlebar(bool(enabled)))
    except Exception: return False


@eel.expose
def set_mod_beta_override(game_id: str, enabled=None) -> dict:
    """Per-mod beta opt-in override (None clears it → fall back to the global).
    A PAID title the user hasn't bought exposes no mod settings - no-op."""
    from translation_manager import launcher_prefs as _p
    if _title_locked(game_id):
        return get_update_prefs()
    _p.set_mod_beta_override(game_id, None if enabled is None else bool(enabled))
    return get_update_prefs()


def _display_version() -> str:
    """The FULL launcher version shown everywhere - joins the clean SemVer core
    with the channel and the per-build counter, e.g. "v1.0.0-dev.7". A stable
    channel shows just "v1.0.0"; a non-stable channel with no counter (dev run /
    old build) shows "v1.0.0-dev"."""
    core = LAUNCHER_VERSION
    if not LAUNCHER_CHANNEL or LAUNCHER_CHANNEL == "stable":
        return f"v{core}"
    suffix = f"-{LAUNCHER_CHANNEL}"
    # Append the per-build counter ONLY on the developer channels (dev/canary),
    # where it's useful. A public beta/stable shows a clean "v1.0.0-beta" - the
    # counter is monotonic across channels so "beta.19" reads like 19 betas.
    # (Mirrors the website DownloadsPage devSuffix gate.)
    if DEV_BUILD and LAUNCHER_CHANNEL in ("dev", "canary"):
        suffix += f".{DEV_BUILD}"
    return f"v{core}{suffix}"


@eel.expose
def get_app_info() -> dict:
    """Launcher identity for the UI: {version, channel, devBuild, display}.
    `display` is the FULL joined version (v1.0.0-dev.N) - the single source of
    truth the UI renders verbatim. The channel + counter are baked per-build."""
    return {
        "version":  LAUNCHER_VERSION,
        "channel":  LAUNCHER_CHANNEL,
        "devBuild": DEV_BUILD,
        "display":  _display_version(),
    }


def _cp2077_disable_crash_reporter(game_root) -> None:
    """Rename bin\\x64\\REDEngineErrorReporter.exe → .bak.

    Running CP2077 in the Arabic locale slot fires CDPR's crash-reporter
    window on the engine's teardown when quitting - harmless (the
    session already ended, saves are safe) but ugly. With the reporter
    exe renamed the engine simply can't spawn it, so no window appears.
    This is the per-mod equivalent of the manual fix applied to the
    project's own game copy. Reversible - see the restore fn below."""
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
    """Undo _cp2077_disable_crash_reporter - restore REDEngineErrorReporter.exe
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


# SM2 is now distributed via GitHub Release (slug 'spiderman2-hebrew'), like
# CP2077 - new versions ship without a launcher rebuild. The bundled .modular
# files remain as an OFFLINE fallback only.
_SM2_SLUG = "spiderman2-hebrew"


def _sm2_cache_dir() -> Path:
    d = Path.home() / ".translation_manager" / "mod_cache" / "spiderman2"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sm2_state() -> dict:
    try:
        return json.loads((_sm2_cache_dir() / "state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sm2_write_state(d: dict) -> None:
    try:
        (_sm2_cache_dir() / "state.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:                                   # pragma: no cover
        pass


def _sm2_payload_files() -> list:
    """The BUNDLED Spider-Man 2 Hebrew mod files (offline fallback).
    Resolves for both the frozen build (sys._MEIPASS) and a dev run."""
    base = getattr(sys, "_MEIPASS", None)
    roots = []
    if base:
        roots.append(Path(base) / "translation_manager" / "assets" / "spiderman2")
    roots.append(ROOT / "translation_manager" / "assets" / "spiderman2")
    for r in roots:
        full = r / "hebrew_full.modular"
        if full.is_file():
            out = [full]
            font = r / "hebrew_font_v7.modular"
            if font.is_file():
                out.append(font)
            return out
    return []


def _sm2_download_payloads(cb=None) -> tuple[list, str | None]:
    """Download the SM2 mod from its GitHub Release (via the Worker), cache the
    .modular files, and return (payload_paths, version). On ANY failure falls
    back to the bundled payload → (bundled_paths, None). The bundled files keep
    SM2 installable fully offline."""
    try:
        extracted, version = _mod_source.fetch_and_extract(cb, slug=_SM2_SLUG)
        try:
            mods = sorted(Path(extracted).rglob("*.modular"))
            if not mods:
                raise RuntimeError("no .modular files in archive")
            cache = _sm2_cache_dir()
            out = []
            for m in mods:
                dst = cache / m.name
                shutil.copy2(m, dst)
                out.append(dst)
            return out, version
        finally:
            shutil.rmtree(Path(extracted).parent, ignore_errors=True)
    except Exception as e:                              # pragma: no cover
        print(f"[spiderman2] download failed ({e}); using bundled payload", flush=True)
        return _sm2_payload_files(), None


# Shown when a native mod could not be fetched AND no local copy exists. Since
# NOTHING ships inside the installer any more (every mod is downloaded and then
# kept in the launcher cache), this is always a connectivity/server problem - so
# it names the two real ways out instead of the old, misleading "files not found".
_DL_FAILED_MSG = ("לא הצלחנו להוריד את קובצי התרגום מהשרת. בדוק את החיבור לאינטרנט ונסה שוב, "
                  "או השתמש בחבילת ההתקנה האופליין (התרגומים נשמרים במטמון אחרי הורדה אחת).")


def _native_download_payload(slug: str, cb, cache_dir: Path, pick):
    """GENERIC native-mod fetch (the reusable core behind every native applier).
    Downloads the mod from the Worker, hands the extracted archive dir to
    `pick(extracted_dir, cache_dir) -> payload` (game-specific: it copies the
    files the applier needs into the cache and returns them in whatever shape the
    applier wants - a Path, a list, a (path, rel) map), and returns
    (payload, version). Returns (None, None) on ANY failure so the caller falls
    back to its BUNDLED payload. This is what makes new mod versions reach users
    without a launcher rebuild; a NEW native game inherits auto-update just by
    calling this with its slug + a small `pick`."""
    try:
        extracted, version = _mod_source.fetch_and_extract(cb, slug=slug)
        try:
            return pick(Path(extracted), cache_dir), version
        finally:
            shutil.rmtree(Path(extracted).parent, ignore_errors=True)
    except Exception as e:                              # pragma: no cover
        print(f"[{slug}] download failed ({e}); trying offline bundle", flush=True)
        # OFFLINE PACKAGE fallback. The bundle stores the EXACT Worker archive,
        # so extracting it yields the same tree `pick()` already knows how to
        # read - every native applier inherits offline support with no per-game
        # code. The payload is SHA-verified inside offline_bundle.extract, so an
        # offline install keeps the same integrity gate as an online one.
        # game_id is the cache dir's name (see _native_cache_dir).
        try:
            got = _offline_bundle.extract(Path(cache_dir).name, cb)
            if got is not None:
                ed, version = got
                try:
                    print(f"[{slug}] using OFFLINE bundle payload v{version}", flush=True)
                    return pick(Path(ed), cache_dir), version
                finally:
                    shutil.rmtree(Path(ed).parent, ignore_errors=True)
        except Exception as e2:                         # pragma: no cover
            print(f"[{slug}] offline bundle failed ({e2})", flush=True)
        print(f"[{slug}] no offline payload; using bundled payload", flush=True)
        return None, None


@eel.expose
def get_spiderman2_mod_state() -> dict:
    """State for the Spider-Man 2 native applier (drives its panel CTA):
    {hasPath, installed, available, installPath, version, updateAvailable, latestVersion}."""
    base = _install_path(_SM2_ID)
    applied = False
    try:
        if base is not None:
            applied = _sm2.is_applied(base)
    except Exception:                                   # pragma: no cover
        applied = False
    state = _sm2_state()
    installed_version = state.get("version") if applied else None
    return {
        "hasPath":     base is not None,
        "installed":   applied,
        # SM2 ships via GitHub Release now, but the bundled payload keeps it
        # installable offline - so it's always "available".
        "available":   True,
        "installPath": str(base) if base else None,
        **_owned_fields(_SM2_ID),
        "version":     installed_version,
    }


@eel.expose
def check_spiderman2_update() -> dict:
    """Off the install path (network) - is a newer SM2 version on the server?
    Returns {updateAvailable, installedVersion, latestVersion}. Soft-fails."""
    try:
        if not _sm2.is_applied(_install_path(_SM2_ID) or Path(".")):
            return {"updateAvailable": False}
    except Exception:
        return {"updateAvailable": False}
    installed = _sm2_state().get("version")
    try:
        latest = _mod_source.fetch_manifest(slug=_SM2_SLUG).get("version")
    except Exception:
        return {"updateAvailable": False, "installedVersion": installed}
    upd = _offer_update(_SM2_ID, latest, installed)
    return {"updateAvailable": upd, "installedVersion": installed, "latestVersion": latest}


def _run_sm2_install() -> None:
    """Background worker: DOWNLOAD the SM2 Hebrew mod from its GitHub Release
    (bundled payload as offline fallback), apply it to the game's TOC, flip the
    in-game text language to Hebrew (Arabic slot), and record the installed
    version. Progress streams over the mod_install_progress channel."""
    try:
        base = _install_path(_SM2_ID)
        if base is None:
            _mod_progress_cb("error", 0, "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות")
            return
        # DRM gate on the LIVE catalog price. Free today - but a title's price is
        # admin-editable at any time (the Witcher 3 went 0 -> 5300 mid-life and its
        # mod installed for an account that never bought it), so every applier gates
        # unconditionally. price <= 0 makes this a no-op for a genuinely free mod.
        if _game_price_cents(_SM2_ID) > 0 and not auth_owns_game(_SM2_ID):
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        if not _game_mod.is_writable(base):
            _mod_progress_cb("error", 0,
                "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב.")
            return
        payloads, version = _sm2_download_payloads(_mod_progress_cb)
        if not payloads:
            _mod_progress_cb("error", 0, _DL_FAILED_MSG)
            return
        r = _sm2.apply(base, payloads, _mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהחלת המוד")
            return
        # Record the installed version (None → bundled fallback was used).
        _sm2_write_state({"version": version or "bundled", "installed": True})
        # Flip the game's own text language to Hebrew (the Arabic locale slot).
        try:
            _game_language.set_mode(_SM2_ID, "hebrew", installed=True)
        except Exception as e:                          # pragma: no cover
            print(f"[spiderman2] language set failed: {e}", flush=True)
        _mod_progress_cb("done", 100, "התרגום הותקן")
    except Exception as e:                              # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def install_spiderman2_mod() -> dict:
    """Kick off the Spider-Man 2 native apply on a background worker. Progress
    + a terminal done/error tick stream over mod_install_progress."""
    base = _install_path(_SM2_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות"}
    if _game_price_cents(_SM2_ID) > 0 and not auth_owns_game(_SM2_ID):
        return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
    # NO bundled-payload pre-check: the mod is DOWNLOADED at install time
    # (nothing ships in the installer). A network failure is reported by the
    # worker with an actionable message instead of hiding the action here.
    import gevent
    gevent.spawn(_run_sm2_install)
    return {"ok": True, "started": True}


@eel.expose
def remove_spiderman2_mod() -> dict:
    """Revert the Spider-Man 2 Hebrew mod (restore the backed-up TOC + delete
    our mod archives) and flip the language back to English."""
    base = _install_path(_SM2_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא", "state": get_spiderman2_mod_state()}
    r = _sm2.revert(base)
    if r.get("ok"):
        _sm2_write_state({})   # clear the recorded installed version
    try:
        _game_language.set_mode(_SM2_ID, "english", installed=False)
    except Exception as e:                              # pragma: no cover
        print(f"[spiderman2] language restore failed: {e}", flush=True)
    return {**r, "state": get_spiderman2_mod_state()}


# ─────────────────────────────────────────────────────────────
# Watch Dogs 2 - native FAT5 fat-redirect applier (no Overstrike / mod manager)
# ─────────────────────────────────────────────────────────────
# WD2 ships the Hebrew translation as 3 files (localization .loc + Hebrew font
# .ffd + atlas .xbt) BUNDLED inside the launcher; watchdogs2_mod redirects them
# into the game's FAT5 archives. Backups live in the launcher cache (outside the
# game folder) so a Program-Files install still reverts. Activation is in-game
# (Settings → Written Language = العربية), so we never touch a game setting here.
def _wd2_cache_dir() -> Path:
    d = Path.home() / ".translation_manager" / "mod_cache" / "watchdogs2"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _wd2_backup_dir() -> Path:
    d = _wd2_cache_dir() / "backup"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _wd2_state() -> dict:
    try:
        return json.loads((_wd2_cache_dir() / "state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _wd2_write_state(d: dict) -> None:
    try:
        (_wd2_cache_dir() / "state.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:                                   # pragma: no cover
        pass


def _wd2_payload_map() -> list:
    """The BUNDLED Watch Dogs 2 Hebrew files → [(payload_path, in_archive_rel)].
    Resolves for both the frozen build (sys._MEIPASS) and a dev run. Empty list
    if any file is missing (→ 'unavailable' in the UI)."""
    base = getattr(sys, "_MEIPASS", None)
    roots = []
    if base:
        roots.append(Path(base) / "translation_manager" / "assets" / "watchdogs2")
    roots.append(ROOT / "translation_manager" / "assets" / "watchdogs2")
    for r in roots:
        files = [(r / local, rel) for local, rel in _wd2.TARGETS]
        if all(p.is_file() for p, _ in files):
            return files
    return []


@eel.expose
def get_watchdogs2_mod_state() -> dict:
    """State for the Watch Dogs 2 native applier (drives its panel CTA):
    {hasPath, installed, available, installPath, version}."""
    base = _install_path(_WD2_ID)
    applied = False
    try:
        applied = _wd2.is_applied(str(_wd2_backup_dir()))
    except Exception:                                   # pragma: no cover
        applied = False
    state = _wd2_state()
    return {
        "hasPath":     base is not None,
        "installed":   applied,
        # The mod is DOWNLOADED from the Worker (nothing ships inside the
        # installer), so it is always offerable; a network failure is reported
        # by the install itself, not by hiding the button.
        "available":   True,
        "installPath": str(base) if base else None,
        **_owned_fields(_WD2_ID),
        "version":     (state.get("version") or _WD2_BUNDLED_VERSION) if applied else None,
    }


def _wd2_download_payloads(cb=None) -> tuple[list, str | None]:
    """DOWNLOAD the WD2 mod from the Worker, copy the 3 files it needs into the
    cache, and return ([(path, in_archive_rel)], version). Falls back to the
    BUNDLED payload → (bundled_map, None) on any failure (offline-safe)."""
    def pick(extracted: Path, cache: Path):
        out = []
        for local, rel in _wd2.TARGETS:
            src = next(iter(extracted.rglob(local)), None)
            if src is None:
                raise RuntimeError(f"missing {local} in archive")
            dst = cache / local
            shutil.copy2(src, dst)
            out.append((dst, rel))
        return out
    payload, version = _native_download_payload(_WD2_SLUG, cb, _wd2_cache_dir(), pick)
    if payload:
        return payload, version
    return _wd2_payload_map(), None


def _run_wd2_install() -> None:
    """Background worker: DOWNLOAD the WD2 Hebrew files from the Worker (bundled
    payload as offline fallback), apply them to the game's FAT5 archives
    (fat-redirect), and record the installed version. Progress + a terminal
    done/error tick stream over mod_install_progress. The user must set Written
    Language = Arabic in-game to see the Hebrew (we say so on success)."""
    try:
        base = _install_path(_WD2_ID)
        if base is None:
            _mod_progress_cb("error", 0, "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות")
            return
        # DRM gate on the LIVE catalog price. Free today - but a title's price is
        # admin-editable at any time (the Witcher 3 went 0 -> 5300 mid-life and its
        # mod installed for an account that never bought it), so every applier gates
        # unconditionally. price <= 0 makes this a no-op for a genuinely free mod.
        if _game_price_cents(_WD2_ID) > 0 and not auth_owns_game(_WD2_ID):
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        data = Path(base) / "data_win64"
        if not data.is_dir():
            _mod_progress_cb("error", 0, "לא נמצאה תיקיית data_win64 בנתיב המשחק - בדוק את הנתיב")
            return
        if not _game_mod.is_writable(data):
            _mod_progress_cb("error", 0,
                "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב.")
            return
        payloads, version = _wd2_download_payloads(_mod_progress_cb)
        if not payloads:
            _mod_progress_cb("error", 0, _DL_FAILED_MSG)
            return
        r = _wd2.apply(base, payloads, str(_wd2_backup_dir()), _mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהחלת המוד")
            return
        _wd2_write_state({"version": version or _WD2_BUNDLED_VERSION, "installed": True})
        _mod_progress_cb("done", 100,
            'הותקן! במשחק: Settings → Written Language ובחרו "עברית", והפעל עם ‎-eac_launcher')
    except Exception as e:                              # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def install_watchdogs2_mod() -> dict:
    """Kick off the Watch Dogs 2 native apply on a background worker. Progress +
    a terminal done/error tick stream over mod_install_progress."""
    base = _install_path(_WD2_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות"}
    if _game_price_cents(_WD2_ID) > 0 and not auth_owns_game(_WD2_ID):
        return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
    # NO bundled-payload pre-check: the mod is DOWNLOADED at install time
    # (nothing ships in the installer). A network failure is reported by the
    # worker with an actionable message instead of hiding the action here.
    import gevent
    gevent.spawn(_run_wd2_install)
    return {"ok": True, "started": True}


@eel.expose
def remove_watchdogs2_mod() -> dict:
    """Revert the Watch Dogs 2 Hebrew mod (restore the original FAT5 archives +
    delete our backups)."""
    base = _install_path(_WD2_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא", "state": get_watchdogs2_mod_state()}
    r = _wd2.revert(base, str(_wd2_backup_dir()))
    if r.get("ok"):
        _wd2_write_state({})   # clear the recorded installed version
    return {**r, "state": get_watchdogs2_mod_state()}


# ── God of War: Ragnarök - native single-file localization-WAD swap ───────────
# Replaces exec\wad\pc_le\r_lang_ar.wad (the Arabic text slot) with our bundled
# Hebrew build. The ORIGINAL is backed up in the launcher cache (outside the game)
# so a Program-Files install still reverts; only that one file is ever touched;
# writes are atomic. Activation is in-game (Settings → Text Language = العربية).
def _gowr_cache_dir() -> Path:
    d = Path.home() / ".translation_manager" / "mod_cache" / "gowragnarok"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gowr_backup_dir() -> Path:
    d = _gowr_cache_dir() / "backup"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gowr_state() -> dict:
    try:
        return json.loads((_gowr_cache_dir() / "state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _gowr_write_state(d: dict) -> None:
    try:
        (_gowr_cache_dir() / "state.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:                                   # pragma: no cover
        pass


def _gowr_payload() -> "Path | None":
    """The BUNDLED God of War: Ragnarök Hebrew WAD. Resolves for both the frozen
    build (sys._MEIPASS) and a dev run. None if missing (→ 'unavailable')."""
    base = getattr(sys, "_MEIPASS", None)
    roots = []
    if base:
        roots.append(Path(base) / "translation_manager" / "assets" / "godofwar_ragnarok")
    roots.append(ROOT / "translation_manager" / "assets" / "godofwar_ragnarok")
    for r in roots:
        p = r / "r_lang_ar.wad"
        if p.is_file():
            return p
    return None


_GOWR_SHA_CACHE: dict = {}


def _gowr_bundled_sha() -> "str | None":
    """SHA-256 of the bundled Hebrew WAD (cached) - lets is_applied verify the live
    game file IS our build (content check, not just 'a backup exists')."""
    p = _gowr_payload()
    if p is None:
        return None
    key = str(p)
    cached = _GOWR_SHA_CACHE.get(key)
    if cached:
        return cached
    try:
        sha = _gowr.sha256_of(p)
    except Exception:                                   # pragma: no cover
        return None
    _GOWR_SHA_CACHE[key] = sha
    return sha


@eel.expose
def get_gowr_mod_state() -> dict:
    """State for the God of War: Ragnarök native applier (drives its panel CTA):
    {hasPath, installed, available, installPath, version}."""
    base = _install_path(_GOWR_ID)
    state = _gowr_state()
    applied = False
    try:
        if base is not None:
            # Verify the live file IS our build: the DOWNLOADED wad's sha (recorded
            # at install) if present, else the bundled sha (legacy/offline installs).
            sha = state.get("sha") or _gowr_bundled_sha()
            applied = _gowr.is_applied(str(_gowr_backup_dir()), base, sha)
    except Exception:                                   # pragma: no cover
        applied = False
    return {
        "hasPath":     base is not None,
        "installed":   applied,
        "available":   True,          # downloaded from the Worker - see WD2 note
        "installPath": str(base) if base else None,
        **_owned_fields(_GOWR_ID),
        "version":     (state.get("version") or _GOWR_BUNDLED_VERSION) if applied else None,
    }


def _gowr_download_payload(cb=None) -> tuple["Path | None", str | None]:
    """DOWNLOAD the GoWR mod from the Worker, copy r_lang_ar.wad into the cache,
    and return (path, version). Falls back to the BUNDLED WAD → (bundled, None)."""
    def pick(extracted: Path, cache: Path):
        src = next(iter(extracted.rglob("r_lang_ar.wad")), None)
        if src is None:
            raise RuntimeError("missing r_lang_ar.wad in archive")
        dst = cache / "r_lang_ar.wad"
        shutil.copy2(src, dst)
        return dst
    payload, version = _native_download_payload(_GOWR_SLUG, cb, _gowr_cache_dir(), pick)
    if payload:
        return payload, version
    return _gowr_payload(), None


def _run_gowr_install() -> None:
    """Background worker: DOWNLOAD the Hebrew WAD from the Worker (bundled = offline
    fallback), back up the original then atomically swap it in, and record the
    installed version + the applied file's sha (is_applied is a content check).
    Progress streams over mod_install_progress. User sets Text Language = Arabic."""
    try:
        base = _install_path(_GOWR_ID)
        if base is None:
            _mod_progress_cb("error", 0, "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות")
            return
        # DRM gate on the LIVE catalog price. Free today - but a title's price is
        # admin-editable at any time (the Witcher 3 went 0 -> 5300 mid-life and its
        # mod installed for an account that never bought it), so every applier gates
        # unconditionally. price <= 0 makes this a no-op for a genuinely free mod.
        if _game_price_cents(_GOWR_ID) > 0 and not auth_owns_game(_GOWR_ID):
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        payload, version = _gowr_download_payload(_mod_progress_cb)
        if payload is None:
            _mod_progress_cb("error", 0, _DL_FAILED_MSG)
            return
        target_dir = Path(base) / "exec" / "wad" / "pc_le"
        if not target_dir.is_dir():
            _mod_progress_cb("error", 0,
                "לא נמצאה תיקיית exec\\wad\\pc_le בנתיב המשחק - בדוק את הנתיב")
            return
        if not _game_mod.is_writable(target_dir):
            _mod_progress_cb("error", 0,
                "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב.")
            return
        # Pass the PREVIOUSLY-applied Hebrew sha so a mod UPDATE doesn't overwrite
        # the vanilla backup with the old Hebrew build (revert-to-vanilla safety).
        r = _gowr.apply(base, payload, str(_gowr_backup_dir()), _mod_progress_cb,
                        prev_hebrew_sha=_gowr_state().get("sha"))
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהחלת המוד")
            return
        try:
            applied_sha = _gowr.sha256_of(payload)
        except Exception:                              # pragma: no cover
            applied_sha = None
        _gowr_write_state({"version": version or _GOWR_BUNDLED_VERSION,
                           "sha": applied_sha, "installed": True})
        _mod_progress_cb("done", 100,
            'הותקן! במשחק: Settings → Text Language ובחרו "עברית". הקול יכול להישאר באנגלית.')
    except Exception as e:                              # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def install_gowr_mod() -> dict:
    """Kick off the God of War: Ragnarök native apply on a background worker.
    Progress + a terminal done/error tick stream over mod_install_progress."""
    base = _install_path(_GOWR_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות"}
    if _game_price_cents(_GOWR_ID) > 0 and not auth_owns_game(_GOWR_ID):
        return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
    # NO bundled-payload pre-check: the mod is DOWNLOADED at install time
    # (nothing ships in the installer). A network failure is reported by the
    # worker with an actionable message instead of hiding the action here.
    import gevent
    gevent.spawn(_run_gowr_install)
    return {"ok": True, "started": True}


@eel.expose
def remove_gowr_mod() -> dict:
    """Revert the God of War: Ragnarök Hebrew mod (restore the original WAD from
    our backup)."""
    base = _install_path(_GOWR_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא", "state": get_gowr_mod_state()}
    r = _gowr.revert(base, str(_gowr_backup_dir()))
    if r.get("ok"):
        _gowr_write_state({})
    return {**r, "state": get_gowr_mod_state()}


# ══════════════════════════════════════════════════════════════════════════════
# Three DOWNLOAD-ONLY native appliers (Hogwarts Legacy / The Witcher 3 / A Plague
# Tale: Requiem). No bundled payload - the mod is fetched from the Worker once
# published (until then install shows a clean "not published yet"). Each reuses the
# generic `_native_download_payload` + auto-update infra. State + backups live in
# ~/.translation_manager/mod_cache/<id>/ (OUTSIDE the game). Activation is in-game.
# ══════════════════════════════════════════════════════════════════════════════
def _native_cache_dir(game_id: str) -> Path:
    d = Path.home() / ".translation_manager" / "mod_cache" / game_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _native_backup_dir(game_id: str) -> Path:
    d = _native_cache_dir(game_id) / "backup"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _native_state(game_id: str) -> dict:
    try:
        return json.loads((_native_cache_dir(game_id) / "state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _native_write_state(game_id: str, d: dict) -> None:
    try:
        (_native_cache_dir(game_id) / "state.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:                                   # pragma: no cover
        pass


# ── Hogwarts Legacy - additive UE4 override pak into ~mods ─────────────────────
def _hl_download_payload(cb=None) -> tuple["Path | None", str | None]:
    def pick(extracted: Path, cache: Path):
        src = next((p for p in extracted.rglob("*.pak") if p.is_file()), None)
        if src is None:
            raise RuntimeError("no .pak in archive")
        dst = cache / "hebrew.pak"
        shutil.copy2(src, dst)
        return dst
    return _native_download_payload(_HL_SLUG, cb, _native_cache_dir(_HL_ID), pick)


@eel.expose
def get_hogwarts_mod_state() -> dict:
    """State for the Hogwarts Legacy native applier (drives its panel CTA)."""
    base = _install_path(_HL_ID)
    applied = False
    try:
        if base is not None:
            applied = _hl.is_applied(base)
    except Exception:                                   # pragma: no cover
        applied = False
    st = _native_state(_HL_ID)
    return {"hasPath": base is not None, "installed": applied, "available": True,
            "installPath": str(base) if base else None,
            **_owned_fields(_HL_ID),
            "version": st.get("version") if applied else None}


def _run_hl_install() -> None:
    try:
        base = _install_path(_HL_ID)
        if base is None:
            _mod_progress_cb("error", 0, "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות")
            return
        # DRM gate. These three were shipped as FREE titles, so no purchase check
        # was ever written - but the price lives in the CATALOG and an admin can
        # make any of them paid at any time (the Witcher 3 went 0 -> 5300 while it
        # was already published, and the mod installed for an account that never
        # bought it). Gate on the LIVE price, in the worker as well as the RPC:
        # the bridge starts this worker directly, so an RPC-only check is not a gate.
        if _game_price_cents(_HL_ID) > 0 and not auth_owns_game(_HL_ID):
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        paks = Path(base) / "Phoenix" / "Content" / "Paks"
        if not paks.is_dir():
            _mod_progress_cb("error", 0, "לא נמצאה תיקיית Phoenix\\Content\\Paks - בדוק את הנתיב")
            return
        if not _game_mod.is_writable(paks):
            _mod_progress_cb("error", 0,
                "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב.")
            return
        payload, version = _hl_download_payload(_mod_progress_cb)
        if payload is None:
            _mod_progress_cb("error", 0, "התרגום עדיין לא פורסם להורדה")
            return
        r = _hl.apply(base, payload, None, _mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהחלת המוד")
            return
        _native_write_state(_HL_ID, {"version": version or "downloaded", "installed": True})
        _mod_progress_cb("done", 100,
            'הותקן! במשחק: הגדרות → שפת טקסט → בחרו English כדי לראות את התרגום.')
    except Exception as e:                              # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def install_hogwarts_mod() -> dict:
    if _install_path(_HL_ID) is None:
        return {"ok": False, "error": "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות"}
    if _game_price_cents(_HL_ID) > 0 and not auth_owns_game(_HL_ID):
        return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
    import gevent
    gevent.spawn(_run_hl_install)
    return {"ok": True, "started": True}


@eel.expose
def remove_hogwarts_mod() -> dict:
    base = _install_path(_HL_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא", "state": get_hogwarts_mod_state()}
    r = _hl.revert(base)
    if r.get("ok"):
        _native_write_state(_HL_ID, {})
    return {**r, "state": get_hogwarts_mod_state()}


# ── The Witcher 3 - non-destructive Mods\modHebrew overlay ─────────────────────
def _w3_mod_root_cache() -> Path:
    """Where the extracted W3 mod (install.py + lib/ + data/) is cached. Persisted
    with the mod cache so revert can re-run the installer's own revert later."""
    return _native_cache_dir(_W3_ID) / "modroot"


def _w3_download_payload(cb=None) -> tuple["Path | None", str | None]:
    def pick(extracted: Path, cache: Path):
        # The real mod is a self-contained installer (install.py + lib/ + data/),
        # NOT a modHebrew overlay - find that root and cache it whole.
        root = next(
            (p.parent for p in extracted.rglob("install.py")
             if (p.parent / "lib").is_dir() and (p.parent / "data").is_dir()),
            None,
        )
        if root is None:
            raise RuntimeError("no install.py mod root in archive")
        dst = _w3_mod_root_cache()
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(root, dst)
        return dst
    return _native_download_payload(_W3_SLUG, cb, _native_cache_dir(_W3_ID), pick)


@eel.expose
def get_witcher3_mod_state() -> dict:
    base = _install_path(_W3_ID)
    applied = False
    try:
        if base is not None:
            applied = _w3.is_applied(base)
    except Exception:                                   # pragma: no cover
        applied = False
    st = _native_state(_W3_ID)
    return {"hasPath": base is not None, "installed": applied, "available": True,
            "installPath": str(base) if base else None,
            **_owned_fields(_W3_ID),
            "version": st.get("version") if applied else None}


def _run_w3_install() -> None:
    try:
        _CUR_INSTALL_GAME[0] = _W3_ID          # attribute any install_error to this game
        base = _install_path(_W3_ID)
        if base is None:
            _mod_progress_cb("error", 0, "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות")
            return
        # DRM gate. These three were shipped as FREE titles, so no purchase check
        # was ever written - but the price lives in the CATALOG and an admin can
        # make any of them paid at any time (the Witcher 3 went 0 -> 5300 while it
        # was already published, and the mod installed for an account that never
        # bought it). Gate on the LIVE price, in the worker as well as the RPC:
        # the bridge starts this worker directly, so an RPC-only check is not a gate.
        if _game_price_cents(_W3_ID) > 0 and not auth_owns_game(_W3_ID):
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        if not _game_mod.is_writable(base):
            _mod_progress_cb("error", 0,
                "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב.")
            return
        payload, version = _w3_download_payload(_mod_progress_cb)
        if payload is None:
            _mod_progress_cb("error", 0, "התרגום עדיין לא פורסם להורדה")
            return
        r = _w3.apply(base, payload, None, _mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהחלת המוד")
            return
        _native_write_state(_W3_ID, {"version": version or "downloaded", "installed": True})
        try:
            _game_language.set_mode(_W3_ID, "hebrew", installed=True)
        except Exception as e:                          # pragma: no cover
            print(f"[witcher3] language set failed: {e}", flush=True)
        _mod_progress_cb("done", 100,
            "הותקן! במשחק: Options → Language → Text = Hebrew (עברית). הקול/דיבור נשאר כרצונך.")
    except BaseException as e:                          # pragma: no cover
        # BaseException, NOT Exception: _w3.apply() runs the DOWNLOADED mod's
        # own install.py in-process, which can `raise SystemExit(...)`. A bare
        # `except Exception` would let that skip this error toast entirely and
        # leave the progress bar frozen with no feedback (defense-in-depth on
        # top of the same fix already applied inside witcher3_mod.apply()).
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def install_witcher3_mod() -> dict:
    if _install_path(_W3_ID) is None:
        return {"ok": False, "error": "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות"}
    if _game_price_cents(_W3_ID) > 0 and not auth_owns_game(_W3_ID):
        return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
    import gevent
    gevent.spawn(_run_w3_install)
    return {"ok": True, "started": True}


@eel.expose
def remove_witcher3_mod() -> dict:
    base = _install_path(_W3_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא", "state": get_witcher3_mod_state()}
    r = _w3.revert(base, str(_w3_mod_root_cache()))
    if r.get("ok"):
        _native_write_state(_W3_ID, {})
    try:
        _game_language.set_mode(_W3_ID, "english", installed=False)
    except Exception:                                   # pragma: no cover
        pass
    return {**r, "state": get_witcher3_mod_state()}


# ── A Plague Tale: Requiem - overwrite tt23.pc/.IGN + ENGLISH.DPC (backed up) ──
def _pt_download_payload(cb=None) -> tuple["list | None", str | None]:
    def pick(extracted: Path, cache: Path):
        out = []
        wanted = {"tt23.pc": os.path.join("TRTEXT", "tt23.pc"),
                  "tt23.IGN": os.path.join("TRTEXT", "tt23.IGN"),
                  "ENGLISH.DPC": os.path.join("FONT", "ENGLISH.DPC")}
        for name, rel in wanted.items():
            src = next((p for p in extracted.rglob(name) if p.is_file()), None)
            if src is None:
                if name == "tt23.pc":
                    raise RuntimeError("missing tt23.pc in archive")
                continue                                # .IGN / font optional
            dst = cache / name
            shutil.copy2(src, dst)
            out.append((dst, rel))
        return out
    return _native_download_payload(_PT_SLUG, cb, _native_cache_dir(_PT_ID), pick)


@eel.expose
def get_plaguetale_mod_state() -> dict:
    base = _install_path(_PT_ID)
    st = _native_state(_PT_ID)
    applied = False
    try:
        if base is not None:
            applied = _pt.is_applied(str(_native_backup_dir(_PT_ID)), base, st.get("key_sha"))
    except Exception:                                   # pragma: no cover
        applied = False
    return {"hasPath": base is not None, "installed": applied, "available": True,
            "installPath": str(base) if base else None,
            **_owned_fields(_PT_ID),
            "version": st.get("version") if applied else None}


def _run_pt_install() -> None:
    try:
        base = _install_path(_PT_ID)
        if base is None:
            _mod_progress_cb("error", 0, "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות")
            return
        # DRM gate. These three were shipped as FREE titles, so no purchase check
        # was ever written - but the price lives in the CATALOG and an admin can
        # make any of them paid at any time (the Witcher 3 went 0 -> 5300 while it
        # was already published, and the mod installed for an account that never
        # bought it). Gate on the LIVE price, in the worker as well as the RPC:
        # the bridge starts this worker directly, so an RPC-only check is not a gate.
        if _game_price_cents(_PT_ID) > 0 and not auth_owns_game(_PT_ID):
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        trtext = Path(base) / "TRTEXT"
        if not trtext.is_dir():
            _mod_progress_cb("error", 0, "לא נמצאה תיקיית TRTEXT - בדוק את הנתיב")
            return
        if not _game_mod.is_writable(trtext):
            _mod_progress_cb("error", 0,
                "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב.")
            return
        payload, version = _pt_download_payload(_mod_progress_cb)
        if not payload:
            _mod_progress_cb("error", 0, "התרגום עדיין לא פורסם להורדה")
            return
        # Pass the PREVIOUSLY-applied Hebrew shas so a mod UPDATE doesn't overwrite
        # the vanilla backups with the old Hebrew build (revert-to-vanilla safety).
        prev_shas = set(_native_state(_PT_ID).get("shas") or [])
        old = _native_state(_PT_ID).get("key_sha")
        if old:
            prev_shas.add(old)
        r = _pt.apply(base, payload, str(_native_backup_dir(_PT_ID)), _mod_progress_cb,
                      prev_shas=prev_shas)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהחלת המוד")
            return
        # record the applied tt23.pc sha (is_applied marker) + ALL applied file
        # shas (so the NEXT update recognises them as ours, not fresh vanilla).
        key_sha = None
        applied_shas: list[str] = []
        for p, rel in payload:
            try:
                s = _pt.sha256_of(p)
            except Exception:                           # pragma: no cover
                s = None
            if s:
                applied_shas.append(s)
                if str(rel).endswith("tt23.pc"):
                    key_sha = s
        _native_write_state(_PT_ID, {"version": version or "downloaded",
                                     "key_sha": key_sha, "shas": applied_shas,
                                     "installed": True})
        _mod_progress_cb("done", 100,
            "הותקן! במשחק: Options → Text Language = العربية (ערבית). הקול נשאר באנגלית.")
    except Exception as e:                              # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def install_plaguetale_mod() -> dict:
    if _install_path(_PT_ID) is None:
        return {"ok": False, "error": "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות"}
    if _game_price_cents(_PT_ID) > 0 and not auth_owns_game(_PT_ID):
        return {"ok": False, "error": "יש לרכוש את התרגום לפני ההתקנה"}
    import gevent
    gevent.spawn(_run_pt_install)
    return {"ok": True, "started": True}


@eel.expose
def remove_plaguetale_mod() -> dict:
    base = _install_path(_PT_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא", "state": get_plaguetale_mod_state()}
    r = _pt.revert(base, str(_native_backup_dir(_PT_ID)))
    if r.get("ok"):
        _native_write_state(_PT_ID, {})
    return {**r, "state": get_plaguetale_mod_state()}


# ── Grand Theft Auto V - native OpenIV-free RPF7 read-modify-write ─────────────
# Edits the user's EXISTING OPEN `mods\` folder (every other mod byte-exact). The
# backup of the 2 touched RPFs lives OUTSIDE the game in the launcher cache, so a
# revert is always exact. A clean install (no mods folder) is GUIDED, not automated
# (the launcher can't decrypt the vanilla - see _GTAV_ID).
def _gtav_cache_dir() -> Path:
    d = Path.home() / ".translation_manager" / "mod_cache" / "gtav"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gtav_backup_dir() -> Path:
    d = _gtav_cache_dir() / "backup"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gtav_payload_dir() -> Path:
    d = _gtav_cache_dir() / "payload"
    d.mkdir(parents=True, exist_ok=True)
    return d


_GTAV_ZIPS = ("gtav_he_payload.zip", "gtav_vanilla_payload.zip")


def _gtav_use_cached_payload() -> bool:
    """Point gtav_mod at an ALREADY-downloaded payload (both zips present). Called
    before a remove/state read so the surgical revert uses the same vanilla files
    the install came from, not a possibly-older bundled copy."""
    d = _gtav_payload_dir()
    if all((d / n).is_file() for n in _GTAV_ZIPS):
        _gtav.set_payload_dir(d)
        return True
    _gtav.set_payload_dir(None)
    return False


def _gtav_download_payload(cb=None) -> tuple["Path | None", str | None]:
    """Fetch the CURRENT GTA payload pair from the Worker (Hebrew + vanilla-English
    in one archive) into the launcher cache, and point gtav_mod at it. Returns
    (payload_dir, version); (None, None) on any failure -> the caller keeps the
    BUNDLED zips, so a server outage or an offline machine still installs."""
    def pick(extracted: Path, cache: Path):
        dst = _gtav_payload_dir()
        found = 0
        for name in _GTAV_ZIPS:
            src = next(extracted.rglob(name), None)
            if src is None:
                raise RuntimeError(f"archive is missing {name}")
            shutil.copy2(src, dst / name)
            found += 1
        if found != len(_GTAV_ZIPS):                    # pragma: no cover
            raise RuntimeError("incomplete GTA payload")
        return dst
    payload, version = _native_download_payload(
        _GTAV_SLUG, cb, _gtav_cache_dir(), pick)
    _gtav.set_payload_dir(payload)                      # None -> bundled fallback
    return payload, version


@eel.expose
def get_gtav_mod_state() -> dict:
    """State for the GTA V native applier (drives its panel CTA + the scenario
    message). scenario ∈ {ready, mods_no_loader, clean, no_game}."""
    # Nothing ships inside the installer any more - the payload pair lives in the
    # launcher cache after the first download, so point the resolver at it before
    # reporting what is available (this is what makes the surgical remove offerable).
    _gtav_use_cached_payload()
    base = _install_path(_GTAV_ID)
    has_mods = loader = applied = False
    if base is not None:
        try:
            has_mods = _gtav.has_mods_folder(base)
            loader   = _gtav.loader_connected(base)
        except Exception:                                   # pragma: no cover
            pass
    try:
        applied = _gtav.is_applied(str(_gtav_backup_dir()))
    except Exception:                                       # pragma: no cover
        applied = False
    if base is None:
        scenario = "no_game"
    elif not has_mods:
        scenario = "clean"
    elif not loader:
        scenario = "mods_no_loader"
    else:
        scenario = "ready"
    price = _game_price_cents(_GTAV_ID)
    owned = True if price <= 0 else auth_owns_game(_GTAV_ID)
    try:
        backup = _gtav.has_backup(str(_gtav_backup_dir()))
    except Exception:                                       # pragma: no cover
        backup = False
    return {
        "hasPath":         base is not None,
        "installPath":     str(base) if base else None,
        "available":       True,      # downloaded from the Worker - see WD2 note
        "vanillaAvailable":_gtav.vanilla_available(),
        "hasMods":         has_mods,
        "loaderConnected": loader,
        "scenario":        scenario,
        "installed":       applied,
        "backupAvailable": backup,
        "priceCents":      price,
        "owned":           owned,
        # Report the version actually APPLIED (server payload when one was
        # downloaded), falling back to the bundled constant for an install made
        # before the server path existed.
        "version": ((_native_state(_GTAV_ID).get("version") or _GTAV_BUNDLED_VERSION)
                    if applied else None),
    }


def _run_gtav_install() -> None:
    """Background worker: read-modify-write the Hebrew text + fonts into the OPEN
    mods RPFs (backup first, atomic). Heavy (multi-GB) - always off the main flow.
    Activation is in-game (Settings → Language = American); we say so on success."""
    try:
        _CUR_INSTALL_GAME[0] = _GTAV_ID         # attribute any install_error to this game
        base = _install_path(_GTAV_ID)
        if base is None:
            _mod_progress_cb("error", 0, "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות")
            return
        if _game_price_cents(_GTAV_ID) > 0 and not auth_owns_game(_GTAV_ID):
            _mod_progress_cb("error", 0, "המשחק טרם נרכש")
            return
        if not _gtav.has_mods_folder(base):
            _mod_progress_cb("error", 0,
                "אין תיקיית mods פתוחה. צור אותה פעם אחת ב-OpenIV (התקנה נקייה), "
                "ואז התוכנה תנהל את התרגום לבד.")
            return
        # Fail FAST on a non-writable mods folder (Program-Files / no admin) BEFORE
        # the multi-GB backup+rebuild, with the same actionable message every other
        # applier gives - not a raw errno after minutes of wasted I/O.
        if not _game_mod.is_writable(base / "mods"):
            _mod_progress_cb("error", 0,
                "אין הרשאת כתיבה לתיקיית ה-mods - הפעל את התוכנה כמנהל (Run as administrator) "
                "או העבר את המשחק לתיקייה שאינה Program Files.")
            return
        # SERVER-FIRST: pull the current payload pair from the Worker; on any
        # failure fall back to the bundled zips (offline / server down) so the
        # install never depends on the network being up.
        _, version = _gtav_download_payload(_mod_progress_cb)
        if version is None:
            _gtav_use_cached_payload()                  # reuse an earlier download
        if not (_gtav.payload_available() and _gtav.vanilla_available()):
            _mod_progress_cb("error", 0, _DL_FAILED_MSG)
            return
        r = _gtav.apply(base, str(_gtav_backup_dir()), _mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהתקנת התרגום")
            return
        _native_write_state(_GTAV_ID, {"version": version or _GTAV_BUNDLED_VERSION,
                                       "installed": True})
        msg = "הותקן! במשחק: הגדרות → שפה = American (אנגלית-אמריקאית) כדי לראות את העברית."
        if not _gtav.loader_connected(base):
            msg += " ודא ש-ASI של OpenIV מותקן (dinput8.dll) כדי שהמשחק יקרא את תיקיית ה-mods."
        _mod_progress_cb("done", 100, msg)
    except Exception as e:                                  # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def install_gtav_mod() -> dict:
    """Kick off the GTA V Hebrew apply on a background worker."""
    base = _install_path(_GTAV_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא - הגדר נתיב תחילה בהגדרות"}
    # (No bundled-payload pre-check: the payload is downloaded at install time.
    #  A network failure is reported by the worker with an actionable message.)
    # DRM gate - paid mod; defense-in-depth (the UI gates too, and _run_gtav_install
    # re-checks). Without a completed purchase, no install.
    if _game_price_cents(_GTAV_ID) > 0 and not auth_owns_game(_GTAV_ID):
        return {"ok": False, "error": "המשחק טרם נרכש", "state": get_gtav_mod_state()}
    if not _gtav.has_mods_folder(base):
        return {"ok": False, "error": "אין תיקיית mods - נדרשת הקמה חד-פעמית עם OpenIV",
                "state": get_gtav_mod_state()}
    import gevent
    gevent.spawn(_run_gtav_install)
    return {"ok": True, "started": True}


def _run_gtav_remove() -> None:
    """SURGICAL remove: swap the translation files back to vanilla English IN PLACE,
    preserving every other mod (does NOT use the possibly-stale install backup)."""
    try:
        base = _install_path(_GTAV_ID)
        if base is None:
            _mod_progress_cb("error", 0, "המשחק לא נמצא")
            return
        # Revert with the SAME payload pair the install used (the downloaded one
        # when present) so the vanilla files written back match byte-for-byte.
        # UPGRADE PATH: a user who installed on an older build (payload bundled in
        # the exe) has nothing cached, and nothing ships in the installer any more -
        # so fetch it now, exactly like the install does. Without this, "remove"
        # would fail with a raw "payload not bundled" for every pre-1.1.0 install.
        if not _gtav_use_cached_payload():
            _gtav_download_payload(_mod_progress_cb)
        if not _gtav.vanilla_available():
            _mod_progress_cb("error", 0, _DL_FAILED_MSG)
            return
        r = _gtav.revert(base, str(_gtav_backup_dir()), _mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהסרת התרגום")
            return
        _mod_progress_cb("done", 100,
            "התרגום הוסר - הטקסט חזר לאנגלית והפונטים המקוריים; המודים האחרים שלך נשמרו.")
    except Exception as e:                                  # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def remove_gtav_mod() -> dict:
    """Surgical remove (vanilla swap) on a worker - heavy multi-GB I/O, streams
    progress like the install. Preserves the user's other mods."""
    base = _install_path(_GTAV_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא", "state": get_gtav_mod_state()}
    import gevent
    gevent.spawn(_run_gtav_remove)
    return {"ok": True, "started": True}


def _run_gtav_restore_backup() -> None:
    """Full restore from the install-time backup (the EXACT pre-install state).
    ⚠ Discards any change made to those RPFs since the install - the separate
    'restore the snapshot from before I installed' action."""
    try:
        base = _install_path(_GTAV_ID)
        if base is None:
            _mod_progress_cb("error", 0, "המשחק לא נמצא")
            return
        r = _gtav.restore_backup(base, str(_gtav_backup_dir()), _mod_progress_cb)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בשחזור הגיבוי")
            return
        _mod_progress_cb("done", 100, "שוחזר הגיבוי המלא - המצב חזר לרגע שלפני ההתקנה.")
    except Exception as e:                                  # pragma: no cover
        _mod_progress_cb("error", 0, f"שגיאה: {e}")


@eel.expose
def restore_gtav_backup() -> dict:
    """Full pre-install restore (separate from the surgical remove). On a worker."""
    base = _install_path(_GTAV_ID)
    if base is None:
        return {"ok": False, "error": "המשחק לא נמצא", "state": get_gtav_mod_state()}
    if not _gtav.has_backup(str(_gtav_backup_dir())):
        return {"ok": False, "error": "אין גיבוי מלא לשחזור", "state": get_gtav_mod_state()}
    import gevent
    gevent.spawn(_run_gtav_restore_backup)
    return {"ok": True, "started": True}


@eel.expose
def get_offline_assets() -> dict:
    """What the OFFLINE package on this machine carries.

    Drives (a) the frontend's LOCAL image resolver - covers are absolute
    Supabase URLs, so with no internet they only render if we point them at the
    bundled copies - and (b) a diagnostics line. Never raises."""
    try:
        pay = _offline_bundle.images_payload()
        inf = _offline_bundle.info()
        return {
            "available":  bool(inf.get("available")),
            "createdAt":  inf.get("createdAt"),
            "games":      inf.get("games") or [],
            "path":       inf.get("path"),
            "imagesBase": pay.get("base") or "",
            "imageRels":  pay.get("rels") or [],
        }
    except Exception:                                   # pragma: no cover
        return {"available": False, "createdAt": None, "games": [], "path": None,
                "imagesBase": "", "imageRels": []}


def _seed_cache_from_bundle(game_id: str) -> bool:
    """Populate a download-mod's cache from the OFFLINE package (no network).

    Makes the DOWNLOAD step unnecessary - the launcher's own install() still
    performs the actual apply into the game folder, so a mod is always written
    by the code that knows how to revert it. The payload is SHA-verified inside
    offline_bundle.extract, so this keeps the online integrity posture."""
    try:
        got = _offline_bundle.extract(game_id, _mod_progress_cb)
        if got is None:
            return False
        ed, version = got
        try:
            r = _game_mod.cache_from_dir(game_id, pathlib.Path(ed), version)
            if r.get("ok"):
                print(f"[{game_id}] cache seeded from OFFLINE bundle v{version}", flush=True)
                return True
            print(f"[{game_id}] offline seed failed: {r.get('error')}", flush=True)
            return False
        finally:
            shutil.rmtree(pathlib.Path(ed).parent, ignore_errors=True)
    except Exception as e:                              # pragma: no cover
        print(f"[{game_id}] offline seed error: {e}", flush=True)
        return False


def _run_game_mod_install(game_id: str) -> None:
    """Background worker: download (if needed) + install a game mod.

    Runs as a gevent GREENLET on the launcher's main hub (see
    download_and_install_game_mod for why a real thread is wrong here).
    Streams mod_install_progress ticks as it works and emits a terminal
    'done' / 'error' tick the GameDetailPanel watches for."""
    try:
        _CUR_INSTALL_GAME[0] = game_id          # attribute any install_error to this game
        # DRM gate INSIDE the worker. The RPC checks too, but the Qt bridge starts
        # this worker DIRECTLY (bridge.download_and_install_game_mod ->
        # QThreadPool.start(_run_game_mod_install)), so an RPC-only check is not a
        # gate on the shipped build - which is exactly how a paid mod could be
        # installed by an account that never bought it.
        if _game_price_cents(game_id) > 0 and not auth_owns_game(game_id):
            _mod_progress_cb("error", 0, "יש לרכוש את התרגום לפני ההתקנה")
            return
        cfg  = _config_for(game_id)
        base = _install_path(game_id)
        # Where the files actually go - the game folder for most mods, or
        # %Documents%\…\mods for a loose-file Documents mod (Anno). For a
        # Documents mod the folder may not exist yet (game never launched) -
        # create it so the writability probe + copy succeed.
        deploy = _deploy_root(game_id)
        if cfg and getattr(cfg, "documents_subdir", "") and deploy is not None:
            try:
                deploy.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        # Decide whether to (re)download. NOT cached → must download. Cached
        # but the server has a NEWER version → this is an UPDATE, so refresh
        # the cache (download_and_cache wipes it first). Without this, an
        # update click silently re-installed the stale cached version and the
        # panel stayed stuck on "update available".
        need_dl  = not _game_mod.is_cached(game_id)
        cached_v = (_game_mod.read_state(game_id) or {}).get("version")
        # OFFLINE BUNDLE first: if a pre-built package carries this game and the
        # cache is empty or older, seed the cache from it. No network at all, and
        # the payload is SHA-verified inside offline_bundle - so an offline
        # machine installs (and UPDATES) exactly like an online one.
        bundle_v = _offline_bundle.version_for(game_id)
        if bundle_v and (not cached_v or _version_is_newer(bundle_v, cached_v)):
            if _seed_cache_from_bundle(game_id):
                need_dl, cached_v = False, bundle_v
        if not need_dl:
            try:
                latest_v = _mod_source.fetch_manifest(slug=cfg.mod_slug).get("version")
                if cached_v and latest_v and _version_is_newer(latest_v, cached_v):
                    need_dl = True
            except Exception:                              # offline → install cache as-is
                pass
        # Fail fast on a read-only game folder (e.g. a game under Program Files
        # with a non-elevated launcher). Checked for EVERY install, not just a
        # downloading one - an offline install from a warm cache would otherwise
        # only fail with a raw PermissionError at the very end of the copy.
        if deploy is not None and not _game_mod.is_writable(deploy):
            _mod_progress_cb("error", 0,
                "אין הרשאת כתיבה לתיקיית היעד. הפעל את התוכנה כמנהל, "
                "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב.")
            return
        if need_dl:
            r = _game_mod.download_and_cache(game_id, cfg.mod_slug, _mod_progress_cb)
            if not r.get("ok"):
                # Network down (or the mod is unreachable) → last chance is the
                # offline package, even at the SAME version as the cache.
                if not _seed_cache_from_bundle(game_id):
                    _mod_progress_cb("error", 0, r.get("error") or "כשל בהורדת התרגום")
                    return
        r = _game_mod.install(game_id, deploy, _mod_progress_cb,
                              cfg.payload_exclude if cfg else None)
        if not r.get("ok"):
            _mod_progress_cb("error", 0, r.get("error") or "כשל בהתקנת התרגום")
            return
        if game_id == _CP2077_ID:
            try:
                _cp2077_enable_arabic_slot()
            except Exception as e:                      # pragma: no cover
                print(f"[cp2077_language] enable failed: {e}", flush=True)
            _cp2077_disable_crash_reporter(base)
        elif game_id == _ANNO_ID:
            # Auto-select the English text slot (where the Hebrew ships), then deploy the
            # Hebrew-injected maindata data4.rda (the English-slot build needs it for the
            # cold-boot pre-baked atlas; the loose mod alone leaves those screens garbled).
            _anno1800_set_language_english()
            d4 = _anno1800_deploy_data4(base)
            if not d4.get("ok"):
                _mod_progress_cb("error", 0, d4.get("error") or "כשל בהתקנת גופני המשחק")
                return
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
        return {"ok": False, "error": "נתיב המשחק לא הוגדר - הגדר אותו תחילה בהגדרות"}
    # DRM gate - defense-in-depth; the UI gates too.
    if _game_price_cents(game_id) > 0 and not auth_owns_game(game_id):
        return {"ok": False, "error": "המשחק טרם נרכש"}

    # gevent GREENLET, NOT a real thread: eel's progress callback
    # (eel.mod_install_progress(...)()) is bound to the launcher's main
    # gevent hub - invoking it from a separate OS thread throws every
    # time, so nothing reaches the UI (the install still finishes, but
    # the bar sits at 0% and only a panel re-mount shows the result).
    # A greenlet shares the hub: requests cooperatively yields and every
    # progress tick - and the terminal 'done' - streams live.
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
    # File target - game folder for most mods, %Documents%\… for Anno.
    deploy = _deploy_root(game_id)
    if installed and cfg.documents_subdir and deploy is not None:
        try:
            deploy.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    if installed:
        # DRM gate - mirrors download_and_install_game_mod. Without this,
        # any user with a stale local cache could re-apply a paid mod by
        # clicking "Reinstall" even after their purchase was revoked / a
        # different account signed in. The install RPC must check
        # ownership at every entry point, not just on the first download.
        if _game_price_cents(game_id) > 0 and not auth_owns_game(game_id):
            return {"ok": False, "error": "המשחק טרם נרכש",
                    "state": get_game_mod_state(game_id)}
        r = _game_mod.install(game_id, deploy, _mod_progress_cb,
                              cfg.payload_exclude if cfg else None)
        hook = _cp2077_enable_arabic_slot
    else:
        r = _game_mod.disable(game_id, deploy, cfg.mod_files if cfg else None)
        hook = _cp2077_restore_language
    if r.get("ok") and game_id == _ANNO_ID:
        if installed:
            _anno1800_set_language_english()
            d4 = _anno1800_deploy_data4(base)
            if not d4.get("ok"):
                return {"ok": False, "error": d4.get("error") or "כשל בהתקנת גופני המשחק",
                        "state": get_game_mod_state(game_id)}
        else:
            _anno1800_revert_data4(base)
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
    """Remove a game mod entirely - from the game folder AND the launcher
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
    # Anno: restore the user's original maindata data4.rda before wiping the cache.
    if game_id == _ANNO_ID:
        _anno1800_revert_data4(base)
    r = _game_mod.clear_cache(game_id, _deploy_root(game_id), cfg.mod_files if cfg else [])
    return {**r, "state": get_game_mod_state(game_id)}


@eel.expose
def clear_native_mod_cache(game_id: str) -> dict:
    """Consistency 'clear cache' for the native appliers (SM2/WD2/GTAV/GoWR/HL/
    W3/PT/VirtualDJ) - mirrors clear_game_mod_cache for download mods.

    SAFE ORDER: revert the mod from the game FIRST (the applier's own remove,
    which restores from the backup that lives inside the cache dir), and only
    then wipe the cache so a reinstall pulls a fresh copy. If the mod is still
    installed and revert fails (e.g. the game is running), we DO NOT wipe - that
    would destroy the backup and strand the mod. VirtualDJ has its own clear."""
    if game_id == _VDJ_ID:
        return clear_virtualdj_mod_cache()
    if game_id == _BG_ID:
        return clear_borderless_gaming_mod_cache()
    removers = {
        # ⚠️ GTAV → the SYNC worker `_run_gtav_remove`, NOT the eel wrapper
        # `remove_gtav_mod` (which does `gevent.spawn(...)`). Under the shipped Qt
        # build there is no gevent hub pumping that greenlet, so the wrapper would
        # return started:True while the revert NEVER runs → the re-check below sees
        # installed still True and forever reports "ההסרה רצה ברקע". clear_native is
        # already dispatched off-thread by the bridge, so a synchronous revert here
        # is safe and actually completes before we re-read the state.
        _SM2_ID: remove_spiderman2_mod, _WD2_ID: remove_watchdogs2_mod,
        _GTAV_ID: _run_gtav_remove,     _GOWR_ID: remove_gowr_mod,
        _HL_ID:  remove_hogwarts_mod,   _W3_ID:  remove_witcher3_mod,
        _PT_ID:  remove_plaguetale_mod,
    }
    getters = {
        _SM2_ID: get_spiderman2_mod_state, _WD2_ID: get_watchdogs2_mod_state,
        _GTAV_ID: get_gtav_mod_state,      _GOWR_ID: get_gowr_mod_state,
        _HL_ID:  get_hogwarts_mod_state,   _W3_ID:  get_witcher3_mod_state,
        _PT_ID:  get_plaguetale_mod_state,
    }
    fn, get_st = removers.get(game_id), getters.get(game_id)
    if fn is None or get_st is None:
        return {"ok": False, "error": "not-a-native-applier"}
    try:
        st = get_st()
    except Exception:                                   # pragma: no cover
        st = {}
    if st.get("installed"):
        try:
            r = fn()
        except Exception as e:                          # pragma: no cover
            print(f"[clear_native_mod_cache] revert failed: {e}", flush=True)
            return {"ok": False, "error": f"revert-failed: {e}", "state": st}
        if isinstance(r, dict) and not r.get("ok", True):
            return {"ok": False, "error": r.get("error") or "revert-failed",
                    "state": r.get("state") if isinstance(r.get("state"), dict) else st}
        # ⚠️ An applier whose remove runs on a BACKGROUND worker (GTAV:
        # `gevent.spawn(_run_gtav_remove)`) returns {"ok": True, "started": True}
        # IMMEDIATELY - `ok` proves NOTHING about the revert. So re-read the REAL
        # state and refuse to wipe while the mod is still applied; that keeps this
        # generic over sync AND async removes without hardcoding which is which.
        try:
            st = get_st()
        except Exception:                               # pragma: no cover
            st = {}
        if st.get("installed"):
            return {"ok": False,
                    "error": "ההסרה עדיין רצה ברקע - נסה לנקות את המטמון שוב בסיומה",
                    "state": st}
    # Not installed now → the backup is no longer needed; wipe the whole cache.
    try:
        import shutil
        shutil.rmtree(_native_cache_dir(game_id), ignore_errors=True)
    except Exception:                                   # pragma: no cover
        pass
    try:
        state = get_st()
    except Exception:                                   # pragma: no cover
        state = {}
    return {"ok": True, "state": state}


def _lang_mod_installed(game_id: str) -> bool | None:
    """Is the Hebrew mod present, for the 'auto' language mode?

    Launcher-tracked mods (CP2077) → the real install state. Games whose mod
    the launcher doesn't manage (Spider-Man 2 ships via Overstrike) → None,
    which game_language reads as 'translated' so auto means Hebrew."""
    # VirtualDJ has no GameConfig (loose-file applier) - resolve from the applier.
    if game_id == _VDJ_ID:
        return _mod_state(_VDJ_ID) == "ACTIVE"
    if game_id == _BG_ID:
        return _mod_state(_BG_ID) == "ACTIVE"
    if game_id == _SRGB_ID:
        return _mod_state(_SRGB_ID) == "ACTIVE"
    # SM2 (no GameConfig) + W3 (mod_files=[]) ARE launcher-tracked native appliers -
    # _mod_state knows their real install state. Without this they'd hit the
    # `return None` below → game_language reads None as "translated" → "auto" would
    # force the Arabic/Hebrew locale even when the mod was NEVER installed, showing
    # the game's untranslated base Arabic instead of English.
    if game_id in (_SM2_ID, _W3_ID):
        return _mod_state(game_id) == "ACTIVE"
    cfg = _config_for(game_id)
    if cfg is None or not cfg.mod_files:
        return None
    try:
        st = get_game_mod_state(game_id)
        if st.get("modSlug"):
            return bool(st.get("installed"))
    except Exception:                                   # pragma: no cover
        pass
    return _mod_state(game_id) == "ACTIVE"


@eel.expose
def get_game_language(game_id: str) -> dict:
    """Current in-game TEXT-language state for the launcher's 3-way switch
    (auto / Hebrew[Arabic] / English). {supported:false} for unsupported
    titles so the UI simply hides the control."""
    try:
        return _game_language.get_state(game_id, installed=_lang_mod_installed(game_id))
    except Exception as e:                              # pragma: no cover
        return {"supported": False, "error": str(e)}


def _title_locked(game_id: str) -> bool:
    """A PAID title the signed-in user has not bought → every mod control is
    off-limits (language switch, beta channel, cache). Enforced HERE, not just
    in the UI - a disabled button is not a gate. Free titles → never locked.

    auth_owns_game is fail-closed (returns False on a network error too), so a
    confirmed buyer could be wrongly re-locked by a momentary blip. We keep a
    session record of confirmed purchases and leave such a title unlocked; a
    title never confirmed owned stays locked (fail-closed) until a check passes."""
    price = _game_price_cents(game_id)
    if price <= 0:
        return False
    try:
        if _owns_confirm(game_id):
            return False
    except Exception:                                   # pragma: no cover
        pass
    # Not owned right now - but a title CONFIRMED bought earlier this session
    # stays unlocked, so a momentary network blip can't re-lock a real buyer.
    # A title never confirmed owned stays LOCKED (fail-closed).
    return game_id not in _owned_confirmed


# Errors that are the USER's situation, not a defect: reporting them would bury
# the real bugs in noise. Everything else that fails is worth knowing about.
_EXPECTED_ERRORS = ("not-purchased", "not-supported", "unsupported")


def _report_op_failure(op: str, game_id: str, res: dict | None, **ctx) -> None:
    """Report a HANDLED operational failure (a normal `{ok: False, error}`
    return) as an anonymous, silent event.

    THE GAP THIS CLOSES: crash reporting only ever saw EXCEPTIONS - handled
    failures just returned a dict, showed the user a message, and vanished. So
    exactly the errors worth acting on (a language switch that could not write, a
    mod that would not install) were never reported, while the opt-in toggle said
    reporting was on. Same disclosed opt-in, same scrubbing, same per-session
    cap; expected/user-state errors are skipped."""
    try:
        if not isinstance(res, dict) or res.get("ok") is not False:
            return
        err = str(res.get("error") or "")
        if not err or any(x in err for x in _EXPECTED_ERRORS):
            return
        _event("op_failed", err, source=op, code=err[:60],
               game=game_id, **ctx)
    except Exception:
        pass


@eel.expose
def set_game_language(game_id: str, mode: str) -> dict:
    """Apply a language mode ('auto' | 'hebrew' | 'english') and persist it.
    The pre-mod language is captured on first write so restore stays exact."""
    if _title_locked(game_id):
        return {"ok": False, "supported": True, "error": "not-purchased"}
    try:
        res = _game_language.set_mode(game_id, mode, installed=_lang_mod_installed(game_id))
    except Exception as e:                              # pragma: no cover
        res = {"ok": False, "supported": True, "error": str(e)}
    _report_op_failure("set_game_language", game_id, res, mode=mode)
    return res


@eel.expose
def restore_game_language(game_id: str) -> dict:
    """Revert the game's text language to whatever it was before the launcher
    first touched it (the genuine pre-mod value; English if never captured)."""
    if _title_locked(game_id):
        return {"ok": False, "error": "not-purchased"}
    try:
        res = _game_language.restore_original(game_id)
    except Exception as e:                              # pragma: no cover
        res = {"ok": False, "error": str(e)}
    _report_op_failure("restore_game_language", game_id, res)
    return res


@eel.expose
def open_purchase_page(game_id: str) -> dict:
    """Open the website's per-game checkout deep link in the user's
    default browser. The website's GamesPage component auto-opens the
    matching modal (one click away from PayPal). After payment the
    launcher re-checks ownership via the post-purchase burst poll in
    GameDetailPanel."""
    import webbrowser
    # SOFTWARE (VirtualDJ…) lives at /software/<id> on the site; opening it at
    # /games/<id> just redirects to the games grid, so a paid software mod could
    # never be bought from the launcher. Route by which catalog the id is in.
    try:
        is_software = any(s.get("id") == game_id for s in _load_software())
    except Exception:                                   # pragma: no cover
        is_software = False
    section = "software" if is_software else "games"
    url = f"https://hebrew-translation-hub.com/{section}/{game_id}?buy=1"
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
    # Best-effort - failures degrade silently so they never block the
    # file-level mod operation that already succeeded above.
    if ok and game_id == _CP2077_ID:
        try:
            lang_result = _cp2077_enable_arabic_slot()
        except Exception as e:  # pragma: no cover - defensive
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
        except Exception as e:  # pragma: no cover - defensive
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
        except Exception as e:  # pragma: no cover - defensive
            print(f"[cp2077_language] restore (uninstall) failed: {e}", flush=True)
            lang_result = {"ok": False, "error": str(e)}
    return {
        "ok": ok, "count": count, "error": err, "state": _mod_state(game_id),
        "language": lang_result,
    }


MINIMIZE_FOR_GAME = None          # the Qt shell installs its window-minimiser here


def set_native_minimize(fn) -> None:
    """The Qt shell installs `lambda: window.hide_to_tray()` here so a game
    launch can put the whole Chromium window away (see `_yield_to_game`)."""
    global MINIMIZE_FOR_GAME
    MINIMIZE_FOR_GAME = fn


def _yield_to_game(proc) -> None:
    """Hand the machine to the game we just launched, and take it back when the
    game exits. Best-effort throughout - a failure here must never break a launch.

    WHY: a user measured it - "through the launcher the FPS is low, through the
    game's own launcher it runs smooth". While the game plays we were still a
    VISIBLE Chromium window (composited on the same GPU, ambient animations
    running), polling at full cadence, holding a few hundred MB of working set,
    at the same process priority as the game. Steam/Epic get out of the way on
    launch; we did nothing at all.

    Three levers, cheapest first - none of them touches the game process:
      1. minimise to tray  → Chromium stops painting/compositing entirely, and an
         always-on-top surface can no longer knock the game out of exclusive
         fullscreen (the classic cause of exactly this symptom).
      2. below-normal priority for US → we are I/O-bound pollers, so this costs
         nothing and guarantees the game wins every scheduling contest.
      3. trim the working set + tell perf_manager a game is running → hundreds of
         MB back to the game, and every background poller backs off hard.
    """
    import threading as _th

    try:
        from translation_manager import perf_manager as _pm
    except Exception:                                    # pragma: no cover
        _pm = None

    def _priority(below: bool) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
            # A HANDLE must be declared c_void_p: ctypes defaults to a 32-bit int
            # and TRUNCATES the 64-bit pseudo-handle, so the call fails (silently,
            # inside this except) and the priority is never actually changed. Same
            # trap that made perf_manager's EmptyWorkingSet a no-op for months.
            k = ctypes.windll.kernel32
            k.GetCurrentProcess.restype  = ctypes.c_void_p
            k.SetPriorityClass.argtypes  = [ctypes.c_void_p, ctypes.c_uint]
            # BELOW_NORMAL_PRIORITY_CLASS / NORMAL_PRIORITY_CLASS
            k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000 if below else 0x00000020)
        except Exception:
            pass

    try:
        if MINIMIZE_FOR_GAME:
            MINIMIZE_FOR_GAME()
    except Exception:
        pass
    _priority(True)
    if _pm:
        try:
            _pm.set_game_running(True)
            _pm.trim_memory(force=True)
        except Exception:
            pass

    def _restore() -> None:
        try:
            proc.wait()                                  # the game exited
        except Exception:
            pass
        _priority(False)
        if _pm:
            try:
                _pm.set_game_running(False)
            except Exception:
                pass

    _th.Thread(target=_restore, name="game-exit-watch", daemon=True).start()


@eel.expose
def launch_game(game_id: str) -> dict:
    """Find the game's (or SOFTWARE's) executable and spawn it."""
    cfg = _config_for(game_id)
    exe: Path | None = None

    # SOFTWARE (VirtualDJ …): no GameConfig and not in the game path cache, so
    # `_install_path` is always None here → "install path not set". Resolve the
    # folder AND the real exe through software_detector instead.
    if _is_software(game_id):
        info = _software_detect(game_id)
        base = _software_install_path(game_id)
        exe_hint = info.get("exe")
        if exe_hint and Path(exe_hint).exists():
            exe = Path(exe_hint)
    else:
        base = _install_path(game_id)

    if base is None and exe is None:
        return {"ok": False, "error": "install path not set"}
    if base is None and exe is not None:
        base = exe.parent

    # HIGHEST authority: an exe the user picked BY HAND in Settings. It was being
    # ignored here, so an explicit choice lost to the guesses below (and the user
    # got "executable not found" on a game they had just pointed us at).
    if exe is None:
        try:
            picked = user_paths.get_exe(game_id)
            if picked:
                exe = Path(picked)
        except Exception:
            pass

    # Preferred: the validation_file from config (it's the real exe).
    if exe is None and cfg and cfg.validation_file:
        candidate = base / cfg.validation_file
        if candidate.exists():
            exe = candidate

    # The detector knows this game's REAL exe names across the known bin/ layouts
    # - far better than "largest .exe", which picks a crash handler / redist stub
    # when the launcher exe is small (and finds nothing when the layout differs).
    if exe is None:
        try:
            from translation_manager import game_detector as _gd
            hit = _gd.find_exe(game_id, base)
            if hit:
                exe = Path(hit)
        except Exception:
            pass

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
        # SAY WHICH failure it is. "executable not found" is identical whether the
        # folder is gone (moved / external drive unplugged / uninstalled) or is
        # there but has no exe - and the user can only act on the first one. Real
        # report: two `no_exe` clicks 3 minutes apart, then the user gave up.
        try:
            gone = not base.exists()
        except OSError:
            gone = True
        if gone:
            _event("launch_error", f"game folder missing: {base}", source="launch_game",
                   code="base_missing", game=game_id, severity="warn")
            return {"ok": False, "error":
                    "תיקיית המשחק לא נמצאה - ייתכן שהיא הועברה, נמחקה, או שהכונן מנותק. "
                    "עדכנו את הנתיב בהגדרות המשחק."}
        _event("launch_error", f"no exe under {base}", source="launch_game",
               code="no_exe", game=game_id, severity="warn")
        return {"ok": False, "error":
                "לא נמצא קובץ הפעלה בתיקיית המשחק. בחרו את קובץ ה-EXE ידנית בהגדרות המשחק."}

    try:
        # NORMAL_PRIORITY_CLASS explicitly: a child inherits the PARENT's priority
        # class at creation, and we drop ours to below-normal below. Without this
        # the game would inherit the lowered class on a second launch.
        _kw = {"creationflags": 0x00000020} if sys.platform == "win32" else {}
        proc = subprocess.Popen([str(exe)], cwd=str(exe.parent), **_kw)
        # GET OUT OF THE WAY. Real user report: "launching through the launcher the
        # FPS is low; launching from the game's own launcher it runs smooth" - a
        # clean A/B from the user's own machine. We kept a Chromium window painting
        # + composited on the SAME GPU, our pollers at full cadence, and a few
        # hundred MB of working set, for the whole play session.
        _yield_to_game(proc)
        # Fire any 'on launch' / 'realtime' save-backups for this game (best-effort).
        try:
            _plugins().host.on_game_launch(game_id)
        except Exception:                               # pragma: no cover
            pass
        return {"ok": True, "exe": str(exe)}
    except OSError as e:
        # WinError 740 = the game exe DEMANDS elevation (its manifest
        # requestedExecutionLevel=requireAdministrator - common for FitGirl/other
        # repacks + some AAA launchers). We run non-elevated, so Popen can't spawn
        # it. Re-launch ELEVATED via ShellExecute "runas" (a UAC prompt) instead of
        # surfacing a raw error.
        if getattr(e, "winerror", None) == 740 and sys.platform == "win32":
            try:
                import ctypes
                rc = int(ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", str(exe), None, str(exe.parent), 1))  # SW_SHOWNORMAL
                if rc > 32:
                    return {"ok": True, "exe": str(exe), "elevated": True}
                if rc == 1223:   # ERROR_CANCELLED - user declined the UAC prompt
                    return {"ok": False, "error": "ההפעלה בוטלה - המשחק דורש הרשאת מנהל"}
                return {"ok": False, "error": f"הפעלה מוגבהת נכשלה (קוד {rc})"}
            except Exception as e2:                         # pragma: no cover
                _event("launch_error", str(e2), source="launch_game",
                       code="elevate_fail", game=game_id)
                return {"ok": False, "error": str(e2)}
        _event("launch_error", str(e), source="launch_game",
               code=f"winerror_{getattr(e, 'winerror', 0)}", game=game_id)
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────
# Downloads - wire downloads.py into Eel.
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
def report_ui_event(kind: str = "ui_error", message: str = "",
                    source: str = "", code: str = "",
                    severity: str = "error") -> dict:
    """Frontend → backend bridge for a handled UI event (an RPC that rejected,
    a button handler that threw, an unhandled JS error / promise rejection, a
    React render error). Anonymous + silent + opt-in-gated by report_event."""
    _event(str(kind or "ui_error"), str(message or ""),
           source=str(source or "ui"), code=str(code or ""),
           severity="warn" if severity == "warn" else "error")
    return {"ok": True}


@eel.expose
def list_updates() -> list[dict]:
    return _load_updates()


@eel.expose
def get_all_software() -> list[dict]:
    """SOFTWARE library - the `isSoftware` rows of the SAME catalog, enriched
    EXACTLY like games (install path · mod state · language) so the frontend
    renders them with the identical GameCard / GameDetailPanel. One admin
    panel, one shape, two libraries."""
    return _enrich_catalog(_load_software())


@eel.expose
def scan_software() -> dict:
    """Full re-scan of installed software. Used by the "סרוק" button under
    the תוכנות tab - also clears any "forgotten" software paths so a
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


# ═════════════════════════════════════════════════════════════
# PLUGINS - cloud-delivered add-ons (Settings → "תוספים")
# Gated: a signed-in user who has bought at least one GAME (not software).
# The first plugin is the automatic game-save backup.
# ═════════════════════════════════════════════════════════════
def _owns_any_game() -> bool:
    """True iff the signed-in user has a completed purchase for at least one
    GAME (not software). The entitlement gate for the whole plugin system.
    Fails CLOSED (signed out / network error → no plugins)."""
    if not (_auth_available and _auth):
        return False
    try:
        res = _auth.get_purchases()
        if res.get("reason") != "ok":
            return False
        soft_ids = {s.get("id") for s in _load_software()}
        for row in res.get("rows") or []:
            gid = row.get("game_id")
            if gid and gid not in soft_ids:              # a GAME purchase
                return True
        return False
    except Exception:                                   # pragma: no cover
        return False


def _signed_in() -> bool:
    """True iff an account is signed in on this launcher. The gate for a FREE
    plugin - reads the ON-DISK identity cache, never the network: a volunteer who
    is donating their machine must not be locked out by a connectivity blip."""
    if not (_auth_available and _auth):
        return False
    try:
        return bool(_auth.cached_user())
    except Exception:                                   # pragma: no cover
        return False


_plugins_configured = False


def _plugins():
    """Lazily import + configure the plugins package (wires the DRM gate once)."""
    global _plugins_configured
    from translation_manager import plugins as _pl
    # Belt-and-braces with the package's own `from . import host`: callers reach
    # the scheduler as `_plugins().host.…`, and an un-imported submodule is not
    # an attribute of its package - which failed SILENTLY behind their broad
    # `except`, so the plugin host never started at boot.
    from translation_manager.plugins import host as _host  # noqa: F401
    if not _plugins_configured:
        try:
            _pl.registry.configure(owns_any_game=_owns_any_game,
                                   signed_in=_signed_in)
        except Exception:                               # pragma: no cover
            pass
        try:
            # Wire the declarative engine's audited capabilities to the RPC-layer
            # helpers (installed-games detection + native folder pick/open). This
            # is what lets a cloud plugin's UI drive save_backup with NO code exec.
            from translation_manager.plugins import engine as _eng
            _eng.configure(
                detect_fn=savebackup_detect,
                pick_folder_fn=lambda title: pick_folder(str(title or ""), ""),
                pick_file_fn=lambda title: pick_file(str(title or "")),
                open_folder_fn=lambda p: open_folder(str(p or "")),
            )
        except Exception:                               # pragma: no cover
            pass
        _plugins_configured = True
    return _pl


@eel.expose
def get_plugins() -> dict:
    """{entitled, plugins:[{…, installed, enabled}]} - drives the Plugins tab."""
    try:
        return _plugins().registry.snapshot()
    except Exception as e:                              # pragma: no cover
        return {"entitled": False, "plugins": [], "error": str(e)}


@eel.expose
def install_plugin(plugin_id: str) -> dict:
    try:
        return _plugins().registry.install(str(plugin_id))
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


@eel.expose
def remove_plugin(plugin_id: str) -> dict:
    try:
        return _plugins().registry.remove(str(plugin_id))
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


@eel.expose
def update_plugin(plugin_id: str) -> dict:
    """Adopt the catalog's current version of an installed plugin (version stamp
    + any config default a newer version added). No app rebuild involved."""
    try:
        return _plugins().registry.update(str(plugin_id))
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


@eel.expose
def refresh_plugins() -> dict:
    """Re-read the plugin catalog from the cloud NOW (bypasses the 300s cache),
    then return the fresh snapshot - so an added/removed/updated plugin shows up
    on demand instead of whenever the cache happens to expire."""
    try:
        reg = _plugins().registry
        fresh = reg.refresh_catalog()
        snap = reg.snapshot()
        snap["refreshed"] = bool(fresh)
        return snap
    except Exception as e:                              # pragma: no cover
        return {"entitled": False, "plugins": [], "error": str(e)}


@eel.expose
def set_plugin_enabled(plugin_id: str, enabled: bool) -> dict:
    try:
        return _plugins().registry.set_enabled(str(plugin_id), bool(enabled))
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


@eel.expose
def get_plugin_config(plugin_id: str) -> dict:
    try:
        return _plugins().registry.get_config(str(plugin_id))
    except Exception:                                   # pragma: no cover
        return {}


@eel.expose
def set_plugin_config(plugin_id: str, config: dict) -> dict:
    try:
        return _plugins().registry.set_config(str(plugin_id), config or {})
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


# ── generic declarative-plugin surface (STABLE - no per-plugin rebuild) ──
# A cloud plugin ships a declarative `ui` manifest + calls audited primitives via
# `plugin_action`. These two RPCs render + drive ANY such plugin, so new plugin UI
# (and new save/file-domain plugins) reach installed users with no app rebuild.
@eel.expose
def plugin_ui(plugin_id: str) -> dict:
    """{ui, state, meta} for a declarative plugin: `ui` = the catalog manifest's
    UI tree, `state` = the live engine state the UI binds to, `meta` = catalog
    metadata (name/icon/accent/version). `ui` is None for a manifest-less plugin
    (the caller then falls back to a built-in panel)."""
    try:
        _pl = _plugins()
        from translation_manager.plugins import engine as _eng
        meta = _pl.registry.by_id(str(plugin_id)) or {}
        return {
            "ok":    True,
            "ui":    meta.get("ui"),
            "state": _eng.get_state(str(plugin_id)),
            "meta":  {k: meta.get(k) for k in
                      ("id", "name", "icon", "accent", "version", "kind")},
        }
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e), "ui": None, "state": {}, "meta": {}}


@eel.expose
def plugin_action(plugin_id: str, action: str, args: dict | None = None) -> dict:
    """Perform one audited primitive for a declarative plugin and return fresh
    state. `args` is a plain dict (the manifest's declared action args)."""
    try:
        from translation_manager.plugins import engine as _eng
        _plugins()  # ensure the engine is configured
        return _eng.run_action(str(plugin_id), str(action or ""),
                               args if isinstance(args, dict) else {})
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


# ── save-backup plugin specifics ─────────────────────────────
@eel.expose
def savebackup_detect() -> list[dict]:
    """Smart auto-locate: find save folders for every INSTALLED game."""
    try:
        from translation_manager.plugins import save_backup
        games = []
        for cg in _load_catalog():
            gid = cg.get("id")
            if not gid:
                continue
            if _install_path(gid) is not None:          # only games we can see on disk
                games.append({"id": gid,
                              "title": cg.get("titleEn") or cg.get("titleHe") or gid})
        return save_backup.detect_all(games)
    except Exception as e:                              # pragma: no cover
        log_ = __import__("logging").getLogger("launcher")
        log_.warning("savebackup_detect failed: %s", e)
        return []


@eel.expose
def savebackup_run_now(plugin_id: str = "save-backup", name: str = "") -> dict:
    try:
        return _plugins().host.run_now(str(plugin_id), str(name or ""))
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


@eel.expose
def savebackup_list(plugin_id: str = "save-backup") -> list[dict]:
    try:
        from translation_manager.plugins import save_backup
        cfg = _plugins().registry.get_config(str(plugin_id))
        return save_backup.list_backups(cfg)
    except Exception:                                   # pragma: no cover
        return []


@eel.expose
def savebackup_restore(backup_path: str, target: str) -> dict:
    try:
        from translation_manager.plugins import save_backup
        return save_backup.restore(str(backup_path), str(target))
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


@eel.expose
def open_external(url: str) -> dict:
    """Open an allowlisted external URL in the user's default browser. Host-pinned
    to the hub (the plugin 'buy a game' link etc.) so a hostile string can't turn
    this into an arbitrary-URL launcher."""
    import webbrowser
    from urllib.parse import urlparse
    try:
        u = urlparse(str(url))
        host = (u.hostname or "").lower()
        allowed = host == "hebrew-translation-hub.com" or host.endswith(".hebrew-translation-hub.com")
        if u.scheme != "https" or not allowed:
            return {"ok": False, "error": "blocked"}
        webbrowser.open(url)
        return {"ok": True}
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": str(e)}


# Set by main_qt to Bridge.pick_folder_blocking once the bridge exists. That is
# a REAL QFileDialog, safely marshalled from any thread to the GUI thread.
NATIVE_PICK_FOLDER = None


def set_native_pick_folder(fn) -> None:
    """The Qt shell installs its native picker here.

    The old comment claimed "the Qt bridge overrides this" - it never did. The
    bridge's pick_folder is a separate @Slot the FRONTEND calls; nothing replaced
    THIS function, so the plugin engine (which is handed `pick_folder` at
    configure time) always got the stub below and "change backup location"
    silently did nothing."""
    global NATIVE_PICK_FOLDER
    NATIVE_PICK_FOLDER = fn


@eel.expose
def pick_folder(req_id: str = "", title: str = "", start: str = "") -> dict:
    """Native 'choose a folder' dialog when the Qt shell provided one.

    The Qt build calls the bridge Slot (non-blocking, delivers via a Signal).
    This Eel-build fallback is synchronous - it returns {ok, path} directly, so
    the frontend's pickFile() resolves it immediately without waiting for a
    Signal. `req_id` is accepted for signature-parity and ignored here."""
    fn = NATIVE_PICK_FOLDER
    if fn is not None:
        try:
            return fn(title, start)
        except Exception as e:                          # pragma: no cover
            return {"ok": False, "path": "", "error": str(e)}
    return {"ok": False, "path": "", "error": "no-native-dialog"}


NATIVE_PICK_FILE = None


def set_native_pick_file(fn) -> None:
    """The Qt shell installs its native FILE dialog here (used by a plugin
    action such as "import my API keys from a file")."""
    global NATIVE_PICK_FILE
    NATIVE_PICK_FILE = fn


def pick_file(title: str = "", start: str = "") -> dict:
    """Native 'choose a file' dialog, or a clean no-op when unavailable."""
    fn = NATIVE_PICK_FILE
    if fn is not None:
        try:
            return fn(title, start)
        except Exception as e:                          # pragma: no cover
            return {"ok": False, "path": "", "error": str(e)}
    return {"ok": False, "path": "", "error": "no-native-dialog"}


NATIVE_PICK_EXE = None


def set_native_pick_exe(fn) -> None:
    """The Qt shell may install a native 'choose an .exe' dialog here (Eel build
    only; the Qt build's frontend calls the bridge's pick_exe Slot directly)."""
    global NATIVE_PICK_EXE
    NATIVE_PICK_EXE = fn


@eel.expose
def pick_exe(req_id: str = "", title: str = "", start: str = "") -> dict:
    """Native 'choose the game EXE' file dialog. Mirrors pick_folder: the Qt
    frontend calls the bridge Slot (non-blocking + Signal); this Eel-build
    fallback returns {ok, path} synchronously. `req_id` is ignored here."""
    fn = NATIVE_PICK_EXE
    if fn is not None:
        try:
            return fn(title, start)
        except Exception as e:                          # pragma: no cover
            return {"ok": False, "path": "", "error": str(e)}
    return {"ok": False, "path": "", "error": "no-native-dialog"}


@eel.expose
def plugins_boot() -> dict:
    """Run once after the app is up: fire on-boot backups + start the scheduler.
    Safe to call more than once (idempotent)."""
    try:
        _plugins().host.on_boot()
        return {"ok": True}
    except Exception as e:                              # pragma: no cover
        # LOUD on purpose: this failing is invisible from the UI (a background
        # plugin just quietly does nothing), so it has to be findable in the log.
        __import__("logging").getLogger("launcher").exception(
            "[plugins] plugins_boot failed - the host did NOT start")
        return {"ok": False, "error": str(e)}


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
        "disableGpu":    launcher_prefs.get_disable_gpu_compositing(),
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
def set_gpu_compositing(enabled: bool) -> dict:
    """Persist the GPU-acceleration choice. `enabled=True` (default) uses the
    GPU for a smooth, Steam-grade UI; `False` routes paint through the CPU to
    avoid flicker when another workload saturates the GPU. Stored inverted as
    `disable_gpu_compositing`; takes effect on the NEXT launch (Chromium flags
    are fixed at boot). Returns a fresh prefs snapshot."""
    from translation_manager import autostart, launcher_prefs
    launcher_prefs.set_disable_gpu_compositing(not bool(enabled))
    return {
        "ok": True,
        "disableGpu":    launcher_prefs.get_disable_gpu_compositing(),
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
# App icon (window / taskbar / tray + launch shortcut) - switchable
# ─────────────────────────────────────────────────────────────
@eel.expose
def get_app_icon() -> dict:
    """Current app-icon variant + the full picker option list (id/style/shape/
    corner/thumb). The Settings picker binds to this."""
    from translation_manager import app_icon
    return {
        "variant": app_icon.current(),
        "default": app_icon.DEFAULT,
        "options": app_icon.options(),
    }


@eel.expose
def set_app_icon(variant: str) -> dict:
    """Persist the chosen variant + repoint the launch shortcuts at its .ico.
    (In the Qt build the bridge slot overrides this to ALSO apply the icon LIVE
    to the running window/taskbar/tray - this eel path has no Qt handle.)"""
    from translation_manager import app_icon
    eff = app_icon.set_variant(variant)
    return {"ok": app_icon.is_valid(variant), "variant": eff,
            "options": app_icon.options()}


# ─────────────────────────────────────────────────────────────
# Live progress proxy - same data the public website displays.
# Pulls /api/progress?game=<id> via the SWR cache so the launcher's
# HomeView renders the universal ProgressDashboard instantly from the
# last-known-good snapshot, with a quiet background refresh.
# ─────────────────────────────────────────────────────────────
PROGRESS_API_BASE = "https://hebrew-translation-hub.com/api/progress"


def _fetch_progress(game_id: str) -> dict | None:
    """Single-shot fetch used by SWR. Returns:
       - dict on 200 with a JSON object body
       - None on 404 / non-dict body  (legitimately "no data" - cached as null)
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
# Launcher self-update - in-app download + silent install.
# ─────────────────────────────────────────────────────────────
# The "הורדות ועדכונים" tab carries a persistent panel that checks the
# /api/launcher release feed, downloads the installer in-app with a
# live progress bar, verifies its SHA-256, then runs it silently
# (/VERYSILENT - no external wizard window). The installer's
# PrepareToInstall hook force-closes this process; its [Run] entry
# relaunches the freshly-installed version.

# Pre-release stage model - MIRRORS website/src/lib/version.ts and
# frontend/src/lib/version.ts. Keep the three in lockstep.
_STAGE_RANK = {"alpha": 0, "beta": 1, "rc": 2, "stable": 3}
_STAGE_ALIASES = {
    "alpha": "alpha", "a": "alpha", "pre": "alpha",
    "beta": "beta", "b": "beta",
    "rc": "rc", "release-candidate": "rc", "releasecandidate": "rc",
    "stable": "stable", "final": "stable", "release": "stable", "": "stable",
}


def _parse_version(v: str) -> tuple:
    """'1.2.3' / '1.1.0-beta.2' → (scheme, major, minor, patch, stage_rank, pre).

    SemVer `MAJOR.MINOR.PATCH` with an optional pre-release stage suffix
    `-<stage>.<n>`. Stages oldest→newest: alpha → beta → rc → stable; a
    pre-release ranks BELOW the matching stable (SemVer §11), encoded as
    stage_rank alpha=0/beta=1/rc=2/stable=3 then the prerelease counter.

    The CP2077 mod versioning moved from a date scheme (YYYY.MM.DD, e.g.
    2026.05.22) to semver. A date's major (>=2000) would dwarf a semver major,
    so a date is ranked BELOW every semver via a leading 0/1 scheme tag (and
    `1.0.2` correctly reads as newer than `2026.05.22`).
    """
    raw = (v or "").strip()
    body = raw.lstrip("vV")
    dash = body.find("-")
    core = body[:dash] if dash >= 0 else body
    pre_s = body[dash + 1:] if dash >= 0 else ""

    nums: list[int] = []
    for part in core.split(".")[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    while len(nums) < 3:
        nums.append(0)
    major, minor, patch = nums[0], nums[1], nums[2]
    scheme = 0 if major >= 2000 else 1   # date-scheme ranks below semver

    stage, pre = "stable", 0
    if pre_s:
        import re as _re
        m = _re.match(r"([a-zA-Z][a-zA-Z-]*)\.?(\d+)?", pre_s)
        if m:
            stage = _STAGE_ALIASES.get(m.group(1).lower(), "stable")
            pre = int(m.group(2)) if m.group(2) else 0
    return (scheme, major, minor, patch, _STAGE_RANK[stage], pre)


def _version_is_newer(latest: str, current: str) -> bool:
    try:
        return _parse_version(latest) > _parse_version(current)
    except Exception:
        return False


def _is_prerelease(v: str) -> bool:
    """True for alpha/beta/rc versions (stage_rank < stable=3)."""
    try:
        return _parse_version(v)[4] < 3
    except Exception:
        return False


def _offer_update(game_id: str, latest: str, installed: str) -> bool:
    """Whether to OFFER `latest` as an update over `installed`: it must be
    newer AND either stable, OR the user opted into pre-release (beta) updates
    for this mod (per-mod override wins over the global beta-channel flag).
    This is what keeps stable users off betas unless they choose otherwise."""
    if not (installed and latest and _version_is_newer(latest, installed)):
        return False
    if _is_prerelease(latest):
        # If the user is ALREADY on a pre-release of this mod, keep them on the
        # beta track - offer the newer beta without requiring the opt-in toggle
        # (this is the whole point for beta-only mods: SM2/WD2/GoWR/GTAV ship
        # only betas, so a stable-only gate would strand every installed user on
        # their first version forever). A user on a STABLE build still needs the
        # explicit opt-in before we push a pre-release at them.
        if _is_prerelease(installed):
            return True
        try:
            from translation_manager import launcher_prefs
            return launcher_prefs.wants_prerelease(game_id)
        except Exception:
            return False
    return True


@eel.expose
def get_launcher_update_info() -> dict:
    """Check the release feed. Returns current-vs-latest version and
    whether an update is available. Network failures come back as a
    soft `error` string - the panel degrades gracefully, never throws.

    Update detection is version-OR-build: a higher version, OR the SAME
    version carrying a different build-id than this build. The launcher
    re-releases in place (same version), so without the build-id arm the
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
    except Exception as e:                               # pragma: no cover - network
        info["error"] = str(e)
    return info


def _emit_update_progress(phase: str, pct: float, detail: str) -> None:
    """Push one progress tick to the React self-update panel. Best-effort."""
    try:
        eel.launcher_update_progress(phase, round(float(pct), 1), detail)()  # type: ignore[attr-defined]
    except Exception:
        pass


# Cancel signal for an in-flight self-update. Cleared on each new
# start_launcher_update() invocation; set by cancel_launcher_update()
# when the user clicks the cancel button in the download phase. The
# worker polls it inside the download chunk loop and before launching
# the installer. Once the installer is actually running, cancel is a
# no-op (the install can't be cleanly aborted mid-copy).
import threading as _su_threading_root
_launcher_update_cancel = _su_threading_root.Event()

# The self-updater downloads an installer and EXECUTES it, so the URL must be
# HTTPS on a host we control/trust - never a feed-controlled http:// or foreign
# host (MITM / redirect-to-arbitrary-installer on an unsigned exe = RCE).
_TRUSTED_UPDATE_HOSTS = (
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "hebrew-translation-hub.com",
)


def _is_trusted_update_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        u = urlparse(url)
        if u.scheme != "https":
            return False
        host = (u.hostname or "").lower()
        return any(host == h or host.endswith("." + h) for h in _TRUSTED_UPDATE_HOSTS)
    except Exception:
        return False


def _ping_install() -> None:
    """Fire-and-forget anonymous install ping → the /api/launcher feed logs a
    stable per-install id so we can count ACTIVE installs (incl. signed-out
    users). The id is a random uuid (no PII); no IP is stored server-side.
    Best-effort: never raises, never blocks boot."""
    try:
        dev = _auth.device_id() if (_auth_available and _auth) else ""
        if not dev:
            return
        requests.get(
            REMOTE_LAUNCHER_URL,
            params={
                "device": dev,
                "v":      LAUNCHER_VERSION,
                "ch":     LAUNCHER_CHANNEL,
                "b":      BUILD_ID,
                "os":     sys.platform,
            },
            timeout=REMOTE_TIMEOUT,
        )
    except Exception:                                    # pragma: no cover - network
        pass


def _run_launcher_update() -> None:
    """Background worker: download installer → verify SHA-256 → run it
    silently. Streams progress back through launcher_update_progress.
    Cancellable up to the moment the installer process is launched."""
    import hashlib
    import tempfile
    import time

    info = get_launcher_update_info()
    url = info.get("downloadUrl")
    if not url:
        _emit_update_progress("error", 0, info.get("error") or "אין קישור הורדה זמין")
        return
    # Security: the downloaded file is executed as an installer - reject any
    # non-HTTPS / non-allowlisted URL before touching the network.
    if not _is_trusted_update_url(url):
        _emit_update_progress(
            "error", 0,
            "כתובת ההורדה אינה מאובטחת (נדרש https מהמקור הרשמי). העדכון בוטל.")
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
                    if _launcher_update_cancel.is_set():
                        # Best-effort: drop the partial file so a retry
                        # starts clean and doesn't misreport progress %.
                        try: installer.unlink(missing_ok=True)
                        except OSError: pass
                        _emit_update_progress("cancelled", 0, "ההורדה בוטלה")
                        return
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

    if _launcher_update_cancel.is_set():
        try: installer.unlink(missing_ok=True)
        except OSError: pass
        _emit_update_progress("cancelled", 0, "בוטל")
        return

    # ── Verify SHA-256 (MANDATORY - the installer is executed next) ──
    # No hash from the feed → refuse to run an unverified installer.
    if not expected_sha:
        try: installer.unlink(missing_ok=True)
        except OSError: pass
        _emit_update_progress(
            "error", 0,
            "העדכון בוטל - השרת לא סיפק חתימת אימות (SHA-256) לקובץ.")
        return
    try:
        _emit_update_progress("verify", 0, "מאמת את תקינות הקובץ…")
        h = hashlib.sha256()
        with open(installer, "rb") as fh:
            for blk in iter(lambda: fh.read(1048576), b""):
                h.update(blk)
        if h.hexdigest().lower() != expected_sha:
            try: installer.unlink(missing_ok=True)
            except OSError: pass
            _emit_update_progress(
                "error", 0,
                "אימות הקובץ נכשל - ההורדה כנראה פגומה או שונתה. נסה שוב.",
            )
            return
        _emit_update_progress("verify", 100, "הקובץ אומת בהצלחה")
    except Exception as e:
        _emit_update_progress("error", 0, f"שגיאת אימות: {e}")
        return

    if _launcher_update_cancel.is_set():
        try: installer.unlink(missing_ok=True)
        except OSError: pass
        _emit_update_progress("cancelled", 0, "בוטל")
        return

    # ── Run the installer via a detached VBScript trampoline ───
    # History of attempts that failed identically (Inno log stopped at
    # "Created protected temporary directory", level 3 protected
    # process never started):
    #   1. subprocess.Popen([installer, /VERYSILENT, ...])
    #   2. ShellExecuteExW(runas, SEE_MASK_NOCLOSEPROCESS)
    #   3. ShellExecuteW(runas) + self-exit 3s later, with /SILENT
    # Common factor: in EVERY case the launcher's process tree was
    # still alive when Inno tried to hand off from level 2 SL5 →
    # level 3 protected Setup. RG in enforcing mode appears to
    # silently abort the protected handoff when it can detect ANY
    # surviving relative of the elevation requester. Manual install
    # works because explorer.exe → consent.exe → installer has no
    # lingering relative the installer can stumble across.
    #
    # The trampoline closes this gap: we write a tiny .vbs that
    # waits 2s (giving us time to fully exit) and then runs the
    # installer fresh via WScript.Shell.Run. wscript.exe is used
    # instead of cmd.exe because cmd briefly flashes a console
    # window even under CREATE_NO_WINDOW (Windows allocates a hidden
    # console it sometimes shows for an instant). wscript has NO
    # console at all, so the user sees nothing between clicking
    # "Update" and the installer's own UI appearing.
    #
    # /LOG= removed: writing to a path inside the user-writable temp
    # dir is the prime RG suspect, since RG protects exactly against
    # the parent being able to redirect that path between the
    # CreateFile and the elevated write. Without /LOG Inno still
    # logs to its default secure location if anything goes wrong.
    import logging as _logging
    import os as _os
    import subprocess as _subprocess
    import threading as _threading

    _su_log = _logging.getLogger("launcher")

    # Trampoline VBS. WScript.Shell.Run's third arg `False` means
    # "don't wait" → the script exits immediately after spawning the
    # installer. The installer's parent is the (now-dead) wscript,
    # which makes Windows reparent it to a system process - exactly
    # the relationship Inno's RG requires for the protected handoff.
    # VBS strings need doubled quotes around paths containing spaces;
    # our temp path has none, but doubling defends future-proofs.
    script_path = dest_dir / "run-update.vbs"
    installer_esc = str(installer).replace('"', '""')
    script = (
        "' Auto-generated by Translation Manager self-updater. Safe to delete.\r\n"
        "Option Explicit\r\n"
        "WScript.Sleep 2000\r\n"
        "Dim shell\r\n"
        "Set shell = CreateObject(\"WScript.Shell\")\r\n"
        f"shell.Run \"\"\"{installer_esc}\"\"\" & \" /SILENT /SUPPRESSMSGBOXES /NORESTART\", 1, False\r\n"
    )
    try:
        # VBScript reads as ANSI by default. A UTF-8 BOM (EF BB BF) at
        # the start of the file makes wscript fail with error 800A0408
        # ("invalid character") at line 1 char 1 - that's not a comment
        # to VBScript, it's a tokenizer error. Our script body is pure
        # ASCII (no Hebrew in the script itself), so write as bytes
        # with NO BOM and no encoding declaration.
        script_path.write_bytes(script.encode("ascii"))
    except OSError as e:
        _su_log.error("[self-update] failed to write trampoline vbs: %s", e)
        _emit_update_progress("error", 0, f"לא ניתן ליצור סקריפט עדכון: {e}")
        return

    _emit_update_progress(
        "launch", 100,
        "מריץ את ההתקנה - האפליקציה תיסגר ותיפתח מחדש בגרסה החדשה…",
    )

    DETACHED_PROCESS         = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW         = 0x08000000

    _su_log.info("[self-update] launching VBS trampoline %s", script_path)
    try:
        _subprocess.Popen(
            ["wscript.exe", str(script_path)],
            creationflags=(DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW),
            close_fds=True,
            cwd=str(dest_dir),
        )
    except OSError as e:
        _su_log.error("[self-update] failed to spawn trampoline: %s", e)
        _emit_update_progress("error", 0, f"כשל בהפעלת סקריפט עדכון: {e}")
        return

    _su_log.info("[self-update] trampoline scheduled; self-exiting in 1s")

    # Brief delay so the trampoline cmd's CreateProcess fully detaches
    # before our process dies (otherwise on rare timing the child can
    # inherit a dying parent state). 1 s is plenty; the trampoline's
    # own `timeout /t 2` waits another second after we're gone before
    # actually launching the installer.
    def _self_exit() -> None:
        try:
            time.sleep(1.0)
            _su_log.info("[self-update] self-exiting so installer can take over")
            _os._exit(0)
        except BaseException:                                  # noqa: BLE001
            pass
    _threading.Thread(target=_self_exit, daemon=True).start()


@eel.expose
def start_launcher_update() -> dict:
    """Kick the self-update on a gevent GREENLET so the eel RPC returns at
    once AND progress pushes work - eel.launcher_update_progress(...)()
    is bound to the main gevent hub; firing it from a separate OS thread
    silently drops every tick (that's the exact bug that left the
    download progress bar frozen at 0% for the entire transfer).
    `requests` is monkey-patched (socket/ssl/select) so its blocking
    .read()s cooperatively yield, and the greenlet doesn't pin the hub."""
    import gevent
    _launcher_update_cancel.clear()
    gevent.spawn(_run_launcher_update)
    return {"ok": True}


@eel.expose
def cancel_launcher_update() -> dict:
    """Set the cancel flag; the download loop polls it and aborts at
    the next chunk boundary (≤ 256 KB later). No effect once the
    installer process has already been launched - at that point the
    install is the installer's responsibility, not ours."""
    _launcher_update_cancel.set()
    return {"ok": True}


@eel.expose
def open_folder(path: str) -> dict:
    """Open a folder in Windows Explorer.

    SECURITY: `os.startfile` on a FILE runs it via its default handler (an
    .exe just executes, a .lnk follows its target and executes THAT, etc.) -
    it is not a benign "reveal in Explorer" call for anything but a real
    directory. This is exposed as a cloud-plugin action primitive
    (`plugins.engine`'s `open_folder`/`open_backup_folder`), whose `path`
    argument can originate from a cloud-editable manifest - so without the
    is_dir() check below, a hostile/malformed manifest could turn "open this
    folder" into "run this program", with no code download at all. Every
    real caller in this app only ever passes a directory (game install path,
    downloads/mod-cache folder, the backup destination) - restricting to
    directories costs no legitimate functionality."""
    p = Path(path)
    if not p.is_dir():
        return {"ok": False, "error": "not a directory"}
    try:
        os.startfile(str(p))  # type: ignore[attr-defined]
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}


# ═════════════════════════════════════════════════════════════
# Auth bridge - Supabase OAuth (Google) + DRM ownership check
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
# worker thread, so this doesn't freeze the UI - but we cap the
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
    is the native blocking primitive - `event.wait()` from a greenlet
    halts the entire gevent loop, which means a second Eel call
    (`auth_abort_login`) cannot dispatch until the first returns. The
    user clicks "בטל וחזור" and nothing happens for 180 s. Running the
    blocker in an OS thread and polling cooperatively breaks the
    deadlock - gevent stays alive, the abort bridge fires instantly."""
    if not _auth_available or _auth is None:
        return {"ok": False, "error": f"auth-unavailable: {_auth_error or 'module not loaded'}"}
    _owned_confirmed.clear(); _OWNS_CACHE.clear()   # a NEW sign-in starts with a fresh ownership cache

    # CRITICAL: run the blocking login() inside a GREENLET, not a native
    # OS thread. Eel/bottle_websocket invokes gevent.monkey.patch_all(),
    # which replaces the stdlib socket with a gevent-cooperative one.
    # That patched socket REQUIRES a gevent hub in the current thread to
    # dispatch I/O - the hub only exists on the thread the gevent event
    # loop runs on. Spawning a native threading.Thread moves the
    # subsequent requests.get/post calls off the hub-bearing thread, so
    # the first HTTPS read silently deadlocks (the auth_debug.log gets
    # stuck right between "storing initial tokens" and "fetching user
    # profile", i.e. exactly at the next outbound HTTPS read).
    #
    # gevent.spawn keeps the work in the hub's thread. The Eel handler
    # waits on a gevent.AsyncResult which yields cooperatively, so the
    # websocket loop keeps dispatching other Eel calls (including
    # auth_abort_login) while we wait - same UX guarantees as the
    # threading version was supposed to have, without the deadlock.
    import gevent                                                                 # type: ignore[import-not-found]
    from gevent.event import AsyncResult                                          # type: ignore[import-not-found]

    result_box: AsyncResult = AsyncResult()

    def _worker() -> None:
        try:
            user = _auth.login()
            if isinstance(user, dict) and user.get("mfaRequired"):
                # Account has 2FA - the UI must collect the 6-digit code and
                # call auth_verify_mfa. No session was persisted yet.
                result_box.set({"ok": True, "mfaRequired": True,
                                "factorId": user.get("factorId"),
                                "email":    user.get("email")})
            else:
                result_box.set({"ok": True, "user": user})
        except _auth.AuthError as e:
            result_box.set({"ok": False, "error": str(e)})
        except BaseException as e:                                                # noqa: BLE001
            # BaseException catches KeyboardInterrupt / SystemExit /
            # GreenletExit / etc. so even an exotic crash resolves the
            # AsyncResult - the Eel handler returns a clean error
            # instead of leaving the React Promise unresolved forever.
            result_box.set({
                "ok":    False,
                "error": f'unexpected: {type(e).__name__}: {e}',
            })

    greenlet = gevent.spawn(_worker)

    # Outer safety cap. _auth.login()'s internal timeout is 300 s; this
    # 320 s wrap is belt-and-braces in case something exotic eats both
    # success AND failure paths inside the greenlet. AsyncResult.get
    # yields cooperatively to the gevent hub, so the websocket loop
    # stays responsive - auth_abort_login dispatches normally while we
    # wait, identical UX to a non-blocking handler.
    try:
        return result_box.get(timeout=320.0)
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
def auth_cached_user() -> dict | None:
    """Last-known signed-in identity from the on-disk cache - NO network.
    The Qt bridge falls back to this if a live auth_me() runs too long, so a
    slow network never crashes/signs-out the launcher. None if signed out."""
    if not _auth_available or _auth is None:
        return None
    try:
        return _auth.cached_user()
    except Exception:
        return None


@eel.expose
def auth_logout() -> dict:
    """Local sign-out - clears the OS keyring entry."""
    # Drop the session ownership cache so a DIFFERENT user who signs in next on
    # this running process can't inherit the prior user's confirmed purchases
    # (which would leave a paid title's mod controls wrongly unlocked).
    _owned_confirmed.clear(); _OWNS_CACHE.clear()
    if not _auth_available or _auth is None:
        return {"ok": True}  # already effectively signed out
    try:
        _auth.logout()
        return {"ok": True}
    except Exception as e:  # pragma: no cover
        return {"ok": False, "error": str(e)}


@eel.expose
def auth_consume_takeover() -> bool:
    """One-shot: True iff THIS install was just displaced by a sign-in on
    another device (single-session enforcement), then clears the marker.
    The UI calls this when auth_me() flips to signed-out to decide whether
    to show the 'you signed in from another device' notice."""
    if not _auth_available or _auth is None:
        return False
    try:
        return bool(_auth.consume_takeover())
    except Exception:
        return False


@eel.expose
def auth_owns_game(game_id: str) -> bool:
    """DRM check - fails closed on any error.

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
def report_crash(error_type: str, message: str, traceback_: str = "",
                 screen: str = "") -> bool:
    """Frontend → backend crash bridge. The React ErrorBoundary + global
    error listeners call this so a UI crash is reported through the SAME
    PII-scrubbing + opt-in path as Python crashes. Fire-and-forget."""
    try:
        _crash.report(error_type or "FrontendError", message or "",
                      traceback_ or "", screen=screen or None)
        return True
    except Exception:
        return False


@eel.expose
def get_crash_opt_in() -> bool:
    """Whether crash reporting is enabled (default True)."""
    try:
        return _crash.is_enabled()
    except Exception:
        return True


@eel.expose
def set_crash_opt_in(enabled: bool) -> bool:
    """Toggle crash reporting (Settings checkbox)."""
    try:
        return _crash.set_enabled(bool(enabled))
    except Exception:
        return False


@eel.expose
def auth_get_authorize_url() -> str | None:
    """Return the URL of the in-flight Google OAuth attempt so the
    AuthModal can offer a "copy link" affordance - useful when the OS
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
    UI - the Python loopback HTTP server keeps blocking in
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


# Email/password bridges - keep the entire credential flow inside the
# launcher UI without bouncing through the system browser. Tokens land
# in the OS keyring the same way as the OAuth flow, so me() / owns_game
# / sign-out are agnostic about which entry point was used.

@eel.expose
def auth_signin_password(email: str, password: str) -> dict:
    if not _auth_available or _auth is None:
        return {"ok": False, "error": f"auth-unavailable: {_auth_error or 'module not loaded'}"}
    if not email or not password:
        return {"ok": False, "error": "missing-credentials"}
    _owned_confirmed.clear(); _OWNS_CACHE.clear()   # a NEW sign-in starts with a fresh ownership cache
    try:
        result = _auth.signin_with_password(str(email), str(password))
        if isinstance(result, dict) and result.get("mfaRequired"):
            # Account has 2FA - the UI collects the 6-digit code and calls
            # auth_verify_mfa. No session was persisted yet.
            return {"ok": True, "mfaRequired": True,
                    "factorId": result.get("factorId"),
                    "email":    result.get("email")}
        return {"ok": True, "user": result}
    except _auth.AuthError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:                                                    # pragma: no cover
        return {"ok": False, "error": f"unexpected: {e}"}


@eel.expose
def auth_verify_mfa(code: str) -> dict:
    """Complete a pending two-factor (TOTP) login with the 6-digit code.
    Returns {ok, user} on success, or {ok:False, error} on a wrong/expired
    code. Called by the launcher's MFA code screen after a sign-in that
    returned {mfaRequired:True}."""
    if not _auth_available or _auth is None:
        return {"ok": False, "error": f"auth-unavailable: {_auth_error or 'module not loaded'}"}
    try:
        user = _auth.verify_mfa(str(code or ""))
        return {"ok": True, "user": user}
    except _auth.AuthError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:                                                    # pragma: no cover
        return {"ok": False, "error": f"unexpected: {e}"}


@eel.expose
def auth_cancel_mfa() -> dict:
    """Abandon a pending TOTP challenge (user closed the code screen). The
    in-memory aal1 session is discarded - nothing was persisted."""
    if not _auth_available or _auth is None:
        return {"ok": True}
    try:
        _auth.cancel_mfa()
    except Exception:
        pass
    return {"ok": True}


def _win_set_clipboard(text: str) -> bool:
    """Write `text` to the Windows clipboard via raw Win32 (ctypes) - the most
    reliable path, independent of Qt/QtWebEngine (which BLOCKS JS clipboard) and
    of the browser sandbox. Used by BOTH builds' copy_to_clipboard. Returns True
    on success. Safe to call from the GUI thread / a gevent greenlet."""
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        from ctypes import wintypes
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE  = 0x0002
        k32 = ctypes.windll.kernel32
        u32 = ctypes.windll.user32
        # CRITICAL: declare argtypes/restype so 64-bit HANDLEs are NOT truncated
        # to 32-bit ints (the default when argtypes are unset) - truncation makes
        # SetClipboardData silently fail and nothing lands on the clipboard.
        k32.GlobalAlloc.argtypes  = [wintypes.UINT, ctypes.c_size_t]
        k32.GlobalAlloc.restype   = wintypes.HGLOBAL
        k32.GlobalLock.argtypes   = [wintypes.HGLOBAL]
        k32.GlobalLock.restype    = wintypes.LPVOID
        k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        k32.GlobalFree.argtypes   = [wintypes.HGLOBAL]
        k32.GlobalFree.restype    = wintypes.HGLOBAL
        u32.OpenClipboard.argtypes  = [wintypes.HWND]
        u32.OpenClipboard.restype   = wintypes.BOOL
        u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        u32.SetClipboardData.restype  = wintypes.HANDLE
        data = (text or '').encode('utf-16-le') + b'\x00\x00'
        # OpenClipboard can fail transiently when another process (or Qt's own
        # clipboard integration) briefly holds the clipboard - retry a few times
        # before giving up. This is the standard Windows robustness pattern and
        # is the likely reason a single-shot setText "silently didn't copy".
        opened = False
        for _ in range(20):
            if u32.OpenClipboard(None):
                opened = True
                break
            import time as _t
            _t.sleep(0.01)
        if not opened:
            return False
        try:
            u32.EmptyClipboard()
            h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not h:
                return False
            ptr = k32.GlobalLock(h)
            if not ptr:
                k32.GlobalFree(h)
                return False
            ctypes.memmove(ptr, data, len(data))
            k32.GlobalUnlock(h)
            if not u32.SetClipboardData(CF_UNICODETEXT, h):
                k32.GlobalFree(h)   # ownership stays with us on failure
                return False
            return True             # on success the OS owns the handle
        finally:
            u32.CloseClipboard()
    except Exception:
        return False


@eel.expose
def copy_to_clipboard(text: str) -> bool:
    # Bulletproof native copy via raw Win32 (works in BOTH builds; QtWebEngine
    # blocks JS clipboard and the Eel Chrome sandbox can too). Returns True on
    # success so the UI flashes "copied" without needing a JS fallback.
    ok = _win_set_clipboard(text)
    try:
        import logging as _lg
        _lg.getLogger("launcher").info("copy_to_clipboard: len=%d ok=%s", len(text or ''), ok)
    except Exception:
        pass
    return ok


@eel.expose
def js_log(message: str) -> None:
    """Write a JS-side console.log line to launcher.log so the user can
    read it via `type %USERPROFILE%\\.translation_manager\\launcher.log`.
    Needed because frontend/src/main.tsx disables the right-click
    context menu globally, blocking DevTools entry in production builds."""
    try:
        import logging
        logging.getLogger("js_console").info(message)
    except Exception:
        pass


@eel.expose
def auth_get_access_token() -> str | None:
    """Current Supabase access token (refreshes on expiry; None when
    signed out). Surfaced for the launcher's in-window PayPal Smart
    Buttons - createOrder + capture-order both need a Bearer token to
    authenticate against the website's /api/paypal endpoints."""
    if not _auth_available or _auth is None:
        return None
    try:
        return _auth.get_access_token()
    except Exception:
        return None


@eel.expose
def auth_signup_password(email: str, password: str, full_name: str = "") -> dict:
    if not _auth_available or _auth is None:
        return {"ok": False, "error": f"auth-unavailable: {_auth_error or 'module not loaded'}"}
    _owned_confirmed.clear(); _OWNS_CACHE.clear()   # a NEW sign-up starts with a fresh ownership cache
    if not email or not password:
        return {"ok": False, "error": "missing-credentials"}
    try:
        user = _auth.signup_with_password(str(email), str(password), str(full_name or ""))
        # `confirmed=True` means a session was returned and stored; the
        # UI should treat it like a successful sign-in. `False` means
        # the project requires email confirmation - UI shows "check
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
# timer - so without this greenlet the launcher UI only updated when the
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
#      path as the tray menu's "Open" item - `tray._relaunch_self()`
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
    itself visibly. Best-effort - failures are swallowed because we're
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
    """Eel close_callback - fires the moment the Chromium window dies.

    Behaviour now depends on the user's persisted close preference:

      - "minimize" → the tray icon is already running; we do NOT exit.
                     eel.start() returns to main(), which then parks
                     the process until the tray's "Open" menu spawns
                     a fresh launcher instance.
      - "close" or unset → os._exit(0), same as before.

    We can't actually show a React modal HERE - by the time this fires
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
    log.info("window closed - close_behavior=%r", pref)
    if pref == "minimize":
        log.info("close=minimize → process kept alive")
        print("[eel] Window closed → minimised to tray (process stays alive).", flush=True)
        return
    log.info("close=%r → os._exit(0)", pref)
    print("[eel] Window closed - exiting.", flush=True)
    os._exit(0)


def _setup_file_logging() -> None:
    """Route Python logging to ~/.translation_manager/launcher.log.

    The frozen build runs console=False, so without a file handler every
    log line - tray failures, the close-behavior decision, eel.start
    teardown - is lost. With it, a misbehaving close-to-tray leaves a
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
                    help="Skip frontend serving - assume Vite dev server on :5173")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--silent", action="store_true",
                    help="Boot hidden in the system tray (no Chromium window). "
                         "Used by the autostart Run-key entry when the app launches at "
                         "Windows logon - user explicitly opts in via the settings toggle.")
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
        # Cold start (genuine fresh boot, NOT a tray restore) - force a
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
        print("[boot] Another launcher instance is running - signalling it to show.", flush=True)
        _signal_show_to_existing_instance()
        sys.exit(0)
    _start_show_event_listener()

    # Anonymous install ping (active-install counting). Off the boot thread so
    # a slow/offline network never delays the first paint. Only the real
    # running instance reaches here - a single-instance re-signal already
    # exited above, so this never double-counts a tray restore.
    try:
        import threading
        threading.Thread(target=_ping_install, name="install-ping", daemon=True).start()
    except Exception:                                            # noqa: BLE001
        pass

    # Tray icon - always spawn it, regardless of how main() reaches eel.start.
    # The tray is the lifeline for both --silent boots (no main window at
    # all) and minimize-to-tray (window closes, tray stays).
    from translation_manager import tray as _tray
    _tray_ok = _tray.start(title="Translation Manager")
    _log.info("tray.start() returned %r", _tray_ok)

    # game_detector seeds its cache from disk at import time (no work to do
    # here). We deliberately do NOT run an automatic scan on boot - the user
    # owns scanning via the explicit "Full Drive Scan" button.

    if not _has_any_cache() and not _ping_api():
        _show_no_internet_dialog()
        sys.exit(1)

    # --silent boot (Windows autostart). No Chromium window opens - the
    # process sits with just the tray icon until the user double-clicks
    # it. The tray callback relaunches us WITHOUT --silent so the second
    # run opens normally.
    if args.silent:
        print("[boot] --silent - tray-only mode, no main window.", flush=True)
        import time
        while True:
            time.sleep(3600)

    # Idle live-refresh - runs on the gevent hub once eel.start() spins it
    # up. Spawned here (after the --silent early-return) so it only exists
    # for a real window session.
    _start_catalog_poller()

    if args.dev:
        # Vite dev mode - Eel only serves /eel.js + JSON-RPC; the React app
        # runs on http://localhost:5173 with `npm run dev`.
        eel.init(str(FRONTEND_DIST if FRONTEND_DIST.exists() else ROOT / "frontend"))
        print(f"[eel] DEV mode - Vite frontend at http://localhost:5173, "
              f"Eel API on :{args.port}")
        try:
            eel.start({"port": 5173}, mode=None, host="localhost", port=args.port,
                      block=True, suppress_error=True,
                      close_callback=_on_window_closed)
        except (SystemExit, KeyboardInterrupt):
            pass
        except Exception:
            # Any other eel teardown error must NOT crash main() - fall
            # through to the park check so close-to-tray still works.
            _log.exception("eel.start() raised")
    else:
        if not FRONTEND_DIST.exists():
            print(f"[eel] frontend/dist/ not built. Run: cd frontend && npm run build")
            sys.exit(2)
        eel.init(str(FRONTEND_DIST))
        print(f"[eel] PROD mode - serving {FRONTEND_DIST}")
        # Hardening flags so the Chrome --app window doesn't feel like a browser:
        #   --disable-features=Translate,TranslateUI  : kill the "translate this page" bar
        #   --no-first-run / --no-default-browser-check : silence Chromium nags
        #   --disable-pinch                            : laptop trackpads can't pinch-zoom
        #   --overscroll-history-navigation=0          : no back/forward swipe gesture
        #   --disable-background-mode                  : Chrome doesn't linger after close
        #   --disable-features=AutofillServerCommunication : no autofill chatter
        # (`--disable-context-menu` is not a real Chromium flag - the React
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
            # Any other eel teardown error must NOT crash main() - fall
            # through to the park check so close-to-tray still works.
            _log.exception("eel.start() raised")

    # Reached when eel.start() returns (the window closed and the eel
    # server stopped). If the user picked "minimize to tray" we park the
    # process here so the tray icon stays alive; otherwise main() returns
    # and the process exits.
    from translation_manager import launcher_prefs
    _behavior = launcher_prefs.get_close_behavior()
    _log.info("eel.start() returned - close_behavior=%r", _behavior)
    if _behavior == "minimize":
        _log.info("parking process in tray (close-to-tray)")
        print("[boot] Parked in tray after window close.", flush=True)
        import time
        while True:
            time.sleep(3600)
    _log.info("main() returning - process will exit")



# ─────────────────────────────────────────────────────────────
# Headless entry points for the Big Launch console (see main_qt._mod_cli).
#
# These deliberately reuse the SAME worker functions the GUI runs, called
# synchronously instead of spawned: the console is a front-end, so an install
# started there must take the identical path - the same backups, the same
# game-update checks, the same DRM gate - as one started from the desktop app.
# Anything else would be a second implementation that drifts.

# game id -> (install worker, remove callable). A game absent from this map is a
# generic download-mod and goes through _run_game_mod_install / disable, which
# already handle any slug from the catalog.
def _native_mod_actions() -> dict:
    return {
        _SM2_ID:  (_run_sm2_install,  remove_spiderman2_mod),
        _WD2_ID:  (_run_wd2_install,  remove_watchdogs2_mod),
        _GOWR_ID: (_run_gowr_install, remove_gowr_mod),
        _HL_ID:   (_run_hl_install,   remove_hogwarts_mod),
        _W3_ID:   (_run_w3_install,   remove_witcher3_mod),
        _PT_ID:   (_run_pt_install,   remove_plaguetale_mod),
        _GTAV_ID: (_run_gtav_install, _run_gtav_remove),
        _VDJ_ID:  (_run_vdj_install,  clear_virtualdj_mod_cache),
        _BG_ID:   (_run_bg_install,   clear_borderless_gaming_mod_cache),
        _SRGB_ID: (_run_srgb_install, clear_signalrgb_mod_cache),
    }


def cli_install_mod(game_id: str) -> dict:
    """Install a translation, synchronously, for the headless CLI."""
    try:
        native = _native_mod_actions().get(game_id)
        if native is not None:
            native[0]()                       # streams its own progress ticks
        else:
            _run_game_mod_install(game_id)
        st = get_game_mod_state(game_id)
        ok = bool(st.get("installed"))
        return {"ok": ok, "state": st,
                "message": "התרגום הותקן" if ok else "ההתקנה לא הושלמה"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


def cli_remove_mod(game_id: str) -> dict:
    """Remove a translation, synchronously, for the headless CLI."""
    try:
        native = _native_mod_actions().get(game_id)
        if native is not None:
            r = native[1]()
            r = r if isinstance(r, dict) else {"ok": True}
        else:
            r = set_game_mod_installed(game_id, False)
        st = get_game_mod_state(game_id)
        ok = bool(r.get("ok", True)) and not st.get("installed")
        return {"ok": ok, "state": st,
                "message": "התרגום הוסר" if ok else r.get("error", "ההסרה לא הושלמה")}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


if __name__ == "__main__":
    main()
