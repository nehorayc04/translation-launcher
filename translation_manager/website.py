"""
Website integration — serves the local build of the translation hub and
parses src/data/games.ts to feed the launcher's library view.
"""

import os
import re
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from .config import WEBSITE_DIST_DIR, WEBSITE_GAMES_TS, WEBSITE_PROJECT_DIR


# ─────────────────────────────────────────────────────────────
# Local static server (for serving dist/ on a free port)
# ─────────────────────────────────────────────────────────────
_server: HTTPServer | None = None
_server_port: int | None = None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_server(directory: Path, port: int) -> None:
    """Background thread: serve `directory` via HTTPServer."""
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(directory), **kw)
        def log_message(self, *a, **kw):
            pass  # silence per-request logs
    global _server
    _server = HTTPServer(("127.0.0.1", port), Handler)
    _server.serve_forever()


def serve_dist() -> tuple[bool, str]:
    """Start a local server for dist/ and open the browser."""
    global _server, _server_port

    if not WEBSITE_DIST_DIR.exists():
        return False, f"dist not found at {WEBSITE_DIST_DIR}"

    if _server is None:
        _server_port = _free_port()
        thread = threading.Thread(
            target=_run_server,
            args=(WEBSITE_DIST_DIR, _server_port),
            daemon=True,
        )
        thread.start()

    url = f"http://localhost:{_server_port}"
    webbrowser.open(url)
    return True, url


def open_project_folder() -> bool:
    """Open the website source directory in Windows Explorer."""
    if not WEBSITE_PROJECT_DIR.exists():
        return False
    if sys.platform == "win32":
        os.startfile(str(WEBSITE_PROJECT_DIR))   # noqa: S606
    else:
        subprocess.Popen(["xdg-open", str(WEBSITE_PROJECT_DIR)])
    return True


def open_url(url: str) -> None:
    webbrowser.open(url)


# ─────────────────────────────────────────────────────────────
# games.ts parser — extracts featured-game cards for Home view
# ─────────────────────────────────────────────────────────────
_GAME_BLOCK = re.compile(
    r"\{\s*"
    r"id:\s*'(?P<id>[^']+)',\s*"
    r"titleEn:\s*'(?P<titleEn>[^']+)',\s*"
    r"titleHe:\s*'(?P<titleHe>[^']+)',\s*"
    r"version:\s*[\"']?(?P<version>[^,'\"]+)[\"']?,\s*"
    r"versionLabel:\s*'(?P<versionLabel>[^']+)',\s*"
    r"status:\s*'(?P<status>[^']+)',\s*"
    r"cover:\s*(?P<cover>null|'[^']*'),\s*"
    r"themeKey:\s*'(?P<themeKey>[^']+)',\s*"
    r"availability:\s*'(?P<availability>[^']+)',\s*"
    r"(?:progress:\s*(?P<progress>\d+),\s*)?",
    re.DOTALL,
)


def parse_featured_games(limit: int = 8) -> list[dict]:
    """Parse games.ts and return list of game dicts (best-effort)."""
    if not WEBSITE_GAMES_TS.exists():
        return []
    try:
        text = WEBSITE_GAMES_TS.read_text(encoding="utf-8")
    except OSError:
        return []

    results = []
    for m in _GAME_BLOCK.finditer(text):
        d = m.groupdict()
        d["progress"] = int(d["progress"]) if d.get("progress") else None
        results.append(d)
        if len(results) >= limit:
            break
    return results


def shutdown_server() -> None:
    """Stop the background server (called on app exit)."""
    global _server
    if _server is not None:
        _server.shutdown()
        _server = None
