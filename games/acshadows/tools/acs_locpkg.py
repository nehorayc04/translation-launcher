#!/usr/bin/env python3
"""
acs_locpkg.py — DECODE AC Shadows LocalizationPackage resources into
{oasisID: text} dicts (all languages incl. English + Arabic).

Ported byte-for-byte from the decompiled free AnvilToolkit v1.3.4
(AnvilToolkit.FileTypes.AnvilNext.UI: LocalizationPackage / IndexedData /
StringFragment / StringTable / StringTableEntry). See ../FORMAT.md §4b.

The text is NOT stored as literal UTF-16 — it is a char-INDEX / fragment-tree
serialization (AC2-style), which is why a literal UTF-16/UTF-8 search finds
nothing. Layout (Shadows = the `default` case in ATK):

  resource (decompressed via CFD multi-block) holds, somewhere:
    i32 Type ; u32 Language ; <skip 12> ; u32 marker=0xD28389B5 ; i32 num ;
    `num` bytes -> BIG-ENDIAN payload:
      IndexedData: u16 MaxIndexSize ; u16 fragCount ;
                   fragCount x StringFragment{ u16 right, u16 left }
        fragment decode: left==0&&right==0 -> "" ; left==0 -> UTF-16 unit `right`;
                         else  left.String + right.String   (binary tree)
      u16 tableCount ; tableCount x StringTable{ u32 FirstEntryID, u32 Headers, u32 Entries }
      per table @Entries:  u16 n ; off0(u16) ; n x { u16 idDelta, u16 off }
      per table @Headers:  DecodeString — read codes until consumed==entry.off:
        code b: b<MaxIndexSize -> frag[b+1]
                b==255         -> frag[ readBEint16 + 1 ]
                else           -> frag[ ((b<<8)|next) - MaxIndexSize*255 + 1 ]
        (entry offsets are cumulative byte counts into the Headers region)

    python acs_locpkg.py scan  "<forge>" [--top N] [--min-size B] [--flag F]
    python acs_locpkg.py info  "<forge>" <index>          # langs + samples
    python acs_locpkg.py dump  "<forge>" <index> <out.json> [--lang L]
    python acs_locpkg.py selftest                          # round-trip a synthetic pkg
"""
import sys
import os
import struct
import json
import argparse

MARKER = 0xD28389B5          # == crc32(b"CompressedLocalizationData") -- the nested object
CLASS_HASH = 0x6E3C9C6F      # == crc32(b"LocalizationPackage") in AC Shadows (v42).
# The class hash is plain CRC32 of the reflection class NAME; the names live in a
# plaintext table at the forge tail (after the last resource). AC2's LocalizationPackage
# hashed to 0x6E37B1AF -- anchoring Shadows on THAT value finds nothing and is what led
# to the wrong "Shadows has no LocalizationPackage / text is literal UTF-16" conclusion.
# After ScimitarClass.Deserialize reads ClassID + ClassHash, LocalizationPackage.Read
# (Shadows = default case) reads: Type(i32) Language(u32) <skip 12> <discard u32> num(i32)
# then `num` big-endian payload bytes. So anchoring on the class hash:
#   hash@H  Type@H+4  Language@H+8  num@H+28  BE-payload@H+32


def _tools():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import acs_forge as F
    import acs_cfd as C
    return F, C


# ---- big-endian readers --------------------------------------------------
def _u16(b, p): return struct.unpack_from(">H", b, p)[0]
def _u32(b, p): return struct.unpack_from(">I", b, p)[0]
def _i16(b, p): return struct.unpack_from(">h", b, p)[0]


def _resolve_fragments(frags):
    """frags = [(right,left), ...]. Returns list[str], memoized, recursion-free.
    Leaf chars are kept as lone UTF-16 code units (chr); surrogate pairs are
    recombined per-entry at the end."""
    n = len(frags)
    cache = [None] * n
    for start in range(n):
        if cache[start] is not None:
            continue
        stack = [start]
        while stack:
            j = stack[-1]
            if cache[j] is not None:
                stack.pop()
                continue
            right, left = frags[j]
            if left == 0 and right == 0:
                cache[j] = ""
                stack.pop()
                continue
            if left == 0:
                cache[j] = chr(right)        # single UTF-16 code unit
                stack.pop()
                continue
            need = []
            if not (0 <= right < n):
                cache[j] = ""
                stack.pop()
                continue
            if not (0 <= left < n):
                cache[j] = ""
                stack.pop()
                continue
            if cache[right] is None:
                need.append(right)
            if cache[left] is None:
                need.append(left)
            if need:
                stack.extend(need)
                continue
            cache[j] = cache[left] + cache[right]   # ATK: leftValue + rightValue
            stack.pop()
    return cache


def _recombine(s):
    """Recombine lone UTF-16 surrogate halves into proper codepoints."""
    try:
        return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    except Exception:
        return s


