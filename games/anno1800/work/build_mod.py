#!/usr/bin/env python3
"""
build_mod.py - assemble the full Anno 1800 Hebrew translation mod (loose-file).

Inputs:
  - games/anno1800/work/hebrew.json          {guid: hebrew_text}  (the translation, LOGICAL order)
  - the base spine games/anno1800/extract/data/config/gui/texts_english.xml (for coverage stats)
Outputs a loose-file mod:
  <mods>/zzz_hebrew_translation/
    ├── modinfo.json
    ├── data/config/gui/texts_english.xml    # ModOps: one <Text> per translated GUID (overrides base)
    └── data/fonts/<injected Hebrew TTFs>     # loose-file font overrides

Deploy = copy into Documents/Anno 1800/mods/ (default here) or <install>/mods/.
NO .rda repack. Activation: in-game UI Language = English.

Usage:
  python work/build_mod.py [--logical] [--out <dir>]
    default  : store Hebrew VISUAL (pre-reversed per line). PROVEN in-game
               2026-06-21 that Anno's native HUD is NON-bidi and needs VISUAL
               (WD2-menu/AC2 class).
    --logical: store reading order (only for re-testing; renders reversed in-game).
"""
import argparse
import json
import os
import sys
import xml.sax.saxutils as sx

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rda_reader import RDAArchive          # noqa: E402
import anno_font                            # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = r"C:/Program Files (x86)/Steam/steamapps/common/Anno 1800"
DATA4 = GAME + "/maindata/data4.rda"
DATA25 = GAME + "/maindata/data25.rda"
# The 2 Latin Meta PHXFT font descriptors (data/ui/studio/generated/<guid>). The
# uint32 at offset (len-8) is the boot atlas-mode flag: 0 = static limited atlas at
# boot (Latin+diacritics only -> Hebrew U+0590-05FF = notdef "????" on COLD BOOT);
# 1 = dynamic glyph rasterization at boot (includes any cmap codepoint -> Hebrew
# renders). The 4 CJK descriptors already ship as 1, but the Latin Meta font is
# loaded for EVERY language (HUD chrome / static UI text) at flag 0 -- that is why
# cold-boot showed "????" until a live language switch forced a dynamic rebuild.
# Shipping these two with the flag flipped 0->1 fixes cold-boot. (RCA 2026-06-22.)
PHXFT_LATIN = ("122f6155-d20d-42cb-80f1-9df48135e737",   # MetaOffcPro-Norm
               "14ef0df1-612e-4680-87f5-e9847d6591f6")   # MetaSerifOffcPro-Medium
EXTRACT_SPINE = os.path.join(HERE, "..", "extract", "data", "config", "gui", "texts_english.xml")
HEBREW_JSON = os.path.join(HERE, "hebrew.json")
# English source spine (the full EN per GUID). Untranslated/skip-list GUIDs are filled
# with their English value so they render Latin (Meta-renderable) instead of falling
# through to Korean -> "????" once the Korean slot is bound to the narrow Meta font.
EN_FALLBACK_JSON = os.path.join(HERE, "..", "agent_handoff", "to_translate.json")
DEFAULT_MODS = os.path.join(os.path.expanduser("~"), "Documents", "Anno 1800", "mods")
MOD_NAME = "zzz_hebrew_translation"

# The Anno PHXFT font-defs (data/ui/studio/generated/*) reference EXACTLY 6 UI
# fonts: the 2 Latin Meta fonts + 4 CJK fonts. heuristica/kelvinch/roboto are
# unreferenced dead weight (confirmed by a full data+exe scan: no 7th font exists).
#
# We ONLY inject Hebrew into the 2 Meta fonts (they have no Hebrew natively). The 4
# CJK fonts ALREADY carry native Hebrew glyphs (uni05D0..) -- so we deliberately do
# NOT ship them: the engine then loads the ORIGINAL CJK fonts from the .rda, whose
# native Hebrew is guaranteed valid. (Shipping a fontTools-modified .ttc / a CJK
# .ttf with vhea/vmtx stripped risks the engine rejecting it -> notdef "????" if a
# body/label widget happens to use that style.)
META_FONTS = {"metaoffcpro-norm.ttf", "metaserifoffcpro-medium.ttf"}
# The settings ROW-LABELS + popup body render with a EUROPEAN font (proven in-game: a
# Cyrillic/Greek/Turkish probe rendered, Hebrew didn't, and our Meta cmap-remap was
# IGNORED -> labels don't use Meta). The only data/fonts/ candidates with Latin+Greek+
# Cyrillic and NO Hebrew are heuristica / kelvinch / roboto. Inject Hebrew into ALL of
# them too (+ OS/2 Hebrew bits, done in anno_font) and ship as loose-file overrides so
# whichever one the label widget loads now carries Hebrew. CJK fonts stay UNSHIPPED
# (their ORIGINAL already has native Hebrew).
INJECT_FONTS = META_FONTS | {
    "heuristica-regular.ttf", "heuristica-bold.ttf",
    "heuristica-italic.ttf", "heuristica-bolditalic.ttf",
    "kelvinch.ttf", "kelvinch-bold.ttf",
    "kelvinch-italic.ttf", "kelvinch-bolditalic.ttf",
    "roboto-regular.ttf", "roboto-light.ttf",
    # CJK fonts: the ORIGINAL ones have NO Hebrew (verified 0/27). In a CJK game
    # language the settings ROW-LABELS render with the CJK font (proven: Chinese
    # labels show, Hebrew showed "????"). So inject Hebrew into them + ship, so a
    # CJK-language run renders Hebrew labels. dfhei5a = Simplified Chinese.
    "dfhei5a.ttf", "dfpt_b5.ttf", "md_cgothic_l.ttf", "32df-udmarugothic-w6.ttc",
}


