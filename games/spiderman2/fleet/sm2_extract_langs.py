# -*- coding: utf-8 -*-
"""עידן חדש — extract EVERY shipped SM2 language from its localization variant into
extract/<lang>.json, keyed by the game's string key. These are the multi-language
gender/meaning oracle for the line-by-line QA (see universal/NEW_ERA_LANGUAGE_ROLES.md).

The SM2 localization ships each language as a separate `variant_NN.localization` (a DAT1)
under games/spiderman2/extracted/loc_variants/. The variant index == the in-game
TextLanguage id (0=English, 18=Arabic — the slot we hijacked for Hebrew). LANG_MAP below
was established by content detection (script + exclusive markers: gli/perché=it, ñ/vosotros
=es-ES, ãõ/você=pt, ß=de, Cyrillic=ru, أ=ar, ł/ą=pl, 你们=zh).

Run:  python sm2_extract_langs.py       (writes extract/<lang>.json for each mapped lang)
"""
import os, io, sys, json, struct, glob

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib, dat1lib.types.dat1  # noqa: E402

LOC_DIR = os.path.join(ROOT, "games", "spiderman2", "extracted", "loc_variants")
OUT_DIR = os.path.join(HERE, "extract")

# variant index -> language code (established 2026-07-12 by content detection).
# The 5 core oracle langs (ar/ru/pl/es/it) + useful extras (fr/de/pt/zh/esmx/en).
LANG_MAP = {
    0:  "en",     # English (source)
    18: "ar",     # Arabic  — addressee gender + true plural أنتم  (PRIMARY)
    14: "ru",     # Russian — speaker gender (past -л/-ла)
    12: "pl",     # Polish  — speaker+addressee gender, wy = clean plural
    15: "es",     # Spanish (Spain) — referent gender, vosotros = clean plural
    8:  "it",     # Italian — referent gender
    6:  "fr",     # French  — referent gender (secondary vote)
    7:  "de",     # German  — du/ihr number + meaning
    13: "pt",     # Portuguese — referent gender
    21: "zh",     # Chinese — 你们 clean plural + 他/她 referent
    20: "esmx",   # Spanish (LatAm) — ustedes plural (extra vote)
}

TAG_VALUES = 0x70A382B8
TAG_KEYS   = 0x4D73CEBD
TAG_TOFF   = 0xF80DEEB4
TAG_KOFF   = 0xA4EA55B2
TAG_CNT    = 0xD540A903


def _cstr(buf, off):
    e = buf.find(b"\x00", off)
    e = e if e >= 0 else len(buf)
    return buf[off:e]


def load_variant(path):
    """Parse a .localization DAT1 -> {key: value(str)} (first value per key wins)."""
    raw = open(path, "rb").read()
    pay = raw[36:]
    d = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
    secs = {sh.tag: (sh.offset, sh.size) for sh in d.header.sections}

    def sb(tag):
        o, s = secs[tag]
        return pay[o:o + s]

    cnt = struct.unpack("<I", sb(TAG_CNT))[0]
    keys, vals = sb(TAG_KEYS), sb(TAG_VALUES)
    toff = struct.unpack(f"<{cnt}I", sb(TAG_TOFF))
    koff = struct.unpack(f"<{cnt}I", sb(TAG_KOFF))
    out = {}
    for i in range(cnt):
        k = _cstr(keys, koff[i]).decode("utf-8", "replace")
        if k not in out:
            out[k] = _cstr(vals, toff[i]).decode("utf-8", "replace")
    return out


def variant_path(idx):
    hits = glob.glob(os.path.join(LOC_DIR, f"variant_{idx:02d}_*.localization"))
    return hits[0] if hits else None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for idx, lang in sorted(LANG_MAP.items()):
        p = variant_path(idx)
        if not p:
            print(f"[!] variant_{idx:02d} ({lang}) not found — skipped")
            continue
        m = load_variant(p)
        outp = os.path.join(OUT_DIR, f"{lang}.json")
        json.dump(m, open(outp, "w", encoding="utf-8"), ensure_ascii=False)
        nonempty = sum(1 for v in m.values() if v and v.strip())
        print(f"[+] {lang:5} (variant_{idx:02d}): {len(m):6} keys, {nonempty} non-empty -> extract/{lang}.json")
    print("DONE")


if __name__ == "__main__":
    main()
