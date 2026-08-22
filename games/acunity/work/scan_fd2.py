#!/usr/bin/env python3
"""Fast FireData sweep: peek only the first block of each resource's content CFD, read
content[0] (the ScimitarClass hash). content[0]==2940455555 => FireData (Scaleform SWF)."""
import sys, struct
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
import acu_forge as F, acu_loc as L

FIREDATA = 2940455555
CAP = 12 * 1024 * 1024


def peek_content_head(blob, need=32):
    """Decompress just enough of the 2nd CFD to return its first `need` content bytes."""
    if struct.unpack_from("<Q", blob, 0)[0] != L._MAGIC:
        return None
    p, _ = L.cfd_decompress(blob, 0)           # meta CFD (small)
    if p + 8 > len(blob) or struct.unpack_from("<Q", blob, p)[0] != L._MAGIC:
        return None
    pos = p + 8
    ver, algo, maxU, maxC = struct.unpack_from("<hBHH", blob, pos); pos += 7
    n = struct.unpack_from("<i", blob, pos)[0]; pos += 4
    bi = pos; pos += n * 4
    out = bytearray()
    for i in range(n):
        uncomp, comp = struct.unpack_from("<HH", blob, bi + i * 4)
        pos += 4
        payload = blob[pos:pos + comp]; pos += comp
        out += payload if uncomp == comp else L._lzo_dec(payload, uncomp)
        if len(out) >= need:
            break
    return bytes(out)


def main():
    path = sys.argv[1]
    fg = F.Forge(path)
    hits = 0
    for i in range(fg.count):
        off = fg.recs[i][0]
        if off == 0:
            continue
        ds = fg.disk_size(i)
        if ds > CAP or ds < 40:
            continue
        try:
            head = peek_content_head(fg.extract_index(i), 8)
        except Exception:
            continue
        if head is None or len(head) < 4:
            continue
        if struct.unpack_from("<I", head, 0)[0] == FIREDATA:
            nm = fg.index_to_name.get(i, "")
            print(f"  [{i:5}] disk={ds:>9,}  {nm}", flush=True)
            hits += 1
    print(f"# {path.split('/')[-1]}: FireData={hits}", flush=True)


if __name__ == "__main__":
    main()
