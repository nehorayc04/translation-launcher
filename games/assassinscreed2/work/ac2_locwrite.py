#!/usr/bin/env python3
"""
Rebuild a LocalizationPackage forge resource with modified strings.

resource = FILEDATA(8)+name(128) + DataFile( prefetch + CFD1 + CFD2 + sig ).
CFD2 decompresses to the DataFile entry:
  id(u32) count(i32) nameLen(u32) name fileheader(1)  +  LocalizationPackage:
    ScimitarClass... Type Language skip8 discard  blobLen(i32 @start-4)  blob.
The blob is the LAST bytes (start+blobLen == payload_len). So a length change
only touches two LE-i32 fields: the DataFile `count` (@4) and `blobLen` (@start-4).
We re-pack CFD2 as STORED blocks (no LZO) and splice it back into the resource.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ac2_loc, ac2_cfd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _find_cfd2(resource):
    cfds = []
    pos = resource.find(ac2_cfd.CFD_MAGIC)
    while 0 <= pos < len(resource) - 8 and resource[pos:pos+8] == ac2_cfd.CFD_MAGIC:
        data, nxt = ac2_cfd.parse_one_cfd(resource, pos)
        cfds.append((pos, nxt, data))
        pos = nxt if resource[nxt:nxt+8] == ac2_cfd.CFD_MAGIC else resource.find(ac2_cfd.CFD_MAGIC, nxt)
    return max(cfds, key=lambda c: len(c[2]))


def rebuild(resource: bytes, edits: dict) -> bytes:
    """edits = {string_id: new_text}. Returns a new resource."""
    cfd2_start, cfd2_end, payload = _find_cfd2(resource)
    start, parsed, strings = ac2_loc.decode_payload(payload)
    old_blob_len = struct.unpack_from("<i", payload, start - 4)[0]
    old_count = struct.unpack_from("<i", payload, 4)[0]
    d = dict(strings)
    for sid, txt in edits.items():
        if sid not in d:
            raise KeyError(f"string id {sid} not in package")
        d[sid] = txt
    new_blob = ac2_loc.encode_blob(sorted(d.items()))
    delta = len(new_blob) - old_blob_len
    new_payload = (payload[:4] + struct.pack("<i", old_count + delta)
                   + payload[8:start - 4] + struct.pack("<i", len(new_blob)) + new_blob)
    new_cfd2 = ac2_cfd.encode_cfd_stored(new_payload)
    return resource[:cfd2_start] + new_cfd2 + resource[cfd2_end:]


def scan_size_fields(resource):
    _, _, payload = _find_cfd2(resource)
    start, parsed, strings = ac2_loc.decode_payload(payload)
    bl = struct.unpack_from("<i", payload, start - 4)[0]
    cnt = struct.unpack_from("<i", payload, 4)[0]
    hits = []
    for p in range(0, start):
        v = struct.unpack_from("<i", payload, p)[0]
        if v in (bl, cnt, bl + 33, len(payload), len(payload) - 8):
            hits.append((p, v))
    return start, bl, cnt, len(payload), hits
