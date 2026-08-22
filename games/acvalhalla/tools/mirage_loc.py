#!/usr/bin/env python3
"""
mirage_loc.py — AC Mirage (scimitar v29) LocalizationPackage decoder.

Chain:  forge entry -> CFD chain (Oodle, acs_cfd) -> Anvil object
        [u32 class_hash][i32 size][i32 name_len][name][... ScimitarClass base ...]
        [i32 Type][u32 Language][12 pad][u32 marker 0xD28389B5][i32 count][BE payload]
        payload = the char-index / fragment-tree string store (same format as
        AC2 v25 / AC Unity v27 — decoder reused verbatim from acu_loc.py).

    python mirage_loc.py <forge> <resource_id> [out.json]
    python mirage_loc.py <forge> --list
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "acunity", "work"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402
from acu_loc import decode_payload  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOC_CLASS = 1849465967
MARKER = 0xD28389B5


def decode_cfds(buf, oodle):
    off, out = 0, []
    while off < len(buf) - 8 and struct.unpack_from("<Q", buf, off)[0] == acs_cfd.MAGIC:
        data, off, _ci = acs_cfd.parse_cfd(buf, off, oodle)
        out.append(data)
    return out


def object_info(content):
    cls, size, nlen = struct.unpack_from("<Iii", content, 0)
    encrypted = bool(nlen & 0x40000000)
    n = nlen & 0xFFFF
    name = None if encrypted else content[12:12 + n].decode("utf-8", "replace")
    return cls, size, n, encrypted, name


def find_payload(content):
    """Locate [marker][count][payload] after the object header."""
    mk = content.find(struct.pack("<I", MARKER))
    if mk < 0:
        raise ValueError("marker 0xD28389B5 not found (encrypted or different layout?)")
    count = struct.unpack_from("<i", content, mk + 4)[0]
    if not (0 < count <= len(content) - mk - 8):
        raise ValueError(f"bad payload count {count}")
    language = struct.unpack_from("<I", content, mk - 16)[0]
    ptype = struct.unpack_from("<i", content, mk - 20)[0]
    return ptype, language, content[mk + 8: mk + 8 + count]


def load(forge_path, res_id, oodle=None):
    fg = Forge(forge_path)
    od = oodle or acs_cfd._oodle()
    ents = [e for e in fg.entries if e.id == int(res_id)]
    if not ents:
        raise SystemExit(f"id {res_id} not in {os.path.basename(forge_path)}")
    cfds = decode_cfds(fg.read(ents[0]), od)
    content = cfds[-1]
    cls, size, nlen, enc, name = object_info(content)
    if cls != LOC_CLASS:
        raise SystemExit(f"resource class {cls} is not a LocalizationPackage")
    if enc:
        raise SystemExit(f"resource is ENCRYPTED (name_len flag 0x40000000) — {os.path.basename(forge_path)}")
    ptype, language, payload = find_payload(content)
    return name, ptype, language, decode_payload(payload)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("res_id", nargs="?")
    ap.add_argument("out", nargs="?")
    a = ap.parse_args()

    name, ptype, language, strings = load(a.forge, a.res_id)
    print(f"# {name}")
    print(f"# Type={ptype}  Language={language}  strings={len(strings):,}")
    if a.out:
        json.dump({str(k): v for k, v in strings.items()}, open(a.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        print(f"wrote {a.out}")
    else:
        for k, v in list(strings.items())[:25]:
            print(f"  [{k}] {v!r}")


if __name__ == "__main__":
    main()
