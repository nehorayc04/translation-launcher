#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pack_english_release.py — package the Anno 1800 Hebrew mod (ENGLISH-slot build).

Unlike the old loose-only pack_and_release.py (Korean-slot), this bundles the FULL
English-slot experience: the loose mod + the Hebrew-injected maindata `data4.rda` + a
self-contained install.py (backup + replace data4, deploy loose, activate English, revert).

Sources (the DEPLOYED, proven artifacts on this machine):
  * loose mod : Documents/Anno 1800/mods/zzz_hebrew_translation   (built by build_arabic_disguise.py)
  * data4.rda : <Steam>/Anno 1800/maindata/data4.rda              (injected by deploy_maindata.py)
  * install.py: games/anno1800/release_files/install.py

Output: release/anno1800_hebrew.zip + manifest.json  (Worker-consumed; website download_url).
Usage:  python pack_english_release.py [version]   (default 1.0.0-beta.2)
"""
from __future__ import annotations
import hashlib, json, os, sys, zipfile
from pathlib import Path

REAL_HOME    = Path(r"C:/Users/Nehoray_Cohen")          # env-redirect trap
MOD_NAME     = "zzz_hebrew_translation"
ARCHIVE_NAME = "anno1800_hebrew.zip"
STEAM_DATA4  = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Anno 1800/maindata/data4.rda")

ROOT      = Path(__file__).resolve().parent
LOOSE_MOD = REAL_HOME / "Documents" / "Anno 1800" / "mods" / MOD_NAME
INSTALLER = ROOT / "release_files" / "install.py"
OUT_DIR   = ROOT / "release"

README = """\
תרגום עברי מלא ל-Anno 1800 — גרסת English (בלי החלפת שפה)
=========================================================

מה זה נותן
----------
עברית מלאה בממשק, מוצגת מימין-לשמאל כבר מרגע העלייה, עם שפת טקסט = English —
בלי צורך להחליף שפה ואפילו לא פעם אחת. תפריט המערכת ותוכן ה-web (mod.io/חדשות)
נשארים באנגלית; כל שאר המשחק בעברית.

התקנה (הכי פשוט)
----------------
1. סגרו את המשחק.
2. הריצו:  python install.py
   (הסקריפט מאתר את המשחק, מגבה את הקובץ המקורי, ומתקין הכול.)
3. הפעילו — עברית מלאה מיד. שמע מומלץ = English.

מה ההתקנה עושה
--------------
* מעתיקה את zzz_hebrew_translation אל Documents\\Anno 1800\\mods\\
* מגבה את data4.rda המקורי שלכם ומחליפה אותו בגרסה עם הפונטים העבריים
  (זה מה שמאפשר עברית מלאה גם במסכים הפנימיים בסלוט האנגלית).
* מגדירה Text/Audio = English.

הסרה
----
python install.py --revert
(משחזר את data4.rda המקורי ומסיר את מוד ה-loose.)

הערות
-----
* אם המשחק מתעדכן וה-Steam משחזר את data4.rda — הריצו שוב את install.py.
* שמות שאתם יכולים לערוך (איים/ערים/ספינות) נשארים באנגלית בכוונה, כדי לא לדרוס
  שם שנתתם. הקלדת עברית בשדה שם תופיע הפוך (מגבלת מנוע המשחק).
"""


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 18), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    version = next((a for a in sys.argv[1:] if not a.startswith("--")), "1.0.0-beta.2")
    tag = f"v{version}"

    for label, p in (("loose mod", LOOSE_MOD / "modinfo.json"), ("data4.rda", STEAM_DATA4),
                     ("install.py", INSTALLER)):
        if not p.is_file():
            print(f"FATAL: {label} missing at {p}")
            return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    files: list[tuple[Path, str]] = []
    for dp, _, fns in os.walk(LOOSE_MOD):
        for fn in fns:
            real = Path(dp) / fn
            arc = f"{MOD_NAME}/" + str(real.relative_to(LOOSE_MOD)).replace(os.sep, "/")
            files.append((real, arc))
    files.sort(key=lambda t: t[1])

    print(f"packing {len(files)} loose files + data4.rda + install.py -> release/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for real, arc in files:
            z.write(real, arc)
        z.write(STEAM_DATA4, "data4.rda")
        z.write(INSTALLER, "install.py")
        z.writestr("קרא_אותי.txt", README)
    print(f"  + {len(files)} loose + data4.rda ({STEAM_DATA4.stat().st_size:,} B) + install.py + readme")

    digest = sha256_of(zip_path)
    manifest = {
        "archive_name": ARCHIVE_NAME,
        "sha256":       digest,
        "version":      version,
        "channel":      "beta",
        "scope":        "full",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nzip     : {zip_path}  ({zip_path.stat().st_size:,} bytes)")
    print(f"sha256  : {digest}")
    print(f"version : {version}  (tag {tag}, FULL release)")
    print("\nnext: gh/token release + PATCH games/mod_version_history (see publish steps).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
