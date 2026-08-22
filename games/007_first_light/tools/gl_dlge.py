"""
gl_dlge.py — decode Glacier DLGE (dialogue subtitle) resources for 007 First Light.

Format from AnthonyFuller/TonyTools HMLanguages Languages.cpp (DLGE::Convert). A DLGE is a small
container tree (WavFile / Random / Switch / Sequence). The translatable text lives in the WavFile
leaves: each WavFile holds one subtitle per language slot, XTEA-encrypted (007 l10n key), keyed by
the shared wavNameHash so EN maps to HE.

Byte layout (non-H2016 / H3-family, which 007 follows):
  u32 DITL_ref_index, u32 CLNG_ref_index            (indices into the resource's references; skipped)
  repeat until index == size-2:
    peek u8 section type:
      0x01 WavFile:  u8 type, u32 soundTagHash, u32 wavNameHash, u32 (skip),
                     per language: u32 wavIndex, u32 ffxIndex,
                        peek u32 subLen: if !=0 -> read {u32 len; len bytes}=XTEA subtitle; else skip 4
      0x02/03/04 Container: u8 type, u32 SwitchGroupHash, u32 DefaultSwitchHash,
                     u32 count, count x { u16 typeIndex; u32 n; n x u32 SwitchHashes }
  u16 rootTypedIndex                                 (last 2 bytes)

007 language slots (15, from CLNG): xx en fr it de es ru mx br pl cn jp tc kr tr.
"""
import struct
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gl_locr import xtea_decrypt, xtea_encrypt, _cstr

LANGS_007 = ["xx", "en", "fr", "it", "de", "es", "ru", "mx", "br", "pl", "cn", "jp", "tc", "kr", "tr"]


class _Buf:
    def __init__(self, d):
        self.d = d
        self.i = 0

    def u8(self):
        v = self.d[self.i]; self.i += 1; return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.i)[0]; self.i += 2; return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.i)[0]; self.i += 4; return v

    def peek_u8(self):
        return self.d[self.i]

    def peek_u32(self):
        return struct.unpack_from("<I", self.d, self.i)[0]

    def take(self, n):
        v = self.d[self.i:self.i + n]; self.i += n; return v


# 007-specific WavFile layout (brute-forced against 60 DLGE, 60/60 exact-consume):
#   type u8=0x01, then a 13-byte header (soundTagHash u32 + wavNameHash u32 + u32 + u8),
#   then per language a 9-byte prefix (wavIndex u32 + 1 byte + ffxIndex u32) + subtitle:
#     size u32; if != 0 -> `size` XTEA bytes; else the size u32 (=0) is the whole field.
WAV_HDR = 13
LANG_PREFIX = 9


def decode_dlge(data: bytes, langs=LANGS_007):
    """Return (wavs, ok). wavs = list of {wavName:int, soundtag:int, langs:{lang:str}} in order.
    ok = the buffer consumed exactly to size-2 (structural validity)."""
    b = _Buf(data)
    b.u32(); b.u32()                       # DITL, CLNG reference indices
    wavs = []
    end = len(data) - 2
    while b.i < end:
        t = b.peek_u8()
        if t == 0x01:                      # WavFile
            b.u8()
            soundtag = struct.unpack_from("<I", data, b.i)[0]
            wavname = struct.unpack_from("<I", data, b.i + 4)[0]
            b.i += WAV_HDR
            entry = {"wavName": wavname, "soundtag": soundtag, "langs": {}}
            for lang in langs:
                b.i += LANG_PREFIX          # wavIndex + 1 + ffxIndex
                sz = b.peek_u32()
                if sz != 0:
                    b.u32()
                    txt = _cstr(xtea_decrypt(b.take(sz)))
                    if txt:
                        entry["langs"][lang] = txt
                else:
                    b.u32()                # zero size marker
            wavs.append(entry)
        elif t in (0x02, 0x03, 0x04):      # Random / Switch / Sequence container
            b.u8()
            b.u32()                        # SwitchGroupHash
            b.u32()                        # DefaultSwitchHash
            count = b.u32()
            for _ in range(count):
                b.u16()                    # typeIndex
                n = b.u32()                # SwitchHashes count
                for _ in range(n):
                    b.u32()
        else:
            return wavs, False             # unknown section -> parse desync
    b.u16()                                # rootTypedIndex
    return wavs, (b.i == len(data))


def english_lines(data: bytes, source="en"):
    """Return list of (wav_ordinal, wavNameHash, english_text) for WavFiles that carry source text."""
    wavs, ok = decode_dlge(data)
    out = []
    for i, w in enumerate(wavs):
        s = w["langs"].get(source)
        if s:
            out.append((i, w["wavName"], s))
    return out, ok


def _cli():
    import argparse
    from gl_rpkg import RPKG
    ap = argparse.ArgumentParser()
    ap.add_argument("rpkg")
    ap.add_argument("cmd", choices=["one", "validate", "sample"])
    ap.add_argument("arg", nargs="?", default="")
    a = ap.parse_args()
    r = RPKG(a.rpkg)
    if a.cmd == "one":
        i = int(a.arg)
        wavs, ok = decode_dlge(r.read(i))
        print(f"DLGE {r.resources[i].name()} wavs={len(wavs)} structural_ok={ok}")
        for w in wavs[:6]:
            en = w["langs"].get("en", "")
            print(f"  wav {w['wavName']:08X} en={en!r}  (langs: {sorted(w['langs'])})")
    elif a.cmd == "validate":
        idxs = r.indices("DLGE")
        n = int(a.arg) if a.arg else len(idxs)
        ok_c = bad_c = txt_c = 0
        for i in idxs[:n]:
            try:
                wavs, ok = decode_dlge(r.read(i))
            except Exception:
                bad_c += 1; continue
            ok_c += ok; bad_c += (not ok)
            txt_c += sum(1 for w in wavs if w["langs"].get("en"))
        print(f"DLGE validate: {ok_c}/{n} structural-OK, {bad_c} bad, {txt_c} english lines")
    elif a.cmd == "sample":
        for i in r.indices("DLGE")[:12]:
            wavs, ok = decode_dlge(r.read(i))
            en = next((w["langs"]["en"] for w in wavs if w["langs"].get("en")), None)
            print(f"  {r.resources[i].hex()} ok={ok} wavs={len(wavs)} en={en!r}")


if __name__ == "__main__":
    _cli()
