#!/usr/bin/env python3
"""
build_offline_bundle.py - build an OFFLINE package (run this ONLINE).

Why this exists: a static "fat installer" would have to be rebuilt and
re-published every time ANY mod gets a new version. Instead this tool is run
on demand while online: you tick the games you want, it pulls the CURRENT
versions straight from the same SHA-verified sources the launcher uses, and
writes a store you carry to the offline machine.

    python tools/build_offline_bundle.py                 # interactive picker
    python tools/build_offline_bundle.py --all           # everything
    python tools/build_offline_bundle.py --games cyberpunk,gowragnarok
    python tools/build_offline_bundle.py --all --zip     # + one carry file

Output (consumed by translation_manager/offline_bundle.py):

    <out>/manifest.json
    <out>/mods/<game_id>/<archive>.zip     # EXACT Worker archive, sha-verified
    <out>/images/<rest>                    # covers/banners/logos
    <out>/catalog.json                     # /api/games + /api/config + /api/launcher

The store NEVER contains anything that writes into a game folder - applying a
mod stays the launcher's job (backup → apply → revert). This tool only removes
the DOWNLOAD step.

INTEGRITY: each archive's SHA-256 is recorded from the Worker manifest and
verified here at build time; the launcher re-verifies it at USE time, so a
store tampered with in transit is refused rather than applied.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.parse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import requests
except ImportError:                                     # pragma: no cover
    sys.exit("requests is required:  pip install requests")

from translation_manager import mod_source                  # noqa: E402
from translation_manager.config import GAMES as GAME_CONFIGS  # noqa: E402

API_BASE = "https://hebrew-translation-hub.com"
COVERS_BASE = ("https://mfudkftrluabqlrpkvtj.supabase.co"
               "/storage/v1/object/public/covers")

# NATIVE appliers (no GameConfig.mod_slug) that fetch their payload from the
# Worker. KEEP IN SYNC with the _*_SLUG constants in main_eel.py. Nothing is
# bundled inside the installer any more, so EVERY native game must be listed
# here or an offline machine cannot install it at all.
NATIVE_SLUGS = {
    "gtav":                 "gtav-hebrew",
    "spiderman2":           "spiderman2-hebrew",
    "watchdogs2":           "watchdogs2-hebrew",
    "gowragnarok":          "godofwar-ragnarok-hebrew",
    "hogwarts":             "hogwarts-legacy-hebrew",
    "witcher3":             "witcher3-hebrew",
    "plague-tale-requiem":  "plague-tale-requiem-hebrew",
    "virtualdj":            "virtualdj-hebrew",
}

FORMAT_VERSION = 1


def _human(n: int) -> str:
    f = float(n)
    for u in ("B", "KB", "MB", "GB"):
        if f < 1024 or u == "GB":
            return f"{f:,.1f} {u}" if u != "B" else f"{int(f)} B"
        f /= 1024
    return f"{f:.1f} GB"


# ── catalog ───────────────────────────────────────────────────
def fetch_json(url: str, timeout: float = 20.0):
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def load_catalog() -> tuple[list, dict, dict]:
    print("→ מושך קטלוג חי …")
    games = fetch_json(f"{API_BASE}/api/games")
    if isinstance(games, dict):
        games = games.get("games") or []
    try:
        cfg = fetch_json(f"{API_BASE}/api/config")
    except Exception as e:
        print(f"  ! /api/config נכשל ({e}) - ממשיך בלעדיו")
        cfg = {}
    try:
        launcher = fetch_json(f"{API_BASE}/api/launcher")
    except Exception as e:
        print(f"  ! /api/launcher נכשל ({e}) - ממשיך בלעדיו")
        launcher = {}
    return (games if isinstance(games, list) else []), (cfg or {}), (launcher or {})


def slug_for(game_id: str) -> str | None:
    """The Worker slug that serves this game's mod (download OR native)."""
    for cfg in GAME_CONFIGS.values():
        if getattr(cfg, "internal_id", None) == game_id and getattr(cfg, "mod_slug", ""):
            return cfg.mod_slug
    return NATIVE_SLUGS.get(game_id)


def kind_for(game_id: str) -> str:
    for cfg in GAME_CONFIGS.values():
        if getattr(cfg, "internal_id", None) == game_id and getattr(cfg, "mod_slug", ""):
            return "download"
    return "native"


