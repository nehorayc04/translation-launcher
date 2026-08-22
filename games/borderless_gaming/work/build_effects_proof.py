"""Probe the SECOND text surface: the shader metadata.

The effect editor's category names, effect names, parameter labels and tooltips
are NOT in languages/<code>.json - they are authored as attributes inside the
.slang sources:

    [bgfx::EFFECT("CRT Easymode", 2)]
    [bgfx::CATEGORY("CRT")]
    [bgfx::PARAM("Sharpness Horizontal", 0.5, 0.0, 1.0, "Controls ...")]

Round 1 (one Hebrew file in the user effects folder) produced, in the app log:

    [BGFX] Failed to parse effect file: ...\\effects\\CRT\\CRT_Easymode.slang:
    '3' is an invalid escapable character within a JSON string.
    Path: $.parameters[0]...userAttribs[0].arguments[0]

i.e. the user folder IS scanned and IS read, but the Slang reflection step
serialises the non-ASCII attribute text with C-style OCTAL escapes (\\327...),
which is not valid JSON - so the whole file is rejected. All 107 shipped
.slang files are pure ASCII with no BOM, so this path was never exercised
upstream.

This round drops four variants at once so ONE restart answers everything.
Read the answer from BOTH the CRT tree in a screenshot AND the app log:

    A  ZZ-A-LATIN-ZZ   pure ASCII        does a user file parse at all, and
                                         does it OVERRIDE the installed one or
                                         get ADDED next to it?
    B  ZZ-B-UESC-ZZ    \\uXXXX escapes    does Slang decode them to real chars?
    C  ZZ-C-BOM-ZZ     UTF-8 + BOM       does a BOM fix the reflection escape?
    D  ZZ-D-RAW-ZZ     UTF-8, no BOM     control - expected to fail as above

    python work/build_effects_proof.py --deploy
    python work/build_effects_proof.py --log      # parse errors from the log
    python work/build_effects_proof.py --revert
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_menu_proof import real_appdata  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME_EFFECTS = Path(r"F:/SteamLibrary/steamapps/common/Borderless Gaming/effects")
USER_ROOT = real_appdata() / "coreutils" / "borderless-gaming"
USER_EFFECTS = USER_ROOT / "effects"
CACHE = USER_ROOT / "cache" / "effects"
LOGS = USER_ROOT / "logs"

HE_LABEL = "חדות אופקית"
HE_DESC = "בדיקת קידוד"


def uesc(s: str) -> str:
    return "".join(c if c.isascii() else f"\\u{ord(c):04X}" for c in s)


# rel path -> (marker, label text to inject, encoding)
VARIANTS = {
    "CRT/CRT_Easymode.slang": ("ZZ-A-LATIN-ZZ", "Sharpness Horizontal", "utf-8"),
    "CRT/CRT_Geom.slang":     ("ZZ-B-UESC-ZZ",  uesc(HE_LABEL),         "utf-8"),
    "CRT/CRT_Hyllian.slang":  ("ZZ-C-BOM-ZZ",   HE_LABEL,               "utf-8-sig"),
    "CRT/CRT_Lottes.slang":   ("ZZ-D-RAW-ZZ",   HE_LABEL,               "utf-8"),
}


def cache_file(rel: str) -> Path:
    return CACHE / (rel.replace("/", "_") + ".bin")


def patch(text: str, marker: str, label: str) -> str:
    text = re.sub(r'(bgfx::EFFECT\(\s*")[^"]*(")', rf"\1{marker}\2", text, count=1)
    # replace the FIRST parameter label only, leaving every other string ASCII
    return re.sub(r'(bgfx::PARAM(?:_INT|_BOOL)?\(\s*")[^"]*(")',
                  lambda m: m.group(1) + label + m.group(2), text, count=1)


def deploy() -> None:
    for rel, (marker, label, enc) in VARIANTS.items():
        src = GAME_EFFECTS / rel
        dst = USER_EFFECTS / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(patch(src.read_text("utf-8"), marker, label),
                       encoding=enc, newline="\r\n")
        cf = cache_file(rel)
        if cf.exists():
            cf.unlink()
        print(f"  {marker:14} {enc:10} -> {dst}")
    print("\nRestart Borderless Gaming (tray -> Exit), open the effects editor,")
    print("expand CRT, screenshot it - then run --log.")


def revert() -> None:
    for rel in VARIANTS:
        p = USER_EFFECTS / rel
        if p.exists():
            p.unlink()
            print(f"removed {p}")
        cf = cache_file(rel)
        if cf.exists():
            cf.unlink()
    d = USER_EFFECTS / "CRT"
    if d.exists() and not any(d.iterdir()):
        d.rmdir()


def show_log() -> None:
    logs = sorted(LOGS.glob("*.txt"))
    if not logs:
        print("no log files")
        return
    text = logs[-1].read_text("utf-8", errors="replace")
    hits = [ln for ln in text.splitlines() if "BGFX" in ln or "effect" in ln.lower()]
    print(f"--- {logs[-1].name} ({len(hits)} effect lines) ---")
    for ln in hits[-25:]:
        print(ln)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--log", action="store_true")
    a = ap.parse_args()
    if a.revert:
        revert()
    elif a.deploy:
        deploy()
    elif a.log:
        show_log()
    else:
        for rel, (marker, _, enc) in VARIANTS.items():
            p = USER_EFFECTS / rel
            print(f"{marker:14} {enc:10} exists={p.exists()}  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
