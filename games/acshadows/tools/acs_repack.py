#!/usr/bin/env python3
"""
acs_repack.py — inject text into an AC Shadows forge resource and write it back
IN PLACE (same on-disk size, delta-0 so the forge TOC never moves). Reversible:
backs up the original resource bytes to a sidecar before any write.

Record layout (verified on the settings loc resource): each string is
`... u32 length(in chars) ; UTF-16LE chars`. We replace the UTF-16 content with
a Hebrew string PADDED to the SAME char count, keeping the length prefix and the
decoded size byte-identical -> re-encode -> pad compressed resource to the exact
original on-disk size -> overwrite at the original offset. The forge TOC is
untouched.

    python acs_repack.py dryrun  <forge> <index>   # re-encode, report size fit
    python acs_repack.py deploy  <forge> <index>   # backup + in-place overwrite
    python acs_repack.py revert  <forge> <index>   # restore from the backup sidecar
"""
import sys
import os
import struct

# (english_substring, hebrew_replacement) — Hebrew is padded with spaces to the
# english char length so the decoded size is unchanged. Visible test strings.
REPLACEMENTS = [
    ("Field of View", "שדה ראייה"),
    ("Subtitles", "כתוביות"),
    ("Continue", "המשך"),
]


def _tools():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import acs_forge as F
    import acs_cfd as C
    return F, C


def inject(data: bytes) -> bytes:
    """Replace target strings in-place (same char length). Returns new data (same size)."""
    out = bytearray(data)
    for eng, heb in REPLACEMENTS:
        needle = eng.encode("utf-16le")
        pos = out.find(needle)
        if pos < 0:
            print(f"  WARN: '{eng}' not found")
            continue
        nchars = len(eng)
        # length prefix u32 is right before the string
        prefix = struct.unpack_from("<I", out, pos - 4)[0]
        if prefix != nchars:
            print(f"  WARN: '{eng}' length prefix {prefix} != {nchars}; skipping")
            continue
        padded = (heb + " " * nchars)[:nchars]          # pad/truncate to exact char count
        rep = padded.encode("utf-16le")
        assert len(rep) == len(needle)
        out[pos:pos + len(needle)] = rep
        print(f"  '{eng}' -> '{padded.strip()}' (len {nchars})")
    return bytes(out)


def rebuild(forge, index):
    F, C = _tools()
    o = C._oodle()
    info = F.parse(forge)
    r = info["recs"][index]
    with open(forge, "rb") as f:
        f.seek(r["offset"]); orig = f.read(r["size"])
    cfds, consumed = C.decode_resource(orig, o)
    # the string-bearing CFD is the largest one
    si = max(range(len(cfds)), key=lambda i: len(cfds[i][0]))
    new_cfds = []
    for i, (data, cinfo) in enumerate(cfds):
        d = inject(data) if i == si else data
        new_cfds.append(C.build_cfd(d, cinfo, o))
    blob = b"".join(new_cfds)
    return r, orig, blob


def cmd_dryrun(forge, index):
    r, orig, blob = rebuild(forge, index)
    print(f"\nresource {index}: original on-disk {len(orig)} B, re-encoded {len(blob)} B")
    if len(blob) <= len(orig):
        print(f"FITS (pad {len(orig)-len(blob)} bytes) -> in-place delta-0 deploy OK")
        return 0
    print(f"TOO BIG by {len(blob)-len(orig)} B -> needs patch-forge append, not in-place")
    return 1


def cmd_deploy(forge, index):
    r, orig, blob = rebuild(forge, index)
    if len(blob) > len(r and orig):
        print(f"ABORT: re-encoded {len(blob)} > original {len(orig)}")
        return 1
    blob = blob + b"\x00" * (len(orig) - len(blob))      # pad to exact size
    bak = f"{forge}.tmbak_{index}"
    if not os.path.exists(bak):
        with open(bak, "wb") as g:
            g.write(orig)
        print(f"backup -> {bak} ({len(orig)} B)")
    with open(forge, "r+b") as f:
        f.seek(r["offset"]); f.write(blob)
    print(f"wrote {len(blob)} B at offset 0x{r['offset']:x} in {os.path.basename(forge)}")
    print("  -> launch the game (English text language) and check the Settings descriptions")
    return 0


def cmd_revert(forge, index):
    bak = f"{forge}.tmbak_{index}"
    if not os.path.exists(bak):
        print(f"no backup {bak}")
        return 1
    F, _ = _tools()
    info = F.parse(forge)
    r = info["recs"][index]
    with open(bak, "rb") as g:
        orig = g.read()
    with open(forge, "r+b") as f:
        f.seek(r["offset"]); f.write(orig)
    print(f"reverted resource {index} ({len(orig)} B) from {bak}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) >= 4:
        cmd = {"dryrun": cmd_dryrun, "deploy": cmd_deploy, "revert": cmd_revert}.get(sys.argv[1])
        if cmd:
            sys.exit(cmd(sys.argv[2], int(sys.argv[3])))
    print(__doc__)