def downloadable(games: list) -> list[dict]:
    """Catalog rows that actually have a mod we can pre-download."""
    out = []
    for g in games:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        if not gid or not slug_for(gid):
            continue
        out.append(g)
    out.sort(key=lambda g: (g.get("titleEn") or g.get("id") or "").lower())
    return out


# ── selection ─────────────────────────────────────────────────
def pick_games(rows: list[dict]) -> list[dict]:
    """Interactive checklist so the user only carries what they need."""
    print("\n  משחקים/תוכנות עם תרגום זמין להורדה:\n")
    for i, g in enumerate(rows, 1):
        title = g.get("titleEn") or g.get("id")
        he    = g.get("titleHe") or ""
        ver   = g.get("version") or "?"
        price = g.get("priceCents") or 0
        tag   = "בתשלום" if price else "חינם"
        print(f"   [{i:>2}] {title:<38} {he:<22} v{ver:<16} {tag}")
    print("\n  בחר מספרים מופרדים בפסיק (למשל: 1,3,5), 'all' לכולם, ריק לביטול.")
    try:
        raw = input("  בחירה: ").strip()
    except (EOFError, KeyboardInterrupt):
        return []
    if not raw:
        return []
    if raw.lower() in ("all", "הכל", "*"):
        return rows
    sel: list[dict] = []
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        try:
            idx = int(part)
        except ValueError:
            print(f"  ! מתעלם מקלט לא חוקי: {part!r}")
            continue
        if 1 <= idx <= len(rows):
            sel.append(rows[idx - 1])
        else:
            print(f"  ! מחוץ לטווח: {idx}")
    # dedupe, keep order
    seen, out = set(), []
    for g in sel:
        if g["id"] not in seen:
            seen.add(g["id"]); out.append(g)
    return out


# ── mods ──────────────────────────────────────────────────────
def fetch_mod(game_id: str, slug: str, out_dir: Path) -> dict | None:
    """Download + SHA-verify one mod archive into the store."""
    try:
        man = mod_source.fetch_manifest(slug=slug)
    except Exception as e:
        print(f"  ✗ {game_id}: manifest נכשל ({e})")
        return None
    version = man.get("version") or ""
    sha     = (man.get("sha256") or "").lower()
    name    = man.get("archive_name") or f"{slug}.zip"
    if not sha:
        print(f"  ✗ {game_id}: ל-manifest אין sha256 - מדלג (לא נארוז payload לא מאומת)")
        return None

    dest_dir = out_dir / "mods" / game_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name

    last = [0.0]

    def cb(phase: str, pct: float, detail: str) -> None:
        if phase == "download" and pct - last[0] >= 10:
            last[0] = pct
            print(f"     {pct:5.1f}%  {detail}")

    try:
        mod_source.download_archive(dest, cb, slug=slug)
        mod_source.verify(dest, sha, cb)                # build-time integrity gate
    except Exception as e:
        print(f"  ✗ {game_id}: הורדה/אימות נכשלו ({e})")
        dest.unlink(missing_ok=True)
        return None

    size = dest.stat().st_size
    print(f"  ✓ {game_id}  v{version}  {_human(size)}  sha {sha[:12]}…")
    return {"version": version, "archive": name, "sha256": sha,
            "kind": kind_for(game_id), "slug": slug, "size": size}


# ── images ────────────────────────────────────────────────────
def image_rel(url: str | None, game_id: str | None = None) -> str | None:
    """Bucket-relative path for a cover/banner/logo URL (mirrors coverUrl.ts).

    Keeps the sub-path (banners/… , logos/…) because a cover and its banner
    share the SAME basename - flattening them would collide.
    """
    if not url:
        return None
    if "/public/covers/" in url:
        rel = url.split("/public/covers/", 1)[1]
    elif url.startswith("http://") or url.startswith("https://"):
        return None                                     # foreign host - skip
    elif url.startswith("/"):
        return None                                     # site-relative - skip
    else:
        rel = url.replace("covers/", "", 1)             # bare filename
    rel = urllib.parse.unquote(rel).split("?")[0].strip("/")
    if not rel or ".." in rel.split("/"):
        return None
    return rel


