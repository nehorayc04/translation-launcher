import re, json
src=open(r"C:\Users\NEHORA~1\AppData\Local\Temp\GTAKeys.cs","r",encoding="utf-8-sig").read()
def grab_single(name):
    m=re.search(name+r"\s*=\s*new byte\[\]\s*\{([^}]*)\};", src)
    return [int(x,16) for x in re.findall(r"0x[0-9A-Fa-f]{2}",m.group(1))]
def grab_array(name):
    m=re.search(name+r"\s*=\s*new byte\[[^\]]*\]\s*\[\]\s*\{", src)  # definition site
    eq=m.end()-1  # position of '{'
    depth=0; i=eq
    while i<len(src):
        c=src[i]
        if c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:break
        i+=1
    block=src[eq:i+1]
    arrs=re.findall(r"new byte\[\]\s*\{([0-9A-Fa-fx,\s]*?)\}", block)
    return [[int(x,16) for x in re.findall(r"0x[0-9A-Fa-f]{2}",a)] for a in arrs]
aes=grab_single("PC_AES_KEY_HASH"); lut=grab_single("PC_LUT_HASH")
ngk=grab_array("PC_NG_KEY_HASHES"); ngt=grab_array("PC_NG_DECRYPT_TABLE_HASHES")
print("aes",len(aes),"lut",len(lut),"ngk",len(ngk),set(len(x) for x in ngk),"ngt",len(ngt),set(len(x) for x in ngt))
json.dump({"aes":aes,"lut":lut,"ngk":ngk,"ngt":ngt}, open(r"C:\Users\NEHORA~1\AppData\Local\Temp\gta_hashes.json","w"))
print("ok")
