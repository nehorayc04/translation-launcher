#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_hunt_ladder.py — find the REAL SFontData by hunting a codepoint ladder
(ascending Latin/Arabic cp at a fixed record stride) inside candidate KCAP packages."""
import os, sys, struct
import numpy as np

GAME = r"F:/Games/Ghost of Tsushima DC"
PSARC_DIR = os.path.join(GAME, "cache_pc", "psarc")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R

CANDS = [
    ("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps"),
    ("gapack_misc_d.psarc", "downloaded.sprig.xpps"),
    ("gapack_misc_g.psarc", "ghost_title.xpps"),
    ("gapack_misc_c.psarc", "core_iki.sprig.xpps"),
    ("gapack_misc_c.psarc", "core_tsu.sprig.xpps"),
    ("gapack_misc_c.psarc", "core_common.sprig.xpps"),
]


def get(archive, name):
    arc = R.Psarc2(os.path.join(PSARC_DIR, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    data = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return data


def hunt_ladder(data, name):
    """Look for cp='A','B','C',... (0x41..) as u16 at a fixed stride R (2..64):
    positions p with u16[p]==0x41, u16[p+R]==0x42, u16[p+2R]==0x43, u16[p+3R]==0x44."""
    n = len(data)
    # candidate 'A' positions (u16 LE == 0x0041)
    hits = 0
    # find all offsets where byte==0x41 and next==0x00 (u16 0x41)
    b = np.frombuffer(data, dtype=np.uint8)
    aidx = np.nonzero((b[:-1] == 0x41) & (b[1:] == 0x00))[0]
    found = []
    for R_ in range(4, 65, 2):
        for p in aidx:
            p = int(p)
            if p + 5*R_ + 2 > n:
                continue
            ok = True
            for k in range(1, 6):  # B,C,D,E,F
                v = struct.unpack_from("<H", data, p + k*R_)[0]
                if v != 0x41 + k:
                    ok = False; break
            if ok:
                found.append((p, R_))
        if found:
            break
    # also try u32 codepoints
    found32 = []
    if not found:
        aidx4 = np.nonzero((b[:-3]==0x41)&(b[1:-2]==0)&(b[2:-1]==0)&(b[3:]==0))[0]
        for R_ in range(4, 65, 4):
            for p in aidx4:
                p=int(p)
                if p+5*R_+4>n: continue
                ok=all(struct.unpack_from("<I",data,p+k*R_)[0]==0x41+k for k in range(1,6))
                if ok: found32.append((p,R_))
            if found32: break
    return found, found32


def main():
    for archive, name in CANDS:
        try:
            data = get(archive, name)
        except Exception as ex:
            print(f"{name}: ERR {ex}"); continue
        if not data:
            print(f"{name}: not found"); continue
        f16, f32 = hunt_ladder(data, name)
        print(f"{name} [{archive}] {len(data):,}B -> u16-ladder hits={len(f16)} u32-ladder hits={len(f32)}")
        for p, Rr in f16[:3]:
            print(f"    u16 ladder @0x{p:x} stride={Rr}: rec[0..3] "
                  + " ".join(data[p+k*Rr:p+k*Rr+Rr].hex() for k in range(3)))
        for p, Rr in f32[:3]:
            print(f"    u32 ladder @0x{p:x} stride={Rr}")


if __name__ == "__main__":
    main()
