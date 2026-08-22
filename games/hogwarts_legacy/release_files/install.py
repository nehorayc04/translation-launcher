"""Hogwarts Legacy — Hebrew translation install (BETA).

Drops a NON-DESTRUCTIVE additive override pak into the game's `~mods` folder.
Unreal Engine 4 mounts any `*_P.pak` there at higher priority than the base
`pakchunk0`, so the base game files are NEVER touched — Steam/Epic/GOG
"Verify Integrity" can never revert it, and no admin rights are needed
(unless the game itself lives under Program Files).

USAGE
    python install.py                                   # auto-detect the game, then apply
    python install.py "E:\\SteamLibrary\\...\\Hogwarts Legacy"  # explicit game root
    python install.py --revert                           # remove the Hebrew pak

Run with the game CLOSED. After install: launch the game -> Settings ->
Text Language -> "English" (the Hebrew rides the English text slot — you
must select it explicitly; leaving the setting on its default shows the
game's own vanilla text in whatever locale it falls back to).
Voice/speech stays English (a separate, independent setting).
"""
import os, sys, shutil, string

HERE = os.path.dirname(os.path.abspath(__file__))
PAKS_REL = os.path.join("Phoenix", "Content", "Paks")
MODS_REL = os.path.join(PAKS_REL, "~mods")
DEPLOYED_NAME = "zzz_hebrew-WindowsNoEditor_P.pak"
SHIPPED = os.path.join(HERE, "hogwarts_hebrew.pak")

COMMON_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Hogwarts Legacy",
    r"D:\Games\Hogwarts Legacy", r"D:\SteamLibrary\steamapps\common\Hogwarts Legacy",
    r"E:\Games\Hogwarts Legacy", r"E:\SteamLibrary\steamapps\common\Hogwarts Legacy",
    r"F:\Games\Hogwarts Legacy", r"F:\SteamLibrary\steamapps\common\Hogwarts Legacy",
    r"C:\Program Files\Epic Games\HogwartsLegacy",
]


def is_game(root):
    return os.path.isdir(os.path.join(root, PAKS_REL))


def find_game(argpath):
    cands = []
    if argpath:
        cands.append(argpath)
    cands += COMMON_PATHS
    for c in cands:
        c = c.rstrip("\\/")
        for sub in ("", r"\Hogwarts Legacy"):
            root = c + sub
            if is_game(root):
                return root
    # last resort: shallow scan of fixed drives for Phoenix\Content\Paks
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
        print('Could not find Hogwarts Legacy. Run:\n  python install.py "<game folder>"')
        return 1
    print(f"Game: {root}")
    mods_dir = os.path.join(root, MODS_REL)
    deployed = os.path.join(mods_dir, DEPLOYED_NAME)

    if revert:
        if os.path.isfile(deployed):
            os.remove(deployed)
            print("Removed the Hebrew override pak. Vanilla game is untouched underneath.")
        else:
            print("Not installed — nothing to revert.")
        return 0

    if not os.path.isfile(SHIPPED):
        print(f"Missing shipped pak: {SHIPPED}")
        return 1
    os.makedirs(mods_dir, exist_ok=True)
    tmp = deployed + ".tmp_he"
    shutil.copy2(SHIPPED, tmp)
    os.replace(tmp, deployed)
    print(f"Installed -> {deployed}")
    print('\nActivate: launch the game -> Settings -> Text Language -> "English".')
    print("Voice/speech stays English. To undo: python install.py --revert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
