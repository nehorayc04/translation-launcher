"""
mod_source.py — fetch + verify the Steam Hebrew translation archive.

Distribution model
------------------
A PRIVATE GitHub repo (`steam-hebrew-mods`) holds each build as a Release
with two assets:
  - `manifest.json`  — {"archive_name", "sha256", "version"}
  - `<archive_name>` — the zipped `steam_hebrew_output/` tree

A Cloudflare Worker proxies all access. The Worker holds the GitHub PAT
as a server-side secret, so **no token ships in the launcher binary**.
The launcher only ever talks to the Worker.

Worker contract (see worker/src/index.js):
  GET  <PROXY_BASE>/steam-hebrew/manifest  -> application/json  (normalized manifest)
  GET  <PROXY_BASE>/steam-hebrew/archive   -> application/zip   (streamed bytes)

Pipeline
--------
fetch_manifest() -> download_archive() -> verify() -> extract().
`fetch_and_extract()` chains all four and returns (extracted_dir, version).
The caller owns cleanup of `extracted_dir.parent` (a temp dir).
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

import requests

# Progress callback: cb(phase, pct, detail)
#   phase  ∈ {"download", "verify", "extract", "apply"}
#   pct    ∈ 0.0 .. 100.0
#   detail — short human string (e.g. "1,204 KB", filename, "OK")
ProgressCB = Callable[[str, float, str], None]

# Cloudflare Worker base URL. The Worker — not the launcher — holds the
# GitHub token. Override via env for staging without a rebuild.
PROXY_BASE = os.environ.get(
    "MOD_PROXY_BASE",
    "https://steam-hebrew-mods.nc52885.workers.dev",
).rstrip("/")

# Default mod slug. The Worker is multi-mod: each slug maps to its own
# private GitHub repo. `steam-hebrew` is the historical default so the
# Steam call sites keep working without change; the Cyberpunk 2077 game
# mod passes `slug="cp2077-hebrew"`.
MOD_SLUG     = "steam-hebrew"
CHUNK        = 256 * 1024          # 256 KB streaming chunks
NET_TIMEOUT  = 60                  # seconds


class ModSourceError(RuntimeError):
    """Network / proxy / manifest-parsing failure."""


class IntegrityError(ModSourceError):
    """Downloaded archive's SHA-256 did not match the manifest."""


def _get(path: str, *, slug: str = MOD_SLUG, **kwargs) -> requests.Response:
    """GET <PROXY_BASE>/<slug>/<path> with uniform error wrapping."""
    url = f"{PROXY_BASE}/{slug}/{path.lstrip('/')}"
    try:
        r = requests.get(url, timeout=NET_TIMEOUT, **kwargs)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        raise ModSourceError(f"proxy request failed ({path}): {e}") from e


def fetch_manifest(*, slug: str = MOD_SLUG) -> dict:
    """Return the latest release's normalized manifest.

    Shape: {"archive_name": str, "sha256": <64 hex>, "version": str}.
    Raises ModSourceError on a malformed payload."""
    try:
        data = _get("manifest", slug=slug).json()
    except ValueError as e:
        raise ModSourceError(f"manifest is not valid JSON: {e}") from e
    for key in ("archive_name", "sha256", "version"):
        if not data.get(key):
            raise ModSourceError(f"manifest missing '{key}'")
    if len(str(data["sha256"])) != 64:
        raise ModSourceError("manifest sha256 is not a 64-char hex digest")
    return data


def download_archive(dest: Path, cb: ProgressCB | None = None,
                     *, slug: str = MOD_SLUG) -> Path:
    """Stream the archive from the Worker into `dest`, reporting % done."""
    with _get("archive", slug=slug, stream=True) as r:
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(CHUNK):
                if not chunk:
                    continue
                f.write(chunk)
                got += len(chunk)
                if cb:
                    pct = (100.0 * got / total) if total else 0.0
                    cb("download", pct, f"{got // 1024:,} KB")
    return dest


def verify(path: Path, expected_sha256: str, cb: ProgressCB | None = None) -> None:
    """Raise IntegrityError unless `path`'s SHA-256 matches the manifest."""
    if cb:
        cb("verify", 0.0, "")
    h = hashlib.sha256()
    size = max(1, path.stat().st_size)
    read = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
            read += len(chunk)
            if cb:
                cb("verify", 100.0 * read / size, "")
    actual = h.hexdigest()
    if actual.lower() != str(expected_sha256).lower():
        raise IntegrityError(
            f"checksum mismatch — got {actual}, manifest says {expected_sha256}"
        )
    if cb:
        cb("verify", 100.0, "OK")


def _is_within(base: Path, target: Path) -> bool:
    """True iff `target` resolves to a path inside `base` — zip-slip guard."""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def extract(archive: Path, out_dir: Path, cb: ProgressCB | None = None) -> Path:
    """Extract `archive` into `out_dir`. Rejects any zip-slip / absolute member."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        members = z.namelist()
        for i, name in enumerate(members):
            # A member like `../../evil` or `C:\evil` would escape out_dir.
            if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                raise ModSourceError(f"unsafe path in archive: {name!r}")
            if not _is_within(out_dir, out_dir / name):
                raise ModSourceError(f"unsafe path in archive: {name!r}")
            z.extract(name, out_dir)
            if cb:
                cb("extract", 100.0 * (i + 1) / max(1, len(members)), name)
    return out_dir


def fetch_and_extract(cb: ProgressCB | None = None,
                      *, slug: str = MOD_SLUG) -> tuple[Path, str]:
    """Full pipeline: manifest -> download -> verify -> extract.

    Returns (extracted_dir, version). `extracted_dir` lives under a fresh
    temp dir; the caller should delete `extracted_dir.parent` when done.
    `slug` selects which mod (Worker route / GitHub repo) to fetch."""
    manifest = fetch_manifest(slug=slug)
    tmp = Path(tempfile.mkdtemp(prefix=f"{slug}_mod_"))
    archive = download_archive(tmp / str(manifest["archive_name"]), cb, slug=slug)
    verify(archive, str(manifest["sha256"]), cb)
    extracted = extract(archive, tmp / "extracted", cb)
    return extracted, str(manifest["version"])
