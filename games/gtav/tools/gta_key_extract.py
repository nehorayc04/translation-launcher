import hashlib, json, struct, os, sys

EXE=r"F:\Games\Grand Theft Auto V Legacy\GTA5.exe"
H=json.load(open(r"C:\Users\NEHORA~1\AppData\Local\Temp\gta_hashes.json"))

def search_hash(data, target20, length):
    tb=bytes(target20); n=len(data); end=n-length; i=0
    while i<=end:
        if hashlib.sha1(data[i:i+length]).digest()==tb:
            return data[i:i+length]
        i+=8
    return None

def search_many(data, targets, length, label):
    # one pass: build map sha1(window)->offset only for windows whose hash is in target set
    tset={bytes(t):k for k,t in enumerate(targets)}
    found={}
    n=len(data); end=n-length; i=0
    remaining=set(tset.keys())
    while i<=end and remaining:
        h=hashlib.sha1(data[i:i+length]).digest()
        if h in remaining:
            found[tset[h]]=data[i:i+length]
            remaining.discard(h)
        i+=8
    res=[found.get(k) for k in range(len(targets))]
    miss=[k for k in range(len(targets)) if res[k] is None]
    print(f"  {label}: found {len(targets)-len(miss)}/{len(targets)} missing={miss[:10]}")
    return res

def main():
    data=open(EXE,"rb").read()
    print(f"GTA5.exe size={len(data):,}")
    aes=search_hash(data,H["aes"],0x20)
    lut=search_hash(data,H["lut"],0x100)
    print("  AES key:", "FOUND" if aes else "MISS", "len", len(aes) if aes else 0)
    print("  LUT    :", "FOUND" if lut else "MISS", "len", len(lut) if lut else 0)
    ngk=search_many(data,H["ngk"],0x110,"NG_KEYS(101x272)")
    ngt=search_many(data,H["ngt"],0x400,"NG_TABLES(272x1024)")
    out={
      "aes": aes.hex() if aes else None,
      "lut": lut.hex() if lut else None,
      "ngk": [k.hex() if k else None for k in ngk],
      "ngt": [t.hex() if t else None for t in ngt],
    }
    json.dump(out, open(r"C:\Users\NEHORA~1\AppData\Local\Temp\gta_keys.json","w"))
    print("saved gta_keys.json")
main()
