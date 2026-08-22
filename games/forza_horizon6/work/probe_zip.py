"""Verify the ForzaTech ZIP invariant so the writer can reproduce it exactly.

Hypothesis: every entry's compressed data starts on a 4096-byte boundary; the
LOCAL header's `extra` is grown to pad up to it, and the CENTRAL directory
carries a private extra record 0x1123 {u32 alignedDataOffset}.
"""
import os, sys, struct, zipfile, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Games\Forza Horizon 6\media\Stripped\StringTables\EN.zip"

z = zipfile.ZipFile(P)
data = open(P, "rb").read()
print(f"{P}\n  size {len(data):,}  entries {len(z.infolist())}")

align = collections.Counter()
extra_ids = collections.Counter()
mismatch = 0
lh_extra = []
for i in z.infolist():
    # central-directory extra
    off = None
    p = 0
    while p + 4 <= len(i.extra):
        hid, hsz = struct.unpack_from("<HH", i.extra, p)
        extra_ids[hex(hid)] += 1
        if hid == 0x1123 and hsz == 4:
            off = struct.unpack_from("<I", i.extra, p + 4)[0]
        p += 4 + hsz
    sig, ver, flg, meth, t, d, crc, cs, us, nl, el = struct.unpack_from(
        "<IHHHHHIIIHH", data, i.header_offset)
    lh_data = i.header_offset + 30 + nl + el
    lh_extra.append(el)
    if off is not None:
        align[off % 4096] += 1
        if off != lh_data:
            mismatch += 1
print("  CD extra ids:", dict(extra_ids))
print("  alignedOffset %% 4096 ->", dict(align))
print(f"  alignedOffset == localHeaderEnd on {len(z.infolist()) - mismatch}/{len(z.infolist())}")
print(f"  local-header extra len: min {min(lh_extra)} max {max(lh_extra)}")

# does the FIRST entry start at 4096, and is everything contiguous+ordered?
infos = sorted(z.infolist(), key=lambda i: i.header_offset)
prev_end = 0
gaps = 0
for i in infos:
    off = struct.unpack_from("<I", i.extra, 4)[0]
    if i.header_offset < prev_end:
        gaps += 1
    prev_end = off + i.compress_size
print(f"  entries ordered by header_offset, overlaps {gaps}")
print(f"  first entry: header@{infos[0].header_offset} data@"
      f"{struct.unpack_from('<I', infos[0].extra, 4)[0]}")
eocd = data.rfind(b"PK\x05\x06")
cd_off = struct.unpack_from("<I", data, eocd + 16)[0]
print(f"  central directory @ {cd_off:,}  (last data end {prev_end:,})")
