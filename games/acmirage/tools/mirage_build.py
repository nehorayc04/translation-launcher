#!/usr/bin/env python3
"""
mirage_build.py — rebuild an AC Mirage LocalizationPackage resource blob with new
strings, ready for `mirage_deploy.py`.

Object layout (mapped byte-for-byte on the real base forge):

    +0    u32 class_hash        (1849465967 = LocalizationPackage)
    +4    i32 size              <-- LENGTH FIELD #1 = len(content) - (12 + name_len + 1)
    +8    i32 name_len
    +12   char[name_len] name
          u8  0x00              (name terminator)
          u8  0x01              (file header byte)
          u64 ClassID           (== the forge resource id)
          u32 Hash              (== class_hash)
          i32 Type              (0 = UI, 1 = Subtitles)
          u32 Language          (1 = English(US), 22 = Arabic, ...)
          12 bytes              (unused)
          u32 0xD28389B5        (constant marker, read-and-discarded by the engine)
    +mk+4 i32 count             <-- LENGTH FIELD #2 = len(payload)
    +mk+8 payload[count]        BE char-index store; runs to the END of the object

**Both length fields must be re-derived on any content change** — a stale one is an
out-of-bounds read (the AC Black Flag Resynced lesson: "warning window + crash").

    python mirage_build.py <forge> selftest <resource_id>
    python mirage_build.py <forge> build    <resource_id> <strings.json> <out.bin>
    python mirage_build.py <forge> proof    <resource_id> <out.bin>
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
from acu_loc import decode_payload, encode_payload  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOC_CLASS = 1849465967
MARKER = 0xD28389B5

# resource ids in DataPC.forge (identical in DataPC_patch_01.forge)
AR_UI_ID = 2130870776974
AR_SUBS_ID = 2130870776975
EN_UI_ID = 2132259441960
EN_SUBS_ID = 2132259441961


class LocResource:
    """A decoded LocalizationPackage resource, re-serialisable."""

    def __init__(self, blob, oodle):
        self.oodle = oodle
        self.cfds, consumed = acs_cfd.decode_resource(blob, oodle)
        self.trailer = blob[consumed:]          # normally empty
        self.content = self.cfds[-1][0]
        c = self.content
        self.cls, self.size_field, nlen_raw = struct.unpack_from("<Iii", c, 0)
        if self.cls != LOC_CLASS:
            raise SystemExit(f"class {self.cls} is not a LocalizationPackage")
        # 🔴 The 0x40000000 flag encrypts the NAME FIELD ONLY — the payload after the
        # marker stays plaintext. Never abort on it: that guard hid the fact that the
        # patch forge (the copy the engine actually reads) is fully readable.
        # The name bytes are kept OPAQUE and copied through verbatim on rebuild, so we
        # never need the key (same principle as "copy the hash bytes, don't recompute").
        self.name_encrypted = bool(nlen_raw & 0x40000000)
        self.name_len = nlen_raw & 0xFFFF
        self.name = ("<encrypted:%d>" % self.name_len if self.name_encrypted
                     else c[12:12 + self.name_len].decode("utf-8", "replace"))
        self.mk = c.find(struct.pack("<I", MARKER))
        if self.mk < 0:
            raise SystemExit("marker 0xD28389B5 not found")
        self.count = struct.unpack_from("<i", c, self.mk + 4)[0]
        self.payload = c[self.mk + 8: self.mk + 8 + self.count]
        self.tail = c[self.mk + 8 + self.count:]
        self.ptype = struct.unpack_from("<i", c, self.mk - 20)[0]
        self.language = struct.unpack_from("<I", c, self.mk - 16)[0]
        # LENGTH #1 is `len(content) - header_delta`. For a plaintext name the delta is
        # 12 + name_len + 1; for an ENCRYPTED name the stored field is padded up to a
        # 16-byte boundary (51 -> 64, 56 -> 64), so derive the delta from the ORIGINAL
        # instead of re-deriving the rule — that works for both cases with no guessing.
        self.header_delta = len(c) - self.size_field
        self.strings = decode_payload(self.payload)

    # ------------------------------------------------------------------ write
    def rebuild(self, strings=None):
        """Return a new resource blob carrying `strings` (default: unchanged)."""
        payload = encode_payload(strings if strings is not None else self.strings)
        c = self.content
        new_content = (c[:self.mk + 4]
                       + struct.pack("<i", len(payload))
                       + payload
                       + self.tail)
        new_size = len(new_content) - self.header_delta
        new_content = bytearray(new_content)
        struct.pack_into("<i", new_content, 4, new_size)     # LENGTH FIELD #1
        new_content = bytes(new_content)

        out = bytearray()
        for i, (data, cinfo) in enumerate(self.cfds):
            payload_data = new_content if i == len(self.cfds) - 1 else data
            out += acs_cfd.build_cfd(payload_data, cinfo, self.oodle)
        out += self.trailer
        return bytes(out)


def load(forge, res_id, oodle=None):
    fg = Forge(forge)
    od = oodle or acs_cfd._oodle()
    m = [e for e in fg.entries if e.id == int(res_id)]
    if not m:
        raise SystemExit(f"resource id {res_id} not found")
    blob = fg.read(m[0])
    fg.f.close()
    return LocResource(blob, od)


# --------------------------------------------------------------------- proof
PROOF = {
    # a pure-Latin marker proves MOUNT independently of the font,
    # Hebrew on neighbouring keys proves FONT + BIDI in the same screenshot.
    "marker": "ZZ-MIRAGE-OK-ZZ",
    "hebrew": ["הגדרות", "בחר שפה", "יציאה", "המשך", "טען משחק"],
}


def build_proof(res, en_strings):
    """Patch a handful of short, always-visible option-menu keys.

    The ids are located in the ENGLISH package (ids are shared across all 14
    languages) and then written into `res`, which is the ARABIC slot.
    """
    # ordered: the first is the pure-Latin mount marker, the rest carry Hebrew
    plan = [("Options Page", PROOF["marker"])] + list(
        zip(["Controls", "Interface Language", "Credits", "Sound", "Audio"], PROOF["hebrew"]))
    by_text = {}
    for k, v in en_strings.items():
        if v not in by_text:
            by_text[v] = k
    out = dict(res.strings)
    picked = []
    for src, new in plan:
        k = by_text.get(src)
        if k is None or k not in out:
            print(f"    [skip] no id for {src!r}")
            continue
        picked.append((k, src, out[k], new))
        out[k] = new
    return out, picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("cmd", choices=["selftest", "build", "proof", "info"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()

    od = acs_cfd._oodle()
    res = load(a.forge, a.args[0], od)
    print(f"# {res.name}")
    print(f"# Type={res.ptype} Language={res.language} strings={len(res.strings):,} "
          f"payload={len(res.payload):,} content={len(res.content):,} cfds={len(res.cfds)}")

    if a.cmd == "info":
        return 0

    if a.cmd == "selftest":
        blob = res.rebuild()                       # identity rebuild
        back = LocResource(blob, od)
        same = sum(1 for k in res.strings if back.strings.get(k) == res.strings[k])
        okc = back.cls == res.cls and back.name == res.name
        okt = back.ptype == res.ptype and back.language == res.language
        sz_ok = back.size_field == len(back.content) - back.header_delta
        cnt_ok = back.count == len(back.payload)
        print(f"  strings   : {same:,}/{len(res.strings):,} "
              f"{'PASS' if same == len(res.strings) else 'FAIL'}")
        print(f"  header    : class/name {'OK' if okc else 'FAIL'} · "
              f"Type/Language {'OK' if okt else 'FAIL'}")
        print(f"  len field1: {'OK' if sz_ok else 'FAIL'} (size={back.size_field:,})")
        print(f"  len field2: {'OK' if cnt_ok else 'FAIL'} (count={back.count:,})")
        print(f"  blob      : {len(blob):,} B  (payload {len(res.payload):,} -> "
              f"{len(back.payload):,}, {len(back.payload)/len(res.payload):.2f}x)")
        return 0 if (same == len(res.strings) and okc and okt and sz_ok and cnt_ok) else 1

    if a.cmd == "proof":
        en_id = a.args[2] if len(a.args) > 2 else EN_UI_ID
        en = load(a.forge, en_id, od)
        strings, picked = build_proof(res, en.strings)
        blob = res.rebuild(strings)
        open(a.args[1], "wb").write(blob)
        print(f"  patched {len(picked)} keys (ids from {en.name}):")
        for k, src, old, new in picked:
            print(f"    [{k}] {src!r}  {old!r} -> {new!r}")
        print(f"  wrote {a.args[1]} ({len(blob):,} B)")
        return 0

    if a.cmd == "build":
        new = json.load(open(a.args[1], encoding="utf-8"))
        strings = dict(res.strings)
        applied = 0
        for k, v in new.items():
            ik = int(k)
            if ik in strings:
                strings[ik] = v
                applied += 1
        blob = res.rebuild(strings)
        open(a.args[2], "wb").write(blob)
        print(f"  applied {applied:,}/{len(new):,} overrides; wrote {a.args[2]} ({len(blob):,} B)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
