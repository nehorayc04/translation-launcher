"""Corsair Cove -- Hebrew translation install.

Replaces two shipped 339-byte EMPTY-STUB paks with the full Hebrew build
(locres + injected Hebrew fonts). Fully reversible -- a one-time backup of
each original stub is kept next to it (pakchunk0_sN-WinGDK.pak.he_backup).

USAGE
    python install.py                         # auto-detect the game, then apply
    python install.py "E:\\Games\\Corsair Cove"  # explicit game root
    python install.py --revert                # restore the original (empty) stubs

Run with the game CLOSED. No settings to change -- Hebrew is in the default
(English) slot, so it just shows up the next time you launch.
"""
import os
import sys
import shutil
import string

HERE = os.path.dirname(os.path.abspath(__file__))
PAKS_REL = os.path.join("CorsairCove", "Content", "Paks")
STUB_LOC = "pakchunk0_s2-WinGDK.pak"
STUB_FNT = "pakchunk0_s4-WinGDK.pak"
STUBS = [STUB_LOC, STUB_FNT]

COMMON_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Corsair Cove",
    r"C:\Program Files\Corsair Cove",
    r"D:\Games\Corsair Cove",
    r"E:\Games\Corsair Cove",
    r"F:\Games\Corsair Cove",
    r"C:\Games\Corsair Cove",
]


def is_game(root):
    return os.path.isfile(os.path.join(root, PAKS_REL, STUB_LOC))


def find_game(argpath):
    cands = []
    if argpath:
        cands.append(argpath)
    cands += COMMON_PATHS
    for c in cands:
        c = c.rstrip("\\/")
        if is_game(c):
            return c
    # last resort: shallow scan of fixed drives for CorsairCove\Content\Paks
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


def install(root):
    paks = os.path.join(root, PAKS_REL)
    for stub in STUBS:
        live = os.path.join(paks, stub)
        bak = live + ".he_backup"
        shipped = os.path.join(HERE, stub)
        if not os.path.isfile(shipped):
            print(f"FATAL: missing shipped file {shipped}")
            return 1
        if not os.path.isfile(bak):
            shutil.copy2(live, bak)
            print(f"  backed up {stub} -> {os.path.basename(bak)}")
        else:
            print(f"  backup already exists for {stub} (skipping backup)")
        shutil.copy2(shipped, live)
        print(f"  installed {stub}  ({os.path.getsize(live):,} bytes)")
    print("\nDone. Launch the game -- Hebrew is on by default.")
    return 0


def revert(root):
    paks = os.path.join(root, PAKS_REL)
    n = 0
    for stub in STUBS:
        live = os.path.join(paks, stub)
        bak = live + ".he_backup"
        if os.path.isfile(bak):
            shutil.copy2(bak, live)
            os.remove(bak)
            print(f"  restored {stub}")
            n += 1
        else:
            print(f"  no backup for {stub} (already vanilla?)")
    print(f"\nReverted {n}/{len(STUBS)} file(s).")
    return 0


def main():
    args = sys.argv[1:]
    do_revert = "--revert" in args
    args = [a for a in args if not a.startswith("--")]
    argpath = args[0] if args else None

    root = find_game(argpath)
    if not root:
        print("Could not find the Corsair Cove installation.")
        print("Run again with the game folder as an argument, e.g.:")
        print(r'  python install.py "E:\Games\Corsair Cove"')
        return 1
    print(f"Game found: {root}")

    return revert(root) if do_revert else install(root)


if __name__ == "__main__":
    sys.exit(main())
