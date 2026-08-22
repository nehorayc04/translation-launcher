"""Decode the Values section (0x70A382B8) of every variant as NUL-separated UTF-8,
print counts + real sample strings, definitively map each variant to a language,
and search ALL variants for any Arabic/Hebrew codepoints. Read-only."""
import os, sys, io
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOCS = os.path.join(ROOT, "games", "ratchet_rift_apart", "extracted", "loc_variants")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1

VALUES_TAG = 0x70A382B8
KEYS_TAG   = 0x4D73CEBD

def load(path):
    raw = open(path, "rb").read()
    pay = raw[36:]
    d = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
    return pay, d

def section(pay, d, tag):
    sh = next((s for s in d.header.sections if s.tag == tag), None)
    if not sh: return b""
    return pay[sh.offset: sh.offset+sh.size]

def lang_of(strings):
    cnt = Counter()
    for s in strings:
        for ch in s:
            cp = ord(ch)
            if   0x0590<=cp<=0x05FF: cnt["hebrew"]+=1
            elif 0x0600<=cp<=0x06FF: cnt["arabic"]+=1
            elif 0x0400<=cp<=0x04FF: cnt["cyrillic"]+=1
            elif 0x0370<=cp<=0x03FF: cnt["greek"]+=1
            elif 0x3040<=cp<=0x30FF: cnt["kana"]+=1
            elif 0xAC00<=cp<=0xD7AF: cnt["hangul"]+=1
            elif 0x4E00<=cp<=0x9FFF: cnt["cjk"]+=1
            elif 0x00C0<=cp<=0x024F: cnt["latin_accent"]+=1
    if not cnt: return "english/latin"
    dom, n = cnt.most_common(1)[0]
    return dom if n > 100 else "english/latin"

fns = sorted(os.listdir(LOCS))
print(f"[*] {len(fns)} variants\n")

# keys count (shared)
pay0, d0 = load(os.path.join(LOCS, fns[0]))
keys_blob = section(pay0, d0, KEYS_TAG)
keys = [k for k in keys_blob.split(b"\x00") if k]
print(f"[*] KEYS section: {len(keys_blob)} bytes, {len(keys)} NUL-separated tokens")
print(f"    sample keys: {[k.decode('utf-8','replace') for k in keys[:6]]}\n")

any_arabic = 0
any_hebrew = 0
for k, fn in enumerate(fns):
    pay, d = load(os.path.join(LOCS, fn))
    vblob = section(pay, d, VALUES_TAG)
    strings = [s.decode("utf-8","replace") for s in vblob.split(b"\x00") if s]
    lang = lang_of(strings)
    a = sum(1 for s in strings for ch in s if 0x0600<=ord(ch)<=0x06FF)
    h = sum(1 for s in strings for ch in s if 0x0590<=ord(ch)<=0x05FF)
    any_arabic += a; any_hebrew += h
    # a couple of representative non-ascii strings
    samp = next((s for s in strings if any(ord(c)>0x2000 for c in s) and len(s)>8), "")
    samp2 = next((s for s in strings if len(s)>25), "")
    print(f"  v{k:02d} strings={len(strings):5} lang={lang:13} ar={a:5} he={h:4} | {samp[:40]!r}")

print(f"\n=== TOTAL across all variants: arabic_codepoints={any_arabic}  hebrew_codepoints={any_hebrew}")
print("=== english source candidate: a variant with 0 non-latin (pure english) ===")
for k, fn in enumerate(fns):
    pay, d = load(os.path.join(LOCS, fn))
    vblob = section(pay, d, VALUES_TAG)
    strings = [s.decode("utf-8","replace") for s in vblob.split(b"\x00") if s]
    if not strings: continue
    non_latin = sum(1 for s in strings for ch in s if ord(ch)>0x024F)
    if non_latin == 0 and len(strings) > 500:
        # show a few english samples
        eng = [s for s in strings if len(s)>15][:4]
        print(f"  v{k:02d} PURE-LATIN strings={len(strings)} samples={eng}")
        break
