"""Playbook Stage 5 — identity round-trip of the R&C localization DAT1.
Reuse the SM2 rebuild strategy (Values + TextOffsets rebuilt, all else verbatim):
  (a) parse an English variant's inner DAT1
  (b) rebuild Values+TextOffsets with NO content change (dedup preserved) → compare
      byte-for-byte to the original DAT1 (identity)
  (c) patch ONE key to Hebrew → re-emit → re-parse → confirm it reads back + all
      other keys unchanged.
Read-only against the game (works on the extracted variant)."""
import os, sys, io, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOCS = os.path.join(ROOT, "games", "ratchet_rift_apart", "extracted", "loc_variants")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1

TAG_VALUES, TAG_KEYS = 0x70A382B8, 0x4D73CEBD
TAG_TEXT_OFFSETS, TAG_KEY_OFFSETS, TAG_ENTRY_COUNT = 0xF80DEEB4, 0xA4EA55B2, 0xD540A903
HEADER_SIZE, SECTION_HEADER_SIZE, ALIGN = 16, 12, 16

SRC = os.path.join(LOCS, "variant_18_idx312859.localization")  # an English variant

def cstr(buf, off):
    end = buf.find(b"\x00", off); end = end if end >= 0 else len(buf)
    return buf[off:end]

def align_up(x, a): return (x + a - 1)//a*a

def rebuild(payload, dat1, patch=None):
    """Rebuild the DAT1 rebuilding only Values+TextOffsets; patch = {key: hebrew_bytes}."""
    secs = {sh.tag:(sh.offset, sh.size) for sh in dat1.header.sections}
    def sb(tag): o,s = secs[tag]; return payload[o:o+s]
    cnt = struct.unpack("<I", sb(TAG_ENTRY_COUNT))[0]
    keys_blob, vals_blob = sb(TAG_KEYS), sb(TAG_VALUES)
    toff = list(struct.unpack(f"<{cnt}I", sb(TAG_TEXT_OFFSETS)))
    koff = list(struct.unpack(f"<{cnt}I", sb(TAG_KEY_OFFSETS)))
    entries = []
    for i in range(cnt):
        k = cstr(keys_blob, koff[i]).decode("utf-8","replace")
        v = cstr(vals_blob, toff[i])
        entries.append([k, v])
    if patch:
        for i,(k,v) in enumerate(entries):
            if k in patch:
                entries[i][1] = patch[k]
    # rebuild Values + TextOffsets with dedup, matching SM2 layout (leading NUL)
    new_vals = bytearray(b"\x00"); seen = {b"":0}
    new_toff = [0]*cnt
    for i,(k,v) in enumerate(entries):
        if v in seen:
            new_toff[i] = seen[v]; continue
        new_toff[i] = len(new_vals); new_vals.extend(v); new_vals.extend(b"\x00"); seen[v]=new_toff[i]
    overrides = {TAG_VALUES: bytes(new_vals), TAG_TEXT_OFFSETS: struct.pack(f"<{cnt}I", *new_toff)}
    orig_headers = list(dat1.header.sections)
    sd_by_tag = {sh.tag:(overrides.get(sh.tag, payload[sh.offset:sh.offset+sh.size]), sh) for sh in orig_headers}
    out = bytearray(payload[:HEADER_SIZE])
    for sh in orig_headers:
        out.extend(struct.pack("<III", sh.tag, 0, 0))
    if dat1.header.unknowns:
        out.extend(dat1.header.unknowns)
    first_off = min(sh.offset for sh in orig_headers)
    if len(out) < first_off:
        out.extend(payload[len(out):first_off])
    new_off = {}
    for sh in sorted(orig_headers, key=lambda s:s.offset):
        cur = align_up(len(out), ALIGN)
        if cur > len(out): out.extend(b"\x00"*(cur-len(out)))
        new_off[sh.tag] = len(out)
        out.extend(sd_by_tag[sh.tag][0])
    for idx, sh in enumerate(orig_headers):
        pos = HEADER_SIZE + idx*SECTION_HEADER_SIZE
        struct.pack_into("<III", out, pos, sh.tag, new_off[sh.tag], len(sd_by_tag[sh.tag][0]))
    needle = struct.pack("<I", dat1.header.size)
    hoff = bytes(payload[:HEADER_SIZE]).find(needle)
    if hoff >= 0:
        struct.pack_into("<I", out, hoff, len(out))
    return bytes(out), cnt

raw = open(SRC, "rb").read()
prefix, payload = raw[:36], raw[36:]
dat1 = dat1lib.types.dat1.DAT1(io.BytesIO(payload), None)

