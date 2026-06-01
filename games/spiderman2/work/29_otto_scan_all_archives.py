"""Scan every d/* archive for *validated* OTTO/TTF/TTC fonts.
Strategy: stream read, find OTTO bytes, validate the OTF header. Early-exit per
archive once we find anything. Save extracted fonts."""
import os, sys, struct, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "found_fonts")
os.makedirs(OUT, exist_ok=True)

KNOWN = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name", b"post",
         b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS", b"GSUB", b"hmtx",
         b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF"}

def validate(buf, j, magic, buf_end):
    """Return total length if valid, else None."""
    if j + 12 > buf_end: return None
    if buf[j:j+4] != magic: return None
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    if not (4 <= nt <= 40): return None
    extents = []
    known = 0
    for k in range(nt):
        rec = buf[j+12 + k*16 : j+12 + (k+1)*16]
        if len(rec) < 16: return None
        tag = rec[:4]
        if not all(0x20<=b<=0x7E for b in tag): return None
        off = struct.unpack(">I", rec[8:12])[0]
        ln  = struct.unpack(">I", rec[12:16])[0]
        extents.append((tag, off, ln))
        if tag in KNOWN: known += 1
    if known < 4: return None
    return max(o+l for _, o, l in extents)

def scan_archive(arch_path, max_hits=10):
    """Yield (file_offset, magic, total_len) for each validated font found."""
    size = os.path.getsize(arch_path)
    CHUNK = 64 * 1024 * 1024   # 64 MB chunks
    OVERLAP = 64 * 1024        # in case a font straddles a boundary
    hits = []
    with open(arch_path, "rb") as f:
        pos = 0
        prev_tail = b""
        while pos < size:
            buf_raw = f.read(CHUNK)
            if not buf_raw: break
            buf = prev_tail + buf_raw
            buf_end = len(buf)
            # OTTO scan (rare 4-byte magic — fast)
            i = 0
            while True:
                j = buf.find(b"OTTO", i)
                if j < 0: break
                total = validate(buf, j, b"OTTO", buf_end)
                if total and 30_000 < total < 50_000_000:
                    abs_off = pos + j - len(prev_tail)
                    hits.append((abs_off, "OTTO", total))
                    if len(hits) >= max_hits: return hits
                i = j + 4
            # TTC magic
            i = 0
            while True:
                j = buf.find(b"ttcf", i)
                if j < 0: break
                if j+12 <= buf_end:
                    v = struct.unpack(">I", buf[j+4:j+8])[0]
                    if v in (0x00010000, 0x00020000):
                        nfonts = struct.unpack(">I", buf[j+8:j+12])[0]
                        if 1 <= nfonts <= 50:
                            abs_off = pos + j - len(prev_tail)
                            hits.append((abs_off, "TTC", -1))
                            if len(hits) >= max_hits: return hits
                i = j + 4
            # Move pos forward; keep last OVERLAP bytes as prev_tail
            prev_tail = buf_raw[-OVERLAP:] if len(buf_raw) >= OVERLAP else buf_raw
            pos += len(buf_raw)
            # progress
            if pos % (256 * 1024 * 1024) == 0:
                print(f"      ... {pos/(1024*1024):.0f} MB done in {arch_path}")
    return hits

D = os.path.join(GAME, "d")
arch_files = sorted(os.listdir(D))
# Sort by size for efficiency — small first
arch_files = sorted(arch_files, key=lambda a: os.path.getsize(os.path.join(D, a)))

results = {}
for arch in arch_files:
    p = os.path.join(D, arch)
    if not os.path.isfile(p): continue
    sz = os.path.getsize(p)
    print(f"\n=== d/{arch} ({sz/(1024*1024):.1f} MB) ===", flush=True)
    start = time.time()
    try:
        hits = scan_archive(p, max_hits=20)
    except Exception as ex:
        print(f"  ERROR: {ex}")
        continue
    dt = time.time() - start
    if hits:
        results[arch] = hits
        print(f"  ★ {len(hits)} hits  ({dt:.1f}s)")
        for off, magic, total in hits[:10]:
            print(f"    offset={off:>11}  magic={magic}  totalLen~{total}")
            # Extract for inspection
            if total > 0:
                with open(p, "rb") as f:
                    f.seek(off)
                    font = f.read(total)
                outp = os.path.join(OUT, f"{arch}_off{off}_{magic}.bin")
                with open(outp, "wb") as wf: wf.write(font)
    else:
        print(f"  no font hits  ({dt:.1f}s)")
    # Stop after first 6 archives done — fail-fast
    # if hits and len(results) >= 3: break

print()
print("=== FINAL ===")
for a, h in results.items():
    print(f"  d/{a}: {len(h)} hits")