def decode_payload(buf):
    """Decode one big-endian LocalizationPackage payload -> {id(int): str}."""
    p = 0
    max_index = _u16(buf, p); p += 2
    index_mask = max_index * 255
    frag_count = _u16(buf, p); p += 2
    frags = []
    for _ in range(frag_count):
        right = _u16(buf, p)
        left = _u16(buf, p + 2)
        p += 4
        frags.append((right, left))
    cache = _resolve_fragments(frags)
    nfrag = len(cache)
    table_count = _u16(buf, p); p += 2
    tables = []
    for _ in range(table_count):
        first = _u32(buf, p)
        headers = _u32(buf, p + 4)
        entries = _u32(buf, p + 8)
        p += 12
        tables.append((first, headers, entries))

    out = {}
    for first, headers_off, entries_off in tables:
        q = entries_off
        n = _u16(buf, q); q += 2
        ents = []
        off0 = _u16(buf, q); q += 2
        ents.append((first, off0))
        for _ in range(n):
            iddelta = _u16(buf, q)
            off = _u16(buf, q + 2)
            q += 4
            ents.append((first + iddelta, off))
        # decode strings sequentially from the headers region
        r = headers_off
        consumed = 0
        for (eid, end_off) in ents:
            units = []
            while consumed < end_off:
                b = buf[r]; r += 1; consumed += 1
                if b < max_index:
                    idx = b + 1
                elif b == 255:
                    num = _i16(buf, r); r += 2; consumed += 2
                    idx = num + 1
                else:
                    b2 = buf[r]; r += 1; consumed += 1
                    idx = (((b << 8) | b2) - index_mask) + 1
                units.append(cache[idx] if 0 <= idx < nfrag else "")
            out[eid] = _recombine("".join(units))
    return out


def find_packages(data):
    """Scan a decompressed resource for every LocalizationPackage, anchoring on
    the inline class hash 0x6E37B1AF. Returns
    [{'lang':int,'type':int,'offset':int,'strings':dict}, ...]."""
    needle = struct.pack("<I", CLASS_HASH)
    pkgs = []
    pos = 0
    n = len(data)
    while True:
        h = data.find(needle, pos)
        if h < 0:
            break
        pos = h + 4
        if h + 32 > n:
            continue
        try:
            typ = struct.unpack_from("<i", data, h + 4)[0]
            lang = struct.unpack_from("<I", data, h + 8)[0]
            num = struct.unpack_from("<i", data, h + 28)[0]
            if num <= 4 or h + 32 + num > n:
                continue
            payload = data[h + 32: h + 32 + num]
            strings = decode_payload(payload)
            if strings:
                pkgs.append({"lang": lang, "type": typ, "offset": h, "strings": strings})
        except Exception:
            continue
    return pkgs


# ---- forge plumbing ------------------------------------------------------
def _peek_block0(forge_path, rec, oodle):
    """Decompress only CFD block0 of a resource (cheap loc-package probe)."""
    import acs_cfd as C
    want = min(rec["size"], 600000)
    with open(forge_path, "rb") as f:
        f.seek(rec["offset"]); head = f.read(want)
    if len(head) < 23 or struct.unpack_from("<Q", head, 0)[0] != C.MAGIC:
        return None
    count = struct.unpack_from("<i", head, 15)[0]
    if count < 1 or count > 1_000_000:
        return None
    bi = 19
    if bi + 8 > len(head):
        return None
    uncomp0, comp0 = struct.unpack_from("<ii", head, bi)
    if uncomp0 <= 0 or comp0 <= 0 or comp0 > 4_000_000:
        return None
    pdata = bi + count * 8 + 4
    if pdata + comp0 > len(head):
        with open(forge_path, "rb") as f:
            f.seek(rec["offset"]); head = f.read(min(rec["size"], pdata + comp0))
    cdata = head[pdata:pdata + comp0]
    if len(cdata) < comp0:
        return None
    try:
        return cdata if comp0 == uncomp0 else oodle.decompress(cdata, uncomp0)
    except Exception:
        return None


def _full_decode(forge_path, rec, oodle):
    import acs_cfd as C
    with open(forge_path, "rb") as f:
        f.seek(rec["offset"]); blob = f.read(rec["size"])
    cfds, _ = C.decode_resource(blob, oodle)
    data = b"".join(d for d, _ in cfds)
    return find_packages(data)


def _oodle():
    F, C = _tools()
    return C._oodle()


