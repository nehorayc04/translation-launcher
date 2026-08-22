#!/usr/bin/env python3
r"""
oodle.py — ctypes wrapper around the Oodle DLL for DECODING (and ENCODING) the
Kraken/Mermaid blocks inside The Last of Us Part I PSARC archives.

Unlike AC Shadows, TLOU Part I SHIPS its own Oodle DLL right in the game folder:
    D:\Games\The Last of Us - Part I\oo2core_9_win64.dll   (Oodle 2.9.x)

so no borrowing. Override with env TLOU_OODLE_DLL or --dll.

Both OodleLZ_Decompress and OodleLZ_Compress are exported, so we can unpack AND
re-pack — the Oodle license only restricts REDISTRIBUTING the DLL, not local calls.
"""
import os
import ctypes
from ctypes import c_void_p, c_int64, c_int

# compressor ids: Kraken=8, Mermaid=9, Selkie=11, Leviathan=13, Hydra=12
OODLE_KRAKEN = 8
OODLE_LEVEL_NORMAL = 4          # None=0 SuperFast=1 VeryFast=2 Fast=3 Normal=4 Opt1..5=5..9

_CANDIDATE_DLLS = [
    os.environ.get("TLOU_OODLE_DLL", ""),
    r"D:\Games\The Last of Us - Part I\oo2core_9_win64.dll",
    r"C:\Games\Battlefield 6\oo2core_9_win64.dll",
]


def _find_dll(explicit=None):
    for p in ([explicit] if explicit else []) + _CANDIDATE_DLLS:
        if p and os.path.isfile(p):
            return p
    raise FileNotFoundError("no oo2core_*_win64.dll found — pass --dll or set TLOU_OODLE_DLL")


class Oodle:
    def __init__(self, dll_path=None):
        self.path = _find_dll(dll_path)
        self.dll = ctypes.CDLL(self.path)
        self.dll.OodleLZ_Decompress.restype = c_int64
        self.dll.OodleLZ_Decompress.argtypes = [
            c_void_p, c_int64, c_void_p, c_int64,
            c_int, c_int, c_int,
            c_void_p, c_int64, c_void_p, c_void_p,
            c_void_p, c_int64, c_int,
        ]
        self.dll.OodleLZ_Compress.restype = c_int64
        self.dll.OodleLZ_Compress.argtypes = [
            c_int, c_void_p, c_int64, c_void_p, c_int,
            c_void_p, c_void_p, c_void_p, c_void_p, c_int64,
        ]

    def decompress(self, comp: bytes, raw_size: int) -> bytes:
        out = ctypes.create_string_buffer(raw_size)
        n = self.dll.OodleLZ_Decompress(
            comp, len(comp), out, raw_size,
            1, 0, 0,          # fuzzSafe=Yes checkCRC=No verbosity=None
            None, 0, None, None,
            None, 0, 3,       # threadPhase = Unthreaded
        )
        if n != raw_size:
            raise RuntimeError(f"OodleLZ_Decompress returned {n}, expected {raw_size}")
        return out.raw[:raw_size]

    def compress(self, raw: bytes, compressor=OODLE_KRAKEN, level=OODLE_LEVEL_NORMAL) -> bytes:
        bound = len(raw) + len(raw) // 2 + 65536
        out = ctypes.create_string_buffer(bound)
        n = self.dll.OodleLZ_Compress(
            compressor, raw, len(raw), out, level,
            None, None, None, None, 0,
        )
        if n <= 0:
            raise RuntimeError(f"OodleLZ_Compress returned {n}")
        return out.raw[:n]


if __name__ == "__main__":
    o = Oodle()
    sample = (b"The Last of Us Part I -- oodle round-trip test. " * 500)
    comp = o.compress(sample)
    back = o.decompress(comp, len(sample))
    print(f"dll={o.path}")
    print(f"raw={len(sample)}  comp={len(comp)}  roundtrip={'OK' if back == sample else 'FAIL'}")
