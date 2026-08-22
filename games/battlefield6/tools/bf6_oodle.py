"""Oodle wrapper for Battlefield 6 (ships its own oo2core_9_win64.dll — same DLL/version
already used elsewhere in this project, e.g. games/acshadows/tools/acs_oodle.py, which
this is adapted from)."""
import os
import ctypes
from ctypes import c_void_p, c_int64, c_int

OODLE_KRAKEN = 8
OODLE_LEVEL_NORMAL = 4

_CANDIDATE_DLLS = [
    os.environ.get("BF6_OODLE_DLL", ""),
    r"C:\Game Lab\Battlefield 6\oo2core_9_win64.dll",
    r"C:\Games\Battlefield 6\oo2core_9_win64.dll",
]


def _find_dll(explicit=None):
    for p in ([explicit] if explicit else []) + _CANDIDATE_DLLS:
        if p and os.path.isfile(p):
            return p
    raise FileNotFoundError("no oo2core_*_win64.dll found")


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

    def decompress(self, comp: bytes, raw_size: int) -> bytes:
        out = ctypes.create_string_buffer(raw_size)
        n = self.dll.OodleLZ_Decompress(
            comp, len(comp), out, raw_size,
            1, 0, 0,
            None, 0, None, None,
            None, 0, 3,
        )
        if n != raw_size:
            raise RuntimeError(f"OodleLZ_Decompress returned {n}, expected {raw_size}")
        return out.raw[:raw_size]
