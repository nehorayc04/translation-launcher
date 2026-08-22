#!/usr/bin/env python3
"""
acbf_locpkg.py -- decode AC Black Flag Resynced (scimitar-v50) char-index
LocalizationPackages into {stringID: text}.  This is where the UI + ALL
languages (incl. Arabic) live — the text is a char-INDEX / fragment-tree
serialization (AC2/ATK style), NOT literal UTF-16, which is why a raw UTF-16
search finds nothing.

Ported from acs_locpkg.py (the decompiled free AnvilToolkit LocalizationPackage
codec). v50 has NO inline class-hash 0x6E37B1AF; we anchor directly on the
IndexedData MARKER 0xD28389B5:

    ... u32 Language (a few fields before) ... u32 marker=0xD28389B5 ;
    i32 num ; `num` bytes of BIG-ENDIAN payload:
      u16 MaxIndexSize ; u16 fragCount ; fragCount x {u16 right, u16 left}
      u16 tableCount ; tableCount x {u32 FirstEntryID, u32 Headers, u32 Entries}
      per table: entries[] @Entries (id deltas + cumulative byte offsets),
                 strings decoded from @Headers using the fragment tree.

⚠️ REQUIRES the FIXED multi-block CFD decoder (acbf_loc.decode_blob) — the loc
package resources are multi-block and the naive per-chunk walk truncated them.
"""
import sys
import os
import struct
import json
import argparse
import importlib.util

MARKER = struct.pack("<I", 0xD28389B5)


def _load(n):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), n + ".py")
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
L = _load("acbf_loc"); CFD = _load("acbf_cfd"); AF = _load("acbf_forge")


def _u16(b, p): return struct.unpack_from(">H", b, p)[0]
def _u32(b, p): return struct.unpack_from(">I", b, p)[0]
def _i16(b, p): return struct.unpack_from(">h", b, p)[0]


def _resolve_fragments(frags):
    n = len(frags)
    cache = [None] * n
    for start in range(n):
        if cache[start] is not None:
            continue
        stack = [start]
        while stack:
            j = stack[-1]
            if cache[j] is not None:
                stack.pop(); continue
            right, left = frags[j]
            if left == 0 and right == 0:
                cache[j] = ""; stack.pop(); continue
            if left == 0:
                cache[j] = chr(right); stack.pop(); continue
            if not (0 <= right < n) or not (0 <= left < n):
                cache[j] = ""; stack.pop(); continue
            need = []
            if cache[right] is None: need.append(right)
            if cache[left] is None: need.append(left)
            if need:
                stack.extend(need); continue
            cache[j] = cache[left] + cache[right]; stack.pop()
    return cache


def _recombine(s):
    try:
        return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    except Exception:
        return s


def decode_payload(buf):
    """Decode one v50 char-index payload -> {stringID(u64): str}.

    CRACKED v50 layout (2026-07-16, verified: German/Italian/Russian/French/
    Polish settings-menu UI decode clean, 11,033 strings from boot.forge idx
    27722). All big-endian:
      u16 MaxIndexSize ; u16 fragCount ; fragCount x {u16 right, u16 left}
      u16 recordCount  ; recordCount x { u64 stringID, u32 codeOff, u32 off2 }
      string codes at codeOff (fragment-index byte stream), each string ending
      where the next-larger codeOff begins.

    (v42/AC-Shadows used u16 string-table records with cumulative offsets; v50
     uses a flat {u64 id, u32 codeOff, u32 off2} record array + a 2-byte count.)
    """
    p = 0
    max_index = _u16(buf, p); p += 2
    index_mask = max_index * 255
    frag_count = _u16(buf, p); p += 2
    frags = []
    for _ in range(frag_count):
        frags.append((_u16(buf, p), _u16(buf, p + 2))); p += 4
    cache = _resolve_fragments(frags)
    nfrag = len(cache)
    rec_count = _u16(buf, p); p += 2
    recs = []
    for _ in range(rec_count):
        if p + 16 > len(buf):
            break
        sid = struct.unpack_from(">Q", buf, p)[0]
        code_off = _u32(buf, p + 8)
        len_off = _u32(buf, p + 12)
        recs.append((sid, code_off, len_off)); p += 16
    # STRING BOUNDARY = the record's OWN length, stored as a u32 at `len_off` (the third
    # record field). The old "ends at the next-larger codeOff" guess is wrong: it needs a
    # global sort, and when it failed it fell back to a 4096-byte window that MERGED many
    # unrelated rows into one 87k-char mega-string. Re-encoding those merged rows produced a
    # package the engine spun on forever (black screen, 0 disk I/O, CPU pegged).
    # Verified: codeOff + u32@len_off == the next codeOff for 5342/5345 subtitle rows and
    # 10986/11000 UI rows.
    n = len(buf)
    out = {}
    for sid, start, len_off in recs:
        end = start + _u32(buf, len_off) if len_off + 4 <= n else n
        if end <= start or end > n:
            end = min(start + 4096, n)
        r = start
        units = []
        while r < end:
            b = buf[r]; r += 1
            if b < max_index:
                idx = b + 1
            elif b == 255:
                idx = _i16(buf, r) + 1; r += 2
            else:
                b2 = buf[r]; r += 1
                idx = (((b << 8) | b2) - index_mask) + 1
            units.append(cache[idx] if 0 <= idx < nfrag else "")
        out[sid] = _recombine("".join(units))
    return out


