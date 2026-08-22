"""pack_and_release.py — package the Anno 1800 Hebrew translation mod (loose-file)
and (optionally) publish a GitHub Release. Mirrors the SM2/WD2/CP2077 pack shape.

Anno's mod is a pure LOOSE-FILE folder (`zzz_hebrew_translation/` = modinfo.json +
data/config/gui/texts_*.xml + data/fonts/*.ttf + data/ui/studio/generated/<phxlf>).
No repack, no installer — the user just extracts the zip into
`Documents/Anno 1800/mods/`. We zip the DEPLOYED mod folder (the verified artifact)
+ a Hebrew readme, compute SHA-256, and write manifest.json (Worker-consumed).

Usage:
    python pack_and_release.py [version] [--pack-only]

`version` defaults to 1.0.0-beta.1. FULL release (NOT prerelease) so GitHub
`releases/latest` (read by the Worker) resolves it. Artifacts land in ./release/.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/anno1800-hebrew-mods"   # create once: gh repo create
ARCHIVE_NAME = "anno1800_hebrew.zip"
MOD_NAME     = "zzz_hebrew_translation"

ROOT     = Path(__file__).resolve().parent
MOD_DIR  = Path.home() / "Documents" / "Anno 1800" / "mods" / MOD_NAME
OUT_DIR  = ROOT / "release"

README = """\
תרגום עברי מלא ל-Anno 1800
==========================

התקנה
-----
1. חלצו את התיקייה zzz_hebrew_translation אל:
   Documents\\Anno 1800\\mods\\
   (שתתקבל: Documents\\Anno 1800\\mods\\zzz_hebrew_translation\\modinfo.json)
2. הפעילו את המשחק.

הפעלת העברית — שתי דרכים
------------------------
דרך A (ללא החלפה, עברית מיד):
  הגדירו במשחק Text Language = 한국어 (קוריאנית). העברית תופיע מלאה כבר מהעלייה.
  חיסרון: פאנלי ה-web החיים (דפדפן mod.io, באנר חדשות) יוצגו בקוריאנית.

דרך B (אנגלית + החלפה אחת):
  הגדירו Text Language = English. בעלייה ייתכן רגע של טקסט שבור — פתחו הגדרות,
  החליפו שפה פעם אחת (English -> שפה אחרת -> English) והעברית המלאה תיכנס.
  כך התפריט ותוכן ה-web נשארים באנגלית.

הסרה: מחקו את התיקייה zzz_hebrew_translation מתוך תיקיית ה-mods.

שמע: מומלץ Audio Language = English.
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
    version = positional[0] if positional else "1.0.0-beta.1"
    tag = f"v{version}"

    if not (MOD_DIR / "modinfo.json").is_file():
        print(f"FATAL: deployed mod not found at {MOD_DIR}\n  run work/build_mod.py first")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    # collect every file under the deployed mod folder, store as zzz_.../<rel>
    files = []
    for dp, _, fns in os.walk(MOD_DIR):
        for fn in fns:
            real = Path(dp) / fn
            arc = f"{MOD_NAME}/" + str(real.relative_to(MOD_DIR)).replace(os.sep, "/")
            files.append((real, arc))
    files.sort(key=lambda t: t[1])

    print(f"packing {len(files)} mod files -> release/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for real, arc in files:
            z.write(real, arc)
        z.writestr(f"{MOD_NAME}/קרא_אותי.txt", README)
        print(f"  + {len(files)} files + readme")

    digest = sha256_of(zip_path)
    manifest = {
        "archive_name": ARCHIVE_NAME,
        "sha256":       digest,
        "version":      version,
        "channel":      "beta",
        "scope":        "full",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nzip      : {zip_path}  ({zip_path.stat().st_size:,} bytes)")
    print(f"sha256   : {digest}")
    print(f"version  : {version}  (tag {tag}, FULL release)")

    if pack_only:
        print("\n--pack-only — GitHub release skipped.")
        return 0

    notes = (
        f"Hebrew translation (BETA) for Anno 1800 — version {version}.\n\n"
        f"FULL Hebrew UI (~56,400 strings): menus, settings, buildings, goods, quests, "
        f"expeditions, newspaper, encyclopedia. Loose-file mod (no repack, no anti-cheat).\n\n"
        f"Install: extract `{MOD_NAME}` into `Documents\\Anno 1800\\mods\\`. "
        f"For instant Hebrew with no toggle, set Text Language = Korean (한국어); "
        f"for an English menu, set English and toggle the language once after launch. "
        f"See קרא_אותי.txt.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"Anno 1800 Hebrew (beta) {version}",
           "--notes", notes, str(manifest_path), str(zip_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("gh release create FAILED:\n" + (proc.stderr or proc.stdout).strip())
        return 1
    print(proc.stdout.strip())
    print(f"\nRelease {tag} published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
