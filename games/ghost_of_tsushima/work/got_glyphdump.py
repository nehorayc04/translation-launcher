# -*- coding: utf-8 -*-
r"""got_glyphdump.py — dump the RUNTIME glyph object + its outline data for given codepoints.

THE ROSETTA HUNT: the runtime already holds decoded glyph geometry for every rendering
glyph (Arabic/Latin).  If we dump a KNOWN glyph's runtime data we can correlate it back to
the on-disk tail-kind2 store -> that mapping IS the file codec.

  python got_glyphdump.py 0645 062A 0041 05D0

Walk:  cmap record (64 B, +20==0xF8, +62==FFFF)
         +0  u32 codepoint
         +6  48-bit pointer  (zero on disk, relocated at load)
         +14 u16 face   +16 u16 ref   +18 u16 cnt
         +22/+26/+30 f32 geom
       -> glyph object:  +0x40 data ptr   +0x50 count   +0x80 geom   +0x90 metrics
Run with the repo .venv python.  Game must be RUNNING (RUNASINVOKER, non-elevated).
"""
import sys, os, ctypes, struct, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M

k32 = ctypes.windll.kernel32
REC = re.compile(rb"\xf8[\s\S]{41}\xff\xff", re.S)


def regions(hp, lo=0x10000, hi=0x4000000):
    mbi = M.MEMORY_BASIC_INFORMATION64(); a = 0; out = []
    while a < 0x7fffffffffff:
        if not k32.VirtualQueryEx(hp, ctypes.c_void_p(a), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        if (mbi.State == 0x1000 and (mbi.Protect & 0xff) in (0x02, 0x04, 0x20, 0x40)
                and lo <= mbi.RegionSize <= hi):
            out.append((mbi.BaseAddress, mbi.RegionSize))
        a = mbi.BaseAddress + mbi.RegionSize
        if mbi.RegionSize == 0:
            a += 0x1000
    return out


def isrec(b, o):
    if o < 0 or o + 64 > len(b):
        return False
    if b[o + 20] != 0xF8 or b[o + 62] != 0xFF or b[o + 63] != 0xFF:
        return False
    cp = struct.unpack_from("<I", b, o)[0]
    return 0x20 <= cp < 0x110000


def rd(hp, va, n):
    try:
        return M.read(hp, va, n) or b""
    except Exception:
        return b""


def ptr48(b, o):
    return int.from_bytes(b[o:o + 6], "little")


def looks_ptr(v):
    return 0x10000 <= v < 0x7FFFFFFFFFFF


def f32s(b, n=None):
    n = n if n is not None else len(b) // 4
    return list(struct.unpack_from("<%df" % n, b, 0))


def fmt_f(v):
    if v != v:
        return "nan"
    if abs(v) > 1e18 or (v != 0 and abs(v) < 1e-18):
        return "%.2e" % v
    return "%.5f" % v


def main():
    want = set(int(a, 16) for a in sys.argv[1:]) or {0x0645, 0x062A, 0x0041, 0x05D0}
    pid = M.pid()
    if not pid:
        print("game not running"); return
    hp = M.open_proc(pid)
    regs = regions(hp)
    print(f"pid {pid}: {len(regs)} regions, hunting {len(want)} codepoints", flush=True)

    hits = {}
    t0 = time.time()
    for i, (base, size) in enumerate(regs):
        data = rd(hp, base, size)
        if not data:
            continue
        for m in REC.finditer(data):
            o = m.start() - 20
            if not isrec(data, o):
                continue
            cp = struct.unpack_from("<I", data, o)[0]
            if cp in want and cp not in hits:
                # confirm it sits inside a real table (a neighbour record exists)
                if isrec(data, o + 64) or isrec(data, o - 64):
                    hits[cp] = (base + o, data[o:o + 64])
        if len(hits) == len(want):
            break
        if i % 300 == 0:
            print(f"  ..{i}/{len(regs)} {time.time()-t0:.0f}s found={len(hits)}", flush=True)

    print(f"\n== located {len(hits)}/{len(want)} in {time.time()-t0:.0f}s ==\n", flush=True)

    for cp in sorted(hits):
        va, rec = hits[cp]
        p6 = ptr48(rec, 6)
        face, ref, cnt = struct.unpack_from("<HHH", rec, 14)
        gx, gy, gz = struct.unpack_from("<3f", rec, 22)
        print(f"---- U+{cp:04X}  rec@0x{va:012x}")
        print(f"     raw: {rec[:32].hex(' ')}")
        print(f"          {rec[32:].hex(' ')}")
        print(f"     +6 ptr=0x{p6:012x}  face={face}  ref={ref}  cnt={cnt}  geom=({gx:.4f},{gy:.4f},{gz:.4f})")
        if not looks_ptr(p6):
            print("     (+6 not a pointer -> nothing to walk)\n"); continue

        blob = rd(hp, p6, 0x100)
        if not blob:
            print("     (+6 unreadable)\n"); continue
        print(f"     [+6 target 0x100 B]")
        for off in range(0, 0x100, 16):
            qs = struct.unpack_from("<2Q", blob, off)
            mark = "  <ptr>" if any(looks_ptr(q) for q in qs) else ""
            print(f"       +{off:03x}: {blob[off:off+16].hex(' ')}{mark}")

        # glyph object fields
        d40 = struct.unpack_from("<Q", blob, 0x40)[0] if len(blob) >= 0x48 else 0
        c50 = struct.unpack_from("<I", blob, 0x50)[0] if len(blob) >= 0x54 else 0
        print(f"     glyph-obj: +0x40 data=0x{d40:012x}  +0x50 count={c50}")
        if looks_ptr(d40):
            n = c50 if 0 < c50 < 4096 else 64
            raw = rd(hp, d40, max(n * 32, 512))
            if raw:
                print(f"     [DATA @0x{d40:012x}  {len(raw)} B]")
                for off in range(0, min(len(raw), 384), 16):
                    fs = struct.unpack_from("<4f", raw, off)
                    us = struct.unpack_from("<4I", raw, off)
                    print(f"       +{off:03x}: {raw[off:off+16].hex(' ')}   f=[{', '.join(fmt_f(x) for x in fs)}]"
                          f"   u=[{', '.join(str(x) for x in us)}]")
                out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   f"_glyph_{cp:04X}.bin")
                open(out, "wb").write(raw)
                print(f"     -> saved {out}")
        print(flush=True)

    k32.CloseHandle(hp)


if __name__ == "__main__":
    main()
