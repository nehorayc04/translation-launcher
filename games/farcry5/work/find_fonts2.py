"""Focused FC5 font hunt: sfnt anywhere in the first 4 KB (fonts may sit behind a wrapper).

Order the archives by how likely the UI font is there; print progress unbuffered so a
long run is observable (never pipe this through `tail` -- that buffers everything away).
"""
import sys, os, io, struct, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat
from fontTools.ttLib import TTFont

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
SFNT = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")
HEB = range(0x05D0, 0x05EB); LAT = range(0x41, 0x5B); ARA = range(0x620, 0x650)
ARCHIVES = sys.argv[1:] or ["patch.fat", "common.fat", "worlds/installpkg.fat",
                            "ige.fat", "igepatch.fat", "worlds/farcry5.fat"]

def probe(blob, where, e, arch):
    for magic in SFNT:
        i = blob.find(magic)
        while i != -1 and i < 4096:
            try:
                nt = struct.unpack_from(">H", blob, i + 4)[0]
                if 3 <= nt <= 64:
                    ft = TTFont(io.BytesIO(blob[i:]), fontNumber=0, lazy=True)
                    cm = ft.getBestCmap()
                    nm = ""
                    try:
                        nm = ft["name"].getDebugName(4) or ft["name"].getDebugName(1) or ""
                    except Exception:
                        pass
                    o = "glyf" if "glyf" in ft else ("CFF" if "CFF " in ft else "?")
                    print(f"FONT {arch:26s} {e.hash:016x} off={i:<5} unc={e.unc:>9,} {o:4s} "
                          f"lat={sum(1 for c in LAT if c in cm):>2}/26 "
                          f"ara={sum(1 for c in ARA if c in cm):>2}/48 "
                          f"heb={sum(1 for c in HEB if c in cm):>2}/27 "
                          f"cmap={len(cm):>5} {nm}", flush=True)
                    return True
            except Exception:
                pass
            i = blob.find(magic, i + 1)
    return False

for arch in ARCHIVES:
    p = os.path.join(PC, arch)
    if not os.path.exists(p):
        continue
    f = Fat(p)
    band = [e for e in f.entries if 4000 <= e.unc <= 30_000_000]
    print(f"\n### {arch}: {len(band):,} entries in band (of {f.count:,})", flush=True)
    fh = open(f.dat_path, "rb")
    t0 = time.time(); found = 0
    for i, e in enumerate(band):
        if i and i % 5000 == 0:
            print(f"   ... {i:,}/{len(band):,}  {time.time()-t0:.0f}s  found={found}", flush=True)
        try:
            if e.scheme == 0:
                fh.seek(e.off); blob = fh.read(min(4200, e.comp))
            else:
                blob = f.read_data(e)[:4200]
        except Exception:
            continue
        if not any(m in blob[:4096] for m in SFNT):
            continue
        try:
            full = f.read_data(e)
        except Exception:
            continue
        if probe(full, 0, e, arch):
            found += 1
    fh.close()
    print(f"### {arch}: {found} font(s), {time.time()-t0:.0f}s", flush=True)
