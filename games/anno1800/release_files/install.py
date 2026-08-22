#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install.py — Anno 1800 Hebrew (English-slot) installer / uninstaller.

מתקין תרגום עברי מלא ל-Anno 1800, שמוצג מימין-לשמאל כבר מהעלייה, עם שפת טקסט = English
(בלי צורך להחליף שפה ידנית). המנגנון: מוד loose לטקסט + הזרקת פונטים עברית לקובץ ה-maindata
data4.rda (למסכים ה-pre-baked שהמוד ה-loose לבדו לא מגיע אליהם).

מה זה עושה (install):
  1. מאתר את התקנת המשחק (Steam / Ubisoft), עם maindata/data4.rda.
  2. מגבה את data4.rda המקורי שלך (פעם אחת) ומחליף אותו בגרסה עם הפונטים העבריים.
  3. מעתיק את zzz_hebrew_translation אל Documents/Anno 1800/mods/.
  4. מגדיר Text/Audio = English ב-engine.ini (הפעלת סלוט האנגלית).

הסרה:  python install.py --revert   (משחזר את data4.rda המקורי + מסיר את מוד ה-loose)

⚠️ סגור את המשחק לפני ההרצה — הוא נועל את קובצי ה-maindata.
"""
from __future__ import annotations
import argparse, ctypes, hashlib, json, os, re, shutil, sys
from ctypes import wintypes
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
MOD_NAME = "zzz_hebrew_translation"
BUNDLED_DATA4 = HERE / "data4.rda"       # the Hebrew-injected maindata font archive
BUNDLED_MOD = HERE / MOD_NAME            # the loose-file mod folder
BACKUP_DIRNAME = "_hebrew_backup"        # under Documents/Anno 1800/
DATA4_BACKUP = "data4.rda.original"      # the user's ORIGINAL retail data4 (for revert)


# --------------------------------------------------------------- real folders ---
def _known_folder(folderid_guid: str) -> Path | None:
    """SHGetKnownFolderPath — the ONLY reliable Documents/Profile even under a redirected env."""
    try:
        class GUID(ctypes.Structure):
            _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD),
                        ("d3", wintypes.WORD), ("d4", ctypes.c_byte * 8)]
        parts = folderid_guid.split("-")
        g = GUID()
        g.d1 = int(parts[0], 16); g.d2 = int(parts[1], 16); g.d3 = int(parts[2], 16)
        rest = parts[3] + parts[4]
        for i in range(8):
            g.d4[i] = int(rest[i * 2:i * 2 + 2], 16)
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) == 0:
            p = Path(out.value); ctypes.windll.ole32.CoTaskMemFree(out)
            return p
    except Exception:
        pass
    return None


def real_documents() -> Path:
    p = _known_folder("FDD39AD0-238F-46AF-ADB4-6C85480369C7")   # FOLDERID_Documents
    if p and p.exists():
        return p
    return Path.home() / "Documents"


# ------------------------------------------------------------- game detection ---
def _steam_libraries() -> list[Path]:
    libs: list[Path] = []
    steam_roots = []
    try:
        import winreg
        for hive, key, val in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key) as k:
                    steam_roots.append(Path(winreg.QueryValueEx(k, val)[0]))
            except Exception:
                pass
    except Exception:
        pass
    steam_roots.append(Path(r"C:/Program Files (x86)/Steam"))
    for sr in steam_roots:
        vdf = sr / "steamapps" / "libraryfolders.vdf"
        libs.append(sr / "steamapps" / "common")
        if vdf.is_file():
            try:
                for m in re.finditer(r'"path"\s*"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
                    libs.append(Path(m.group(1).replace("\\\\", "/")) / "steamapps" / "common")
            except Exception:
                pass
    return libs


def find_anno_maindata() -> Path | None:
    cands: list[Path] = []
    for lib in _steam_libraries():
        cands.append(lib / "Anno 1800")
    # Ubisoft Connect + common fallbacks
    try:
        import winreg
        for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"),):
            try:
                with winreg.OpenKey(hive, key) as k:
                    i = 0
                    while True:
                        sub = winreg.EnumKey(k, i); i += 1
                        with winreg.OpenKey(k, sub) as sk:
                            try:
                                d = Path(winreg.QueryValueEx(sk, "InstallDir")[0])
                                if "anno" in str(d).lower():
                                    cands.append(d)
                            except Exception:
                                pass
            except OSError:
                pass
    except Exception:
        pass
    for base in (r"C:/Program Files (x86)/Steam/steamapps/common",
                 r"C:/Program Files/Ubisoft/Ubisoft Game Launcher/games",
                 r"C:/Ubisoft/Anno 1800", r"D:/Games/Anno 1800", r"E:/Games/Anno 1800",
                 r"F:/Games/Anno 1800"):
        cands.append(Path(base) / "Anno 1800" if "Anno 1800" not in base else Path(base))
    seen = set()
    for c in cands:
        md = c / "maindata"
        key = str(md).lower()
        if key in seen:
            continue
        seen.add(key)
        if (md / "data4.rda").is_file():
            return md
    return None


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _anno_running() -> bool:
    try:
        return "Anno1800.exe" in os.popen('tasklist /FI "IMAGENAME eq Anno1800.exe" /NH 2>NUL').read()
    except Exception:
        return False


def _set_engine_ini(docs_anno: Path) -> None:
    ini = docs_anno / "config" / "engine.ini"
    if not ini.is_file():
        return   # the game writes it on first run; nothing to do
    try:
        txt = ini.read_text(encoding="utf-8", errors="replace")
        for key in ("TextLanguage", "AudioLanguage"):
            txt2 = re.sub(rf'("{key}"\s*:\s*")[^"]*(")', rf'\1English\2', txt)
            txt = txt2
        ini.write_text(txt, encoding="utf-8")
        print(f"  set engine.ini Text/Audio = English")
    except Exception as e:
        print(f"  (could not update engine.ini automatically: {e} — set Text Language = English in-game)")


# ------------------------------------------------------------------- actions ---
def do_install() -> int:
    if not BUNDLED_DATA4.is_file() or not (BUNDLED_MOD / "modinfo.json").is_file():
        print("FATAL: bundled files missing (data4.rda / zzz_hebrew_translation). Re-extract the zip.")
        return 1
    if _anno_running():
        print("!! Anno 1800 רץ — סגור את המשחק תחילה (הוא נועל את קובצי ה-maindata). מבטל.")
        return 1

    md = find_anno_maindata()
    if not md:
        print("FATAL: לא נמצאה התקנת Anno 1800 (חיפשתי ב-Steam ו-Ubisoft).")
        print("  אתר ידנית את התיקייה שבה יש 'maindata\\data4.rda' והרץ:")
        print(r'  python install.py --game "C:\...\Anno 1800"')
        return 1
    print(f"נמצא המשחק: {md.parent}")

    docs = real_documents()
    docs_anno = docs / "Anno 1800"
    backup_dir = docs_anno / BACKUP_DIRNAME
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 1. back up the USER'S ORIGINAL data4 (once), then replace with the injected one
    live_d4 = md / "data4.rda"
    bak = backup_dir / DATA4_BACKUP
    if not bak.is_file():
        shutil.copy2(live_d4, bak)
        print(f"  גובה data4.rda מקורי -> {bak}  ({bak.stat().st_size:,} B)")
    else:
        print(f"  (גיבוי data4.rda מקורי כבר קיים — לא דורס)")
    tmp = live_d4.with_suffix(".rda.new")
    shutil.copy2(BUNDLED_DATA4, tmp)
    os.replace(tmp, live_d4)   # atomic
    print(f"  הותקן data4.rda עם פונטים עבריים  ({live_d4.stat().st_size:,} B)")

    # 2. loose mod -> Documents/Anno 1800/mods/
    dest_mod = docs_anno / "mods" / MOD_NAME
    if dest_mod.exists():
        shutil.rmtree(dest_mod, ignore_errors=True)
    shutil.copytree(BUNDLED_MOD, dest_mod)
    n = sum(1 for _ in dest_mod.rglob("*") if _.is_file())
    print(f"  הותקן מוד ה-loose -> {dest_mod}  ({n} קבצים)")

    # 3. activate the English slot
    _set_engine_ini(docs_anno)

    print("\n✅ הותקן. הפעל את המשחק — עברית מלאה מהעלייה, שפת טקסט = English (בלי החלפה).")
    print("   הסרה:  python install.py --revert")
    return 0


def do_revert() -> int:
    md = find_anno_maindata()
    docs = real_documents()
    docs_anno = docs / "Anno 1800"
    bak = docs_anno / BACKUP_DIRNAME / DATA4_BACKUP
    if md and bak.is_file():
        if _anno_running():
            print("!! Anno 1800 רץ — סגור אותו תחילה. מבטל.")
            return 1
        tmp = (md / "data4.rda").with_suffix(".rda.new")
        shutil.copy2(bak, tmp); os.replace(tmp, md / "data4.rda")
        print(f"  שוחזר data4.rda מקורי מהגיבוי")
    elif md:
        print("  (אין גיבוי data4.rda — אמת קבצי משחק ב-Steam כדי לשחזר את המקורי)")
    dest_mod = docs_anno / "mods" / MOD_NAME
    if dest_mod.exists():
        shutil.rmtree(dest_mod, ignore_errors=True)
        print(f"  הוסר מוד ה-loose")
    print("\n✅ הוסר. (engine.ini נשאר English — שנה ידנית אם תרצה.)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true", help="הסר את התרגום ושחזר את data4 המקורי")
    ap.add_argument("--game", help="נתיב שורש המשחק (אם הזיהוי האוטומטי נכשל)")
    args = ap.parse_args()
    if args.game:
        globals()["_FORCED_MD"] = Path(args.game) / "maindata"
        global find_anno_maindata
        _orig = find_anno_maindata
        find_anno_maindata = lambda: (Path(args.game) / "maindata"
                                      if (Path(args.game) / "maindata" / "data4.rda").is_file() else _orig())
    return do_revert() if args.revert else do_install()


if __name__ == "__main__":
    sys.exit(main())
