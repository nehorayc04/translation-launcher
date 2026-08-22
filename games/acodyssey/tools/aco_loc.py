#!/usr/bin/env python3
r"""
aco_loc.py — AC Odyssey (scimitar v28) LocalizationPackage codec.

Chain:  forge entry -> CFD chain (Oodle, aco_cfd) -> Anvil object
        [u32 class_hash][i32 obj_size][i32 name_len][name][… ScimitarClass base …]
        [i32 Type][u32 Language][12 pad][u32 marker 0xD28389B5][i32 count][BE payload]
        payload = the char-index / fragment-tree string store (identical to
        AC2 v25 / AC Unity v27 / AC Mirage v29 — decoder reused verbatim).

🔑 ODYSSEY DELTA vs Mirage: object names are **PLAINTEXT and never encrypted**
(`name_len & 0x40000000` is clear on all 66 packages), so a package is addressed by
its NAME (`LocalizationPackage_Arabe_MTM`) instead of by content-sniffing. Mirage's
patch forge encrypted them; Odyssey's do not.

There are TWO length fields that must BOTH be re-derived on any content change:
  • obj_size  at content[4]    = len(content) - (12 + name_len + 1)
  • count     at marker+4      = len(payload)

    python aco_loc.py list  <forge>
    python aco_loc.py dump  <forge> <name|#index> [out.json]
    python aco_loc.py stats <forge>
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acunity", "work"))

import aco_forge                                       # noqa: E402
import aco_cfd                                         # noqa: E402
from acu_loc import decode_payload                     # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOC_CLASS = 1849465967
MARKER = 0xD28389B5

# 🔴 DERIVED from the shipped package NAMES, not guessed. A plausible-looking
# "standard" enum was wrong by an offset on the European block — always read the
# id off the object and reconcile it against that object's own name.
LANG_NAMES = {
    1: "English", 2: "French", 3: "Italian", 4: "German", 5: "Spanish(Spain)",
    6: "Spanish(Mexico)", 8: "Portuguese(Brazil)", 9: "Czech", 11: "Dutch",
    16: "Polish", 17: "Russian", 18: "Japanese", 19: "Korean",
    20: "Chinese(Trad)", 21: "Chinese(Simp)", 22: "Arabic",
    23: "Auditioning(Male)",
    # 24..39 = the parallel "_MTM" family (a second full set of every locale)
    24: "Arabic(MTM)", 25: "French(MTM)", 26: "Italian(MTM)", 27: "German(MTM)",
    28: "Spanish(Spain)(MTM)", 29: "Dutch(MTM)", 30: "Czech(MTM)",
    31: "Polish(MTM)", 32: "Russian(MTM)", 33: "Portuguese(Brazil)(MTM)",
    34: "Spanish(Mexico)(MTM)", 35: "Japanese(MTM)", 36: "Korean(MTM)",
    37: "Chinese(Trad)(MTM)", 38: "Chinese(Simp)(MTM)", 39: "LocTest",
}
TYPE_NAMES = {0: "UI", 1: "Subtitles"}


class Package:
    """One decoded LocalizationPackage."""

    __slots__ = ("entry", "content", "cls", "obj_size", "name_len", "name",
                 "encrypted", "mk", "ptype", "language", "payload", "parts")

    def __init__(self, entry, parts):
        self.entry = entry
        self.parts = parts                              # [(data, cinfo, codec), …]
        c = parts[-1][0]
        self.content = c
        self.cls, self.obj_size, nlen = struct.unpack_from("<Iii", c, 0)
        self.encrypted = bool(nlen & 0x40000000)
        self.name_len = nlen & 0xFFFF
        self.name = (None if self.encrypted
                     else c[12:12 + self.name_len].decode("utf-8", "replace"))
        mk = c.find(struct.pack("<I", MARKER))
        if mk < 0:
            raise ValueError("marker 0xD28389B5 not found")
        self.mk = mk
        self.ptype = struct.unpack_from("<i", c, mk - 20)[0]
        self.language = struct.unpack_from("<I", c, mk - 16)[0]
        count = struct.unpack_from("<i", c, mk + 4)[0]
        self.payload = c[mk + 8: mk + 8 + count]

    @property
    def lang_name(self):
        return LANG_NAMES.get(self.language, f"lang{self.language}")

    @property
    def type_name(self):
        return TYPE_NAMES.get(self.ptype, f"type{self.ptype}")

    def strings(self):
        """Decode the char-index payload -> {id: text}."""
        if not self.payload:
            return {}
        return decode_payload(self.payload)

    # -------------------------------------------------------------- rebuild
    def rebuild(self, payload: bytes) -> bytes:
        """Re-emit the object content with a NEW payload, fixing BOTH length
        fields. Everything outside the payload is carried over verbatim."""
        c = self.content
        head = bytearray(c[: self.mk + 4])
        out = bytes(head) + struct.pack("<i", len(payload)) + payload
        # obj_size = total content minus (class + obj_size + name_len + name + NUL)
        obj_size = len(out) - (12 + self.name_len + 1)
        out = bytearray(out)
        struct.pack_into("<i", out, 4, obj_size)
        return bytes(out)


def open_forge(path):
    return aco_forge.Forge(path)


def iter_packages(fg, od=None, names_only=False):
    """Yield Package for every LocalizationPackage in the forge."""
    od = od or aco_cfd.oodle()
    for e in fg.entries:
        try:
            blob = fg.read(e)
            if aco_cfd.peek_class(blob, od) != LOC_CLASS:
                continue
            parts = aco_cfd.decode_resource(blob, od)
            yield Package(e, parts)
        except Exception:
            continue


def find(fg, key, od=None):
    """Find a package by exact name, substring, or #index."""
    od = od or aco_cfd.oodle()
    if key.startswith("#"):
        e = fg.entries[int(key[1:])]
        return Package(e, aco_cfd.decode_resource(fg.read(e), od))
    best = None
    for p in iter_packages(fg, od):
        if p.name == key:
            return p
        if best is None and p.name and key.lower() in p.name.lower():
            best = p
    if best is None:
        raise KeyError(f"no LocalizationPackage matching {key!r}")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "dump", "stats"])
    ap.add_argument("forge")
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()

    fg = open_forge(a.forge)
    od = aco_cfd.oodle()

    if a.cmd == "list":
        print(f"{'idx':>6} {'id':>14} {'type':<10} {'language':<20} "
              f"{'payload':>10}  name")
        for p in iter_packages(fg, od):
            print(f"{p.entry.index:>6} {p.entry.id:>14} {p.type_name:<10} "
                  f"{p.lang_name:<20} {len(p.payload):>10,}  {p.name}")
        return

    if a.cmd == "stats":
        tot = 0
        for p in iter_packages(fg, od):
            s = p.strings()
            tot += len(s)
            chars = sum(len(v) for v in s.values())
            print(f"  {p.name:<45} {p.type_name:<10} {len(s):>7,} strings "
                  f"{chars:>10,} chars")
        print(f"TOTAL records: {tot:,}")
        return

    if a.cmd == "dump":
        p = find(fg, a.args[0], od)
        s = p.strings()
        print(f"{p.name}  type={p.type_name}  lang={p.lang_name}  "
              f"strings={len(s):,}")
        if len(a.args) > 1:
            with open(a.args[1], "w", encoding="utf-8") as fh:
                json.dump(s, fh, ensure_ascii=False, indent=1)
            print(f"wrote {a.args[1]}")
        else:
            for k in list(s)[:15]:
                print(f"  {k}: {s[k]!r}")
        return


if __name__ == "__main__":
    main()
