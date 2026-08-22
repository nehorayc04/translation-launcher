#!/usr/bin/env python3
"""Minimal-rebuild loc payload: reuse original per-string code bytes, re-encode only edits,
LZO-compress the CFD => delta-0 in-place fit. Offline test + build."""
import sys, struct, zlib
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
import acu_loc as L
import lzallright

_MAGIC = 0x1004FA9957FBAA33


def load_orig(path):
    orig = open(path, "rb").read()
    lang, payload = L._payload_from_data(orig)
    maxIndex = struct.unpack_from(">H", payload, 0)[0]
    fragCount = struct.unpack_from(">H", payload, 2)[0]
    fr = [struct.unpack_from(">HH", payload, 4 + i * 4) for i in range(fragCount)]
    fs = [None] * fragCount
    sys.setrecursionlimit(1 << 20)

    def df(i):
        if fs[i] is not None:
            return fs[i]
        r, l = fr[i]
        s = "" if (l == 0 and r == 0) else (chr(r) if l == 0 else df(l) + df(r))
        fs[i] = s
        return s
    for i in range(fragCount):
        df(i)
    return orig, payload, maxIndex, fragCount, fr, fs


def decode_capture(payload, maxIndex, fragCount):
    """Return (orig_tables=[(firstID,[ids...])], code_by_id, strings)."""
    fp0 = 4 + fragCount * 4
    tc = struct.unpack_from(">H", payload, fp0)[0]
    base = fp0 + 2
    tables = [struct.unpack_from(">III", payload, base + i * 12) for i in range(tc)]
    fs_strings = {}
    # need decoded fragment strings to reconstruct text; caller passes fs separately for edits
    orig_tables = []
    code_by_id = {}
    for fid, ho, eo in tables:
        ep = eo
        ec = struct.unpack_from(">H", payload, ep)[0]
        ep += 2
        ids = [fid]
        offs = [struct.unpack_from(">H", payload, ep)[0]]
        ep += 2
        for _ in range(ec):
            ids.append(fid + struct.unpack_from(">H", payload, ep)[0])
            ep += 2
            offs.append(struct.unpack_from(">H", payload, ep)[0])
            ep += 2
        pos = ho
        cons = 0
        for idd, off in zip(ids, offs):
            start = pos
            while cons < off:
                by = payload[pos]
                pos += 1
                cons += 1
                if by < maxIndex:
                    pass
                elif by == 255:
                    pos += 2
                    cons += 2
                else:
                    pos += 1
                    cons += 1
            code_by_id[idd] = payload[start:pos]
        orig_tables.append((fid, ids))
    return orig_tables, code_by_id


def make_encoder(fs, fragCount, maxIndex):
    indexMask = maxIndex * 255
    fragidx = {}
    for j, s in enumerate(fs):
        if j > 0 and s and s not in fragidx:
            fragidx[s] = j
    maxfl = max(len(s) for s in fs)
    extra, extra_list = {}, []

    def frag_for_char(c):
        if c in fragidx:
            return fragidx[c]
        if c in extra:
            return extra[c]
        j = fragCount + len(extra_list)
        extra[c] = j
        extra_list.append(c)
        return j

    def emit(out, j):
        e = j - 1
        if e < maxIndex:
            out.append(e)
        else:
            v = e + indexMask
            hi = v >> 8
            if maxIndex <= hi <= 254:      # 2-byte high form (decoder: (hi<<8|lo)-indexMask)
                out.append(hi)
                out.append(v & 0xff)
            else:                          # 255-escape 3-byte form (decoder: signed short)
                out.append(255)
                out += struct.pack(">h", e)

    def enc(s):
        out = bytearray()
        i, n = 0, len(s)
        while i < n:
            best = None
            hi = min(maxfl, n - i)
            for L2 in range(hi, 1, -1):
                if s[i:i + L2] in fragidx:
                    best = (fragidx[s[i:i + L2]], L2)
                    break
            if best is None:
                best = (frag_for_char(s[i]), 1)
            emit(out, best[0])
            i += best[1]
        return bytes(out)

    return enc, extra_list


