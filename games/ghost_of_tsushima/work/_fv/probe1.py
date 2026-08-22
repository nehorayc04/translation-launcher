import os, struct
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,"m_lm_menu.sprig.xpps"),"rb").read()
n=len(data)
print(f"file size {n:,} (0x{n:x})")
print("first 64 bytes:", data[:64].hex())
# KCAP / PACK magic?
print("magic[0:4]=", data[:4], " [0:4] rev:", data[:4][::-1])
# find all ascii-ish 4-char tags in first 0x400
import re
print("\n-- ascii tokens in header 0..0x200 --")
for m in re.finditer(rb"[A-Za-z_][A-Za-z0-9_]{2,15}", data[:0x400]):
    print(f"  @0x{m.start():x} {m.group().decode()}")

GREC=64; TBL=0x4223e
tbl_end=TBL
# find real end (sentinel)
q=TBL
while q+GREC<=n:
    cp=struct.unpack_from("<H",data,q)[0]
    if cp==0xffff:
        tbl_end=q+GREC; break
    q+=GREC
print(f"\nglyph table 0x{TBL:x}..0x{tbl_end:x} ({(tbl_end-TBL)//GREC} records)")
print("64 bytes BEFORE table @0x%x:"%(TBL-64), data[TBL-64:TBL].hex())
print("64 bytes AFTER  table @0x%x:"%tbl_end, data[tbl_end:tbl_end+64].hex())
print("256 bytes AFTER table:")
for i in range(0,256,32):
    print(f"  +{i:3d} 0x{tbl_end+i:x}: {data[tbl_end+i:tbl_end+i+32].hex()}")

# Look at what's BEFORE the table too (256 bytes)
print("\n256 bytes BEFORE table:")
for i in range(0,256,32):
    off=TBL-256+i
    print(f"  0x{off:x}: {data[off:off+32].hex()}")
