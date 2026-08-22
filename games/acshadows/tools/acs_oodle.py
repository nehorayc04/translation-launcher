#!/usr/bin/env python3
"""
acs_oodle.py — ctypes wrapper around an Oodle DLL (oo2core_*_win64.dll) for
DECODING and ENCODING the Kraken-compressed resource blocks inside AC Shadows
scimitar-v42 forges.

The game ships NO oo2core; we borrow one already installed on this machine
(found 2026-06-17): C:\\Games\\Battlefield 6\\oo2core_9_win64.dll (Oodle 2.9.x).
Override with env ACS_OODLE_DLL or the --dll flag.

Both OodleLZ_Decompress AND OodleLZ_Compress are exported by the redistributable
DLL, so we can both unpack a forge resource and RE-pack one — the Oodle license
gate only blocks shipping the DLL, not calling it locally. This is what removes
the "Oodle is the wall" blocker for a home-built v42 forge repacker.

    python acs_oodle.py selftest        # synthetic compress->decompress round-trip
"""
import os
import sys
import ctypes
from ctypes import c_void_p, c_int64, c_int, c_char_p

# Kraken = 8 ; CompressionLevel: None=0, SuperFast=1, VeryFast=2, Fast=3,
# Normal=4, Optimal1..5 = 5..9
OODLE_KRAKEN = 8
OODLE_LEVEL_NORMAL = 4

# ⚠️ ORDER MATTERS. Shadows v42 blocks are Mermaid/Kraken from Oodle 2.9 — an OLDER
# oo2core (2.5, shipped with RDR2) loads fine but DECODES NOTHING: OodleLZ_Decompress
# just returns 0. So every 2.9 candidate must come first, and 2.5 is a last resort that
# is loudly rejected in Oodle.__init__ below rather than silently producing garbage.
_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
_CANDIDATE_DLLS = [
    os.environ.get("ACS_OODLE_DLL", ""),
    # in-repo copies (survive a game being uninstalled — the original 2026-06 path
    # C:\Games\Battlefield 6\ disappeared on 2026-08-21 and silently fell back to 2.5)
    os.path.join(_REPO, "Game Lab", "Battlefield 6", "oo2core_9_win64.dll"),
    os.path.join(_REPO, "games", "hogwarts_legacy", "tools", "oo2core_9_win64.dll"),
    os.path.join(_REPO, "games", "acblackflag-resynced", "work", "refmods",
                 "injector", "oo2core_9_win64.dll"),
    r"C:\Games\Battlefield 6\oo2core_9_win64.dll",
    r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2\oo2core_5_win64.dll",
]


def _find_dll(explicit=None):
    for p in ([explicit] if explicit else []) + _CANDIDATE_DLLS:
        if p and os.path.isfile(p):
            return p
    raise FileNotFoundError("no oo2core_*_win64.dll found — pass --dll or set ACS_OODLE_DLL")


class Oodle:
    def __init__(self, dll_path=None):
        self.path = _find_dll(dll_path)
        # A 2.5-era oo2core loads and exports the same symbols, but every
        # OodleLZ_Decompress on a v42 block returns 0. Refuse it up front instead of
        # letting it look like "the resource is corrupt".
        if "oo2core_5" in os.path.basename(self.path).lower() and not os.environ.get(
                "ACS_OODLE_ALLOW_OLD"):
            raise RuntimeError(
                f"refusing {self.path}: Oodle 2.5 cannot decode Shadows v42 blocks "
                f"(OodleLZ_Decompress returns 0). Install/point ACS_OODLE_DLL at an "
                f"oo2core_9_win64.dll.")
        self.dll = ctypes.CDLL(self.path)

        # OO_SINTa OodleLZ_Decompress(const void* comp, OO_SINTa compLen,
        #   void* raw, OO_SINTa rawLen, int fuzzSafe, int checkCRC, int verbosity,
        #   void* decBufBase, OO_SINTa decBufSize, void* cb, void* cbUser,
        #   void* decoderMem, OO_SINTa decoderMemSize, int threadPhase)
        self.dll.OodleLZ_Decompress.restype = c_int64
        self.dll.OodleLZ_Decompress.argtypes = [
            c_void_p, c_int64, c_void_p, c_int64,
            c_int, c_int, c_int,
            c_void_p, c_int64, c_void_p, c_void_p,
            c_void_p, c_int64, c_int,
        ]
        # OO_SINTa OodleLZ_Compress(int compressor, const void* raw, OO_SINTa rawLen,
        #   void* comp, int level, void* opts, void* dictBase, void* lrm,
        #   void* scratch, OO_SINTa scratchSize)
        self.dll.OodleLZ_Compress.restype = c_int64
        self.dll.OodleLZ_Compress.argtypes = [
            c_int, c_void_p, c_int64, c_void_p, c_int,
            c_void_p, c_void_p, c_void_p, c_void_p, c_int64,
        ]

    def decompress(self, comp: bytes, raw_size: int) -> bytes:
        out = ctypes.create_string_buffer(raw_size)
        n = self.dll.OodleLZ_Decompress(
            comp, len(comp), out, raw_size,
            1, 0, 0,        # fuzzSafe=Yes, checkCRC=No, verbosity=None
            None, 0, None, None,
            None, 0, 3,     # threadPhase = Unthreaded(3)
        )
        if n != raw_size:
            raise RuntimeError(f"OodleLZ_Decompress returned {n}, expected {raw_size}")
        return out.raw[:raw_size]

    def compress(self, raw: bytes, compressor=OODLE_KRAKEN, level=OODLE_LEVEL_NORMAL) -> bytes:
        bound = len(raw) + len(raw) // 2 + 65536  # generous upper bound for comp size
        out = ctypes.create_string_buffer(bound)
        n = self.dll.OodleLZ_Compress(
            compressor, raw, len(raw), out, level,
            None, None, None, None, 0,
        )
        if n <= 0:
            raise RuntimeError(f"OodleLZ_Compress returned {n}")
        return out.raw[:n]


def selftest():
    o = Oodle()
    print(f"loaded: {o.path}")
    # a realistic mixed buffer (text + structure, like a LocalizationPackage)
    sample = (b"the quick brown fox jumps over the lazy dog 1234567890 "
              b"\x01\x02\x03\x00\x00oasis_id=4567\x00LocalizedString\x00") * 4096
    raw = sample[:300_000]
    comp = o.compress(raw)
    back = o.decompress(comp, len(raw))
    ok = back == raw
    print(f"raw={len(raw):,}  kraken={len(comp):,}  ratio={len(raw)/len(comp):.2f}x")
    print(f"lead byte of comp stream: 0x{comp[0]:02X}  (forge data blocks observed at 0x8C)")
    print(f"round-trip identical: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1 and sys.argv[1] == "--dll":
        os.environ["ACS_OODLE_DLL"] = sys.argv[2]
        sys.argv = sys.argv[:1] + sys.argv[3:]
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        sys.exit(selftest())
    print(__doc__)
