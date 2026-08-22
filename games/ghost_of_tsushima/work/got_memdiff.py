# -*- coding: utf-8 -*-
r"""got_memdiff.py — isolate the FONT buffers by diffing memory across a Text-Language change.

Changing Text Language forces the engine to re-load + re-tessellate the font, so the font's
runtime buffers are (re)written or freshly allocated. We snapshot PRIVATE+RW committed memory
(per-region CRC + per-page CRC + a set of region bases), then:
  churn  = regions/pages that differ between two IDLE menu snapshots (per-frame UI redraw noise)
  font   = regions/pages that differ across the LANGUAGE CHANGE, MINUS churn, PLUS newly-allocated
           regions (present after, absent before) — the highest-signal font-load candidates.

    python got_memdiff.py snap  <outfile>          # take a snapshot
    python got_memdiff.py diff  <before> <after> [<churn_before> <churn_after>]
Run with the repo .venv python.
"""
import sys, os, ctypes, zlib, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M

k32 = ctypes.windll.kernel32
PAGE_RW = 0x04
PAGE = 0x1000


def private_rw(hp):
    mbi = M.MEMORY_BASIC_INFORMATION64(); addr = 0; out = []
    while addr < 0x7fffffffffff:
        if not k32.VirtualQueryEx(hp, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        if (mbi.State == 0x1000 and mbi.Type == 0x20000 and (mbi.Protect & 0xff) == PAGE_RW):
            out.append((mbi.BaseAddress, mbi.RegionSize))
        addr = mbi.BaseAddress + mbi.RegionSize
        if mbi.RegionSize == 0:
            addr += PAGE
    return out


def snapshot():
    pid = M.pid(); hp = M.open_proc(pid)
    snap = {}
    for base, size in private_rw(hp):
        if size > 0x1000000:      # skip >16MB (font buffers are small; keeps it fast)
            continue
        data = M.read(hp, base, size)
        if not data:
            continue
        snap[base] = (size, zlib.crc32(data) & 0xffffffff)   # one C-level crc per region
    k32.CloseHandle(hp)
    return snap


def changed_regions(a, b):
    """regions in b whose per-region crc differs from a (or are newly present)."""
    out = {"changed": [], "new": []}
    for base, (size, rcrc) in b.items():
        if base not in a:
            out["new"].append((base, size))
        elif a[base][1] != rcrc:
            out["changed"].append((base, size, 0, 0))
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "snap":
        snap = snapshot()
        pickle.dump(snap, open(sys.argv[2], "wb"))
        print(f"snapshot: {len(snap)} private-RW regions -> {sys.argv[2]}")
    elif cmd == "diff":
        before = pickle.load(open(sys.argv[2], "rb"))
        after = pickle.load(open(sys.argv[3], "rb"))
        d = changed_regions(before, after)
        churn = set()
        if len(sys.argv) >= 6:
            cb = pickle.load(open(sys.argv[4], "rb")); ca = pickle.load(open(sys.argv[5], "rb"))
            cd = changed_regions(cb, ca)
            churn = {b for b, *_ in cd["changed"]} | {b for b, _ in cd["new"]}
            print(f"(churn set: {len(churn)} regions change per-frame — excluded)")
        print(f"\n== NEWLY ALLOCATED regions (present after, absent before) — top font-load signal ==")
        for base, size in sorted(d["new"], key=lambda x: -x[1])[:20]:
            mark = "" if base not in churn else "  (churn)"
            print(f"   NEW  0x{base:012x} size=0x{size:x}{mark}")
        print(f"\n== CHANGED regions (differ across the change), churn-excluded ==")
        cc = [r for r in d["changed"] if r[0] not in churn]
        for base, size, nch, npg in sorted(cc, key=lambda x: -x[2])[:25]:
            print(f"   CHG  0x{base:012x} size=0x{size:x}  changed_pages={nch}/{npg}")
        print(f"\ntotals: new={len(d['new'])} changed={len(d['changed'])} (churn-excluded changed={len(cc)})")
    else:
        print(__doc__)


if __name__ == "__main__":
    sys.exit(main() or 0)
