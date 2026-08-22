#!/usr/bin/env python3
"""
acbf_locpkg2.py — FULL-FIDELITY parse/build for the v50 char-index LocalizationPackage.

What the older `acbf_locpkg` got wrong: it treated every record as one flat string and
derived the end from "the next-larger codeOff", falling back to a 4096-byte window when
that failed. For the SUBTITLE package that merged thousands of separate dialogue lines
into 87k-character mega-strings; re-encoding those made the engine spin forever (black
screen, CPU pegged, zero disk I/O).

The real layout — the third record field (`aux_off`) points at a per-record descriptor:

    aux_off -> [u16 count][u16 firstEnd][count x (u16 aux, u16 cumEnd)]
               line count = count + 1        entry size = 4 + 4*count
               count == 0 is just the 1-line case (firstEnd = its byte length)
               cumEnd is relative to the record's codeOff; the last one equals the
               record's whole code span EXACTLY (verified). `aux` is opaque (monotonic,
               believed to be timing) and is preserved verbatim on rebuild.

Payload:
    [u16 maxIndex][u16 fragCount][fragCount x (u16 right,u16 left)]
    [u16 recordCount][recordCount x (u64 stringID, u32 codeOff, u32 aux_off)]
    [aux descriptors region][code streams]

Records here are (stringID -> list[str]); a single-line record is a 1-element list.
"""
import struct

MARKER = struct.pack("<I", 0xD28389B5)


def _u16(b, p):
    return struct.unpack_from(">H", b, p)[0]


def _u32(b, p):
    return struct.unpack_from(">I", b, p)[0]


def _resolve_fragments(frags):
    """Reuse the proven resolver: a node may reference fragments with HIGHER indices, so a
    plain in-order loop silently yields "" for forward refs and DROPS characters."""
    import importlib.util as _ilu, os as _os
    _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "acbf_locpkg.py")
    _s = _ilu.spec_from_file_location("_acbf_locpkg", _p)
    _m = _ilu.module_from_spec(_s); _s.loader.exec_module(_m)
    return _m._resolve_fragments(frags)


def parse(buf):
    """-> dict(max_index, frags, records=[(sid, [lines], [aux])])"""
    max_index = _u16(buf, 0)
    frag_count = _u16(buf, 2)
    frags = [struct.unpack_from(">HH", buf, 4 + i * 4) for i in range(frag_count)]
    cache = _resolve_fragments(frags)
    nfrag = len(cache)
    idx_mask = max_index * 255
    p = 4 + frag_count * 4
    rec_count = _u16(buf, p); p += 2
    raw = []
    for _ in range(rec_count):
        sid = struct.unpack_from(">Q", buf, p)[0]
        raw.append((sid, _u32(buf, p + 8), _u32(buf, p + 12))); p += 16

    def decode(start, end):
        r = start; units = []
        while r < end:
            b = buf[r]; r += 1
            if b < max_index:
                idx = b + 1
            elif b == 255:
                idx = struct.unpack_from(">h", buf, r)[0] + 1; r += 2
            else:
                b2 = buf[r]; r += 1
                idx = (((b << 8) | b2) - idx_mask) + 1
            units.append(cache[idx] if 0 <= idx < nfrag else "")
        return "".join(units)

    records = []
    for sid, code_off, aux_off in raw:
        cnt = _u16(buf, aux_off)
        first = _u16(buf, aux_off + 2)
        pairs = [struct.unpack_from(">HH", buf, aux_off + 4 + i * 4) for i in range(cnt)]
        ends = [first] + [pr[1] for pr in pairs]
        aux = [pr[0] for pr in pairs]
        lines, prev = [], 0
        for e in ends:
            lines.append(decode(code_off + prev, code_off + e)); prev = e
        records.append((sid, lines, aux))
    return {"max_index": max_index, "records": records}