import re as _re

_HE = _re.compile(r"[֐-׿]")
_TAG = _re.compile(r"<[^>]+>")
_PCT = _re.compile(r"%[0-9.]*[sdifuxX]")


def _tokens(s):
    """TOP-LEVEL, non-overlapping preservable tokens (single L->R pass): <...> tags,
    NESTED [...] data-binds (e.g. [AssetData([RefGuid] Text)]), and %spec OUTSIDE any
    bind. A %i nested INSIDE a [...] is part of that bind, not a separate token -- so
    the whole bind is protected atomically + LTR + byte-intact."""
    toks = []
    i, n = 0, len(s)
    while i < n:
        if s[i] == "<":
            m = _TAG.match(s, i)
            if m:
                toks.append(m.group(0))
                i = m.end()
                continue
        if s[i] == "[":
            depth = 0
            j = i
            while j < n:
                if s[j] == "[":
                    depth += 1
                elif s[j] == "]":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            toks.append(s[i:j + 1])
            i = j + 1
            continue
        m = _PCT.match(s, i)
        if m:
            toks.append(m.group(0))
            i = m.end()
            continue
        i += 1
    return toks


def _visual_line(s):
    # Protect each token as a single atomic placeholder FIRST (Anno [...] binds
    # contain spaces -> must NOT be split/reversed), then do the visual reversal:
    # whitespace its own run, Hebrew runs reversed, Latin/token runs kept forward,
    # run order flipped. Restore tokens last (intact, LTR).
    mapping = {}
    for i, t in enumerate(_tokens(s)):
        p = chr(0xE000 + i)
        s = s.replace(t, p, 1)
        mapping[p] = t
    runs = _re.findall(r"[֐-׿]+|\s+|[^֐-׿\s]+", s)
    out = "".join((r[::-1] if _HE.match(r) else r) for r in reversed(runs))
    for p, t in mapping.items():
        out = out.replace(p, t)
    return out


_BR = _re.compile(r"(<br\s*/?>|\n)")


def visual_line(s):
    """Logical Hebrew -> stored VISUAL order for Anno's NON-bidi native HUD
    (PROVEN 2026-06-21; WD2-menu/AC2 class). <br/> and \\n are LINE BREAKS -> split
    on them and visual-order each segment INDEPENDENTLY (so line order is preserved,
    not mixed). Within a segment: [...]-binds/<...>/%-spec tokens stay atomic + LTR +
    byte-intact (multiset-preserved); Hebrew runs reversed, run order flipped."""
    return "".join(seg if _BR.fullmatch(seg) else _visual_line(seg) for seg in _BR.split(s))