def fetch_images(rows: list[dict], out_dir: Path) -> list[str]:
    """Mirror each selected game's cover/banner/logo into the store."""
    wanted: dict[str, str] = {}                          # rel → url
    for g in rows:
        gid = g.get("id")
        for field in ("cover", "bannerUrl", "logoUrl"):
            url = g.get(field)
            rel = image_rel(url, gid)
            if rel:
                wanted[rel] = url if url.startswith("http") else f"{COVERS_BASE}/{rel}"
        if not g.get("cover") and gid:                   # convention fallback
            wanted.setdefault(f"{gid}.webp", f"{COVERS_BASE}/{gid}.webp")

    got: list[str] = []
    img_root = out_dir / "images"
    for rel, url in sorted(wanted.items()):
        dest = img_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = requests.get(url, timeout=30)
            if not r.ok or not r.content:
                continue
            dest.write_bytes(r.content)
            got.append(rel)
        except Exception:
            continue
    print(f"  ✓ תמונות: {len(got)}/{len(wanted)}")
    return got


# ── main ──────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="בניית חבילת אופליין (להרצה עם אינטרנט)")
    ap.add_argument("--out", default=str(ROOT / "Output" / "offline_bundle"),
                    help="תיקיית היעד של החבילה")
    ap.add_argument("--games", default="", help="מזהים מופרדים בפסיק (במקום בחירה אינטראקטיבית)")
    ap.add_argument("--all", action="store_true", help="כל המשחקים עם תרגום")
    ap.add_argument("--no-images", action="store_true", help="בלי כריכות/באנרים")
    ap.add_argument("--zip", action="store_true", help="לארוז לקובץ אחד לנשיאה")
    a = ap.parse_args()

    try:
        games, cfg, launcher = load_catalog()
    except Exception as e:
        return int(bool(print(f"✗ לא ניתן למשוך את הקטלוג: {e}"))) or 2
    rows = downloadable(games)
    if not rows:
        print("✗ לא נמצאו משחקים עם תרגום להורדה")
        return 2

    if a.all:
        sel = rows
    elif a.games:
        want = {s.strip() for s in a.games.split(",") if s.strip()}
        sel  = [g for g in rows if g.get("id") in want]
        missing = want - {g.get("id") for g in sel}
        for m in missing:
            print(f"  ! אין תרגום להורדה עבור {m!r} - מדלג")
    else:
        sel = pick_games(rows)
    if not sel:
        print("בוטל - לא נבחר דבר.")
        return 1

    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n→ אורז {len(sel)} פריטים ל-{out}\n")
    entries: dict[str, dict] = {}
    for g in sel:
        gid  = g["id"]
        slug = slug_for(gid)
        if not slug:
            continue
        e = fetch_mod(gid, slug, out)
        if e:
            entries[gid] = e

    if not entries:
        print("\n✗ שום מוד לא נארז - החבילה לא נוצרה")
        shutil.rmtree(out, ignore_errors=True)
        return 3

    images = [] if a.no_images else fetch_images(
        [g for g in sel if g.get("id") in entries], out)

    (out / "catalog.json").write_text(json.dumps(
        {"games": games, "config": (cfg.get("config") if isinstance(cfg, dict) and
                                    isinstance(cfg.get("config"), dict) else cfg),
         "launcher": launcher, "takenAt": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                        time.gmtime())},
        ensure_ascii=False), encoding="utf-8")

    manifest = {
        "formatVersion": FORMAT_VERSION,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "games": {k: {kk: vv for kk, vv in v.items() if kk != "size"}
                  for k, v in entries.items()},
        "images": images,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"\n✓ החבילה מוכנה: {out}")
    print(f"  {len(entries)} מודים · {len(images)} תמונות · סה\"כ {_human(total)}")

    if a.zip:
        zpath = out.with_suffix(".zip")
        zpath.unlink(missing_ok=True)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(out).as_posix())
        print(f"  קובץ נשיאה: {zpath}  ({_human(zpath.stat().st_size)})")

    print("\n  להעברה למחשב אופליין: העתק את התיקייה/קובץ ל-")
    print(r"   %USERPROFILE%\.translation_manager\offline_bundle")
    print("  (או השתמש במתקין האופליין). התוכנה תאמת SHA לכל payload לפני שימוש.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
