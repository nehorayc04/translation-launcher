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

import argparse
import os
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


def _load_catalog() -> list[dict]:
    """SWR-cached catalog. On absolute cold start (no disk cache, no
    bundled file, no network) falls back to the dataclasses bundled
    inside the launcher binary itself."""
    data = swr_cache.swr("games", lambda: _try_remote(REMOTE_CATALOG_URL),
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
    bundled_files={
        "games":   LOCAL_CATALOG_FILE,
        "news":    LOCAL_NEWS_FILE,
        "updates": LOCAL_UPDATES_FILE,
    },
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
