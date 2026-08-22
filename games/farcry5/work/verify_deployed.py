"""Read the deployment back OUT of the live archives -- the only proof that counts.

Checks, per archive that the engine could win with:
  * the patched oasis really carries every proof string
  * the .ffd really carries 1,121 glyphs incl. all 27 Hebrew letters
  * the atlas really is 1024x2048 with the original 1024 rows byte-identical

  python -u verify_deployed.py
"""
import sys, os, subprocess, struct

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, HERE)
from fc5_fat import Fat
from fc5_crc64 import name_hash
import fc5_oasis as O
from fc5_font import Atlas, parse_fnt, ATLAS_W, ORIG_H, NEW_H
import build_proof as P
# which build is deployed decides the expected strings -- default to the menu round
if "--proof" in sys.argv:
    edits_src = P
else:
    import build_menu_he as M
    edits_src = M

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
OUT = os.path.join(HERE, "..", "extract")
FFD_CONV = os.path.abspath(os.path.join(HERE, "..", "..", "watchdogs2", "tools",
                                        "ffdconverter", "FFDConverter.exe"))
UI_H = name_hash("languages/arabic/oasisstrings.oasis.bin")
edits = (P.build() if edits_src is P else
         {k: v for _, ks, v, _ in M.PLAN for k in ks})

src = Atlas(os.path.join(OUT, "arabic_atlas.xbt"))       # pristine, pulled from patch.fat
ok = True
for arch, fat in P.all_archives():
    bits = []
    if UI_H in fat.by_hash:
        e = fat.by_hash[UI_H]
        flat = O.flat(O.parse(fat.read_data(e))[1])
        hit = sum(1 for k, v in edits.items() if flat.get(k) == v)
        bits.append(f"text {hit}/{len(edits)}")
        ok &= hit == len(edits)
    if P.FFD_H in fat.by_hash:
        d = fat.read_data(fat.by_hash[P.FFD_H])
        n = struct.unpack_from("<H", d, 4)[0]
        bits.append(f"ffd {n} glyphs")
        ok &= n == 1121
    if P.XBT_H in fat.by_hash:
        raw = fat.read_data(fat.by_hash[P.XBT_H])
        tmp = os.path.join(OUT, "_live_atlas.xbt")
        open(tmp, "wb").write(raw)
        a = Atlas(tmp)
        same = (a.mip0[:ORIG_H] == src.mip0).all()
        ink = int((a.mip0[ORIG_H:] > 0).sum())
        bits.append(f"atlas {a.w}x{a.h} orig-rows-identical={same} hebrew-ink={ink:,}px")
        ok &= (a.w, a.h) == (ATLAS_W, NEW_H) and same and ink > 10000
        os.remove(tmp)
    if bits:
        print(f"  {arch:44s} {' | '.join(bits)}")

# the .ffd in the LIVE archive must still round-trip with all 27 Hebrew letters
f = Fat(os.path.join(PC, "patch.fat"))
open(os.path.join(OUT, "_live.ffd"), "wb").write(f.read_data(f.by_hash[P.FFD_H]))
rt = os.path.join(OUT, "_live.fnt")
subprocess.run([FFD_CONV, "--ffd2fnt", "-v", "FC5", "-f", os.path.join(OUT, "_live.ffd"),
                "-o", rt], input=f"{ATLAS_W}\n{NEW_H}\n\n", capture_output=True, text=True)
live = parse_fnt(rt)
heb = [c for c in range(0x05D0, 0x05EB) if c in live and live[c][2] > 0]
print(f"\n  live patch.fat .ffd -> {len(live)} glyphs, {len(heb)}/27 hebrew with a real rect")
ok &= len(heb) == 27
print("\n  DEPLOYMENT VERIFIED" if ok else "\n  DEPLOYMENT INCOMPLETE")
