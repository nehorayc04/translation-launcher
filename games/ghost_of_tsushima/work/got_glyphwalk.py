# -*- coding: utf-8 -*-
r"""got_glyphwalk.py — walk the FACE ARRAY at record+6 and find the glyph object for a codepoint.

Model learned from got_glyphdump.py:
  cmap record +6  -> array of pointers to per-glyph objects
  object +0x00 vtable | +0x10 classId (963 = glyph, 931 = other) | +0x20/+0x28 linked list
         +0x40 data ptr | +0x50 count | +0x60 3x4 matrix | +0x80 geom(x,y,z,1) | +0x90 metrics

Identity test: the object whose +0x80 geom == the RECORD's geom (+22/+26/+30) IS that glyph.
Also tries array[ref] directly.

  python got_glyphwalk.py 0645 062A 05D0 0041
Run with the repo .venv python; game must be RUNNING.
"""
import sys, os, ctypes, struct, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M

k32 = ctypes.windll.kernel32
REC = re.compile(rb"\xf8[\s\S]{41}\xff\xff", re.S)
NMAX = 8192          # max face-array entries to walk


def regions(hp):
    mbi = M.MEMORY_BASIC_INFORMATION64(); a = 0; out = []
    while a < 0x7fffffffffff:
        if not k32.VirtualQueryEx(hp, ctypes.c_void_p(a), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        if (mbi.State == 0x1000 and (mbi.Protect & 0xff) in (0x02, 0x04, 0x20, 0x40)
                and 0x10000 <= mbi.RegionSize <= 0x4000000):
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


def looks_ptr(v):
    return 0x10000 <= v < 0x7FFFFFFFFFFF


def find_records(hp, want):
    hits = {}
    for base, size in regions(hp):
        data = rd(hp, base, size)
        if not data:
            continue
        for m in REC.finditer(data):
            o = m.start() - 20
            if not isrec(data, o):
                continue
            cp = struct.unpack_from("<I", data, o)[0]
            if cp in want and cp not in hits and (isrec(data, o + 64) or isrec(data, o - 64)):
                hits[cp] = (base + o, data[o:o + 64])
        if len(hits) == len(want):
            break
    return hits


def obj_info(hp, va):
    b = rd(hp, va, 0xA0)
    if len(b) < 0xA0:
        return None
    cid = struct.unpack_from("<I", b, 0x10)[0]
    d40 = struct.unpack_from("<Q", b, 0x40)[0]
    c50 = struct.unpack_from("<I", b, 0x50)[0]
    geom = struct.unpack_from("<3f", b, 0x80)
    met = struct.unpack_from("<3f", b, 0x90)
    return dict(cid=cid, d40=d40, c50=c50, geom=geom, met=met, raw=b)


def main():
    want = set(int(a, 16) for a in sys.argv[1:]) or {0x0645, 0x062A, 0x05D0, 0x0041}
    pid = M.pid()
    if not pid:
        print("game not running"); return
    hp = M.open_proc(pid)
    t0 = time.time()
    hits = find_records(hp, want)
    print(f"pid {pid}: located {len(hits)}/{len(want)} records in {time.time()-t0:.0f}s\n", flush=True)

    for cp in sorted(hits):
        va, rec = hits[cp]
        p6 = int.from_bytes(rec[6:12], "little")
        face, ref, cnt = struct.unpack_from("<HHH", rec, 14)
        rgeom = struct.unpack_from("<3f", rec, 22)
        print(f"==== U+{cp:04X} rec@0x{va:012x} face={face} ref={ref} cnt={cnt} geom={rgeom}")
        if not looks_ptr(p6):
            print("   (+6 not a pointer)\n"); continue

        arr = rd(hp, p6, NMAX * 8)
        ptrs = []
        for i in range(len(arr) // 8):
            v = struct.unpack_from("<Q", arr, i * 8)[0]
            if not looks_ptr(v):
                break
            ptrs.append(v)
        print(f"   face array @0x{p6:012x}: {len(ptrs)} consecutive pointers")

        # (a) direct index by ref
        for label, idx in (("array[0]", 0), (f"array[ref={ref}]", ref)):
            if idx < len(ptrs):
                o = obj_info(hp, ptrs[idx])
                if o:
                    print(f"   {label} @0x{ptrs[idx]:012x} cid={o['cid']} "
                          f"geom={tuple(round(x,2) for x in o['geom'])} "
                          f"met={tuple(round(x,2) for x in o['met'])} "
                          f"+0x40=0x{o['d40']:012x} +0x50={o['c50']}")

        # (b) identity by geom match
        match = []
        for i, p in enumerate(ptrs[:NMAX]):
            o = obj_info(hp, p)
            if not o:
                continue
            if (abs(o['geom'][0] - rgeom[0]) < 0.01 and abs(o['geom'][1] - rgeom[1]) < 0.01
                    and abs(o['geom'][2] - rgeom[2]) < 0.01):
                match.append((i, p, o))
        print(f"   geom-match: {len(match)} object(s)")
        for i, p, o in match[:3]:
            print(f"     idx={i} @0x{p:012x} cid={o['cid']} +0x40=0x{o['d40']:012x} +0x50={o['c50']} "
                  f"met={tuple(round(x,2) for x in o['met'])}")
            if looks_ptr(o['d40']) and 0 < o['c50'] < 100000:
                n = o['c50']
                raw = rd(hp, o['d40'], min(n * 32 + 64, 8192))
                out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"_gdata_{cp:04X}.bin")
                open(out, "wb").write(raw)
                print(f"     DATA @0x{o['d40']:012x} count={n} -> {out} ({len(raw)} B)")
                for off in range(0, min(len(raw), 256), 16):
                    f4 = struct.unpack_from("<4f", raw, off)
                    i8 = struct.unpack_from("<8h", raw, off)
                    print(f"       +{off:03x}: {raw[off:off+16].hex(' ')}")
                    print(f"              f=[{', '.join('%.3f' % x for x in f4)}]  "
                          f"i16=[{', '.join(str(x) for x in i8)}]")
        print(flush=True)

    k32.CloseHandle(hp)


if __name__ == "__main__":
    main()