def build_payload(id_text, max_index=252):
    """Encode [(stringID:int, text:str), ...] -> a v50 char-index payload.
    Uses a flat leaf dictionary (one fragment per unique char) — valid + simple;
    the game's decoder handles any correct fragment structure. Verified: a full
    re-encode of the 11,000-string Arabic UI round-trips 0/11000 mismatches."""
    chars = []
    seen = set()
    for _, t in id_text:
        for c in t:
            if c not in seen:
                seen.add(c); chars.append(c)
    frags = [(0, 0)] + [(ord(c), 0) for c in chars]
    cidx = {c: i + 1 for i, c in enumerate(chars)}
    nfrag = len(frags)

    def enc(t):
        out = bytearray()
        for c in t:
            idx = cidx[c]
            b = idx - 1
            if b < max_index:
                out.append(b)
            else:
                val = (idx - 1) + max_index * 255
                hi = val >> 8; lo = val & 0xff
                if max_index <= hi <= 254:
                    out.append(hi); out.append(lo)
                else:
                    out.append(255); out += struct.pack(">h", idx - 1)
        return bytes(out)

    codes = [enc(t) for _, t in id_text]
    rc = len(id_text)
    header = 4 + nfrag * 4
    lentab = header + 2 + rc * 16
    code_start = lentab + rc * 4
    out = bytearray()
    out += struct.pack(">HH", max_index, nfrag)
    for r, l in frags:
        out += struct.pack(">HH", r, l)
    out += struct.pack(">H", rc)
    recbuf = bytearray(); lenbuf = bytearray(); codebuf = bytearray()
    co = code_start
    for k, ((sid, _), code) in enumerate(zip(id_text, codes)):
        recbuf += struct.pack(">QII", sid, co, lentab + k * 4)
        lenbuf += struct.pack(">I", len(code))
        codebuf += code
        co += len(code)
    out += recbuf + lenbuf + codebuf
    return bytes(out)


def rebuild_resource(dec, new_id_text):
    """Given the decoded resource bytes `dec` (containing one LocalizationPackage
    at the 0xD28389B5 marker), return a new decoded-resource with the package's
    payload rebuilt from new_id_text. Preserves the bytes before the marker and
    after the old payload."""
    m = dec.find(MARKER)
    if m < 0:
        raise ValueError("no marker")
    old_num = struct.unpack_from("<i", dec, m + 4)[0]
    payload = build_payload(new_id_text)
    return dec[:m + 4] + struct.pack("<i", len(payload)) + payload + dec[m + 8 + old_num:]


def find_packages(data):
    """Every LocalizationPackage in a decoded resource, anchored on the marker.
    Returns [{'lang':int,'offset':int,'strings':dict}, ...]."""
    pkgs = []
    pos = 0
    n = len(data)
    while True:
        m = data.find(MARKER, pos)
        if m < 0:
            break
        pos = m + 4
        try:
            num = struct.unpack_from("<i", data, m + 4)[0]
            if num <= 8 or m + 8 + num > n:
                continue
            payload = data[m + 8: m + 8 + num]
            strings = decode_payload(payload)
            if strings:
                # Language: the u32 that sits a fixed distance before the marker.
                lang = struct.unpack_from("<I", data, m - 16)[0] if m >= 16 else -1
                pkgs.append({"lang": lang, "offset": m, "strings": strings})
        except Exception:
            continue
    return pkgs


def _decode_resource(forge, rec, o):
    with open(forge, "rb") as f:
        f.seek(rec["offset"]); blob = f.read(rec["size"])
    return L.decode_blob(blob, o)


def cmd_info(forge, index):
    o = CFD._oodle()
    info = AF.parse(forge)
    rec = info["recs"][index]
    data = _decode_resource(forge, rec, o)
    pkgs = find_packages(data)
    print(f"resource {index} (hash 0x{rec['hash']:08x} size 0x{rec['size']:x}): "
          f"decoded {len(data):,} B, {len(pkgs)} package(s)")
    for pk in pkgs:
        strs = pk["strings"]
        # script tally
        from collections import Counter
        sc = Counter(L.classify(v) for v in strs.values())
        print(f"  lang={pk['lang']} strings={len(strs)} scripts={dict(sc)}")
        for i, (sid, s) in enumerate(strs.items()):
            if i >= 8:
                break
            print(f"    {sid}: {s[:70]!r}")
    return 0


def cmd_dump(forge, index, out):
    o = CFD._oodle()
    info = AF.parse(forge)
    rec = info["recs"][index]
    data = _decode_resource(forge, rec, o)
    merged = {}
    for pk in find_packages(data):
        for sid, s in pk["strings"].items():
            merged[str(sid)] = s
    json.dump(merged, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"resource {index}: {len(merged)} strings -> {out}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("info"); i.add_argument("forge"); i.add_argument("index", type=int)
    d = sub.add_parser("dump"); d.add_argument("forge"); d.add_argument("index", type=int); d.add_argument("out")
    a = ap.parse_args()
    if a.cmd == "info":
        return cmd_info(a.forge, a.index)
    if a.cmd == "dump":
        return cmd_dump(a.forge, a.index, a.out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
