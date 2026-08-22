import struct
p = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas\70970_88c902b3.bin"
d = open(p,'rb').read()
g = d.find(b'GFOF')
print("count@GFOF+4 =", struct.unpack_from('<I', d, g+4)[0])
# scan first 0x4000 after GFOF for u32 in unicode ranges, report offsets+strides
hits=[]
for off in range(g, g+0x4000, 4):
    v = struct.unpack_from('<I', d, off)[0]
    if 0x0020 <= v <= 0xFFFF:
        hits.append((off, v))
ar = [(o,v) for o,v in hits if 0x0600<=v<=0x06FF or 0xFB50<=v<=0xFEFF]
print("arabic-range u32 hits in first 16KB:", len(ar))
for o,v in ar[:25]: print(f"  {o:#08x} U+{v:04X}  (delta from prev: {o-ar[ar.index((o,v))-1][0] if ar.index((o,v))>0 else 0})")
# also: scan WHOLE file for a dense sorted codepoint table (u16)
import collections
best=None
for off in range(g, min(len(d)-2, g+0x200000)):
    pass
# u16 table scan: find runs of ascending u16 of length>=64
n=len(d)//2
arr = struct.unpack_from(f'<{n}H', d, 0)
run=1; runs=[]
for i in range(1,n):
    if 0x20 <= arr[i] <= 0xFFFF and arr[i] > arr[i-1]:
        run+=1
    else:
        if run>=64: runs.append((i-run, run, arr[i-run], arr[i-1]))
        run=1
if run>=64: runs.append((n-run, run, arr[n-run], arr[n-1]))
print("\nascending u16 runs >=64 (offset, len, first, last):")
for st,l,a,b in runs[:12]: print(f"  byteoff={st*2:#08x} len={l} U+{a:04X}..U+{b:04X}")
