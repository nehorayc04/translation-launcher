#!/usr/bin/env python3
"""
LZO (de)compression for AC2 .data blocks, via AnvilToolkit's bundled liblzo2.

AC2 CompressedFileData blocks use:  CompressionInfo.Algorithm == 1 -> LZO1X,
else -> **LZO2A** (the AC2 default; ported exactly from AnvilToolkit's `LZO` class).
A block whose compressedSize == uncompressedSize is stored raw (no LZO).

⚠️ liblzo2 is __cdecl -> load with ctypes.CDLL (WinDLL/stdcall crashes).
Exact native signatures (from the decompiled DllImports):
    int lzo2a_decompress(byte[] src, ushort src_len, byte[] dst, ref int dst_len, byte[] wrkmem)
    int lzo1x_decompress(byte[] src, ushort src_len, byte[] dst, ref int dst_len, byte[] wrkmem)
    int lzo2a_999_compress / lzo1x_1_compress (same arg shapes)
    int __lzo_init_v2(uint v, int x9...)   -> call (1, -1,-1,...) returns 0
`wrkmem` is a 512 KB buffer passed to BOTH compress and decompress.
"""
import ctypes
import os

LZO_DLL = os.environ.get("AC2_LZO_DLL", r"c:\tmp\anvil_dlls\lzo.dll")
_WRK = 524288  # AnvilToolkit's Mem size

_lib = None
_wrk = None


def _load():
    global _lib, _wrk
    if _lib is not None:
        return
    _lib = ctypes.CDLL(LZO_DLL)
    init = _lib.__lzo_init_v2
    init.restype = ctypes.c_int
    init.argtypes = [ctypes.c_uint] + [ctypes.c_int] * 9
    if init(1, -1, -1, -1, -1, -1, -1, -1, -1, -1) != 0:
        raise RuntimeError("__lzo_init_v2 failed")
    for name in ("lzo2a_decompress", "lzo1x_decompress",
                 "lzo2a_999_compress", "lzo1x_1_compress", "lzo1c_decompress"):
        fn = getattr(_lib, name)
        fn.restype = ctypes.c_int
        fn.argtypes = [ctypes.c_char_p, ctypes.c_ushort, ctypes.c_char_p,
                       ctypes.POINTER(ctypes.c_int), ctypes.c_char_p]
    _wrk = ctypes.create_string_buffer(_WRK)


def _decompress(fn_name, src: bytes, out_len: int) -> bytes:
    _load()
    fn = getattr(_lib, fn_name)
    src_buf = ctypes.create_string_buffer(bytes(src), len(src))
    dst = ctypes.create_string_buffer(out_len + 4096)   # slack vs. minor overrun
    dl = ctypes.c_int(out_len)
    rc = fn(src_buf, ctypes.c_ushort(len(src)), dst, ctypes.byref(dl), _wrk)
    if rc != 0:
        raise RuntimeError(f"{fn_name} rc={rc} (src={len(src)} out={out_len})")
    return dst.raw[:dl.value]


def lzo2a_decompress(src: bytes, out_len: int) -> bytes:
    return _decompress("lzo2a_decompress", src, out_len)


def lzo1x_decompress(src: bytes, out_len: int) -> bytes:
    return _decompress("lzo1x_decompress", src, out_len)


def decompress_block(algo: int, src: bytes, out_len: int) -> bytes:
    """AC2 CompressionInfo.Algorithm dispatch: 1 -> LZO1X, else -> LZO2A."""
    if len(src) == out_len:            # stored raw
        return bytes(src)
    return lzo1x_decompress(src, out_len) if algo == 1 else lzo2a_decompress(src, out_len)


def lzo2a_compress(src: bytes) -> bytes:
    _load()
    fn = _lib.lzo2a_999_compress
    src_buf = ctypes.create_string_buffer(bytes(src), len(src))
    dst = ctypes.create_string_buffer(len(src) + len(src) // 8 + 128 + 3)
    dl = ctypes.c_int(len(dst))
    rc = fn(src_buf, ctypes.c_ushort(len(src)), dst, ctypes.byref(dl), _wrk)
    if rc != 0:
        raise RuntimeError(f"lzo2a_999_compress rc={rc}")
    return dst.raw[:dl.value]


if __name__ == "__main__":
    data = b"the quick brown fox jumps over " * 100
    for name, comp, dec in [("lzo2a", lzo2a_compress, lzo2a_decompress)]:
        c = comp(data)
        back = dec(c, len(data))
        print(f"{name}: orig={len(data)} comp={len(c)} roundtrip={back == data}")
