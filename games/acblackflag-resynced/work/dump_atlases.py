#!/usr/bin/env python3
"""Decode every 0xcbd4939a (font-atlas class) resource in DataPC_boot.forge ONCE and cache
the decoded bytes to work/atlas/<idx>_<fileID>.bin, plus a JSON index. Decoding is slow
(12 MB / 48 Oodle blocks each) so every later analysis reads the cache, never the forge.

    python work/dump_atlases.py            # dump all 11
    ATLAS_IDX=19498 python work/dump_atlases.py   # just one
"""
import importlib.util, os, struct, sys, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
INJ = os.path.join(HERE, "refmods", "injector", "oo2core_9_win64.dll")
os.environ["ACS_OODLE_DLL"] = INJ
OUT = os.path.join(HERE, "atlas")


def _load(n):
    p = os.path.join(TOOLS, n + ".py"); s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


AF = _load("acbf_forge"); CFD = _load("acbf_cfd")
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))
from acs_oodle import Oodle

GAME = os.environ.get("ACBF_GAME", r"C:\Games\Assassin's Creed Black Flag Resynced")
FN = os.path.join(GAME, "DataPC_boot.forge")
CLASS = 0xCBD4939A


def decode_record(f, r, oo):
    """Decode a 2-CFD resource: CFD0 = 51-byte descriptor, CFD1 = the payload."""
    f.seek(r["offset"]); blob = f.read(r["size"])
    out = bytearray(); off = 0
    while off + 19 <= len(blob) and struct.unpack_from("<Q", blob, off)[0] == CFD.MAGIC:
        cnt = struct.unpack_from("<i", blob, off + 15)[0]
        bi = off + 19
        binfo = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(cnt)]
        p = bi + cnt * 8
        for u, c in binfo:
            p += 4
            d = blob[p:p + c]; p += c
            out += d if c == u else oo.decompress(d, u)
        off = p
    return bytes(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    oo = Oodle(INJ)
    info = AF.parse(FN); recs = info["recs"]
    only = os.environ.get("ATLAS_IDX")
    targets = [i for i, r in enumerate(recs) if r["hash"] == CLASS]
    if only:
        targets = [int(only)]
    print(f"dumping {len(targets)} atlas resources -> {OUT}", flush=True)
    index = []
    f = open(FN, "rb")
    for idx in targets:
        r = recs[idx]
        name = f"{idx}_{r['ts']:08x}.bin"
        dst = os.path.join(OUT, name)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            print(f"  idx {idx}: cached ({os.path.getsize(dst):,} B)", flush=True)
            index.append({"idx": idx, "fileID": r["ts"], "file": name,
                          "decoded": os.path.getsize(dst), "ondisk": r["size"]})
            continue
        t0 = time.time()
        dec = decode_record(f, r, oo)
        open(dst, "wb").write(dec)
        print(f"  idx {idx} fileID=0x{r['ts']:08x}: {r['size']:,} -> {len(dec):,} B "
              f"({time.time()-t0:.0f}s) -> {name}", flush=True)
        index.append({"idx": idx, "fileID": r["ts"], "file": name,
                      "decoded": len(dec), "ondisk": r["size"]})
    f.close()
    json.dump(index, open(os.path.join(OUT, "index.json"), "w"), indent=1)
    print("DONE -> atlas/index.json")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
