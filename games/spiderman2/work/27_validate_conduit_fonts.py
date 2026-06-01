"""Validate the 5 conduit candidates that contain OTTO strings — are any real fonts?
For each: dump section structure (DAT1 format) and locate the OTF inside."""
import os, sys, io, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib, dat1lib.types.dat1

R2 = os.path.join(ROOT, "games", "spiderman2", "extracted", "round2")
OUT = os.path.join(ROOT, "games", "spiderman2", "extracted", "found_fonts")
os.makedirs(OUT, exist_ok=True)

KNOWN = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name", b"post",
         b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS", b"GSUB", b"hmtx",
         b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF"}

def validate(data, j, magic):
    if data[j:j+4] != magic: return None
    nt = struct.unpack(">H", data[j+4:j+6])[0]
    if not (4 <= nt <= 40): return None
    extents = []
    known = 0
    for k in range(nt):
        rec = data[j+12 + k*16 : j+12 + (k+1)*16]
        if len(rec) < 16: return None
        tag = rec[:4]
        if not all(0x20<=b<=0x7E for b in tag): return None
        off = struct.unpack(">I", rec[8:12])[0]
        ln = struct.unpack(">I", rec[12:16])[0]
        extents.append((tag, off, ln))
        if tag in KNOWN: known += 1
    if known < 4: return None
    return (nt, known, max(o+l for _, o, l in extents), extents)

def read_otf_name(data, j, ext):
    """Read 'name' table to get Family/Subfamily."""
    nt = struct.unpack(">H", data[j+4:j+6])[0]
    name_off = name_len = None
    for k in range(nt):
        rec = data[j+12 + k*16 : j+12 + (k+1)*16]
        if rec[:4] == b"name":
            name_off = struct.unpack(">I", rec[8:12])[0]
            name_len = struct.unpack(">I", rec[12:16])[0]
            break
    if not name_off: return None
    n = data[j+name_off : j+name_off+name_len]
    if len(n) < 6: return None
    fmt, count, soff = struct.unpack(">HHH", n[:6])
    strings = n[soff:]
    rows = {}
    for i in range(count):
        rec = n[6 + i*12 : 6 + (i+1)*12]
        plat, enc, lang, nid, slen, srecoff = struct.unpack(">HHHHHH", rec)
        s = strings[srecoff:srecoff+slen]
        if plat == 3:
            try: rows[nid] = s.decode("utf-16-be", "replace")
            except: pass
    return rows

CONDUIT_HITS = [
    ("conduit_24608.bin", 24608),
    ("conduit_30549.bin", 30549),
    ("conduit_242997.bin", 242997),
    ("conduit_317305.bin", 317305),
    ("conduit_404227.bin", 404227),
]

for fn, idx in CONDUIT_HITS:
    p = os.path.join(R2, fn)
    if not os.path.exists(p):
        print(f"[!] missing {p}")
        continue
    data = open(p, "rb").read()
    print(f"\n=== {fn} (size={len(data)}) ===")
    print(f"   head: {data[:32].hex(' ')}")
    print(f"   text: {data[:32].decode('ascii','replace')}")

    # If DAT1 — parse sections
    if data[:4] == b"\x44\x41\x54\x31":  # "DAT1"
        try:
            d = dat1lib.types.dat1.DAT1(io.BytesIO(data), None)
            print(f"   DAT1 unk1=0x{d.header.unk1:08X}  sections={len(d.header.sections)}")
            for sh in d.header.sections:
                # Look at section content
                sec = data[sh.offset : sh.offset+sh.size]
                # Validate fonts inside section
                for magic in (b"OTTO", b"\x00\x01\x00\x00", b"ttcf"):
                    i = 0
                    while True:
                        j = sec.find(magic, i)
                        if j < 0: break
                        res = validate(sec, j, magic)
                        if res:
                            nt, known, total, ext = res
                            family = "?"
                            try:
                                names = read_otf_name(sec, j, magic)
                                if names:
                                    family = names.get(1, names.get(4, "?"))
                            except Exception as ex: pass
                            print(f"   FONT in section 0x{sh.tag:08X}, offset_in_sec={j}, size={total}, family={family!r}")
                            if 30_000 < total < 50_000_000:
                                outp = os.path.join(OUT, f"conduit{idx}_sec{sh.tag:08X}_off{j}_{family.replace(' ','_')[:30]}.bin")
                                with open(outp, "wb") as wf: wf.write(sec[j:j+total])
                                print(f"      [+] extracted -> {os.path.basename(outp)}")
                        i = j + 4
        except Exception as ex:
            print(f"   DAT1 parse error: {ex}")
    else:
        # Not DAT1 — scan whole file
        for magic in (b"OTTO", b"\x00\x01\x00\x00", b"ttcf"):
            i = 0
            while True:
                j = data.find(magic, i)
                if j < 0: break
                res = validate(data, j, magic)
                if res:
                    nt, known, total, ext = res
                    family = "?"
                    try:
                        names = read_otf_name(data, j, magic)
                        if names: family = names.get(1, names.get(4, "?"))
                    except: pass
                    print(f"   FONT at {j}, size={total}, family={family!r}")
                    if 30_000 < total < 50_000_000:
                        outp = os.path.join(OUT, f"conduit{idx}_off{j}_{family.replace(' ','_')[:30]}.bin")
                        with open(outp, "wb") as wf: wf.write(data[j:j+total])
                        print(f"      [+] extracted -> {os.path.basename(outp)}")
                i = j + 4

print()
print("=== inventory of found_fonts ===")
for f in sorted(os.listdir(OUT)):
    sz = os.path.getsize(os.path.join(OUT, f))
    print(f"  {sz:>10}  {f}")
