import struct, collections, glob, os
def dump(p):
    d=open(p,'rb').read(); g=d.find(b'GFOF')
    cnt=struct.unpack_from('<I',d,g+4)[0]
    base=0x158-0x114+g   # same relative offset
    recs=[]
    for i in range(cnt):
        o=base+i*36
        if o+36>len(d): break
        cp=struct.unpack_from('<I',d,o)[0]
        recs.append(cp)
    ok=sum(1 for c in recs if 0x20<=c<=0x10FFFF)
    print(f"\n{os.path.basename(p)} GFOF@{g:#x} count={cnt} tableEnd={base+cnt*36:#x} plausibleCP={ok}/{len(recs)}")
    blocks=collections.Counter()
    for c in recs:
        if 0x0590<=c<=0x05FF: blocks['Hebrew']+=1
        elif 0x0600<=c<=0x06FF: blocks['Arabic']+=1
        elif 0x0750<=c<=0x077F: blocks['ArabicSupp']+=1
        elif 0xFB50<=c<=0xFDFF: blocks['ArabPresA']+=1
        elif 0xFE70<=c<=0xFEFF: blocks['ArabPresB']+=1
        elif 0xFB1D<=c<=0xFB4F: blocks['HebrewPres']+=1
        elif c<0x0180: blocks['Latin']+=1
        elif 0x0400<=c<=0x04FF: blocks['Cyrillic']+=1
        elif 0x0E00<=c<=0x0E7F: blocks['Thai']+=1
        elif 0x3000<=c<=0x9FFF: blocks['CJK']+=1
        elif 0x2000<=c<=0x2BFF: blocks['Punct/Sym']+=1
        else: blocks[f'other']+=1
    print("  ", dict(blocks.most_common()))
    print("   first 12 cps:", [f"U+{c:04X}" for c in recs[:12]])
for p in sorted(glob.glob(r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas\*.bin")):
    dump(p)
