#!/usr/bin/env python3
"""
acu_loc.py — AC Unity (AnvilNext v27) LocalizationPackage codec, pure Python.

Ported from the decompiled AnvilToolkit source (c:\\tmp\\anvil_src\\ :
LocalizationPackage.cs / IndexedData.cs / StringTable.cs / StringFragment.cs /
CompressedFileData.cs / DataBlock.cs / CompressionInfo.cs / ScimitarClass.cs).

VALIDATED 2026-07-01: decode of the real DataPC.forge `TLocalizationPackage_English`
`.data` produced 8,999 readable UI strings ("FULL SYNCHRONIZATION COMPLETED",
"PRESS [Y] to activate EAGLE VISION", ...). Encode→decode round-trips.

Stack (a forge resource IS a `.data` blob):
  .data = CompressedFileData(meta) + CompressedFileData(content) + signature
  CompressedFileData = u64 magic 0x1004FA9957FBAA33 + CompressionInfo(i16 ver,u8 algo,
    u16 maxU,u16 maxC) + i32 blockCount + blockInfo[u16 uncomp,u16 comp]*N +
    (per block: u32 crc32 + comp bytes; STORED if uncomp==comp else LZO(algo) decompress)
    Unity algo=1 => lzo1x.  (LZO via `lzallright`; write path can STORE blocks => no LZO compress.)
  content.Data = sub-file container: u32 id, i32 count, i32 namelen, name,
    fileheader(1), skip(1), ClassID u64, Hash u32, then LocalizationPackage payload:
    Type i32, Language u32, skip 12, u32 marker, i32 count, BIG-ENDIAN payload.
  payload (BE) = u16 MaxIndexSize, u16 fragCount, [u16 rightChar,u16 leftIdx]*frag,
    u16 tableCount, [u32 firstID,u32 headersOff,u32 entriesOff]*table, then per table
    an entries block + a char-index code stream (see decode/encode below).

REMAINING to a deploy: re-wrap payload -> ScimitarClass header -> CFD (stored) ->
sub-file -> `.data`, then put back into the forge (append-relocate or full Serialize27),
+ Hebrew font glyphs (.ffd/DDS) + VISUAL reversal. See PIPELINE.md.
"""
import struct
import sys

try:
    import lzallright
    _LZO = lzallright.LZOCompressor()
    def _lzo_dec(data, n):
        return _LZO.decompress(bytes(data), output_size_hint=n)
except Exception:  # pragma: no cover
    _lzo_dec = None

_MAGIC = 0x1004FA9957FBAA33


def cfd_decompress(d, pos):
    """Read one CompressedFileData at `pos`; return (next_pos, decompressed_bytes)."""
    assert struct.unpack_from("<Q", d, pos)[0] == _MAGIC, "bad CFD magic"
    pos += 8
    ver, algo, maxU, maxC = struct.unpack_from("<hBHH", d, pos); pos += 7
    n = struct.unpack_from("<i", d, pos)[0]; pos += 4
    bi = pos; pos += n * 4
    out = bytearray()
    for i in range(n):
        uncomp, comp = struct.unpack_from("<HH", d, bi + i * 4)
        pos += 4  # per-block crc32
        payload = d[pos:pos + comp]; pos += comp
        out += payload if uncomp == comp else _lzo_dec(payload, uncomp)
    return pos, bytes(out)


def _payload_from_data(dat):
    """Extract (language, payload_bytes) from a full `.data` resource blob."""
    p, _meta = cfd_decompress(dat, 0)
    p, content = cfd_decompress(dat, p)
    body_off = 12 + struct.unpack_from("<i", content, 8)[0]   # after id,count,namelen,name
    for off in range(body_off, body_off + 96):
        v = struct.unpack_from("<i", content, off)[0]
        if 1000 < v < len(content) - off and content[off + 4] == 0 and 128 <= content[off + 5] <= 255:
            language = struct.unpack_from("<I", content, off - 24)[0]
            return language, content[off + 4: off + 4 + v]
    raise ValueError("LocalizationPackage payload not found")


