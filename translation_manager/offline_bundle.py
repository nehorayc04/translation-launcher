"""
offline_bundle.py - consume a pre-built OFFLINE package.

A machine with no internet still gets the same mods / images / catalog the
online flow would have fetched. The package is produced ONLINE by
`tools/build_offline_bundle.py` (the user ticks which games they want, so it
only carries what they need) and dropped on the offline machine.

Layout (the "store"), default `~/.translation_manager/offline_bundle`:

    manifest.json                  # what's inside + integrity + versions
    mods/<game_id>/<archive>.zip   # the EXACT archive the Worker serves
    images/<rest>                  # covers/banners/logos, mirroring the bucket
    catalog.json                   # /api/games + /api/config + /api/launcher

THE DIVISION OF RESPONSIBILITY (deliberate, do not "optimise" away):
  the bundle/installer NEVER writes into a GAME folder. It only makes the
  DOWNLOAD step unnecessary by pre-seeding the cache. The launcher's own
  appliers still do backup → apply → state → revert exactly as they do online,
  so a mod is always applied by the code that knows how to revert it.

SECURITY: every payload is re-verified against the manifest's SHA-256 at USE
time (not just at build time), so the offline path keeps the SAME integrity
posture as the online one - a tampered store is refused, never applied.

Everything here is read-only w.r.t. the store and never raises: a missing or
corrupt store simply means "no offline bundle" and the caller falls back to its
normal online/bundled path.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# Same home the mod cache uses (game_mod._CACHE_ROOT) so the two ALWAYS agree.
# Deliberately NOT the SHGetKnownFolderPath "real home": consistency with the
# cache the launcher actually reads matters more than the redirected-dev-env
# case, and both resolve identically for a real end user.
_ROOT = Path.home() / ".translation_manager" / "offline_bundle"

MANIFEST_NAME = "manifest.json"
# Bumped only on a breaking store-layout change.
FORMAT_VERSION = 1


# ── store location ────────────────────────────────────────────
def root() -> Path:
    return _ROOT


def manifest_path() -> Path:
    return _ROOT / MANIFEST_NAME


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ── manifest ──────────────────────────────────────────────────
def manifest() -> dict | None:
    """The store manifest, or None when there is no (readable) bundle."""
    try:
        mp = manifest_path()
        if not mp.is_file():
            return None
        data = json.loads(mp.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if int(data.get("formatVersion") or 0) > FORMAT_VERSION:
            log.warning("offline bundle formatVersion %s newer than supported %s",
                        data.get("formatVersion"), FORMAT_VERSION)
            return None
        return data
    except Exception:
        log.debug("offline_bundle.manifest read failed", exc_info=True)
        return None


def is_available() -> bool:
    return manifest() is not None


def info() -> dict:
    """Small summary for the UI / diagnostics. Always a dict."""
    m = manifest()
    if not m:
        return {"available": False, "games": [], "createdAt": None, "images": 0}
    games = m.get("games") if isinstance(m.get("games"), dict) else {}
    imgs = m.get("images") if isinstance(m.get("images"), list) else []
    return {
        "available": True,
        "createdAt": m.get("createdAt"),
        "games": sorted(games.keys()),
        "images": len(imgs),
        "path": str(_ROOT),
    }


# ── per-game payload ──────────────────────────────────────────
def game_entry(game_id: str) -> dict | None:
    """{version, archive, sha256, kind} for a game carried by the bundle."""
    m = manifest()
    if not m:
        return None
    games = m.get("games")
    if not isinstance(games, dict):
        return None
    e = games.get(game_id)
    return e if isinstance(e, dict) else None


def version_for(game_id: str) -> str | None:
    e = game_entry(game_id) or {}
    v = e.get("version")
    return v if isinstance(v, str) and v else None


def archive_path(game_id: str) -> Path | None:
    """The on-disk archive for a game, or None if absent."""
    e = game_entry(game_id)
    if not e:
        return None
    name = e.get("archive")
    if not isinstance(name, str) or not name:
        return None
    p = _ROOT / "mods" / game_id / name
    return p if p.is_file() else None


def verify(game_id: str) -> Path | None:
    """Re-verify the archive's SHA-256 against the manifest and return its path.

    THE security gate of the offline path: a store that was tampered with after
    it was built fails here and is never applied. None on any mismatch/missing.
    """
    e = game_entry(game_id)
    p = archive_path(game_id)
    if not e or p is None:
        return None
    want = (e.get("sha256") or "").lower().strip()
    if not want:
        log.warning("offline bundle: %s has no sha256 - refusing", game_id)
        return None
    try:
        got = _sha256(p)
    except OSError:
        log.debug("offline_bundle.verify read failed for %s", game_id, exc_info=True)
        return None
    if got != want:
        log.warning("offline bundle: %s SHA mismatch (want %s got %s) - refusing",
                    game_id, want[:12], got[:12])
        return None
    return p


def extract(game_id: str, cb=None) -> tuple[Path, str] | None:
    """Verify + extract the bundled archive to a TEMP dir.

    Returns (extracted_dir, version); the CALLER owns cleanup of
    `extracted_dir.parent` - the exact contract of
    `mod_source.fetch_and_extract`, so an offline payload is a drop-in
    replacement for a downloaded one and every per-game `pick()` works
    unchanged. None when unavailable/unverified.
    """
    p = verify(game_id)
    if p is None:
        return None
    version = version_for(game_id) or ""
    tmp = Path(tempfile.mkdtemp(prefix="tm_offline_"))
    try:
        from . import mod_source
        out = mod_source.extract(p, tmp / "x", cb)   # zip-slip guarded there
        return out, version
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        log.debug("offline_bundle.extract failed for %s", game_id, exc_info=True)
        return None


# ── images ────────────────────────────────────────────────────
def images_dir() -> Path:
    return _ROOT / "images"


def image_rels() -> list[str]:
    """The bucket-relative image paths the bundle carries
    (e.g. "cyberpunk.webp", "banners/cyberpunk.webp")."""
    m = manifest()
    if not m:
        return []
    imgs = m.get("images")
    if not isinstance(imgs, list):
        return []
    return [i for i in imgs if isinstance(i, str) and i]


def image_path(rel: str) -> Path | None:
    """Local file for a bucket-relative image path, if the bundle has it."""
    if not rel or ".." in rel.replace("\\", "/").split("/"):
        return None                                   # no traversal
    p = images_dir() / rel
    return p if p.is_file() else None


def images_payload() -> dict:
    """What the FRONTEND needs to serve covers from disk when offline:
    {base: "file:///.../images", rels: [...]}. Empty when no bundle."""
    rels = [r for r in image_rels() if image_path(r) is not None]
    if not rels:
        return {"base": "", "rels": []}
    base = images_dir().resolve().as_uri()             # file:///C:/...
    return {"base": base, "rels": rels}


# ── catalog snapshot ──────────────────────────────────────────
def catalog_snapshot() -> dict | None:
    """The /api/games + /api/config + /api/launcher snapshot taken at build
    time, so an offline machine sees the CURRENT catalog instead of the stale
    catalog compiled into the exe. None when absent/corrupt."""
    try:
        p = _ROOT / "catalog.json"
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        log.debug("offline_bundle.catalog_snapshot failed", exc_info=True)
        return None


def catalog_games() -> list | None:
    snap = catalog_snapshot() or {}
    g = snap.get("games")
    return g if isinstance(g, list) and g else None


def catalog_config() -> dict | None:
    snap = catalog_snapshot() or {}
    c = snap.get("config")
    return c if isinstance(c, dict) and c else None


# ── update comparison (the "עדכון אופליין" signal) ────────────
def offline_update(game_id: str, installed_version: str | None,
                   is_newer) -> dict | None:
    """Does the BUNDLE carry a newer version than what is applied to the game?

    This is a purely LOCAL comparison (no network), which is what makes an
    offline update visible at all - the normal check asks the server and gets
    nothing when there is no internet.

    `is_newer(a, b)` is injected (main_eel._version_is_newer) so version
    ordering stays in ONE place. Returns {version, source:"offline"} or None.
    """
    bv = version_for(game_id)
    if not bv:
        return None
    if installed_version and not _safe_newer(is_newer, bv, installed_version):
        return None
    # EXISTENCE only - deliberately NOT verify(). This runs inside the update
    # CHECK, which is polled and already the slowest path in the app; hashing
    # every bundled archive just to decide whether to show a label would make it
    # far worse. The SHA-256 gate lives in extract(), i.e. immediately before the
    # payload is actually used - which is where integrity has to hold anyway, and
    # a tampered archive is refused there before anything is applied.
    if archive_path(game_id) is None:
        return None
    return {"version": bv, "source": "offline"}


def _safe_newer(is_newer, a: str, b: str) -> bool:
    try:
        return bool(is_newer(a, b))
    except Exception:
        return False


# ── self-test ─────────────────────────────────────────────────
def _selftest() -> bool:                                # pragma: no cover
    """Build a fake store in a temp dir and exercise the whole read path."""
    global _ROOT
    import zipfile
    keep, ok = _ROOT, True
    tmp = Path(tempfile.mkdtemp(prefix="tm_ob_test_"))
    try:
        _ROOT = tmp / "offline_bundle"
        (_ROOT / "mods" / "demo").mkdir(parents=True)
        (_ROOT / "images" / "banners").mkdir(parents=True)
        zp = _ROOT / "mods" / "demo" / "demo.zip"
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("mod/hello.txt", "shalom")
        sha = _sha256(zp)
        (_ROOT / "images" / "demo.webp").write_bytes(b"img")
        (_ROOT / "images" / "banners" / "demo.webp").write_bytes(b"bnr")
        (_ROOT / "catalog.json").write_text(json.dumps(
            {"games": [{"id": "demo"}], "config": {"plugins": []}}), encoding="utf-8")
        (_ROOT / MANIFEST_NAME).write_text(json.dumps({
            "formatVersion": FORMAT_VERSION, "createdAt": "2026-07-18T00:00:00Z",
            "games": {"demo": {"version": "2.0.0", "archive": "demo.zip",
                               "sha256": sha, "kind": "download"}},
            "images": ["demo.webp", "banners/demo.webp"],
        }), encoding="utf-8")

        assert is_available(), "store not detected"
        assert version_for("demo") == "2.0.0"
        assert verify("demo") is not None, "sha verify failed on a good store"
        got = extract("demo")
        assert got is not None, "extract failed"
        ed, ver = got
        assert ver == "2.0.0" and (ed / "mod" / "hello.txt").is_file(), "bad extract"
        shutil.rmtree(ed.parent, ignore_errors=True)

        pay = images_payload()
        assert len(pay["rels"]) == 2 and pay["base"].startswith("file:"), "images payload"
        assert image_path("../secret") is None, "traversal not blocked"
        assert catalog_games() and catalog_config() is not None, "catalog snapshot"

        newer = lambda a, b: a > b                       # noqa: E731 (test stub)
        assert offline_update("demo", "1.0.0", newer) == {"version": "2.0.0",
                                                          "source": "offline"}
        assert offline_update("demo", "2.0.0", newer) is None, "equal → no update"
        assert offline_update("nope", "1.0.0", newer) is None

        # TAMPER: flip a byte → the USE path must refuse. offline_update() is
        # deliberately existence-only (it runs inside the polled update check and
        # must not hash), so it may still show a label - what matters is that
        # nothing tampered can ever be extracted or applied.
        with open(zp, "r+b") as f:
            f.seek(0); f.write(b"\x00")
        assert verify("demo") is None, "tampered archive was NOT refused"
        assert extract("demo") is None, "tampered archive extracted"
        print("offline_bundle selftest: PASS")
    except AssertionError as e:
        print(f"offline_bundle selftest: FAIL - {e}")
        ok = False
    finally:
        _ROOT = keep
        shutil.rmtree(tmp, ignore_errors=True)
    return ok


if __name__ == "__main__":                              # pragma: no cover
    raise SystemExit(0 if _selftest() else 1)