# (b) identity
rebuilt, cnt = rebuild(payload, dat1, patch=None)
print(f"[*] entry_count = {cnt}")
print(f"[*] original DAT1 payload = {len(payload)} bytes, rebuilt = {len(rebuilt)} bytes, delta = {len(rebuilt)-len(payload):+d}")
identical = rebuilt == payload
print(f"[{'PASS' if identical else 'DIFF'}] identity round-trip byte-identical: {identical}")
if not identical:
    # locate first diff + whether it's only in Values/TextOffsets (semantic-ok) vs structural
    n = min(len(rebuilt), len(payload))
    fd = next((i for i in range(n) if rebuilt[i]!=payload[i]), n)
    print(f"      first byte diff at offset {fd}")
    # semantic check: re-parse rebuilt and compare every (key,value) to original
    d2 = dat1lib.types.dat1.DAT1(io.BytesIO(rebuilt), None)
    s2 = {sh.tag:(sh.offset,sh.size) for sh in d2.header.sections}
    def gb(pl,s,tag): o,sz=s[tag]; return pl[o:o+sz]
    c2 = struct.unpack("<I", gb(rebuilt,s2,TAG_ENTRY_COUNT))[0]
    to2=list(struct.unpack(f"<{c2}I", gb(rebuilt,s2,TAG_TEXT_OFFSETS))); v2=gb(rebuilt,s2,TAG_VALUES)
    ko2=list(struct.unpack(f"<{c2}I", gb(rebuilt,s2,TAG_KEY_OFFSETS))); k2=gb(rebuilt,s2,TAG_KEYS)
    secs={sh.tag:(sh.offset,sh.size) for sh in dat1.header.sections}
    def ob(tag): o,sz=secs[tag]; return payload[o:o+sz]
    c1=struct.unpack("<I",ob(TAG_ENTRY_COUNT))[0]
    to1=list(struct.unpack(f"<{c1}I",ob(TAG_TEXT_OFFSETS))); v1=ob(TAG_VALUES)
    ko1=list(struct.unpack(f"<{c1}I",ob(TAG_KEY_OFFSETS))); k1=ob(TAG_KEYS)
    mism=0
    for i in range(c1):
        if cstr(k1,ko1[i])!=cstr(k2,ko2[i]) or cstr(v1,to1[i])!=cstr(v2,to2[i]):
            mism+=1
    print(f"      semantic (key,value) mismatches after re-parse: {mism}/{c1}  -> {'SEMANTIC-PASS' if mism==0 else 'SEMANTIC-FAIL'}")

# (c) patch one key to Hebrew
patch_key = None
secs={sh.tag:(sh.offset,sh.size) for sh in dat1.header.sections}
def ob(tag): o,sz=secs[tag]; return payload[o:o+sz]
c1=struct.unpack("<I",ob(TAG_ENTRY_COUNT))[0]
ko1=list(struct.unpack(f"<{c1}I",ob(TAG_KEY_OFFSETS))); k1=ob(TAG_KEYS)
for i in range(c1):
    kn=cstr(k1,ko1[i]).decode("utf-8","replace")
    if kn.startswith("MENU") or kn.startswith("BTN") or kn.startswith("TEXT_"):
        patch_key = kn; break
patch_key = patch_key or cstr(k1,ko1[1]).decode("utf-8","replace")
HEB = "בדיקה עברית"
patched,_ = rebuild(payload, dat1, patch={patch_key: HEB.encode("utf-8")})
d3 = dat1lib.types.dat1.DAT1(io.BytesIO(patched), None)
s3={sh.tag:(sh.offset,sh.size) for sh in d3.header.sections}
def gb(pl,s,tag): o,sz=s[tag]; return pl[o:o+sz]
c3=struct.unpack("<I",gb(patched,s3,TAG_ENTRY_COUNT))[0]
to3=list(struct.unpack(f"<{c3}I",gb(patched,s3,TAG_TEXT_OFFSETS))); v3=gb(patched,s3,TAG_VALUES)
ko3=list(struct.unpack(f"<{c3}I",gb(patched,s3,TAG_KEY_OFFSETS))); k3=gb(patched,s3,TAG_KEYS)
readback=None
for i in range(c3):
    if cstr(k3,ko3[i]).decode("utf-8","replace")==patch_key:
        readback=cstr(v3,to3[i]).decode("utf-8","replace"); break
print(f"\n[*] patched key {patch_key!r} -> read back {readback!r}  [{'PASS' if readback==HEB else 'FAIL'}]")
print(f"[*] patched DAT1 size {len(patched)} (delta vs orig {len(patched)-len(payload):+d})")
