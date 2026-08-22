#!/usr/bin/env python3
"""
acbf_walk.py -- linear chunk walker for AC Black Flag Resynced scimitar-v50
.forge archives.  Read-only.

v50's TOC layout differs from v42, but the per-resource CHUNK format is
identical (magic 0x57FBAA33 + const 0x1004FA99, 0x1F-byte header, Oodle-Kraken
payload, lead 0x8C).  So instead of parsing the (not-yet-cracked) v50 TOC we
walk the file chunk-by-chunk:

  - at a position, if the chunk magic matches -> read {uncomp, comp}, decode
    (stored if comp==uncomp), emit; advance past the payload.
  - if the magic does NOT match -> we are at a resource-boundary descriptor;
    scan forward to the next magic, recording the gap bytes (the inter-resource
    header) so the descriptor layout can be reverse-engineered.

Commands:
  python acbf_walk.py scan   "<forge>" [--start 0x41a] [--max-bytes N]
        walk + report: #chunks, #resource gaps, gap-size histogram, decoded MB
  python acbf_walk.py grep   "<forge>" <needle-hex-or-ascii> [--start ...]
        walk, decode, and report every resource whose decoded bytes contain the
        needle (for locating LocalizationPackage / Arabic text)
  python acbf_walk.py dumpres "<forge>" <gap_index> "<out.bin>"
        decode the single resource that starts at the Nth gap and write it
"""
import sys
import os
import struct
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "acshadows", "tools"))
os.environ.setdefault("ACS_OODLE_DLL", r"C:\Games\Battlefield 6\oo2core_9_win64.dll")

MAGIC = 0x57FBAA33
MAGIC_LE = struct.pack("<I", MAGIC)
CONST = 0x1004FA99
HDR = 0x1F
DEFAULT_START = 0x41a


def iter_chunks(data, start, end):
    """Yield (pos, uncomp, comp, payload_off) for every chunk magic at `pos`,
    and ('gap', gap_start, gap_end, None) for a run with no magic.  Walk is
    strictly linear: after a chunk we look for the magic exactly at the next
    byte; if absent we scan forward to the next magic and emit a gap."""
    pos = start
    while pos + HDR <= end:
        if struct.unpack_from("<I", data, pos)[0] == MAGIC:
            uncomp = struct.unpack_from("<I", data, pos + 0x13)[0]
            comp = struct.unpack_from("<I", data, pos + 0x17)[0]
            payload = pos + HDR
            if comp == 0 or comp > end - payload or uncomp == 0 or uncomp > (1 << 26):
                # implausible -> treat this magic as coincidental, scan on
                nxt = data.find(MAGIC_LE, pos + 4, end)
                if nxt == -1:
                    yield ("gap", pos, end, None); return
                yield ("gap", pos, nxt, None); pos = nxt; continue
            yield ("chunk", pos, uncomp, comp)
            pos = payload + comp
        else:
            nxt = data.find(MAGIC_LE, pos, end)
            if nxt == -1:
                yield ("gap", pos, end, None); return
            if nxt != pos:
                yield ("gap", pos, nxt, None)
            pos = nxt


def content_end(data):
    e = len(data)
    while e > 0 and data[e - 1] == 0:
        e -= 1
    return e


def cmd_scan(path, start, max_bytes):
    data = open(path, "rb").read()
    end = content_end(data)
    n_chunk = n_gap = 0
    stored = comp_chunks = 0
    decoded = 0
    gap_sizes = {}
    first_gaps = []
    for ev in iter_chunks(data, start, end):
        if ev[0] == "chunk":
            _, pos, uncomp, comp = ev
            n_chunk += 1
            decoded += uncomp
            if comp == uncomp:
                stored += 1
            else:
                comp_chunks += 1
        else:
            _, gs, ge, _ = ev
            n_gap += 1
            g = ge - gs
            gap_sizes[g] = gap_sizes.get(g, 0) + 1
            if len(first_gaps) < 12:
                first_gaps.append((gs, g, data[gs:gs + min(g, 40)]))
    print(f"{os.path.basename(path)}  size={len(data):,} content_end=0x{end:x} start=0x{start:x}")
    print(f"  chunks={n_chunk:,} (stored={stored:,} kraken={comp_chunks:,})  "
          f"resource-gaps={n_gap:,}  decoded={decoded/1e6:.1f} MB")
    print(f"  gap-size histogram (bytes:count), top 15:")
    for g, c in sorted(gap_sizes.items(), key=lambda kv: -kv[1])[:15]:
        print(f"    {g:>6} : {c}")
    print(f"  first {len(first_gaps)} gaps (offset, size, head bytes):")
    for gs, g, head in first_gaps:
        print(f"    @0x{gs:x} size={g:<4} {' '.join(f'{b:02x}' for b in head)}")
    return 0


def cmd_grep(path, needle, start, max_res):
    from acs_oodle import Oodle
    o = Oodle()
    data = open(path, "rb").read()
    end = content_end(data)
    if all(c in "0123456789abcdefABCDEF" for c in needle) and len(needle) % 2 == 0:
        pat = bytes.fromhex(needle)
        # also try as ascii
        pats = [pat, needle.encode()]
    else:
        pats = [needle.encode(), needle.encode("utf-16-le")]
    # group chunks into resources: a resource = the run of chunks between gaps
    res_start = None
    buf = bytearray()
    res_idx = 0
    hits = 0
    def flush(rstart):
        nonlocal hits
        for p in pats:
            if p and p in buf:
                off = buf.find(p)
                ctx = bytes(buf[max(0, off - 24): off + len(p) + 40])
                print(f"  HIT res#{res_idx} @gap0x{rstart:x} declen={len(buf)}  "
                      f"needle@{off}: {ctx!r}")
                hits += 1
                return True
        return False
    for ev in iter_chunks(data, start, end):
        if ev[0] == "chunk":
            _, pos, uncomp, comp = ev
            payload = data[pos + HDR: pos + HDR + comp]
            try:
                buf += payload if comp == uncomp else o.decompress(payload, uncomp)
            except Exception:
                pass
            if res_start is None:
                res_start = pos
        else:
            if buf:
                flush(res_start if res_start is not None else 0)
                res_idx += 1
                buf = bytearray()
                res_start = None
                if hits >= max_res:
                    break
    if buf:
        flush(res_start if res_start is not None else 0)
    print(f"  total hits: {hits}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("forge")
    s.add_argument("--start", default=hex(DEFAULT_START)); s.add_argument("--max-bytes", type=int, default=0)
    g = sub.add_parser("grep"); g.add_argument("forge"); g.add_argument("needle")
    g.add_argument("--start", default=hex(DEFAULT_START)); g.add_argument("--max-res", type=int, default=40)
    a = ap.parse_args()
    start = int(a.start, 0)
    if a.cmd == "scan":
        return cmd_scan(a.forge, start, a.max_bytes)
    if a.cmd == "grep":
        return cmd_grep(a.forge, a.needle, start, a.max_res)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
