#!/usr/bin/env python3
"""Scan DataPC_boot.forge for EMBEDDED fonts: decode each resource's first block and
look for an sfnt magic (00010000 / OTTO / true / ttcf) -> a real TTF/OTF we could patch
in-forge (the Arabic RTL path ignores the loose resources/ fonts). Writes hits to
work/_embedded_fonts.txt. Timeboxed; reports coverage."""
import importlib.util, os, struct, sys, time
os.environ["ACS_OODLE_DLL"] = os.path.abspath("games/acblackflag-resynced/work/refmods/injector/oo2core_9_win64.dll") \
    if os.path.exists("games/acblackflag-resynced/work/refmods/injector/oo2core_9_win64.dll") else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "refmods", "injector", "oo2core_9_win64.dll")
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
def L(n):
    p = os.path.join(TOOLS, n + ".py"); s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
AF = L("acbf_forge"); CFD = L("acbf_cfd")
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))
from acs_oodle import Oodle
oo = Oodle(os.environ["ACS_OODLE_DLL"])
G = os.environ.get("ACBF_GAME", r"C:\Games\Assassin's Creed Black Flag Resynced")
FN = G + r"\DataPC_boot.forge"
FONTMAG = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf", b"wOFF", b"wOF2")
TB = int(os.environ.get("SCAN_TB", "3000"))

def first_block_decoded(f, r):
    f.seek(r["offset"]); blob = f.read(min(r["size"], 1 << 16))
    off = 0
    # skip small leading CFDs (e.g. the 20-byte descriptor CFD0) to reach the data CFD
    for _ in range(3):
        if off + 19 > len(blob) or struct.unpack_from("<Q", blob, off)[0] != CFD.MAGIC:
            return None
        cnt = struct.unpack_from("<i", blob, off + 15)[0]
        if cnt < 1 or cnt > 100000:
            return None
        bi = off + 19; binfo = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(min(cnt, 1))]
        p = bi + cnt * 8
        u0, c0 = binfo[0]
        if u0 <= 64 and c0 <= 64:                # tiny descriptor CFD -> advance to next CFD
            # advance past ALL blocks of this CFD
            allb = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(cnt)]
            q = bi + cnt * 8
            for u, c in allb:
                q += 4 + c
            off = q; continue
        data0 = blob[p + 4:p + 4 + c0]
        try:
            return oo.decompress(data0, u0)[:16]
        except Exception:
            return None
    return None

def main():
    info = AF.parse(FN); recs = info["recs"]; n = len(recs)
    out = open(os.path.join(HERE, "_embedded_fonts.txt"), "w", encoding="utf-8")
    t0 = time.time(); probed = 0; hits = 0
    f = open(FN, "rb")
    for i, r in enumerate(recs):
        if r["size"] < 40000 or r["size"] > 30_000_000:
            continue
        probed += 1
        if probed % 2000 == 0:
            msg = f"  probed {probed} (rec {i}/{n}) hits={hits} {time.time()-t0:.0f}s"
            print(msg, flush=True); out.write(msg + "\n"); out.flush()
        if time.time() - t0 > TB:
            print(f"TIMEBOX at rec {i}/{n}", flush=True); out.write(f"TIMEBOX at rec {i}/{n}\n"); break
        head = first_block_decoded(f, r)
        if head and head[:4] in FONTMAG:
            hits += 1
            line = f"FONT idx={i} fileID=0x{r['ts']:08x} size={r['size']} hash=0x{r['hash']:08x} head={head[:8].hex()}"
            print(line, flush=True); out.write(line + "\n"); out.flush()
    f.close()
    done = f"DONE probed={probed}/{n} fontHits={hits} ({time.time()-t0:.0f}s)"
    print(done); out.write(done + "\n"); out.close()

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
