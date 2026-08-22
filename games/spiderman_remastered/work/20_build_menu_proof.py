"""Spider-Man Remastered — the Phase-1 menu proof.

Closes every remaining gate in ONE deploy: font-injected Font_LatinAS3.gfx (5 faces,
27/27 Hebrew each — tools/msmr_font.py) + THREE patched localization-slot candidates,
laddered (measure-with-a-ladder) because the language enum does not map 1:1 onto
variant order:

    span   0  -> kLanguageNone  (fallback; byte-identical dup of span 8)
    span   8  -> kLanguageEnglish (=1) -- THE PRIMARY target: TextLanguage was reset
                 to 1 (registry, zero-user-action default) so THIS is what a real
                 launch should read. Gets the FULL proof.
    span 152  -> kLanguageArabic (=19) -- English-text/Arabic-audio slot; this
                 machine's TextLanguage happened to be 19 before the reset. Kept as
                 a rung in case a first-run re-seed overrides the registry write.

No Arabic text locale exists in MSMR (measured: 0 Arabic codepoints across all 23
variants; LANGUAGE_ARABIC is a menu-picker LABEL with no populated Arabic strings
behind it, and span 152 -- MSMR's actual "Arabic" slot -- is English text paired with
the Arabic VOICE track only). So this is an LTR-slot hijack, store-VISUAL class
(Playbook §8b) -- bidi mode is UNKNOWN until proven in-game, so the proof ships BOTH
modes side by side on the primary span and lets one screenshot decide.

Proof design (all on real, always-reachable screens; PRIMARY = span 8):
  TEXT_SPLASHSCREEN_CONTINUE  -> per-span pure-Latin MOUNT marker (distinct per
                                 candidate, independent of font/bidi) -- whichever
                                 marker appears on the boot splash NAMES the live slot
  TEXT_CONTINUE               -> "שלום" stored LOGICAL   )  A/B pair on the
  TEXT_NEW_GAME                -> "שלום" stored VISUAL     )  same boot/menu screen
  TEXT_LOAD_GAME               -> "אבגד" (4-letter direction control, LOGICAL)
  TEXT_QUIT_GAME                -> all 27 Hebrew letters (glyph-coverage row)
  LANGUAGE_ENGLISH             -> punctuation/parens/digits/Latin-island paragraph, LOGICAL
  TEXTLANGUAGE_TITLE           -> the SAME paragraph, VISUAL
(span 0 and span 152 carry only the marker, to keep the ladder cheap.)

Deploy = index-redirect (tools/msmr_deploy.py): the toc is patched to point each
candidate localization asset AND the Latin font-lib asset at new raw files appended
under asset_archive/mods/. Nothing else in the 771,670-asset toc moves.
Revert: `python 20_build_menu_proof.py --revert`.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "games" / "spiderman_remastered" / "tools"
sys.path.insert(0, str(TOOLS))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import msmr_loc     # noqa: E402
import msmr_deploy   # noqa: E402
import msmr_font     # noqa: E402

GAME = Path(os.environ.get("MSMR_GAME", r"D:\Games\Spider-man Remastered"))
LOCS = ROOT / "games" / "spiderman_remastered" / "extract" / "loc_variants"
FONTS = ROOT / "games" / "spiderman_remastered" / "extract" / "fonts"

EN_ASSET_ID = 0xBE55D94F171BF8DE
FONT_ASSET_ID = 0xB1BC4746124FA7ED             # ui/export/fonts/Font_LatinAS3.gfx
FONT_SPAN = 0                                  # single-variant asset

HEB27 = "אבגדהוזחטיכלמנסעפצקרשת"
PARA = 'בדיקה: (טקסט עברי) "מרכאות" - מקף, פסיק. שאלה? 100% תקין! Spider-Man 2026'

# (span, source variant file, marker) -- span 8 = kLanguageEnglish(1), the primary
# candidate after the registry reset; 0 and 152 are ladder rungs (marker-only).
CANDIDATES = [
    (0,   "variant_00_idx207368.localization", "ZZ-SPAN0-NONE-ZZ",    False),
    (8,   "variant_01_idx239528.localization", "ZZ-SPAN8-ENGLISH-ZZ", True),
    (152, "variant_17_idx683222.localization", "ZZ-SPAN152-ARABIC-ZZ", False),
]


def _to_visual(s: str) -> str:
    """Real Unicode Bidi Algorithm, RTL base — the proof's VISUAL candidate. Reused
    inline (small, self-contained) so this proof never depends on a not-yet-written
    per-game rtl module before the bidi gate is even settled."""
    from bidi.algorithm import get_display
    return get_display(s, base_dir="R")


def build_patch(marker: str, full: bool) -> dict[str, str]:
    p = {"TEXT_SPLASHSCREEN_CONTINUE": marker}
    if full:
        p.update({
            "TEXT_CONTINUE": "שלום",                       # LOGICAL
            "TEXT_NEW_GAME": _to_visual("שלום"),            # VISUAL
            "TEXT_LOAD_GAME": HEB27[:4],                    # "אבגד" direction control, LOGICAL
            "TEXT_QUIT_GAME": HEB27,                        # 27-letter coverage row
            "LANGUAGE_ENGLISH": PARA,                       # LOGICAL
            "TEXTLANGUAGE_TITLE": _to_visual(PARA),         # VISUAL
        })
    return p


def build() -> tuple[list[tuple[int, int, bytes]], bytes]:
    assets = []
    for span, fname, marker, full in CANDIDATES:
        loc = msmr_loc.load(LOCS / fname)
        patch = build_patch(marker, full)
        have = set(k for k, _ in loc.pairs)
        missing = [k for k in patch if k not in have]
        if missing:
            raise SystemExit(f"span {span} ({fname}): keys not found: {missing}")
        assets.append((span, EN_ASSET_ID, loc.encode(patch)))
        print(f"[*] span {span:<4} ({fname}) -> {len(assets[-1][2])} B, "
              f"marker={marker!r}, full={full}")

    font_bytes = (FONTS / "Font_LatinAS3_0.bin").read_bytes()
    new_font = msmr_font.inject(font_bytes)
    return assets, new_font


def deploy():
    assets, new_font = build()
    print(f"[*] built {len(assets)} loc candidates + font asset ({len(new_font)} B)")
    res = msmr_deploy.apply(GAME, assets + [(FONT_SPAN, FONT_ASSET_ID, new_font)])
    print("[*] deploy ->", res)
    if not res.get("ok"):
        raise SystemExit(res.get("error"))

    # verify by reading BACK through the live toc (never trust the just-written state)
    t = msmr_deploy.read_toc(msmr_deploy.toc_path(GAME))
    t.set_archives_dir(str(msmr_deploy.arch_dir(GAME)))

    all_ok = True
    for span, fname, marker, full in CANDIDATES:
        slot = msmr_deploy.find_asset_index(t, span, EN_ASSET_ID)
        raw = bytes(t.extract_asset(slot))
        L = msmr_loc.Loc(raw)
        d = L.as_dict()
        patch = build_patch(marker, full)
        ok = all(d.get(k) == v for k, v in patch.items())
        all_ok &= ok
        print(f"[{'PASS' if ok else 'FAIL'}] span {span} read-back: "
              f"{sum(1 for k,v in patch.items() if d.get(k)==v)}/{len(patch)} keys correct "
              f"(marker={d.get('TEXT_SPLASHSCREEN_CONTINUE')!r})")
        if full:
            for k, v in patch.items():
                print(f"    {k:<28} = {d.get(k, '<MISSING>')!r}")

    fslot = msmr_deploy.find_asset_index(t, FONT_SPAN, FONT_ASSET_ID)
    fraw = bytes(t.extract_asset(fslot))
    import gfx_inspect as G  # noqa
    import swf_font as S     # noqa
    heb = 0
    for code, length, off in G.list_tags(fraw):
        if code == 75:
            f = S.parse_definefont3(fraw[off:off + length])
            heb += sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
    print(f"[{'PASS' if heb == 135 else 'FAIL'}] font read-back: {heb} Hebrew glyphs (expect 135)")

    print(f"\n[{'PASS' if all_ok else 'FAIL'}] all candidates written+verified.")
    print("\n[+] DEPLOYED. Registry TextLanguage was reset to 1 (English) before this "
          "build — no in-game setting change needed. Launch Spider-Man.exe and screenshot "
          "the FIRST boot screen (the 'PRESS TO START' splash): whichever marker "
          "(ZZ-SPAN0-NONE-ZZ / ZZ-SPAN8-ENGLISH-ZZ / ZZ-SPAN152-ARABIC-ZZ) appears NAMES "
          "the live slot. If it is ZZ-SPAN8-ENGLISH-ZZ (expected), also screenshot the main "
          "menu (Continue/New Game/Load Game/Quit Game rows) and the Language screen "
          "(English row / Text Language title) for the bidi + glyph-coverage + layout gates.")


def revert():
    print(msmr_deploy.revert(GAME))


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "--build-only" in sys.argv:
        build()
        print("[+] build OK (not deployed)")
    else:
        deploy()
