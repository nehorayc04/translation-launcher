"""Read variant_18 (Arabic) — parse 9 sections, walk KeyNames/Values via
TagOffsets/TextOffsets and produce arabic.json = {key: value}.
Also generate a count + a tiny sample for sanity."""
import os, sys, io, struct, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))

import dat1lib, dat1lib.types.dat1

VARIANT = "variant_18_idx1276510.localization"
SRC = os.path.join(ROOT, "games", "spiderman2", "extracted", "loc_variants", VARIANT)
OUT = os.path.join(ROOT, "games", "spiderman2", "work", "arabic.json")
SAMPLE = os.path.join(ROOT, "games", "spiderman2", "work", "arabic_sample.txt")

TAG_VALUES        = 0x70A382B8   # ValuesSection (text strings, NUL-separated)
TAG_KEYS          = 0x4D73CEBD   # KeyNamesSection (key strings, NUL-separated)
TAG_TEXT_OFFSETS  = 0xF80DEEB4   # u32[count] offsets into Values
TAG_KEY_OFFSETS   = 0xA4EA55B2   # u32[count] offsets into Keys
TAG_ENTRY_COUNT   = 0xD540A903   # u32 count
TAG_FLAGS         = 0xB0653243   # u32[count] flags
TAG_SORTED_HASHES = 0xC43731B5   # u32[count] sorted CRC32 hashes
TAG_SORTED_IDX    = 0x0CD2CFE9   # SortedIndexes (u16? u32?)
TAG_UNK_06A58050  = 0x06A58050   # unknown 4-byte entries

raw = open(SRC, "rb").read()
payload = raw[36:]
print(f"[*] {VARIANT}: raw={len(raw)}  payload={len(payload)}")

dat1 = dat1lib.types.dat1.DAT1(io.BytesIO(payload), None)
secs = {sh.tag: (sh.offset, sh.size) for sh in dat1.header.sections}
print(f"[*] sections: {len(secs)} tags: {[hex(t) for t in secs]}")

def sec(tag):
    off, sz = secs[tag]
    return payload[off:off+sz]

entry_count = struct.unpack("<I", sec(TAG_ENTRY_COUNT))[0]
print(f"[+] entry_count = {entry_count}")

values     = sec(TAG_VALUES)
keys       = sec(TAG_KEYS)
text_offs  = list(struct.unpack(f"<{entry_count}I", sec(TAG_TEXT_OFFSETS)))
key_offs   = list(struct.unpack(f"<{entry_count}I", sec(TAG_KEY_OFFSETS)))

print(f"[*] keys section: {len(keys)} bytes  ({len(keys)/entry_count:.1f} avg per key)")
print(f"[*] values section: {len(values)} bytes  ({len(values)/entry_count:.1f} avg per value)")

def cstr(buf: bytes, off: int) -> str:
    end = buf.find(b"\x00", off)
    if end < 0:
        end = len(buf)
    return buf[off:end].decode("utf-8", "replace")

mapping = {}
collisions = 0
for i in range(entry_count):
    k = cstr(keys, key_offs[i])
    v = cstr(values, text_offs[i])
    if k in mapping:
        collisions += 1
    mapping[k] = v

print(f"[+] built {len(mapping)} unique entries (collisions: {collisions})")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(mapping, f, ensure_ascii=False, indent=1)
print(f"[+] wrote {OUT}")

# Show a tiny sample — first 20 + look for likely main-menu hits
sample_keys = list(mapping.keys())[:15]
print()
print("=== first 15 entries ===")
for k in sample_keys:
    print(f"  {k:<40}  {mapping[k][:80]!r}")

print()
print("=== entries whose KEY contains likely main-menu words ===")
needles = ["MAIN_MENU","MAINMENU","MENU","NEW_GAME","NEWGAME","CONTINUE","LOAD","SAVE","OPTION","SETTINGS","EXIT","QUIT","TITLE","START","PRESS_ANY","PAUSE"]
hits = []
for k in mapping:
    ku = k.upper()
    if any(n in ku for n in needles):
        hits.append(k)
print(f"  {len(hits)} hits")
for k in hits[:60]:
    print(f"  {k:<55}  {mapping[k][:80]!r}")

with open(SAMPLE, "w", encoding="utf-8") as f:
    for k in hits:
        f.write(f"{k}\t{mapping[k]}\n")
print()
print(f"[+] menu-candidate dump → {SAMPLE}  ({len(hits)} rows)")
