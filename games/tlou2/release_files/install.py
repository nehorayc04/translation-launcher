r"""The Last of Us Part II Remastered — Hebrew translation install (BETA).

The mod is a SINGLE PSARC dropped into the game's `mods\` folder and mounted by
**ndmodloader** above the game's core.psarc — it is ADDITIVE, nothing in the game
is overwritten, so it is trivially reversible (just delete the file).

USAGE
    python install.py                                   # auto-detect the game, then install
    python install.py "F:\\Games\\The Last of Us - Part II Remastered"   # explicit root
    python install.py --revert                          # remove the mod

REQUIRES ndmodloader (winmm.dll + modloader.asi in the game root). If it is not
installed, grab it from Nexus "The Last of Us Part II" mod #32 and drop those two
files next to tlou-ii.exe (one-time). After install: launch the game -> Options ->
Language -> Text + Subtitles = English (the hijacked slot). Voice can stay English.
"""
import os, sys, shutil, string

HERE = os.path.dirname(os.path.abspath(__file__))
MOD_NAME = "zzz-hebrew.psarc"
SHIPPED = os.path.join(HERE, MOD_NAME)
CORE_REL = os.path.join("build", "pc", "main", "core.psarc")

COMMON_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\The Last of Us Part II Remastered",
    r"C:\Program Files (x86)\Steam\steamapps\common\The Last of Us Part II",
    r"D:\Games\The Last of Us - Part II Remastered",
    r"E:\Games\The Last of Us - Part II Remastered",
    r"F:\Games\The Last of Us - Part II Remastered",
]


def is_game(root):
    return os.path.isfile(os.path.join(root, "tlou-ii.exe")) or \
           os.path.isfile(os.path.join(root, CORE_REL))


def find_game(argpath):
    cands = []
    if argpath:
        cands.append(argpath)
    cands += COMMON_PATHS
    for c in cands:
        c = c.rstrip("\\/")
        for sub in ("", r"\The Last of Us - Part II Remastered", r"\The Last of Us Part II"):
            root = c + sub
            if is_game(root):
                return root
    for d in string.ascii_uppercase:                # last resort: shallow drive scan
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
        print('Could not find The Last of Us Part II. Run:\n  python install.py "<game folder>"')
        return 1
    print(f"Game: {root}")
    mods = os.path.join(root, "mods")
    dst = os.path.join(mods, MOD_NAME)

    if revert:
        if os.path.isfile(dst):
            os.remove(dst)
            print(f"Removed {MOD_NAME} from mods\\.")
        else:
            print("Mod not present — nothing to revert.")
        return 0

    if not os.path.isfile(SHIPPED):
        print(f"Missing shipped mod: {SHIPPED}")
        return 1
    os.makedirs(mods, exist_ok=True)
    shutil.copy2(SHIPPED, dst)
    print(f"Installed {MOD_NAME} -> mods\\")

    # ndmodloader presence check (informational — user installs it once)
    has_ndml = os.path.isfile(os.path.join(root, "winmm.dll")) and \
        os.path.isfile(os.path.join(root, "modloader.asi"))
    if not has_ndml:
        print("\n[!] ndmodloader not detected (no winmm.dll + modloader.asi in the game root).")
        print("    Install it once (Nexus 'The Last of Us Part II' mod #32) or the mod won't load.")
    print('\nActivate: launch the game -> Options -> Language -> Text + Subtitles = English.')
    print("Voice/speech can stay English. To undo: python install.py --revert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
