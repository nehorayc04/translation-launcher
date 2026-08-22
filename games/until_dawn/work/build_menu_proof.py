#!/usr/bin/env python3
"""
build_menu_proof.py - Until Dawn (Bates) Hebrew menu proof.

There is NO Arabic locale in this game (20 LTR locales only) -> per the
AC2/Anno/GTA/TLOU playbook class we hijack an existing LTR locale slot.
Because it is UNKNOWN whether the engine loads its OWN native-culture
locres override (en) when the active culture equals native, this proof
tests BOTH at once:

  - en/Game.locres  gets a Latin marker "ZZ-UD-EN-OK-ZZ" in BATES_MENU_PAUSED
  - tr/Game.locres  gets a Latin marker "ZZ-UD-TR-OK-ZZ" in BATES_MENU_PAUSED

Both copies ALSO get real Hebrew test text in a handful of other menu/
settings keys, plus Hebrew-injected Univers+Cotford fonts, so ONE deploy
answers: (1) which slot loads with Text Language=English vs =Turkish,
(2) does Hebrew render (bidi/order), (3) does the injected font work.

Usage:
    python build_menu_proof.py build     # writes staging/ + the override pak
    python build_menu_proof.py deploy    # copies the pak into the game's ~mods
    python build_menu_proof.py revert    # deletes the deployed override pak
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
sys.path.insert(0, TOOLS)
import ud_locres as L          # noqa: E402
import ud_font as F            # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPAK = os.path.join(HERE, "..", "..", "hogwarts_legacy", "tools", "repak.exe")
GAME_PAK = r"F:\Games\Until Dawn\Windows\Bates\Content\Paks\Bates-Windows.pak"
GAME_PAKS_DIR = r"F:\Games\Until Dawn\Windows\Bates\Content\Paks"
MODS_DIR = os.path.join(GAME_PAKS_DIR, "~mods")
OUT_PAK_NAME = "pakchunk999-Windows_P.pak"

STAGING = os.path.join(HERE, "_proof_staging")
CACHE = os.path.join(HERE, "_proof_cache")

FONT_FILES = [
    "Bates/Content/UI/Fonts/Univers/UniversLTPro-45Light.ufont",
    "Bates/Content/UI/Fonts/Univers/UniversLTPro-45LightOblique.ufont",
    "Bates/Content/UI/Fonts/Univers/UniversLTPro-55Oblique.ufont",
    "Bates/Content/UI/Fonts/Univers/UniversLTPro-55Roman.ufont",
    "Bates/Content/UI/Fonts/Univers/UniversLTPro-65Bold.ufont",
    "Bates/Content/UI/Fonts/Univers/UniversLTPro-Ex.ufont",
    "Bates/Content/UI/Fonts/Cotford/CotfordDisplay-Italic.ufont",
    "Bates/Content/UI/Fonts/Cotford/CotfordDisplay-Light.ufont",
    "Bates/Content/UI/Fonts/Cotford/CotfordDisplay-LightItalic.ufont",
]

# key -> hebrew test value (applied identically to every hijacked locale copy)
HEB_TEST = {
    "BATES_MENU_PRESSANYKEY": "לחץ על כל כפתור",
    "BATES_MENU_SAVELOAD": "טען משחק",
    "BATES_MENU_QUIT": "יציאה",
    "BATES_SETTING_GROUP_LOCALE": "שפה",
    "BATES_SETTING_TEXTLANGUAGE": "שפת טקסט",
    "BATES_SETTING_SUBTITLELANG": "שפת כתוביות",
    "BATES_SETTING_SPEECHLANG": "שפת דיבור",
    "BATES_MENU_CHAPTERSELECT_TITLE": "שנה את גורלך",
}

# per-locale distinguishing marker (proves THAT slot's locres actually loaded)
MARKERS = {
    "en": "ZZ-UD-EN-OK-ZZ",
    "tr": "ZZ-UD-TR-OK-ZZ",
}


def _repak_get(rel_path, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        r = subprocess.run([REPAK, "get", GAME_PAK, rel_path], stdout=f, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise SystemExit(f"repak get failed for {rel_path}: {r.stderr.decode(errors='replace')}")


def build():
    if os.path.isdir(STAGING):
        shutil.rmtree(STAGING)
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(STAGING, exist_ok=True)

    # --- locres: en + tr, each edited in place from its own pristine copy ---
    for loc, marker in MARKERS.items():
        rel = f"Bates/Content/Localization/Game/{loc}/Game.locres"
        cache_path = os.path.join(CACHE, f"{loc}_Game.locres")
        if not os.path.isfile(cache_path):
            _repak_get(rel, cache_path)
        parsed = L.load(cache_path)
        changed = 0
        for ns in parsed["namespaces"]:
            for e in ns["entries"]:
                if e["key"] == "BATES_MENU_PAUSED":
                    e["value"] = marker
                    changed += 1
                elif e["key"] in HEB_TEST:
                    e["value"] = HEB_TEST[e["key"]]
                    changed += 1
        out_path = os.path.join(STAGING, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        L.save(parsed, out_path)
        print(f"[{loc}] patched {changed} keys -> {out_path}")

    # --- fonts: inject Hebrew into every Univers + Cotford weight ---
    for rel in FONT_FILES:
        cache_path = os.path.join(CACHE, rel.split("/")[-1])
        if not os.path.isfile(cache_path):
            _repak_get(rel, cache_path)
        out_path = os.path.join(STAGING, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        mode, added, skipped, used, cov = F.inject(cache_path, out_path)
        print(f"[font] {os.path.basename(rel)} [{mode}] hebrew={cov[1]}/27")

    # --- pack ---
    out_pak = os.path.join(HERE, OUT_PAK_NAME)
    if os.path.isfile(out_pak):
        os.remove(out_pak)
    r = subprocess.run([REPAK, "pack", "--version", "V11", STAGING, out_pak])
    if r.returncode != 0 or not os.path.isfile(out_pak):
        raise SystemExit("repak pack failed")
    print(f"\nbuilt {out_pak} ({os.path.getsize(out_pak)} bytes)")
    return out_pak


def deploy():
    out_pak = os.path.join(HERE, OUT_PAK_NAME)
    if not os.path.isfile(out_pak):
        out_pak = build()
    os.makedirs(MODS_DIR, exist_ok=True)
    dst = os.path.join(MODS_DIR, OUT_PAK_NAME)
    shutil.copyfile(out_pak, dst)
    print(f"deployed -> {dst}")
    print("\nIn-game: try Text Language = English first (check Paused/Settings for")
    print("ZZ-UD-EN-OK-ZZ + Hebrew). If still English, switch Text Language = Turkish")
    print("(check for ZZ-UD-TR-OK-ZZ + Hebrew). Speech stays English either way.")


def revert():
    dst = os.path.join(MODS_DIR, OUT_PAK_NAME)
    if os.path.isfile(dst):
        os.remove(dst)
        print(f"removed {dst}")
    else:
        print("nothing deployed")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "deploy": deploy, "revert": revert}[cmd]()
