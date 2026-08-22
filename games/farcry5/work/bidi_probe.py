"""Measure how the game's OWN Arabic is stored -> predicts the bidi class.

Signals (same method used on RDR2 / AC Mirage / Witcher 3):
  * presentation forms (U+FB50-FEFF) vs standard block (U+0600-06FF)
        many presforms  -> engine does NO shaping -> we must store VISUAL
        zero presforms  -> engine shapes itself   -> engine HAS an RTL pipeline
  * bidi control chars in the corpus (RLM/LRM/RLE/PDF)
  * sentence-final '.' at the START of the stored string (visual storage tell)
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import fc5_oasis as O

def load(fat_path, lang, mod):
    f = Fat(fat_path)
    e = f.by_hash.get(name_hash(f"languages/{lang}/oasisstrings.oasis.bin"))
    if not e: return None
    ver, secs = mod.parse(f.read_data(e))
    return mod.flat(secs)

def report(tag, vals):
    pres = std = 0
    ctrl = collections.Counter()
    lead_dot = trail_dot = 0
    for v in vals.values():
        for ch in v:
            o = ord(ch)
            if 0xFB50 <= o <= 0xFEFF: pres += 1
            elif 0x0600 <= o <= 0x06FF: std += 1
            elif o in (0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069):
                ctrl[hex(o)] += 1
        s = v.strip()
        if s:
            if s[0] in ".!?": lead_dot += 1
            if s[-1] in ".!?": trail_dot += 1
    print(f"\n{tag}")
    print(f"  arabic standard-block chars : {std:,}")
    print(f"  arabic PRESENTATION forms   : {pres:,}   ratio std:pres = "
          f"{(std/pres if pres else float('inf')):.1f}:1")
    print(f"  bidi control chars          : {dict(ctrl) or 'NONE'}")
    print(f"  lines STARTING with . ! ?   : {lead_dot:,}   (visual-storage tell)")
    print(f"  lines ENDING   with . ! ?   : {trail_dot:,}   (logical-storage tell)")
    verdict = ("engine does NO shaping -> store VISUAL" if pres > std * 0.1
               else "engine SHAPES arabic itself -> it HAS an RTL pipeline")
    print(f"  => {verdict}")
    if lead_dot > trail_dot:
        print("  => punctuation says the ARABIC ITSELF is stored VISUAL")
    else:
        print("  => punctuation says the ARABIC ITSELF is stored LOGICAL")

FC5 = os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5")
report("FAR CRY 5  languages/arabic (patch.fat)",
       load(os.path.join(FC5, "data_final/pc/patch.fat"), "arabic", O))

# --- FC6 reference (already-proven VISUAL for Hebrew) ---
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "farcry6", "tools"))
try:
    import fc6_oasis as O6
    from fc6_fat import Fat as Fat6
    f6 = Fat6(r"F:/Game Lab/Far Cry 6/data_final/pc/common.fat")
    ver, secs = O6.parse(f6.read_data(f6.by_hash[0x14f790b7fb9610c2]))
    report("FAR CRY 6  languages/arabic (reference: Hebrew proved VISUAL)", O6.flat(secs))
except Exception as ex:
    print("\n(FC6 reference unavailable:", ex, ")")
