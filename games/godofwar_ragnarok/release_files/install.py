"""God of War: Ragnarök — Hebrew translation install (BETA).

Replaces the game's Arabic localization slot (r_lang_ar.wad) with the full
Hebrew build. Fully reversible — a one-time backup of the original is kept
next to the file (r_lang_ar.wad.he_backup).

USAGE
    python install.py                                  # auto-detect the game, then apply
    python install.py "D:\\Games\\God of War Ragnarok"  # explicit game root
    python install.py --revert                         # restore the original Arabic WAD

Run with the game CLOSED. After install: launch the game -> Settings -> Text
Language -> "עברית" (Hebrew). Voice/speech can stay English (independent).
The Hebrew text rides the Arabic RTL slot.
"""
import os, sys, shutil, string

HERE = os.path.dirname(os.path.abspath(__file__))
WAD_REL = os.path.join("exec", "wad", "pc_le", "r_lang_ar.wad")
SHIPPED = os.path.join(HERE, "r_lang_ar.wad")

COMMON_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\God of War Ragnarok",
    r"C:\Program Files (x86)\Steam\steamapps\common\GodofWarRagnarok",
    r"C:\Program Files\Epic Games\GodOfWarRagnarok",
    r"D:\Games\God of War Ragnarok", r"D:\Games\God of War - Ragnarok",
    r"E:\Games\God of War Ragnarok", r"E:\Games\God of War - Ragnarok",
    r"F:\Games\God of War Ragnarok", r"F:\Games\God of War - Ragnarok",
]


def is_game(root):
    return os.path.isfile(os.path.join(root, WAD_REL))


def find_game(argpath):
    cands = []
    if argpath:
        cands.append(argpath)
    cands += COMMON_PATHS
    for c in cands:
        c = c.rstrip("\\/")
        for sub in ("", r"\God of War Ragnarok", r"\God of War - Ragnarok"):
            root = c + sub
            if is_game(root):
                return root
    # last resort: shallow scan of fixed drives for exec\wad\pc_le\r_lang_ar.wad
    for d in string.ascii_uppercase:
        base = f"{d}:\\"
        if not os.path.isdir(base):
            continue
        for r, dirs, _ in os.walk(base):
            if r.count(os.sep) > 5:
                dirs[:] = []
                continue
            if is_game(r):
                return r
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    revert = "--revert" in sys.argv
    root = find_game(args[0] if args else None)
    if not root:
        print('Could not find God of War Ragnarok. Run:\n  python install.py "<game folder>"')
        return 1
    print(f"Game: {root}")
    wad = os.path.join(root, WAD_REL)
    backup = wad + ".he_backup"

    if revert:
        if os.path.isfile(backup):
            shutil.copy2(backup, wad)
            print("Reverted r_lang_ar.wad to the original Arabic.")
        else:
            print("No backup found — nothing to revert.")
        return 0

    if not os.path.isfile(SHIPPED):
        print(f"Missing shipped WAD: {SHIPPED}")
        return 1
    if not os.path.isfile(backup):
        shutil.copy2(wad, backup)
        print("Backed up original -> r_lang_ar.wad.he_backup")
    shutil.copy2(SHIPPED, wad)
    print("Installed Hebrew r_lang_ar.wad.")
    print('\nActivate: launch the game -> Settings -> Text Language -> "עברית" (Hebrew).')
    print("Voice/speech can stay English. To undo: python install.py --revert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
