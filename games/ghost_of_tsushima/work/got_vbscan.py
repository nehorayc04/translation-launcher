# -*- coding: utf-8 -*-
r"""got_vbscan.py — find the UI/text VERTEX BUFFER in the live process (CPU-visible upload heap).

The tessellator writes glyph geometry into a D3D12 upload-heap buffer (CPU-visible => VM_READ-able).
Menu text = many quads whose position.xy is bounded in a screen/NDC range and whose Y values fall
into a FEW narrow bands (text baselines). We scan RW committed regions, try vertex strides
16/20/24/28/32 with the position at float offset 0/1/2, and rank regions by "looks like screen-space
UI vertices" (high finite+in-range fraction AND few distinct Y bands). Prints top candidates + a
vertex sample so the buffer can be confirmed by eye. Run with the repo .venv python (numpy).
"""
import sys, os, ctypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M
import numpy as np

k32 = ctypes.windll.kernel32
PAGE_RW = 0x04          # PAGE_READWRITE (upload heaps)
RANGE = 8000.0          # covers pixel-space (0..3840) and NDC (-1..1) and normalized


def score_region(data):
    """Return the best (score, stride_bytes, off_floats, sample) for this region."""
    if len(data) < 64 * 4:
        return None
    # trim to multiple of 4 bytes
    fa = np.frombuffer(data[:len(data) // 4 * 4], dtype="<f4")
    best = None
    for sf in (4, 5, 6, 7, 8):          # stride in floats (16/20/24/28/32 B)
        nv = len(fa) // sf
        if nv < 32:
            continue
        m = fa[:nv * sf].reshape(nv, sf)
        for o in (0, 1, 2):
            if o + 1 >= sf:
                continue
            x = m[:, o]; y = m[:, o + 1]
            finite = np.isfinite(x) & np.isfinite(y)
            inr = finite & (np.abs(x) <= RANGE) & (np.abs(y) <= RANGE) & ~((x == 0) & (y == 0))
            frac = inr.mean()
            if frac < 0.55:
                continue
            yv = y[inr]
            if yv.size < 32:
                continue
            # few distinct Y bands (text baselines) => structured UI text
            yb = np.round(yv).astype(np.int64)
            distinct_y = np.unique(yb).size
            band_ratio = distinct_y / yv.size           # small => few baselines
            xspan = float(x[inr].max() - x[inr].min())  # text spans horizontally
            # score: high valid frac, few Y bands, real horizontal span
            score = frac * (1.0 - min(band_ratio, 1.0)) * (1.0 if xspan > 20 else 0.2)
            if best is None or score > best[0]:
                sample = m[np.where(inr)[0][:6]][:, :min(sf, 8)]
                best = (score, sf * 4, o, frac, distinct_y, yv.size, xspan, sample)
    return best


def private_rw_regions(hp):
    """Walk VirtualQueryEx returning (base,size,prot) for MEM_PRIVATE + PAGE_READWRITE only."""
    mbi = M.MEMORY_BASIC_INFORMATION64()
    addr = 0; out = []
    while addr < 0x7fffffffffff:
        if not k32.VirtualQueryEx(hp, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        if (mbi.State == 0x1000 and mbi.Type == 0x20000            # COMMIT + PRIVATE
                and (mbi.Protect & 0xff) == PAGE_RW):
            out.append((mbi.BaseAddress, mbi.RegionSize))
        addr = mbi.BaseAddress + mbi.RegionSize
        if mbi.RegionSize == 0:
            addr += 0x1000
    return out


def main():
    pid = M.pid()
    if not pid:
        print("game not running"); return 2
    hp = M.open_proc(pid)
    regs = [(b, s) for b, s in private_rw_regions(hp) if 0x1000 <= s <= 0x2000000]
    print(f"{len(regs)} private-RW regions in the 4KB..32MB band", flush=True)
    cands = []
    scanned = 0; total = 0
    for base, size in regs:
        if total > 2_000_000_000:
            print("  (byte cap reached)"); break
        data = M.read(hp, base, size)
        if not data:
            continue
        scanned += 1; total += len(data)
        if scanned % 60 == 0:
            print(f"  ..scanned {scanned}/{len(regs)} ({total//1_000_000}MB)", flush=True)
        r = score_region(data)
        if r and r[0] > 0.15:
            cands.append((r[0], base, size, r))
            _, stride, off, frac, dy, nvalid, xspan, sample = r
            print(f"  [cand] VA 0x{base:012x} score={r[0]:.3f} stride={stride} f{off} valid={frac*100:.0f}% xspan={xspan:.0f}", flush=True)
    cands.sort(key=lambda c: -c[0])
    print(f"\nscanned {scanned} RW regions; {len(cands)} candidate UI/text vertex buffers\n")
    for score, base, size, r in cands[:12]:
        _, stride, off, frac, dy, nvalid, xspan, sample = r
        print(f"VA 0x{base:012x} size=0x{size:x}  score={score:.3f}  stride={stride}B pos@f{off}  "
              f"valid={frac*100:.0f}%  distinctY={dy}/{nvalid}  xspan={xspan:.1f}")
        for row in sample:
            print("     " + "  ".join(f"{v:+11.3f}" for v in row))
    k32.CloseHandle(hp)
    print("\nNEXT: pick the buffer whose sample looks like screen-space glyph quads;"
          " then HW-bp WRITES to it to catch the tessellator RIP.")


if __name__ == "__main__":
    sys.exit(main() or 0)
