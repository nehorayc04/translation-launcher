#!/usr/bin/env python3
"""
acbf_findloc.py -- decode every 0x57FBAA33 chunk in a v50 forge and report the
chunks whose DECOMPRESSED bytes contain real localized text, so the loc record
format can be reverse-engineered on real decoded bytes.

For each chunk that decodes we test two signals:
  (a) a clean Arabic UTF-16LE run  (>= RUN consecutive U+0600..06FF code units)
  (b) the AC-Shadows loc field tag  0xFADE9F44  (may or may not survive in v50)

Reports the chunk's file offset, decoded size, and a hex+utf16 window around the
first Arabic run so we can inspect the surrounding record header.

  python acbf_findloc.py "<forge>" [--start 0x41a] [--run 6] [--limit 30]
"""
import sys
import os
import struct
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "acshadows", "tools"))
os.environ.setdefault("ACS_OODLE_DLL", r"C:\Games\Battlefield 6\oo2core_9_win64.dll")

MAGIC = 0x57FBAA33
MAGIC_LE = struct.pack("<I", MAGIC)
HDR = 0x1F
TAG = struct.pack("<I", 0xFADE9F44)


def content_end(data):
    e = len(data)
    while e > 0 and data[e - 1] == 0:
        e -= 1
    return e


def arabic_run(data, run):
    """Return offset of the first run of >=`run` consecutive UTF-16LE code units
    in U+0600..06FF, else -1.  Cheap: scan for high-byte 0x06 at even stride."""
    n = len(data) - 1
    i = 0
    while i < n - run * 2:
        # candidate: bytes[i+1]==0x06 (high byte of an Arabic code unit)
        if data[i + 1] == 0x06:
            k = 0
            while i + k * 2 + 1 < n and data[i + k * 2 + 1] == 0x06:
                k += 1
            if k >= run:
                return i
            i += (k + 1) * 2
        else:
            i += 1
    return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("--start", default="0x41a")
    ap.add_argument("--run", type=int, default=6)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--max-decode-mb", type=int, default=0, help="stop after decoding N MB (0=all)")
    a = ap.parse_args()
    from acs_oodle import Oodle
    o = Oodle()
    data = open(a.forge, "rb").read()
    end = content_end(data)
    start = int(a.start, 0)
    pos = start
    n_chunk = n_dec = 0
    dec_bytes = 0
    hits = 0
    tag_hits = 0
    print(f"{os.path.basename(a.forge)} size={len(data):,} content_end=0x{end:x}")
    while pos + HDR <= end and hits < a.limit:
        if struct.unpack_from("<I", data, pos)[0] != MAGIC:
            nxt = data.find(MAGIC_LE, pos + 1, end)
            if nxt == -1:
                break
            pos = nxt
            continue
        uncomp = struct.unpack_from("<I", data, pos + 0x13)[0]
        comp = struct.unpack_from("<I", data, pos + 0x17)[0]
        payload_off = pos + HDR
        if comp == 0 or comp > end - payload_off or uncomp == 0 or uncomp > (1 << 26):
            nxt = data.find(MAGIC_LE, pos + 4, end)
            if nxt == -1:
                break
            pos = nxt
            continue
        payload = data[payload_off: payload_off + comp]
        n_chunk += 1
        try:
            dec = payload if comp == uncomp else o.decompress(payload, uncomp)
            n_dec += 1
            dec_bytes += len(dec)
        except Exception:
            pos = payload_off + comp
            continue
        # signals
        tp = dec.find(TAG)
        ar = arabic_run(dec, a.run)
        if tp >= 0:
            tag_hits += 1
        if ar >= 0 or tp >= 0:
            hits += 1
            where = ar if ar >= 0 else tp
            lo = max(0, where - 32)
            win = dec[lo: where + 64]
            txt = dec[where: where + 80].decode("utf-16-le", "replace")
            print(f"\n[{hits}] chunk@0x{pos:x} comp={comp} uncomp={uncomp} dec_len={len(dec)} "
                  f"{'TAG@'+str(tp) if tp>=0 else ''} {'AR@'+str(ar) if ar>=0 else ''}")
            print("    hex: " + " ".join(f"{b:02x}" for b in win))
            print("    utf16: " + repr(txt[:60]))
        pos = payload_off + comp
        if a.max_decode_mb and dec_bytes > a.max_decode_mb * 1_000_000:
            print(f"\n(stopped after {dec_bytes/1e6:.0f} MB decoded)")
            break
    print(f"\nchunks={n_chunk:,} decoded={n_dec:,} dec_bytes={dec_bytes/1e6:.1f}MB "
          f"loc-hits={hits} tag-hits={tag_hits}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
