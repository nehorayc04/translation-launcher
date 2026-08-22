"""R&C Rift Apart — probe the toc: verify dat1lib reads it (same I29/TOC2 as SM2),
list archives/assets, locate localization variants, classify each by script to
find the Arabic slot (the Hebrew-target). Read-only."""
import os, sys, io, struct, inspect

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "ratchet_rift_apart", "extracted", "loc_variants")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import dat1lib, dat1lib.types.dat1

print("[*] toc:", TOC, "exists:", os.path.exists(TOC), "size:", os.path.getsize(TOC))
with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
print("[*] toc class:", type(toc).__name__, "module:", type(toc).__module__)
try:
    toc.set_archives_dir(GAME)
except Exception as ex:
    print("[!] set_archives_dir:", ex)

archs = toc.get_archives_section()
aids  = toc.get_assets_section()
print(f"[+] archives={len(archs.archives)} assets={len(aids.ids)}")

# archive entries mentioning localization
print("\n=== archives mentioning 'localization' ===")
for i, a in enumerate(archs.archives):
    try:
        nm = bytes(a.filename).split(b"\x00")[0].decode("ascii", "ignore")
    except Exception:
        nm = str(a)
    if "local" in nm.lower():
        print(f"  [{i:4}] {nm}")

# resolve localization asset paths
print("\n=== resolve loc paths ===")
cands = [
    "localization/localization_all.localization",
    "localization/localization.localization",
    "localization/english.localization",
    "localization/arabic.localization",
]
loc_entries = None
loc_path = None
for p in cands:
    try:
        entries = toc.get_asset_entries_by_path(p)
        entries = [e for e in (entries or []) if e is not None]
        print(f"  '{p}' -> {len(entries)} entries")
        if entries and loc_entries is None:
            loc_entries = entries
            loc_path = p
    except Exception as ex:
        print(f"  '{p}' -> ERR {ex}")

if not loc_entries:
    print("[!] no localization_all path resolved — will need path hunt (step 02)")
    sys.exit(0)

print(f"\n[+] using '{loc_path}' with {len(loc_entries)} variants")

def sniff(buf: bytes) -> dict:
    c = {"arabic":0,"hebrew":0,"cyrillic":0,"latin_ext":0,"cjk":0,"hiragana":0,
         "katakana":0,"hangul":0,"thai":0,"greek":0,"ascii":0}
    i, n = 0, len(buf)
    while i < n:
        b = buf[i]
        if b < 0x80:
            c["ascii"] += 1; i += 1
        elif b < 0xC0:
            i += 1
        elif b < 0xE0 and i+1 < n:
            cp = ((b&0x1F)<<6)|(buf[i+1]&0x3F)
            if   0x0590<=cp<=0x05FF: c["hebrew"]+=1
            elif 0x0600<=cp<=0x06FF: c["arabic"]+=1
            elif 0x0400<=cp<=0x04FF: c["cyrillic"]+=1
            elif 0x0370<=cp<=0x03FF: c["greek"]+=1
            elif 0x0100<=cp<=0x024F: c["latin_ext"]+=1
            i += 2
        elif b < 0xF0 and i+2 < n:
            cp = ((b&0x0F)<<12)|((buf[i+1]&0x3F)<<6)|(buf[i+2]&0x3F)
            if   0x3040<=cp<=0x309F: c["hiragana"]+=1
            elif 0x30A0<=cp<=0x30FF: c["katakana"]+=1
            elif 0xAC00<=cp<=0xD7AF: c["hangul"]+=1
            elif 0x0E00<=cp<=0x0E7F: c["thai"]+=1
            elif 0x4E00<=cp<=0x9FFF: c["cjk"]+=1
            i += 3
        else:
            i += 4
    return c

try:
    print("[*] extract_asset sig:", inspect.signature(toc.extract_asset))
except Exception:
    pass

results = []
for k, e in enumerate(loc_entries):
    try:
        data = toc.extract_asset(e)
    except Exception:
        try:
            data = toc.extract_asset(e.index)
        except Exception as ex2:
            print(f"  [{k:02d}] extract err: {ex2}"); continue
    if not data:
        print(f"  [{k:02d}] empty"); continue
    outp = os.path.join(OUT, f"variant_{k:02d}_idx{getattr(e,'index','?')}.localization")
    with open(outp, "wb") as f:
        f.write(data)
    s = sniff(data if len(data) <= 400000 else data[:400000])
    results.append((k, getattr(e,'index','?'), len(data), data[:4].hex(), s, outp))
    top = {kk:vv for kk,vv in s.items() if vv > 50 and kk != "ascii"}
    print(f"  [{k:02d}] idx={getattr(e,'index','?')} size={len(data):9} magic={data[:4].hex()} scripts={top}")

print("\n=== ranking by Arabic codepoints (Hebrew-target slot) ===")
for r in sorted(results, key=lambda r: -r[4]["arabic"]):
    print(f"  variant_{r[0]:02d} arabic={r[4]['arabic']:6} hebrew={r[4]['hebrew']:5} size={r[2]:9} -> {os.path.basename(r[5])}")

print("\n=== ranking by ascii (english source slot) ===")
for r in sorted(results, key=lambda r: -r[4]["ascii"])[:5]:
    print(f"  variant_{r[0]:02d} ascii={r[4]['ascii']:8} arabic={r[4]['arabic']:5} size={r[2]:9}")
