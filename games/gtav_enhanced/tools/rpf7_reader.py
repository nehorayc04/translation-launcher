import struct, os, sys
sys.setrecursionlimit(1_000_000)
ENC={0:"NONE",0x4E45504F:"OPEN",0x0FFFFFF9:"AES",0x0FEFFFFF:"NG"}
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
KEY=bytes.fromhex("b38973af8b9e263a8df170321442b3938bd3f21fa4d04dff882e04660ff99dfd")
be=default_backend()
def decrypt_aes(data):
    blocks=len(data)-(len(data)%16); body=bytes(data[:blocks])
    for _ in range(16):
        d=Cipher(algorithms.AES(KEY),modes.ECB(),backend=be).decryptor()
        body=d.update(body)+d.finalize()
    return body+data[blocks:]
def cstr(block,off):
    e=block.find(b"\x00",off); 
    if e<0:e=len(block)
    return block[off:e].decode("latin-1","replace")

def read_toc(blob_read, base_off, file_size):
    # blob_read(absolute_off, length) -> bytes ; TOC at base_off
    hdr=blob_read(base_off,16)
    magic,ec,nl,enc=struct.unpack("<IIII",hdr)
    if magic!=0x52504637: return None
    ent=blob_read(base_off+16, ec*16)
    nms=blob_read(base_off+16+ec*16, nl)
    if enc==0x0FFFFFF9:
        ent=decrypt_aes(ent); nms=decrypt_aes(nms)
    elif enc==0x0FEFFFFF:
        return ("NG",ec,nl,None,None)
    return (ENC.get(enc,hex(enc)),ec,nl,ent,nms)

def entry_is_dir(b): return struct.unpack("<I",b[4:8])[0]==0x7FFFFF00

def list_rpf(path):
    """List all files in an RPF (recursing into nested RPFs by reading them in-place)."""
    f=open(path,"rb"); 
    fsize=os.path.getsize(path)
    def make_reader(base):
        def rd(absoff,length):
            f.seek(absoff); return f.read(length)
        return rd
    results=[]  # (fullpath, is_gxt2, size, abs_data_off, enctype)
    def walk_rpf(rpf_base, path_prefix):
        rd=make_reader(rpf_base)
        toc=read_toc(rd, rpf_base, fsize)
        if toc is None: 
            results.append((path_prefix+" [BAD_RPF]",False,0,0,0)); return
        encname,ec,nl,ent,nms=toc
        if ent is None:
            results.append((path_prefix+" [NG_ENCRYPTED_RPF]",False,0,0,0)); return
        entries=[ent[i*16:i*16+16] for i in range(ec)]
        def rec(idx,prefix,depth):
            if idx<0 or idx>=len(entries) or depth>80: return
            b=entries[idx]
            if entry_is_dir(b):
                noff=struct.unpack("<I",b[0:4])[0]; nm=cstr(nms,noff)
                ei=struct.unpack("<I",b[8:12])[0]; cnt=struct.unpack("<I",b[12:16])[0]
                here=prefix if idx==0 else prefix+nm+"/"
                for c in range(ei,ei+cnt): rec(c,here,depth+1)
            else:
                noff=struct.unpack("<H",b[0:2])[0]; nm=cstr(nms,noff)
                buf=struct.unpack("<Q",b[0:8])[0]
                size=(buf>>16)&0xFFFFFF
                offblocks=(buf>>40)&0xFFFFFF
                usize=struct.unpack("<I",b[8:12])[0]
                enctype=struct.unpack("<I",b[12:16])[0]
                data_abs = rpf_base + offblocks*512
                full=prefix+nm
                low=nm.lower()
                results.append((full,low.endswith(".gxt2"),size,data_abs,enctype))
                if low.endswith(".rpf"):
                    # nested RPF: recurse if its data is plain (enctype 0) and offset valid
                    try:
                        walk_rpf(data_abs, full+"/")
                    except Exception as e:
                        results.append((full+" [NEST_ERR:%s]"%e,False,0,0,0))
        rec(0,path_prefix,0)
    walk_rpf(0,"")
    f.close()
    return results

def main():
    path=sys.argv[1]
    res=list_rpf(path)
    gxt=[r for r in res if r[1]]
    rpfs=[r for r in res if r[0].lower().endswith(".rpf")]
    print(f"FILE={path}")
    print(f"  total_listed={len(res)}  gxt2={len(gxt)}  nested_rpf={len(rpfs)}")
    print("  --- ALL gxt2 ---")
    for full,isg,size,off,enct in gxt:
        print(f"   GXT2 size={size} enc={enct} off=0x{off:X}  {full}")
    # show any lang dirs
    print("  --- lang/global candidates ---")
    for full,isg,size,off,enct in res:
        l=full.lower()
        if l.endswith('.rpf') and ('lang' in l):
            print("   LANGRPF:",full)
    # NG markers
    for full,isg,size,off,enct in res:
        if '[NG_ENCRYPTED_RPF]' in full or '[BAD_RPF]' in full or '[NEST_ERR' in full:
            print("   NOTE:",full)
if __name__=="__main__":
    main()
