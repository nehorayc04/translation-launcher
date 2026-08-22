"""Resolve the glyph atlas to its OWNING UI resource, and from there to its real path.

cf402ed3ebb8872f decodes as a dependency manifest:
    u32 recordCount
    recordCount x { u32 firstIndex, u32 count, u64 ownerHash }
    u64 textureHash[...]              <- firstIndex/count index into THIS array
So the owner of the Arabic atlas is simply whichever record's [first, first+count) range
covers the atlas's index.  The owner is a Scaleform SWF, whose FC5-proprietary tags carry
the asset's plain-text path (243/246 = external image, 244 = .bfd SuperTexture descriptor).
That path is what turns "some pixels" into an addressable font.

  python -u find_atlas_owner.py
"""
import sys, os, struct, re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, HERE)
from fc5_fat import Fat
from fc5_crc64 import name_hash
import find_swf_fonts as F

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
OUT = os.path.join(HERE, "..", "extract")

ATLASES = {
    0x4121034366bd73a3: "arabic 1024x1024",
    0xc44a353a7c4073c2: "latin  1024x1024",
    0xc44a353a7e9073c2: "latin? 512x1024",
    0x505b361009c2ebee: "cjk    2048x1024",
    0x505b36100b12ebee: "cjk    2048x1024",
    0x9fed8662c4bd795e: "cjk    2048x1024",
    0xa719b314e4fccab0: "cjk    2048x1024",
    0xa719b314e62ccab0: "cjk    2048x1024",
    0xd2c5b33f08697ad2: "cjk    2048x1024",
    0xd2c5b33f0ab97ad2: "cjk    2048x1024",
    0x50803c20f249dc40: "?      1024x512",
    0x73205d587ef5a42a: "?      1024x512",
}

b = open(os.path.join(OUT, "fontbank.bin"), "rb").read()
cnt = struct.unpack_from("<I", b, 0)[0]
# the hash array is length-prefixed by its OWN u32 right after the record table
narr = struct.unpack_from("<I", b, 4 + cnt * 16)[0]
ARR = 4 + cnt * 16 + 4
print(f"records={cnt}  array@0x{ARR:x}  n={narr}  tail={len(b) - (ARR + narr*8):,} B\n")

arr = [struct.unpack_from("<Q", b, ARR + i * 8)[0] for i in range(narr)]
recs = []
for i in range(cnt):
    o = 4 + i * 16
    first, c = struct.unpack_from("<II", b, o)
    owner = struct.unpack_from("<Q", b, o + 8)[0]
    recs.append((first, c, owner))
bad = [r for r in recs if r[0] + r[1] > narr]
print(f"records whose range overflows the array: {len(bad)}  (0 == layout confirmed)\n")

idx_of = {h: i for i, h in enumerate(arr)}
owners = {}
for h, label in ATLASES.items():
    i = idx_of.get(h)
    if i is None:
        print(f"  {label:18} {h:016x}  NOT in array")
        continue
    own = [(first, c, o) for (first, c, o) in recs if first <= i < first + c]
    print(f"  {label:18} {h:016x}  arrayIndex={i}  owners={[f'{o:016x}' for _,_,o in own]}")
    for _, _, o in own:
        owners.setdefault(o, []).append(label)

print("\n=== owning UI resources ===")
fats = {}
for q in ("common.fat", "patch.fat", "worlds/installpkg.fat"):
    p = os.path.join(PC, q)
    if os.path.exists(p):
        fats[q] = Fat(p)

PATH_RX = re.compile(rb"[\x20-\x7e]{6,200}")
for owner, labels in owners.items():
    print(f"\n--- {owner:016x}   holds: {labels}")
    for q, f in fats.items():
        e = f.by_hash.get(owner)
        if not e:
            continue
        d = f.read_data(e)
        print(f"    in {q}: unc={e.unc:,} sch={e.scheme} head={d[:4]!r}")
        if d[:3] not in (b"UEF", b"CEF"):
            continue
        # FC5-proprietary Scaleform tags carry the plain-text asset paths
        for code, payload in F.tags(F.deobfuscate(d)):
            if code not in (243, 244, 246, 71):
                continue
            for m in PATH_RX.finditer(payload):
                for part in m.group().decode("latin-1").split("\x00"):
                    part = part.strip()
                    if len(part) < 8 or ("\\" not in part and "/" not in part):
                        continue
                    hh = name_hash(part)
                    star = ""
                    if hh in ATLASES:
                        star = "   <<<< ATLAS"
                    elif hh in idx_of:
                        star = "   (in manifest)"
                    dims = ""
                    if code in (243, 246) and len(payload) >= 6:
                        w, h = struct.unpack_from("<HH", payload, 2)
                        dims = f" {w}x{h}"
                    print(f"      tag{code}{dims}  {part}  -> {hh:016x}{star}")
        break