def build(records, max_index=252):
    """records: [(sid, [lines], [aux])] -> payload bytes. aux is preserved when present.

    INVARIANT (holds in every shipped package, 10/10 checked): fragCount > maxIndex.
    A flat-leaf dictionary can be far smaller than 252, and the engine appears to build a
    lookup of size maxIndex straight off the fragment table — so a small dictionary with a
    large maxIndex reads past its end. maxIndex is clamped below to keep the invariant."""
    # ---- fragment tree (BPE) -------------------------------------------------------
    # A flat one-leaf-per-char dictionary is ~1 byte/char, which both diverges from every
    # shipped package (146 leaves + 2,999 interior nodes) and blows the u16 cumEnd cap on
    # long dialogue records. Merge frequent adjacent pairs into interior fragments, exactly
    # like the shipped tables, so the code stream compresses.
    # Entry layout is (A, B) = (right, left); the resolver computes cache[B] + cache[A].
    from collections import Counter
    chars, seen = [], set()
    for _, lines, _ in records:
        for t in lines:
            for c in t:
                if c not in seen:
                    seen.add(c); chars.append(c)
    frags = [(0, 0)] + [(ord(c), 0) for c in chars]
    cidx = {c: i + 1 for i, c in enumerate(chars)}

    uniq = Counter()
    for _, lines, _ in records:
        for t in lines:
            uniq[t] += 1
    toks = {t: [cidx[c] for c in t] for t in uniq}

    # Target ~3000 fragments, matching the shipped tables (3,146 for the subtitle package).
    # Merging one pair per pass would need thousands of full recounts, so each pass applies
    # the top-K non-overlapping pairs at once.
    TARGET = 3000
    while len(frags) < TARGET:
        pairs = Counter()
        for t, w in uniq.items():
            seq = toks[t]
            for i in range(len(seq) - 1):
                pairs[(seq[i], seq[i + 1])] += w
        if not pairs:
            break
        batch, used = [], set()
        for (a, bn), cnt in pairs.most_common():
            if cnt < 2 or len(frags) + len(batch) >= TARGET:
                break
            if a in used or bn in used:
                continue
            used.add(a); used.add(bn)
            batch.append((a, bn))
            if len(batch) >= 64:
                break
        if not batch:
            break
        newid = {}
        for a, bn in batch:
            newid[(a, bn)] = len(frags)
            frags.append((bn, a))                # (A=right, B=left) -> cache[left]+cache[right]
        for t in list(toks):
            seq = toks[t]; out = []; i = 0
            while i < len(seq):
                if i + 1 < len(seq) and (seq[i], seq[i + 1]) in newid:
                    out.append(newid[(seq[i], seq[i + 1])]); i += 2
                else:
                    out.append(seq[i]); i += 1
            toks[t] = out
    max_index = max(1, min(max_index, len(frags) - 1))     # keep fragCount > maxIndex

    def enc(t):
        out = bytearray()
        for idx in toks[t]:
            b = idx - 1
            if b < max_index:
                out.append(b)
            else:
                val = b + max_index * 255
                hi, lo = val >> 8, val & 0xFF
                if max_index <= hi <= 254:
                    out.append(hi); out.append(lo)
                else:
                    out.append(255); out += struct.pack(">h", b)
        return bytes(out)

    enc_recs = []
    for sid, lines, aux in records:
        codes = [enc(t) for t in lines]
        enc_recs.append((sid, codes, aux))

    header = 4 + len(frags) * 4
    rec_start = header + 2
    aux_start = rec_start + len(enc_recs) * 16
    # aux region: 4 bytes for a single line, 2+4n for multi
    aux_sizes = [4 + 4 * (len(c) - 1) for _, c, a in enc_recs]
    code_start = aux_start + sum(aux_sizes)

    out = bytearray()
    out += struct.pack(">HH", max_index, len(frags))
    for r, l in frags:
        out += struct.pack(">HH", r, l)
    out += struct.pack(">H", len(enc_recs))
    recbuf, auxbuf, codebuf = bytearray(), bytearray(), bytearray()
    ao, co = aux_start, code_start
    for (sid, codes, aux), asz in zip(enc_recs, aux_sizes):
        recbuf += struct.pack(">QII", sid, co, ao)
        cum = len(codes[0])
        auxbuf += struct.pack(">HH", len(codes) - 1, cum)
        codebuf += codes[0]
        for i, c in enumerate(codes[1:]):
            cum += len(c)
            if cum > 0xFFFF:
                raise ValueError(
                    f"record {sid}: code stream {cum} B exceeds the u16 cumEnd limit "
                    f"(65535). The shipped package fits because its fragment tree is "
                    f"compact; a flat-leaf re-encode of long text does not.")
            auxbuf += struct.pack(">HH", aux[i] if i < len(aux) else cum, cum)
            codebuf += c
        co += cum
        ao += asz
    out += recbuf + auxbuf + codebuf
    return bytes(out)