def rebuild_payload(maxIndex, fragCount, fr, extra_list, orig_tables, code_by_id):
    out = bytearray()
    out += struct.pack(">HH", maxIndex, fragCount + len(extra_list))
    for j in range(fragCount):
        out += struct.pack(">HH", *fr[j])
    for c in extra_list:
        out += struct.pack(">HH", ord(c), 0)
    out += struct.pack(">H", len(orig_tables))
    hdr = len(out)
    out += b"\x00" * (12 * len(orig_tables))
    tinfo = []
    for fid, ids in orig_tables:
        eo = len(out)
        out += struct.pack(">H", len(ids) - 1)
        out += b"\x00" * (len(ids) * 4 + 2)
        ho = len(out)
        cum, acc = [], 0
        for idd in ids:
            cb = code_by_id[idd]
            out += cb
            acc += len(cb)
            cum.append(acc)
        struct.pack_into(">H", out, eo + 2, cum[0] & 0xffff)
        wp = eo + 4
        for i in range(1, len(ids)):
            struct.pack_into(">H", out, wp, (ids[i] - fid) & 0xffff)
            wp += 2
            struct.pack_into(">H", out, wp, cum[i] & 0xffff)
            wp += 2
        tinfo.append((fid, ho, eo))
    hp = hdr
    for fid, ho, eo in tinfo:
        struct.pack_into(">III", out, hp, fid, ho, eo)
        hp += 12
    return bytes(out)


def make_cfd_lzo(content, compinfo7):
    maxU = struct.unpack_from("<H", compinfo7, 3)[0] or 0xFFF0
    C = lzallright.LZOCompressor()
    out = bytearray()
    out += struct.pack("<Q", _MAGIC)
    out += compinfo7
    blocks = [content[i:i + maxU] for i in range(0, len(content), maxU)] or [b""]
    out += struct.pack("<i", len(blocks))
    comps = []
    for b in blocks:
        c = bytes(C.compress(bytes(b)))
        if len(c) >= len(b):
            c = bytes(b)      # store (uncomp==comp)
        comps.append(c)
        out += struct.pack("<HH", len(b), len(c))
    for c in comps:
        out += struct.pack("<I", zlib.crc32(c) & 0xffffffff)
        out += c
    return bytes(out)


def build(orig_path, edits, out_path=None):
    orig, payload, maxIndex, fragCount, fr, fs = load_orig(orig_path)
    orig_tables, code_by_id = decode_capture(payload, maxIndex, fragCount)
    enc, extra_list = make_encoder(fs, fragCount, maxIndex)
    for k, v in edits.items():
        code_by_id[k] = enc(v)
    newpay = rebuild_payload(maxIndex, fragCount, fr, extra_list, orig_tables, code_by_id)
    p1, _ = L.cfd_decompress(orig, 0)
    p2, content = L.cfd_decompress(orig, p1)
    sig = orig[p2:]
    bo = 12 + struct.unpack_from("<i", content, 8)[0]
    P = oc = None
    for off in range(bo, bo + 96):
        v = struct.unpack_from("<i", content, off)[0]
        if 1000 < v < len(content) - off and content[off + 4] == 0 and 128 <= content[off + 5] <= 255:
            P, oc = off, v
            break
    newcontent = content[:P] + struct.pack("<i", len(newpay)) + newpay + content[P + 4 + oc:]
    # CRITICAL: content[4:8] is a size field (region-after-header = len(content) - X). Update it.
    field2_orig = struct.unpack_from("<i", content, 4)[0]
    X = len(content) - field2_orig
    newcontent = newcontent[:4] + struct.pack("<i", len(newcontent) - X) + newcontent[8:]
    newdata = orig[:p1] + make_cfd_lzo(newcontent, orig[p1 + 8:p1 + 15]) + sig
    if out_path:
        open(out_path, "wb").write(newdata)
    return orig, newpay, newdata, len(payload)


if __name__ == "__main__":
    from acu_rtl import to_visual
    edits = {521007: "HE-PIPELINE-OK", 497291: "PIPE-OK-123",
             532106: to_visual("אפשרויות"), 558658: to_visual("חזור"),
             456237: to_visual("כתוביות"), 520544: to_visual("תפריט ראשי"),
             544279: to_visual("עברית OK")}
    orig, newpay, newdata, oldpaylen = build(sys.argv[1], edits, r"C:\tmp\acuwork\loc_english_HE_lzo.data")
    print(f"payload: {oldpaylen} -> {len(newpay)} ({len(newpay)-oldpaylen:+d})")
    print(f".data:   {len(orig)} -> {len(newdata)} (slot 345123, FITS in-place: {len(newdata) <= 345123})")
    dec = L.decode_payload(L._payload_from_data(newdata)[1])
    ok = all(dec.get(k) == v for k, v in edits.items())
    print(f"re-decode: {len(dec)} strings, edits applied: {ok}")
    for k, v in edits.items():
        print(f"    {k}: {dec.get(k)!r}")
