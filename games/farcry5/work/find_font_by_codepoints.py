"""Find FC5's font resources by CONTENT, not by name.

A font/glyph descriptor must carry an ascending array of the codepoints it covers.
Signature: a long strictly-ascending run of u16 (or u32) values that starts in ASCII
and reaches the Arabic block -- text data never looks like that.

  python find_font_by_codepoints.py [archive.fat ...]
"""
import sys, os, struct, array
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
ARCHIVES = sys.argv[1:] or ["common.fat", "patch.fat", "worlds/installpkg.fat"]

MIN_RUN = 120          # a real font covers far more than 120 codepoints


def best_ascending_run(vals, lo=0x20, hi=0xFFFD):
    """Longest strictly-ascending run of plausible codepoints; returns (len, start, end)."""
    best = (0, 0, 0); n = len(vals)
    i = 0
    while i < n:
        if not (lo <= vals[i] <= hi):
            i += 1; continue
        j = i + 1
        while j < n and lo <= vals[j] <= hi and vals[j] > vals[j - 1]:
            j += 1
        if j - i > best[0]:
            best = (j - i, vals[i], vals[j - 1])
        i = max(j, i + 1)
    return best


def scan_blob(b):
    out = []
    for width, code in ((2, "H"), (4, "I")):
        for off in range(0, min(width, len(b))):
            body = b[off:]
            body = body[: len(body) - (len(body) % width)]
            if len(body) < MIN_RUN * width:
                continue
            a = array.array(code); a.frombytes(body)
            if sys.byteorder != "little":
                a.byteswap()
            ln, s, e = best_ascending_run(a)
            if ln >= MIN_RUN:
                out.append((ln, s, e, width, off))
    return max(out) if out else None


for arch in ARCHIVES:
    p = os.path.join(PC, arch)
    if not os.path.exists(p):
        continue
    f = Fat(p)
    band = [e for e in f.entries if 512 <= e.unc <= 4_000_000]
    print(f"\n### {arch}: {len(band):,} entries in band (of {f.count:,})", flush=True)
    hits = 0
    for i, e in enumerate(band):
        if i and i % 10000 == 0:
            print(f"   ... {i:,}/{len(band):,} hits={hits}", flush=True)
        try:
            b = f.read_data(e)
        except Exception:
            continue
        r = scan_blob(b)
        if not r:
            continue
        ln, s, en, width, off = r
        # require the run to actually SPAN scripts: start in ASCII, reach >= Arabic
        if s > 0x80 or en < 0x5D0:
            continue
        hits += 1
        print(f"  CAND {arch} {e.hash:016x} unc={e.unc:>9,} sch={e.scheme} "
              f"run={ln} u{width*8} align={off} range=U+{s:04X}..U+{en:04X}", flush=True)
    print(f"### {arch}: {hits} candidate(s)", flush=True)