def cmd_scan(forge, top, min_size, flag):
    F, C = _tools()
    o = _oodle()
    info = F.parse(forge)
    recs = info["recs"]
    if flag is not None:
        recs = [r for r in recs if r["flags"] == flag]
    if min_size:
        recs = [r for r in recs if r["size"] >= min_size]
    if top:
        recs = sorted(recs, key=lambda r: -r["size"])[:top]
    print(f"{os.path.basename(forge)}: probing {len(recs)} resources "
          f"(top={top} min_size={min_size} flag={flag})")
    found = 0
    for n, r in enumerate(recs):
        if n and n % 2000 == 0:
            print(f"  ...{n}/{len(recs)} probed, {found} loc-pkg resources")
        blk = _peek_block0(forge, r, o)
        if not blk or struct.pack("<I", CLASS_HASH) not in blk:
            continue
        # confirmed marker in block0 -> full decode (handles multi-block)
        try:
            pkgs = _full_decode(forge, r, o)
        except Exception as e:
            print(f"  idx {r['i']} hash 0x{r['hash']:08x} size 0x{r['size']:x} "
                  f"flags {r['flags']}: marker but decode FAILED ({e})")
            continue
        if not pkgs:
            continue
        found += 1
        langs = ", ".join(f"lang={p['lang']}:{len(p['strings'])}str" for p in pkgs)
        print(f"  idx {r['i']:>7} hash 0x{r['hash']:08x} size 0x{r['size']:>8x} "
              f"flags {r['flags']:>4}  -> {len(pkgs)} pkg(s): {langs}")
    print(f"DONE: {found} loc-package resources")
    return 0


def _sample(strings, k=6):
    out = []
    for i, (sid, s) in enumerate(strings.items()):
        if i >= k:
            break
        t = s.replace("\n", "\\n")
        out.append(f"    {sid}: {t[:80]}")
    return "\n".join(out)


def cmd_info(forge, index):
    F, C = _tools()
    o = _oodle()
    info = F.parse(forge)
    rec = info["recs"][index]
    pkgs = _full_decode(forge, rec, o)
    print(f"resource {index} (hash 0x{rec['hash']:08x}, size 0x{rec['size']:x}, "
          f"flags {rec['flags']}): {len(pkgs)} LocalizationPackage(s)")
    for p in pkgs:
        print(f"  lang={p['lang']} type={p['type']} strings={len(p['strings'])}")
        print(_sample(p["strings"]))
    return 0


def cmd_dump(forge, index, out, lang):
    F, C = _tools()
    o = _oodle()
    info = F.parse(forge)
    rec = info["recs"][index]
    pkgs = _full_decode(forge, rec, o)
    merged = {}
    for p in pkgs:
        if lang is not None and p["lang"] != lang:
            continue
        for sid, s in p["strings"].items():
            merged[str(sid)] = s
    with open(out, "w", encoding="utf-8") as g:
        json.dump(merged, g, ensure_ascii=False, indent=1)
    print(f"resource {index}: wrote {len(merged)} strings "
          f"(lang={lang if lang is not None else 'ALL'}) -> {out}")
    return 0


def cmd_selftest():
    """Encode a tiny package the ATK way, then decode it back."""
    # build fragments for chars of "Hi" + "!" : dict sorted unique chars
    # Verify the decoder against a hand-built payload.
    import io
    chars = sorted(set("Hi!"))           # ['!','H','i']
    chars.insert(0, "")                  # frag[0] = ""
    # fragments: each a single char (leaf). right=ord(c), left=0 ; frag0=(0,0)
    frags = []
    for c in chars:
        if c == "":
            frags.append((0, 0))
        else:
            frags.append((ord(c), 0))
    # one table, one entry "Hi!" -> codes = indexOf each char in `chars` minus 1
    s = "Hi!"
    codes = [chars.index(ch) - 1 for ch in s]   # bytes (<255)
    payload = bytearray()
    payload += struct.pack(">H", 255)           # MaxIndexSize
    payload += struct.pack(">H", len(frags))    # fragCount
    for right, left in frags:
        payload += struct.pack(">HH", right, left)
    payload += struct.pack(">H", 1)             # tableCount
    # table: FirstEntryID, HeadersOffset, EntriesOffset (fill offsets after)
    hdr_pos = len(payload)
    payload += struct.pack(">III", 1000, 0, 0)
    entries_off = len(payload)
    payload += struct.pack(">H", 0)             # n=0 (single entry0)
    payload += struct.pack(">H", len(codes))    # entry0 offset = #codes
    headers_off = len(payload)
    for cd in codes:
        payload += struct.pack("B", cd)
    struct.pack_into(">III", payload, hdr_pos, 1000, headers_off, entries_off)
    got = decode_payload(bytes(payload))
    ok = got.get(1000) == "Hi!"
    print(f"selftest: decoded {got} -> {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="AC Shadows LocalizationPackage decoder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("forge")
    s.add_argument("--top", type=int, default=0); s.add_argument("--min-size", type=int, default=0)
    s.add_argument("--flag", type=int, default=None)
    i = sub.add_parser("info"); i.add_argument("forge"); i.add_argument("index", type=int)
    d = sub.add_parser("dump"); d.add_argument("forge"); d.add_argument("index", type=int)
    d.add_argument("out"); d.add_argument("--lang", type=int, default=None)
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "scan":
        return cmd_scan(a.forge, a.top, a.min_size, a.flag)
    if a.cmd == "info":
        return cmd_info(a.forge, a.index)
    if a.cmd == "dump":
        return cmd_dump(a.forge, a.index, a.out, a.lang)
    if a.cmd == "selftest":
        return cmd_selftest()


if __name__ == "__main__":
    sys.exit(main())
