#!/usr/bin/env python3
"""
acs_set_language.py — flip Assassin's Creed Shadows' TEXT language in
ACShadows.ini (the Stage-0 "is Arabic a real text slot?" test, see ../FEASIBILITY.md).

This edits ONLY the [Language] Text= and Subtitles= keys (keeps Sound= = English
voice, leaves Client= alone). It makes a ONE-TIME backup the first time it writes
and can fully restore it. Line-based rewrite — comments / other sections / key
order are preserved exactly. The game itself rewrites this file, so the change is
non-destructive and reversible.

USAGE
    python acs_set_language.py --show
        Print the current [Language] block. (read-only)

    python acs_set_language.py --arabic [--code ar-AE]
        Back up ACShadows.ini (once) then set Text=<code> and Subtitles=<code>.
        Default code ar-AE (Arabic-UAE, the Ubisoft ecosystem code). If Arabic
        is gated on your SKU, try --code ar / ar-SA.
        -> launch the VANILLA game and check for an Arabic RTL menu/HUD.

    python acs_set_language.py --english
        Set Text=en-US and Subtitles=en-US (without touching the backup).

    python acs_set_language.py --restore
        Restore ACShadows.ini from the acs_set_language backup.

    --ini "<path>"   override the ini location (default:
                     %USERPROFILE%\\Documents\\Assassin's Creed Shadows\\ACShadows.ini)

Nothing here touches a .forge or any game asset — it only edits a small text ini.
"""
import sys
import os
import shutil
import argparse

DEFAULT_INI = os.path.join(
    os.path.expanduser("~"), "Documents",
    "Assassin's Creed Shadows", "ACShadows.ini",
)
BACKUP_SUFFIX = ".bak.acs_set_language"
KEYS = ("Text", "Subtitles")  # what we flip; Sound/Client left alone


def find_ini(override):
    if override:
        return override
    if os.path.isfile(DEFAULT_INI):
        return DEFAULT_INI
    # OneDrive-redirected Documents fallback
    alt = os.path.join(os.path.expanduser("~"), "OneDrive", "Documents",
                       "Assassin's Creed Shadows", "ACShadows.ini")
    return alt if os.path.isfile(alt) else DEFAULT_INI


def read_language_block(path):
    out = {}
    in_lang = False
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                in_lang = (s.lower() == "[language]")
                continue
            if in_lang and "=" in s:
                k, _, v = s.partition("=")
                out[k.strip()] = v.strip()
    return out


def set_language(path, code, make_backup):
    if make_backup:
        bak = path + BACKUP_SUFFIX
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
            print(f"backup -> {bak}")
        else:
            print(f"backup already exists -> {bak}")
    with open(path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    out = []
    in_lang = False
    changed = []
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_lang = (s.lower() == "[language]")
            out.append(line)
            continue
        if in_lang and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in KEYS:
                nl = "\n" if line.endswith("\n") else ""
                out.append(f"{k}={code}{nl}")
                changed.append(k)
                continue
        out.append(line)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)
    print(f"set {{{', '.join(changed)}}} = {code}  in {path}")
    if set(changed) != set(KEYS):
        missing = set(KEYS) - set(changed)
        print(f"  WARNING: keys not found in [Language]: {missing} (ini layout differs)")


def restore(path):
    bak = path + BACKUP_SUFFIX
    if not os.path.exists(bak):
        print(f"no backup at {bak} — nothing to restore")
        return 1
    shutil.copy2(bak, path)
    print(f"restored {path} from {bak}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Flip AC Shadows text language in ACShadows.ini")
    ap.add_argument("--ini", default=None)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--show", action="store_true")
    g.add_argument("--arabic", action="store_true")
    g.add_argument("--english", action="store_true")
    g.add_argument("--restore", action="store_true")
    ap.add_argument("--code", default="ar-AE", help="Arabic locale code (default ar-AE; try ar / ar-SA)")
    a = ap.parse_args()

    path = find_ini(a.ini)
    if not os.path.isfile(path):
        print(f"ERROR: ACShadows.ini not found at {path}\n  pass --ini \"<path>\"")
        return 2

    if a.show:
        blk = read_language_block(path)
        print(f"[Language] in {path}:")
        for k in ("Client", "Text", "Sound", "Subtitles"):
            print(f"  {k}={blk.get(k, '(absent)')}")
        return 0
    if a.arabic:
        set_language(path, a.code, make_backup=True)
        print("  -> launch the VANILLA game; if the menu/HUD/subtitles show Arabic RTL, the slot is real.")
        print("  -> revert with:  python acs_set_language.py --restore")
        return 0
    if a.english:
        set_language(path, "en-US", make_backup=False)
        return 0
    if a.restore:
        return restore(path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