def build_fonts(out_fonts_dir):
    os.makedirs(out_fonts_dir, exist_ok=True)
    tmp = os.path.join(HERE, "_fonts_src")
    os.makedirs(tmp, exist_ok=True)
    # extract EVERY non-CJK data/fonts/*.ttf from the archive
    names = []
    with RDAArchive(DATA4) as a:
        for e in a.iter_entries():
            base = e.name.rsplit("/", 1)[-1]
            if e.name.startswith("data/fonts/") and base.lower() in INJECT_FONTS:
                names.append(base)
                dst = os.path.join(tmp, base)
                if not os.path.exists(dst):
                    with open(dst, "wb") as fo:
                        fo.write(a.extract_entry(e))
    # CJK Latin-metric fix: the active CJK slot's font draws ASCII/digits as wide CJK
    # cells at a larger px size -> "1920x1080"/"V-Sync" oversized + overflow. Replace
    # ASCII outlines+advances with MetaOffcPro-Norm's proportional ones (scaled to Meta's
    # 32px). Keyed by font basename -> that font's PHXFT render px (from data25.rda).
    # Korean (MD_CGothic) is the user's active slot. Space/CJK/Hebrew untouched.
    # DISABLED: modifying EXISTING glyphs (ASCII outlines/advances) in a CJK font makes
    # the engine's STATIC boot-atlas prebake REJECT the font -> "????" for EVERYTHING at
    # cold boot (confirmed in-game 2026-06-22; a live language-switch still recovers via the
    # dynamic atlas, but cold boot is broken). Only APPENDING Hebrew glyphs is tolerated.
    # So the CJK-Latin-width fix is not viable as a loose-file font edit. Keep empty.
    meta_src = os.path.join(tmp, "MetaOffcPro-Norm.ttf")
    LATIN_FIX_PX = {}
    n_ok = 0
    for n in names:
        px = LATIN_FIX_PX.get(n.lower())
        if px and os.path.exists(meta_src) and n.lower() != "metaoffcpro-norm.ttf":
            anno_font.inject(os.path.join(tmp, n), os.path.join(out_fonts_dir, n),
                             latin_src=meta_src, latin_px=px)
        else:
            anno_font.inject(os.path.join(tmp, n), os.path.join(out_fonts_dir, n))
        n_ok += 1
    return n_ok


_PHXLF_SEP = bytes.fromhex("01ef3e0ad9")               # lang-string -> font-GUID separator
_MD_CGOTHIC_GUID = bytes.fromhex("0695153114a17f4bb25723585ffbcf0e")  # MD_CGothic_L packed GUID


def build_phxlf(out_ui_dir):
    """Re-point the KOREAN language->font binding from MD_CGothic to MetaOffcPro-Norm in
    every PHXLF "language font set" (data/ui/studio/generated/<guid>). WHY: a Korean
    cold-boot builds a BROAD static atlas that DOES preload Hebrew (the atlas follows the
    LANGUAGE, proven in-game 2026-06-22) -- but MD_CGothic draws Latin/digits as WIDE CJK
    cells at 36px. Binding Korean to the narrow proportional Meta font (which also carries
    our injected Hebrew) keeps the full-Hebrew cold-boot AND gives correct 32px Latin.
    Mechanism = a same-size packed-GUID swap to an existing valid font (the engine supports
    CJK-lang->Latin-font; reduced sets ddc78594/5cca36bd already do it) -> NO corruption,
    UNLIKE editing the font glyphs or the PHXFT descriptor (both -> "????")."""
    import glob as _glob
    os.makedirs(out_ui_dir, exist_ok=True)
    maindata = os.path.dirname(DATA4)
    rdas = sorted(_glob.glob(os.path.join(maindata, "*.rda")),
                  key=lambda p: int("".join(filter(str.isdigit, os.path.basename(p))) or -1))
    best = {}  # name -> (rda, full entry name) at the HIGHEST (effective) archive
    for r in rdas:
        try:
            with RDAArchive(r) as a:
                for e in a.iter_entries():
                    if "studio/generated" not in e.name or getattr(e, "size", 0) > 20000:
                        continue
                    d = a.extract_entry(e)
                    if d[:5] == b"PHXLF" and b"Korean" in d and b"SansSerifLanguage" in d:
                        best[e.name.rsplit("/", 1)[-1]] = (r, e.name)
        except Exception:
            pass
    n = 0
    for name, (r, full) in best.items():
        with RDAArchive(r) as a:
            e = next(x for x in a.iter_entries() if x.name == full)
            d = bytearray(a.extract_entry(e))
        ki, si = d.find(b"Korean"), d.find(b"SansSerifLanguage")
        if d[ki + 6:ki + 11] != _PHXLF_SEP or d[si + 17:si + 22] != _PHXLF_SEP:
            continue
        kg, sg = ki + 11, si + 22  # font-GUID byte offsets (16 bytes each)
        if bytes(d[kg:kg + 16]) != _MD_CGOTHIC_GUID:
            continue  # already Latin (reduced set) -> leave it
        d[kg:kg + 16] = d[sg:sg + 16]  # Korean font GUID := SansSerifLanguage's (Meta)
        with open(os.path.join(out_ui_dir, name), "wb") as f:
            f.write(d)
        n += 1
    return n


