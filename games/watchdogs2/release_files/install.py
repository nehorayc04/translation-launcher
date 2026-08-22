"""Watch Dogs 2 - Hebrew UI install (BETA).

Applies the Hebrew interface translation by redirecting the game's Arabic
localization slot + font to our Hebrew build (fat-redirect - fully reversible).
No Overstrike / mod manager needed.

EASIEST: double-click  install.bat  -> paste the game folder path -> choose
install or remove.

Advanced (command line):
    python install.py                 # interactive menu (path + install/remove)
    python install.py "D:\\path\\to\\WATCH_DOGS2"     # explicit game root, install
    python install.py "D:\\path\\to\\WATCH_DOGS2" --revert   # explicit root, remove
    python install.py --revert        # interactive remove

Run with the game CLOSED. After install: launch the game, Settings -> Written
Language = العربية (Arabic), and start it with  WatchDogs2.exe -eac_launcher .
The Hebrew text rides the Arabic RTL slot. In-game spoken subtitles stay English
(this is a UI/interface-only translation).
"""
import os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))

# the 3 files we ship -> their in-archive paths
TARGETS = [
    ("main_arabic.loc", r"languages\main_arabic.loc"),
    ("heb_font.ffd",    r"ui\fonts\helveticaneuelt_w1g_65_md_arabic.ffd"),
    ("heb_font.xbt",    r"ui\fonts\helveticaneuelt_w1g_65_md_arabic_1.xbt"),
]

COMMON_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Watch_Dogs2",
    r"C:\Program Files\Epic Games\WatchDogs2",
    r"C:\Program Files (x86)\Ubisoft\Ubisoft Game Launcher\games\Watch_Dogs2",
    r"D:\Games\WATCH_DOGS2", r"E:\Games\WATCH_DOGS2", r"F:\Games\WATCH_DOGS2",
]


def _clean_path(p):
    """Accept a pasted path with or without surrounding quotes/spaces."""
    return (p or "").strip().strip('"').strip("'").strip().rstrip("\\/")


def _is_game_root(root):
    return bool(root) and os.path.isdir(os.path.join(root, "data_win64"))


def find_game(argpath):
    cands = []
    if argpath:
        cands.append(argpath)
    cands += COMMON_PATHS
    for c in cands:
        c = _clean_path(c)
        for sub in ("", r"\Watch_Dogs2", r"\WATCH_DOGS2"):
            root = c + sub
            if _is_game_root(root):
                return root
    # last resort: scan fixed drives for a WATCH_DOGS2\data_win64
    import string
    for d in string.ascii_uppercase:
        base = f"{d}:\\"
        if not os.path.isdir(base):
            continue
        for r, dirs, _ in os.walk(base):
            if r.count(os.sep) > 4:
                dirs[:] = []
                continue
            if os.path.basename(r).lower() in ("watch_dogs2", "watchdogs2") and \
               os.path.isdir(os.path.join(r, "data_win64")):
                return r
    return None


def ask_path():
    """Interactive: let the user paste the game folder (quotes optional)."""
    print("הזן/הדבק את נתיב תיקיית המשחק Watch Dogs 2 (עם או בלי גרשיים),")
    print("או השאר ריק ולחץ Enter כדי לאתר את המשחק אוטומטית:")
    raw = _clean_path(input("> "))
    if not raw:
        auto = find_game(None)
        if auto:
            print(f"נמצא אוטומטית: {auto}")
        return auto
    # accept the folder itself, or its parent that holds Watch_Dogs2\
    root = find_game(raw)
    return root


def ask_action():
    print("\nמה לעשות?")
    print("  [1] התקן תרגום עברי")
    print("  [2] הסר תרגום (שחזר מקורי)")
    while True:
        choice = input("בחר 1 או 2: ").strip()
        if choice in ("1", "2"):
            return choice == "2"  # revert?
        print("בחירה לא תקינה.")


def apply(root, revert):
    print(f"\nמשחק: {root}")
    spec = importlib.util.spec_from_file_location("wd2arch", os.path.join(HERE, "wd2_archive.py"))
    arch = importlib.util.module_from_spec(spec); spec.loader.exec_module(arch)
    arch.DATA = os.path.join(root, "data_win64")
    arch.BACKUP = os.path.join(HERE, "_wd2_backup")
    os.makedirs(arch.BACKUP, exist_ok=True)
    try:
        for local, relpath in TARGETS:
            if revert:
                arch.revert(relpath)
            else:
                arch.deploy(relpath, os.path.join(HERE, local))
    except PermissionError:
        print("\nשגיאת הרשאה - האם המשחק עדיין פתוח? סגור אותו ונסה שוב.")
        return 1

    if revert:
        print("\nהתרגום הוסר, הקבצים המקוריים שוחזרו.")
    else:
        print("\nהסתיים! עכשיו במשחק: Settings -> Written Language = العربية (Arabic),")
        print("והפעל עם:  WatchDogs2.exe -eac_launcher")
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    revert = "--revert" in sys.argv

    # explicit path given on the command line -> non-interactive
    if args:
        root = find_game(args[0])
        if not root:
            print(f"לא נמצא Watch Dogs 2 בנתיב: {args[0]}")
            return 1
        return apply(root, revert)

    # interactive: ask for the path, then the action
    print("=" * 52)
    print("  Watch Dogs 2 - תרגום עברי (התקנה/הסרה)")
    print("=" * 52)
    root = ask_path()
    if not root:
        print("\nלא נמצאה תיקיית משחק תקינה (חייבת להכיל תת-תיקייה data_win64).")
        return 1
    if not revert:
        revert = ask_action()
    return apply(root, revert)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
