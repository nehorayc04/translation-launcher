"""Skyrim SE / AE — Phase-1 Hebrew menu proof.  ONE build, every gate.

Deploys LOOSE FILES only (Data\\Interface + Data\\Strings). Nothing in the game's
BSAs is touched, so `--revert` is a plain delete and Steam file-verification can
never fight us.

What the ONE main-menu screenshot answers:
    CONTINUE       ZZ-SKY-OK-ZZ         MOUNT   (pure Latin -> independent of font+bidi)
    NEW            "shalom" VISUAL  \\
    LOAD           "shalom" LOGICAL  >  BIDI    (exactly one can read as the real word)
    CREATION CLUB  "abgd"   VISUAL  \\
    CREDITS        "abgd"   LOGICAL  >  DIRECTION control, 4 non-confusable letters
    MODS           all 27 letters       GLYPH COVERAGE (tofu?)
    SETTINGS       Skyrim <heb> 123     MIXED + a size RULER against real Latin
    QUIT           real Hebrew label     what the shipping build looks like

Settings submenu (one click) adds the LAYOUT gate: the same paragraph with
punctuation / parens / quotes / digits / a Latin island, in BOTH modes.

usage:  python build_proof.py [--deploy] [--revert] [--verify] [--body 0.86]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # games/skyrim
sys.path.insert(0, str(ROOT / "tools"))

import strings as ST            # noqa: E402
import translate_txt as TT      # noqa: E402
import skyrim_font as SF        # noqa: E402
from skyrim_rtl import to_visual  # noqa: E402

GAME = Path(os.environ.get("SKYRIM_GAME",
                           r"D:\Games\TES - Skyrim - Anniversary Edition"))
DATA = GAME / "Data"
RAW = ROOT / "extract" / "raw"
OUT = HERE / "_proof"

MARKER = "ZZ-SKY-OK-ZZ"
ALPHABET = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"      # all 27 forms
PARA = ('בדיקת פסקה: "מרכאות" (סוגריים) — מקף, נקודה. '
        'מספרים 1,234 ו-45.6 אחוז; שם לועזי Skyrim באמצע. סוף!')

# donor per face -- chosen by MEASURING both sides (tools/skyrim_font.measure_*)
FONTS_EN = {
    3:  "C:/Windows/Fonts/Heebo-Medium.ttf",        # $CClub_Font_Bold
    4:  "C:/Windows/Fonts/Heebo-Regular.ttf",       # $CClub_Font
    5:  "C:/Windows/Fonts/Heebo-Light.ttf",         # $DialogueFont/$EverywhereFont
    7:  "C:/Windows/Fonts/Heebo-Medium.ttf",        # $EverywhereBoldFont
    9:  "C:/Windows/Fonts/Heebo-Regular.ttf",       # $StartMenuFont/$EverywhereMediumFont
    13: "C:/Windows/Fonts/FrankRuhlLibre-Regular.ttf",   # $SkyrimBooks  (classic HE serif)
    15: "C:/Windows/Fonts/DavidLibre-Regular.ttf",       # $HandwrittenFont
}
FONTS_CONSOLE = {1: "C:/Windows/Fonts/Heebo-Regular.ttf"}          # Arial / console
FONTS_LIB = {                                                     # gfxfontlib.swf
    7:  "C:/Windows/Fonts/Heebo-Regular.ttf",       # Arial
    8:  "C:/Windows/Fonts/Heebo-Light.ttf",         # Futura CondensedLight
    9:  "C:/Windows/Fonts/Heebo-Medium.ttf",        # Futura Condensed
    10: "C:/Windows/Fonts/Heebo-Regular.ttf",       # Futura Condensed
    11: "C:/Windows/Fonts/FrankRuhlLibre-Regular.ttf",   # SkyrimBooks_Gaelic
}

# .STRINGS proof: matched by ENGLISH VALUE so it is self-documenting and
# survives any id shuffle. These show up as soon as a save is loaded.
STRINGS_PROOF = {
    "Whiterun": "וייטראן",
    "Iron Sword": "חרב ברזל",
    "Lockpick": "מפתח פריצה",
    "Gold": "זהב",
    "Health Potion": "שיקוי בריאות",
    "Dragonborn": "בן דרקון",
}

MENU = {
    # main menu -- the free, always-visible surface
    "$CONTINUE":      ("raw",     MARKER),
    "$NEW":           ("visual",  "שלום"),
    "$LOAD":          ("logical", "שלום"),
    "$CREATION CLUB": ("visual",  "אבגד"),
    "$CREDITS":       ("logical", "אבגד"),
    "$MOD MANAGER":   ("visual",  ALPHABET),
    "$SETTINGS":      ("visual",  "Skyrim שלום 123"),
    "$QUIT":          ("visual",  "יציאה לשולחן העבודה"),
    # settings submenu -- the layout gate
    "$Gameplay":      ("visual",  PARA),
    "$Display":       ("logical", PARA),
    "$Audio":         ("visual",  "שמע ומוזיקה"),
    "$Controls":      ("visual",  "פקדים ומקשים"),
    "$GENERAL":       ("visual",  "כללי"),
    "$Dialogue Subtitles": ("visual", "כתוביות דיאלוג"),
    "$General Subtitles":  ("visual", "כתוביות כלליות"),
    "$Brightness":    ("visual",  "בהירות המסך"),
    "$Difficulty":    ("visual",  "רמת קושי"),
}

DEPLOYED = [
    "Interface/fonts_en.swf",
    "Interface/fonts_console.swf",
    "Interface/gfxfontlib.swf",
    "Interface/translate_english.txt",
    "Strings/skyrim_english.STRINGS",
]


def render(mode: str, text: str) -> str:
    return text if mode in ("raw", "logical") else to_visual(text)


def build(body_ratio: float) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "Interface").mkdir(exist_ok=True)
    (OUT / "Strings").mkdir(exist_ok=True)
    report: dict = {"body_ratio": body_ratio, "fonts": {}, "menu": {}, "strings": {}}

    print("== fonts ==")
    for src, faces, dst in (
            ("fonts_en.swf", FONTS_EN, "fonts_en.swf"),
            ("fonts_console.swf", FONTS_CONSOLE, "fonts_console.swf"),
            ("gfxfontlib.swf", FONTS_LIB, "gfxfontlib.swf")):
        print(f" {src}:")
        report["fonts"][src] = SF.inject_swf(RAW / "interface" / src,
                                             OUT / "Interface" / dst,
                                             faces, body_ratio=body_ratio)

    print("== translate_english.txt ==")
    raw = (RAW / "interface" / "translate_english.txt").read_bytes()
    assert TT.roundtrip(RAW / "interface" / "translate_english.txt"), "translate codec drift"
    cur = TT.parse(raw)
    ov = {}
    for k, (mode, text) in MENU.items():
        assert k in cur, f"key missing from the shipped table: {k}"
        ov[k] = render(mode, text)
        report["menu"][k] = {"mode": mode, "stored": ov[k]}
    out = TT.build(raw, ov)
    (OUT / "Interface" / "translate_english.txt").write_bytes(out)
    back = TT.parse(out)
    for k, v in ov.items():
        assert back[k] == v, f"{k} did not survive the rebuild"
    print(f"   {len(ov)} keys patched, re-read OK ({len(out)} B)")

    print("== Strings/skyrim_english.STRINGS ==")
    sp = RAW / "strings" / "skyrim_english.strings"
    ent = ST.load(sp)
    by_val: dict[str, list[int]] = {}
    for sid, v in ent.items():
        by_val.setdefault(v, []).append(sid)
    n = 0
    for en, he in STRINGS_PROOF.items():
        ids = by_val.get(en, [])
        for sid in ids:
            ent[sid] = to_visual(he)
        report["strings"][en] = {"ids": ids, "stored": to_visual(he)}
        n += len(ids)
    dst = OUT / "Strings" / "skyrim_english.STRINGS"
    ST.save(dst, ent)
    chk = ST.load(dst)
    for en, he in STRINGS_PROOF.items():
        for sid in report["strings"][en]["ids"]:
            assert chk[sid] == to_visual(he), f"strings entry {sid} lost"
    print(f"   {n} entries patched across {len(STRINGS_PROOF)} names, "
          f"{len(chk)} total, re-read OK")

    (OUT / "proof_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def deploy() -> None:
    for rel in DEPLOYED:
        src = OUT / rel
        dst = DATA / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  -> {dst}  ({dst.stat().st_size} B)")
    print("\nNOTHING inside a .bsa was modified. Revert = delete those 5 files.")


def revert() -> None:
    for rel in DEPLOYED:
        dst = DATA / rel
        if dst.exists():
            dst.unlink()
            print(f"  removed {dst}")
    for d in ("Interface", "Strings"):
        p = DATA / d
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
            print(f"  removed empty {p}")


def verify() -> None:
    """Read the DEPLOYED files back off disk -- never trust the builder."""
    import swf as SWF
    from swf_font import parse_definefont3
    ok = True
    for rel in DEPLOYED:
        p = DATA / rel
        print(f"{rel}: {'OK ' + str(p.stat().st_size) + ' B' if p.exists() else 'MISSING'}")
        ok &= p.exists()
    if not ok:
        return
    for swf_name, faces in (("fonts_en.swf", FONTS_EN),
                            ("fonts_console.swf", FONTS_CONSOLE),
                            ("gfxfontlib.swf", FONTS_LIB)):
        s = SWF.read(DATA / "Interface" / swf_name)
        for t in s.tags:
            if t.code == SWF.DEFINE_FONT3:
                f = parse_definefont3(t.body)
                if f["font_id"] in faces:
                    heb = sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
                    srt = f["codes"] == sorted(f["codes"])
                    print(f"  {swf_name} id={f['font_id']:<3} heb={heb}/27 sorted={srt}")
    cur = TT.load(DATA / "Interface" / "translate_english.txt")
    for k in ("$CONTINUE", "$NEW", "$LOAD", "$MOD MANAGER"):
        print(f"  {k} = {cur[k]!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--body", type=float, default=0.86)
    a = ap.parse_args()
    if a.revert:
        revert()
        return 0
    if a.verify:
        verify()
        return 0
    build(a.body)
    if a.deploy:
        print("\n== deploy ==")
        deploy()
        print()
        verify()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