def build_texts(hebrew, english_fallback, visual):
    """Hebrew (VISUAL) for every translated GUID; English (as-is, LTR Latin) for every
    other GUID in the source spine -> 100% coverage so nothing falls through to the
    Korean base text (which would render "????" under the narrow Meta font)."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<ModOps>",
             '  <ModOp Type="add" Path="/TextExport/Texts">']
    seen = set()
    for guid, he in hebrew.items():
        v = visual_line(he) if visual else he
        lines.append(f"    <Text><GUID>{guid}</GUID><Text>{sx.escape(v)}</Text></Text>")
        seen.add(guid)
    nfb = 0
    for guid, en in english_fallback.items():
        guid = str(guid)
        if guid in seen or not en or not en.strip():
            continue
        lines.append(f"    <Text><GUID>{guid}</GUID><Text>{sx.escape(en)}</Text></Text>")
        seen.add(guid)
        nfb += 1
    lines.append("  </ModOp>")
    lines.append("</ModOps>")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8"), nfb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logical", action="store_true",
                    help="store reading order (Anno is PROVEN non-bidi -> default is VISUAL)")
    ap.add_argument("--out", default=DEFAULT_MODS)
    args = ap.parse_args()
    visual = not args.logical

    if not os.path.exists(HEBREW_JSON):
        sys.exit(f"missing {HEBREW_JSON} - run the translator first")
    hebrew = json.load(open(HEBREW_JSON, encoding="utf-8"))
    hebrew = {str(k): v for k, v in hebrew.items() if v and v.strip()}

    root = os.path.join(args.out, MOD_NAME)
    os.makedirs(os.path.join(root, "data", "config", "gui"), exist_ok=True)
    print(f"build_mod -> {root}  ({'VISUAL' if visual else 'LOGICAL'} storage)")

    nf = build_fonts(os.path.join(root, "data", "fonts"))
    print(f"  fonts: injected Hebrew into {nf} UI TTFs")

    # COLD-BOOT SOLUTION (RCA 2026-06-22): the user runs TextLanguage=Korean. A Korean
    # cold-boot builds a BROAD static glyph atlas that DOES preload Hebrew (the atlas
    # follows the LANGUAGE), so Hebrew renders fully without any language switch. But the
    # Korean slot's bound font (MD_CGothic) draws Latin/digits as WIDE CJK cells. So we
    # re-point Korean->MetaOffcPro-Norm (narrow, has injected Hebrew) via the PHXLF set ->
    # full cold-boot Hebrew + correct narrow Latin. (Flipping the PHXFT descriptor flag or
    # editing the CJK font's glyphs both -> "????"; only this binding swap is safe.)
    npl = build_phxlf(os.path.join(root, "data", "ui", "studio", "generated"))
    print(f"  phxlf: re-pointed Korean->Meta font in {npl} language sets (narrow Latin)")

    english_fallback = {}
    if os.path.exists(EN_FALLBACK_JSON):
        english_fallback = json.load(open(EN_FALLBACK_JSON, encoding="utf-8"))

    # Ship Hebrew into EVERY language slot (the user can pick any) + English fallback for
    # untranslated GUIDs so nothing falls through to the Korean base ("????" under Meta).
    gui = os.path.join(root, "data", "config", "gui")
    payload, nfb = build_texts(hebrew, english_fallback, visual)
    slots = ("texts_chinese.xml", "texts_taiwanese.xml", "texts_japanese.xml",
             "texts_korean.xml", "texts_english.xml")
    for slot in slots:
        with open(os.path.join(gui, slot), "wb") as f:
            f.write(payload)
    print(f"  texts: {len(hebrew)} Hebrew + {nfb} English-fallback GUID overrides -> {', '.join(slots)}")

    modinfo = {
        "Version": "1.0.0",
        "ModID": "nehoray_hebrew_translation",
        "Category": {"English": "Localization", "Hebrew": "תרגום"},
        "ModName": {"English": "Hebrew Translation", "Hebrew": "תרגום לעברית"},
        "Description": {"English": "Full Hebrew UI. Set Text Language = English, Audio = English; after launch toggle the language once for the full crisp render. (Korean slot also works with no toggle but shows live web content in Korean.)",
                        "Hebrew": "תרגום ממשק מלא לעברית. הגדר שפת טקסט = English, שמע = English; אחרי הפעלה החלף שפה פעם אחת לרינדור מלא וחד. (אפשר גם סלוט Korean ללא החלפה, אך תוכן web חי יוצג בקוריאנית.)"},
        # Shown to players in the in-game mod list - must be the BRAND, never a
        # personal handle (no personal name ships in released content).
        "CreatorName": "Hebrew Translation Hub",
    }
    with open(os.path.join(root, "modinfo.json"), "w", encoding="utf-8") as f:
        json.dump(modinfo, f, ensure_ascii=False, indent=2)
    print("  modinfo.json written")
    print("DONE. Activation: Text Language = English, Audio = English; toggle language once after launch for full render.")


if __name__ == "__main__":
    main()
