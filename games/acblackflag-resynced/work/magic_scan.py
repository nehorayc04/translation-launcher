import os, glob, re
d = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
pats = [b'GFXOF', b'GFOF', b'PHXF', b'PHXFD', b'GFX', b'DDS ', b'SDF', b'FONT', b'font', b'OTTO', b'true', b'\x00\x01\x00\x00']
for p in sorted(glob.glob(os.path.join(d,"*.bin"))):
    n=os.path.basename(p)
    data=open(p,'rb').read()
    out=[]
    for pat in pats:
        idxs=[]
        s=0
        while True:
            i=data.find(pat,s)
            if i<0 or len(idxs)>=6: break
            idxs.append(i); s=i+1
        if idxs: out.append(f"{pat!r}x{data.count(pat)}@{[hex(i) for i in idxs]}")
    print(n, "|", "  ".join(out))
print()
# ascii runs in first 0x400 of arabic atlas
p=os.path.join(d,"70970_88c902b3.bin"); data=open(p,'rb').read()
print("--- ASCII runs >=4 in first 0x800 of Arabic atlas ---")
for m in re.finditer(rb'[ -~]{4,}', data[:0x800]):
    print(hex(m.start()), m.group())
print("--- hexdump 0x100-0x180 ---")
for off in range(0x100,0x180,16):
    ch=data[off:off+16]
    print(f"{off:04x}  {ch.hex(' ')}  {''.join(chr(c) if 32<=c<127 else '.' for c in ch)}")
