"""pack_and_release.py — package the GTA V (Legacy) Hebrew UI mod + publish a
GitHub Release. Mirrors the SM2/WD2/Anno/CP2077 pack shape.

GTA's mod ships as TWO OpenIV packages (the user installs them via OpenIV, which
provides the mods-folder loader the game needs):
  * gtav_hebrew_UPDATE2.oiv  — installs the Hebrew UI (global.gxt2 superset) into
    the update2 base text layer + the 3 Hebrew Scaleform fonts. Mod-safe (file-level).
  * gtav_restore_UPDATE2.oiv — byte-exact vanilla revert of ONLY the files the mod
    touched (does not delete archives / other mods).

We zip both OIVs + a Hebrew readme, sha-256 it, write manifest.json (Worker-consumed).

Usage: python pack_and_release.py [version] [--pack-only]
`version` defaults to 1.0.0-beta.1. FULL release so `releases/latest` resolves.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/gtav-hebrew-mods"
ARCHIVE_NAME = "gtav_hebrew.zip"
# The LAUNCHER downloads a different asset than the website: it needs the raw
# payload pair (Hebrew + vanilla-English gxt2/fonts) that gtav_mod read-modify-
# writes into the user's mods RPFs, NOT the two OIV packages a manual installer
# feeds to OpenIV. Both ride in the same release; manifest.archive_name points at
# THIS one because the Worker exists to serve the launcher (the website links the
# OIV zip straight from games.download_url).
LAUNCHER_ARCHIVE = "gtav_launcher_payload.zip"
LAUNCHER_PARTS   = ("gtav_he_payload.zip", "gtav_vanilla_payload.zip")

ROOT     = Path(__file__).resolve().parent
REL_DIR  = ROOT / "release"
INSTALL  = REL_DIR / "gtav_hebrew_FULLTEXT.oiv"
RESTORE  = REL_DIR / "gtav_restore_FULLTEXT.oiv"
OUT_DIR  = REL_DIR
# Source of truth for the launcher payloads (also bundled as the offline fallback).
PAYLOAD_SRC = ROOT.parents[1] / "translation_manager" / "assets" / "gtav"

README = """\
תרגום עברי מלא ל-Grand Theft Auto V (Legacy) — ממשק + כתוביות (בטא)
==================================================================

דרישה מוקדמת: OpenIV
--------------------
המוד נטען דרך תיקיית ה-mods של OpenIV (כך GTA קורא קבצים מותאמים בלי לגעת
בקבצי המשחק האמיתיים). התקינו OpenIV מ-https://openiv.com והפעילו את מצב ה-mods
(ASI manager) פעם אחת.

התקנה
-----
1. סגרו את המשחק לחלוטין.
2. ב-OpenIV: Tools -> Package Installer -> בחרו את gtav_hebrew_FULLTEXT.oiv
   -> התקינו אל **תיקיית ה-mods** (mods folder).
3. במשחק: Settings -> Language -> **American (English)**. הטקסט יופיע בעברית.

מה כלול
-------
תרגום מלא לעברית של כל הטקסט במשחק — ממשק (תפריטים, הגדרות, HUD, טלפון, מפה,
תיאורי משימות, חנות, דפדפן פנימי) **וכל כתוביות הדיאלוג והסיפור** + פונטים עבריים.
שמות דמויות/מקומות/רכבים וקודים נשארים באנגלית בכוונה.

שחזור (חזרה לאנגלית)
--------------------
1. סגרו את המשחק.
2. ב-OpenIV: Package Installer -> gtav_restore_FULLTEXT.oiv -> אל תיקיית ה-mods.
   מחזיר byte-exact רק את הקבצים שהמוד שינה; מודים אחרים שלכם לא נפגעים.

הערות
-----
- אם Defender/אנטי-וירוס חוסם — זה false positive (הקבצים הם רק טקסט/פונט).
- המוד לא נוגע בקבצי המשחק האמיתיים, רק בתיקיית ה-mods.
"""


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(256 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    raw = sys.argv[1:]
    pack_only = "--pack-only" in raw
    positional = [a for a in raw if not a.startswith("--")]
    version = positional[0] if positional else "1.0.0-beta.2"
    tag = f"v{version}"

    for p in (INSTALL, RESTORE):
        if not p.is_file():
            print(f"FATAL: missing {p}\n  run work/build_update2_oiv.py first")
            return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    print(f"packing 2 OIVs + readme -> release/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.write(INSTALL, INSTALL.name)
        z.write(RESTORE, RESTORE.name)
        z.writestr("קרא_אותי.txt", README)

    digest = sha256_of(zip_path)

    # ── launcher payload (server-first install, no rebuild per mod version) ──
    missing = [n for n in LAUNCHER_PARTS if not (PAYLOAD_SRC / n).is_file()]
    if missing:
        print(f"FATAL: missing launcher payload(s) in {PAYLOAD_SRC}: {missing}")
        return 1
    lz_path = OUT_DIR / LAUNCHER_ARCHIVE
    print(f"packing {len(LAUNCHER_PARTS)} payloads -> release/{LAUNCHER_ARCHIVE}")
    with zipfile.ZipFile(lz_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for n in LAUNCHER_PARTS:
            z.write(PAYLOAD_SRC / n, n)
    lz_digest = sha256_of(lz_path)

    manifest = {
        "archive_name": LAUNCHER_ARCHIVE,
        "sha256":       lz_digest,
        "version":      version,
        "channel":      "beta",
        "scope":        "full",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nzip      : {zip_path}  ({zip_path.stat().st_size:,} bytes)   [website / OpenIV]")
    print(f"sha256   : {digest}")
    print(f"launcher : {lz_path}  ({lz_path.stat().st_size:,} bytes)   [Worker / launcher]")
    print(f"sha256   : {lz_digest}")
    print(f"version  : {version}  (tag {tag}, FULL release)")

    if pack_only:
        print("\n--pack-only — GitHub release skipped.")
        return 0

    notes = (
        f"Full Hebrew translation (BETA) for Grand Theft Auto V (Legacy) — version {version}.\n\n"
        f"Complete Hebrew for the WHOLE game: interface (menus, settings, HUD, phone, map, "
        f"mission text, store, in-game browser) AND all dialogue/story subtitles + Hebrew "
        f"Scaleform fonts. Names/places/vehicles/codes stay English by design.\n\n"
        f"Requires OpenIV (mods-folder loader). Install `gtav_hebrew_FULLTEXT.oiv` to the mods "
        f"folder, set game Language = American. Revert with `gtav_restore_FULLTEXT.oiv` "
        f"(byte-exact, mod-safe). See קרא_אותי.txt.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`\n\n"
        f"`{LAUNCHER_ARCHIVE}` (used by the launcher, not needed for a manual install) "
        f"SHA-256:\n`{lz_digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"GTA V Hebrew FULL (beta) {version}",
           "--notes", notes, str(manifest_path), str(zip_path), str(lz_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("gh release create FAILED:\n" + (proc.stderr or proc.stdout).strip())
        return 1
    print(proc.stdout.strip())
    print(f"\nRelease {tag} published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