def decode_payload(payload):
    """BE char-index payload -> {id: string}."""
    maxIndex = struct.unpack_from(">H", payload, 0)[0]; indexMask = maxIndex * 255
    fragCount = struct.unpack_from(">H", payload, 2)[0]
    fr = [struct.unpack_from(">HH", payload, 4 + i * 4) for i in range(fragCount)]
    fp = 4 + fragCount * 4
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
    tc = struct.unpack_from(">H", payload, fp)[0]; fp += 2
    tables = [struct.unpack_from(">III", payload, fp + i * 12) for i in range(tc)]
    res = {}
    for fid, ho, eo in tables:
        ep = eo; ec = struct.unpack_from(">H", payload, ep)[0]; ep += 2
        ids = [fid]; offs = [struct.unpack_from(">H", payload, ep)[0]]; ep += 2
        for _ in range(ec):
            ids.append(fid + struct.unpack_from(">H", payload, ep)[0]); ep += 2
            offs.append(struct.unpack_from(">H", payload, ep)[0]); ep += 2
        pos = ho; cons = 0
        for idd, off in zip(ids, offs):
            sb = []
            while cons < off:
                by = payload[pos]; pos += 1; cons += 1
                if by < maxIndex:
                    sb.append(fs[by + 1])
                elif by == 255:
                    num = struct.unpack_from(">h", payload, pos)[0]; pos += 2; cons += 2; sb.append(fs[num + 1])
                else:
                    num2 = ((by << 8) | payload[pos]); pos += 1; cons += 1; num2 -= indexMask; sb.append(fs[num2 + 1])
            res[idd] = "".join(sb)
    return res


def encode_payload(strings_by_id, maxIndex=255):
    """{id: string} -> BE char-index payload (single-char fragment dict, AnvilToolkit-style)."""
    chars = set()
    for s in strings_by_id.values():
        chars.update(s)
    frags = [""] + sorted(chars)
    idx = {c: i for i, c in enumerate(frags)}
    items = sorted(strings_by_id.items())
    tables = []; cur = []
    for idd, s in items:
        if not cur:
            cur = [(idd, s)]
        elif (idd - cur[0][0]) < 32767 and len(cur) < 50:
            cur.append((idd, s))
        else:
            tables.append(cur); cur = [(idd, s)]
    if cur:
        tables.append(cur)
    out = bytearray()
    out += struct.pack(">HH", maxIndex, len(frags))
    for c in frags:
        out += struct.pack(">HH", ord(c) if c else 0, 0)
    out += struct.pack(">H", len(tables))
    hdr_pos = len(out); out += b"\x00" * (12 * len(tables))
    tinfo = []
    for tbl in tables:
        entriesOffset = len(out)
        out += struct.pack(">H", len(tbl) - 1)
        out += b"\x00" * (len(tbl) * 4 + 2)
        headersOffset = len(out)
        offs = []
        for _idd, s in tbl:
            o = 0
            for ch in s:
                n = idx[ch]
                if n < 255:
                    out.append((n - 1) & 0xff); o += 1
                else:
                    out.append(255); out += struct.pack(">h", n - 1); o += 3
            offs.append(o)
        firstID = tbl[0][0]
        cum = []; acc = 0
        for o in offs:
            acc += o; cum.append(acc)
        struct.pack_into(">H", out, entriesOffset + 2, cum[0] & 0xffff)
        wp = entriesOffset + 4
        for i in range(1, len(tbl)):
            struct.pack_into(">H", out, wp, (tbl[i][0] - firstID) & 0xffff); wp += 2
            struct.pack_into(">H", out, wp, cum[i] & 0xffff); wp += 2
        tinfo.append((firstID, headersOffset, entriesOffset))
    hp = hdr_pos
    for fid, ho, eo in tinfo:
        struct.pack_into(">III", out, hp, fid, ho, eo); hp += 12
    return bytes(out)


def decode_data_file(path):
    """A forge-extracted `.data` -> {id: string}."""
    _lang, payload = _payload_from_data(open(path, "rb").read())
    return decode_payload(payload)


if __name__ == "__main__":
    import json
    strings = decode_data_file(sys.argv[1])
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"# {len(strings)} strings")
    if len(sys.argv) > 2:
        json.dump({str(k): v for k, v in strings.items()}, open(sys.argv[2], "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        print("wrote", sys.argv[2])
    else:
        for k, v in list(strings.items())[:30]:
            print(f"  [{k}] {v!r}")
