"""Parse each localization variant's inner DAT1, list its sections, and per
section classify by Unicode script. The Values section (translated strings) is
the one whose content DIFFERS across variants; find the Arabic slot there.
Read-only."""
import os, sys, io
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOCS = os.path.join(ROOT, "games", "ratchet_rift_apart", "extracted", "loc_variants")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import dat1lib, dat1lib.types.dat1

def sniff(buf: bytes) -> dict:
    c = defaultdict(int)
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
    return dict(c)

def load_dat1(path):
    raw = open(path, "rb").read()
    payload = raw[36:]
    d = dat1lib.types.dat1.DAT1(io.BytesIO(payload), None)
    return raw, payload, d

fns = sorted(os.listdir(LOCS))
print(f"[*] {len(fns)} variants\n")

# 1) sections of variant_00
raw0, pay0, d0 = load_dat1(os.path.join(LOCS, fns[0]))
print(f"=== variant_00 DAT1 sections ({len(d0.header.sections)}) ===")
sec_info = []
for sh in d0.header.sections:
    seg = pay0[sh.offset: sh.offset + sh.size]
    s = sniff(seg if len(seg) <= 300000 else seg[:300000])
    top = sorted(((k,v) for k,v in s.items() if k!="ascii" and v>20), key=lambda x:-x[1])[:4]
    sec_info.append((sh.tag, sh.offset, sh.size))
    print(f"  tag=0x{sh.tag:08X} off={sh.offset:9} size={sh.size:9} ascii={s.get('ascii',0):8} top={top}")

# 2) for each section tag, check how much content varies across variants
print("\n=== per-section content variance across all variants (find the Values section) ===")
tag_first_bytes = defaultdict(set)
for fn in fns:
    _, pay, d = load_dat1(os.path.join(LOCS, fn))
    for sh in d.header.sections:
        seg = pay[sh.offset: sh.offset + sh.size]
        tag_first_bytes[sh.tag].add(hash(seg[:4096]))
for tag, _, size in sec_info:
    print(f"  tag=0x{tag:08X} size~{size:9}  distinct_content_across_variants={len(tag_first_bytes[tag])}")

# 3) identify the Values section = the one with the most distinct content, then
# classify each variant by that section's script → Arabic slot
values_tag = max(sec_info, key=lambda t: len(tag_first_bytes[t[0]]))[0]
print(f"\n[+] candidate Values section tag = 0x{values_tag:08X}")
print("\n=== classify each variant by the Values section ===")
rows = []
for k, fn in enumerate(fns):
    _, pay, d = load_dat1(os.path.join(LOCS, fn))
    sh = next((s for s in d.header.sections if s.tag == values_tag), None)
    if not sh:
        continue
    seg = pay[sh.offset: sh.offset + sh.size]
    s = sniff(seg)
    non_ascii = {kk:vv for kk,vv in s.items() if kk!="ascii"}
    dom = max(non_ascii.items(), key=lambda x:x[1]) if non_ascii and max(non_ascii.values())>200 else ("english",0)
    rows.append((k, fn, sh.size, dom[0], s))
    top = sorted(((kk,vv) for kk,vv in s.items() if kk!="ascii" and vv>50), key=lambda x:-x[1])[:3]
    print(f"  variant_{k:02d} size={sh.size:8} guess={dom[0]:10} ascii={s.get('ascii',0):7} top={top}")

print("\n=== Arabic-slot candidates (Hebrew target) ===")
for r in sorted(rows, key=lambda r: -r[4].get("arabic",0))[:5]:
    print(f"  variant_{r[0]:02d} {r[1]}  arabic={r[4].get('arabic',0)} hebrew={r[4].get('hebrew',0)}")
