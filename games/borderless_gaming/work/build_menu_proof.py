"""Borderless Gaming - Phase-1 menu proof.

Builds a minimal he-IL.json and drops it in the USER languages folder
(%APPDATA%\\coreutils\\borderless-gaming\\languages) - the install folder is
NEVER touched, so Steam "Verify integrity of game files" cannot revert it.

What one screenshot decides:
  1. DISCOVERY - does a language file we ADD show up in Settings -> Language?
     The Latin marker "ZZ-BG-OK-ZZ" (App.Title) proves it loaded, independent
     of fonts: if the title bar shows the marker, discovery works.
  2. FONT      - do the Hebrew strings render, or tofu boxes? The app ships
     ar/th/zh/ja/ko while embedding only Inter+Roboto, so system-font fallback
     is expected to cover Hebrew too.
  3. BIDI      - Avalonia runs the Unicode Bidi Algorithm, so text is stored
     LOGICAL (natural Hebrew, zero bidi code). The mixed line below is the
     tell-tale: it must read right-to-left with the Latin island upright.
     Panel MIRRORING (FlowDirection) is a separate, cosmetic question.

Usage:
    python build_menu_proof.py --deploy
    python build_menu_proof.py --revert
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bg_lang as B  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INSTALL = Path(os.environ.get(
    "BG_INSTALL", r"F:/SteamLibrary/steamapps/common/Borderless Gaming"))
EN = INSTALL / "languages" / "en-US.json"

def real_appdata() -> Path:
    """Roaming AppData under the REAL user profile.

    Antigravity/sandboxed shells redirect the whole profile, so %APPDATA%
    points at a throwaway folder the app never reads.  Measured here: even
    FOLDERID_RoamingAppData comes back redirected - only FOLDERID_Profile
    survives, so resolve that and append AppData\\Roaming.
    [[env-redirection-real-home]]
    """
    try:
        import ctypes
        import uuid

        FOLDERID_Profile = ctypes.create_string_buffer(
            uuid.UUID("{5E6C858F-0E22-4760-9AFE-EA3317B67173}").bytes_le, 16)
        buf = ctypes.c_wchar_p()
        hr = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(FOLDERID_Profile), 0, None, ctypes.byref(buf))
        home = buf.value
        ctypes.windll.ole32.CoTaskMemFree(buf)
        if hr == 0 and home:
            return Path(home) / "AppData" / "Roaming"
    except Exception:
        pass
    return Path(os.environ.get("APPDATA", ""))


# The app creates this itself on first run; keep the install folder pristine.
USER_LANGS = real_appdata() / "coreutils" / "borderless-gaming" / "languages"

MARKER = "ZZ-BG-OK-ZZ"

# Stored LOGICAL - natural Hebrew, no pre-reversal, no bidi control chars.
PROOF = {
    "App.Title": MARKER,                      # font-independent load proof
    "Language.Name": "עברית",
    "TitleBar.Settings": "הגדרות",
    "TitleBar.Effects": "אפקטים",
    "Windows.Title": "חלונות פעילים",
    "Windows.Search": "חיפוש חלונות...",
    "Windows.Context.MakeBorderless": "הפוך לחסר מסגרת",
    "Windows.Context.RestoreWindow": "שחזר חלון",
    "Tray.Open": "פתח את Borderless Gaming",   # mixed Hebrew + Latin island
    "Tray.Exit": "יציאה",
    "Common.Warning": "אזהרה:",                # trailing colon = bidi tell
}


def target() -> Path:
    return USER_LANGS / "he-IL.json"


def deploy() -> int:
    if not EN.exists():
        print(f"ERROR: en-US.json not found at {EN}")
        return 1
    USER_LANGS.mkdir(parents=True, exist_ok=True)
    doc = B.build_hebrew(EN, PROOF)          # untranslated leaves stay English
    B.dump(doc, target())
    flat = B.flatten(doc)
    assert set(flat) == set(B.flatten(B.load(EN))), "key set drifted - schema would reject"
    print(f"deployed -> {target()}")
    print(f"  keys {len(flat)}, Hebrew leaves {len(PROOF) - 1}, marker {MARKER!r}")
    print("\nNow: launch Borderless Gaming -> Settings -> Language.")
    print("  * 'עברית' listed?            -> discovery works (add, don't hijack)")
    print(f"  * title shows {MARKER}?  -> the file is being loaded")
    print("  * Hebrew readable, no boxes? -> system font fallback covers Hebrew")
    print("  * correct right-to-left order? -> store LOGICAL, zero bidi code")
    return 0


def revert() -> int:
    t = target()
    if t.exists():
        t.unlink()
        print(f"removed {t}")
    else:
        print("nothing to revert")
    # The app persists the picked locale; leaving it pointing at a file we just
    # deleted is untidy, so put it back to "" (= follow the system).
    cfg = USER_LANGS.parent / "settings.json"
    try:
        import json
        data = json.loads(cfg.read_text("utf-8"))
        if data.get("language") == "he-IL":
            data["language"] = ""
            cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                           encoding="utf-8", newline="\r\n")
            print(f"reset settings.json language -> \"\"  ({cfg})")
            print("  NOTE: if the app is open it may rewrite this on exit —"
                  " then just pick English in Settings -> Language.")
    except Exception as exc:  # never let cleanup fail the revert
        print(f"(settings.json untouched: {exc})")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        raise SystemExit(revert())
    if a.deploy:
        raise SystemExit(deploy())
    print(__doc__)
