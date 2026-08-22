"""Read / patch SkyrimSELauncher.exe resources (RT_STRING + RT_BITMAP).

The launcher is a plain Win32 app whose ENTIRE user-visible text lives in resources:

  RT_STRING  576 entries in NINE 1000-wide ID blocks, one per shipped language:
             10xxx EN · 11xxx FR · 12xxx IT · 13xxx DE · 14xxx ES
             15xxx PL · 16xxx RU · 17xxx zh-TW · 18xxx JA
             (64 real strings each; the block is chosen at runtime from sLanguage,
             so hijacking the ENGLISH block costs the user zero actions.)
  RT_BITMAP  72 pre-rendered 275x50 menu images = 4 items (PLAY/OPTIONS/SUPPORT/
             EXIT) x 9 languages x 2 states (dim / highlighted). The main-menu
             buttons are IMAGES, not text -- so they must be re-rendered, and no
             bidi question arises for them at all.

Writing goes through the Windows resource-update API (Begin/Update/EndUpdateResource),
which rebuilds .rsrc properly -- replacements may be longer or shorter than the
original, unlike an in-place byte patch.

`selftest(exe)` proves the codec by writing every resource back UNCHANGED and
re-reading: a no-op patch must reproduce byte-identical resource data.
"""
from __future__ import annotations

import ctypes
import shutil
import struct
from ctypes import wintypes
from pathlib import Path

import pefile

RT_BITMAP = 2
RT_STRING = 6
LANG_EN_US = 0x0409

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.BeginUpdateResourceW.restype = wintypes.HANDLE
_k32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
_k32.UpdateResourceW.restype = wintypes.BOOL
_k32.UpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                 wintypes.WORD, wintypes.LPVOID, wintypes.DWORD]
_k32.EndUpdateResourceW.restype = wintypes.BOOL
_k32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]


def _mkres(i: int):
    return ctypes.cast(ctypes.c_void_p(i), wintypes.LPCWSTR)


# ----------------------------------------------------------------------- read
def _walk(exe):
    pe = pefile.PE(str(exe), fast_load=True)
    pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
    for rt in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        for rid in rt.directory.entries:
            for lang in rid.directory.entries:
                data = pe.get_data(lang.data.struct.OffsetToData, lang.data.struct.Size)
                yield rt.struct.Id, rid.struct.Id, lang.data.lang, bytes(data)
    pe.close()


def read_strings(exe) -> dict[int, str]:
    """-> {stringId: text} (empty slots omitted)."""
    out: dict[int, str] = {}
    for t, blk, _lang, data in _walk(exe):
        if t != RT_STRING:
            continue
        off = 0
        for i in range(16):
            if off + 2 > len(data):
                break
            (ln,) = struct.unpack_from("<H", data, off)
            off += 2
            s = data[off:off + ln * 2].decode("utf-16-le", "replace")
            off += ln * 2
            if s:
                out[(blk - 1) * 16 + i] = s
    return out


def read_bitmaps(exe) -> dict[int, bytes]:
    """-> {bitmapId: raw RT_BITMAP payload (BITMAPINFOHEADER + pixels, no BM header)}"""
    return {rid: data for t, rid, _l, data in _walk(exe) if t == RT_BITMAP}


def block_of(string_id: int) -> tuple[int, int]:
    return string_id // 16 + 1, string_id % 16


def build_string_block(existing: dict[int, str], block: int,
                       overrides: dict[int, str]) -> bytes:
    """Rebuild one 16-string RT_STRING block from the CURRENT strings + overrides."""
    out = bytearray()
    for i in range(16):
        sid = (block - 1) * 16 + i
        s = overrides.get(sid, existing.get(sid, ""))
        b = s.encode("utf-16-le")
        out += struct.pack("<H", len(b) // 2) + b
    return bytes(out)


# ---------------------------------------------------------------------- write
def patch(src, dst, *, strings: dict[int, str] | None = None,
          bitmaps: dict[int, bytes] | None = None, lang: int = LANG_EN_US) -> None:
    src, dst = Path(src), Path(dst)
    if src.resolve() != dst.resolve():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    cur = read_strings(src)
    blocks: dict[int, dict[int, str]] = {}
    for sid, txt in (strings or {}).items():
        blocks.setdefault(block_of(sid)[0], {})[sid] = txt

    h = _k32.BeginUpdateResourceW(str(dst), False)
    if not h:
        raise OSError(f"BeginUpdateResource failed: {ctypes.get_last_error()}")
    try:
        for blk, ov in blocks.items():
            data = build_string_block(cur, blk, ov)
            buf = ctypes.create_string_buffer(data, len(data))
            if not _k32.UpdateResourceW(h, _mkres(RT_STRING), _mkres(blk), lang,
                                        buf, len(data)):
                raise OSError(f"UpdateResource STRING block {blk}: "
                              f"{ctypes.get_last_error()}")
        for bid, data in (bitmaps or {}).items():
            buf = ctypes.create_string_buffer(data, len(data))
            if not _k32.UpdateResourceW(h, _mkres(RT_BITMAP), _mkres(bid), lang,
                                        buf, len(data)):
                raise OSError(f"UpdateResource BITMAP {bid}: {ctypes.get_last_error()}")
    except Exception:
        _k32.EndUpdateResourceW(h, True)         # discard
        raise
    if not _k32.EndUpdateResourceW(h, False):
        raise OSError(f"EndUpdateResource failed: {ctypes.get_last_error()}")


# -------------------------------------------------------------------- bitmaps
def bmp_info(data: bytes) -> dict:
    hs, w, h, planes, bpp, comp, imgsz = struct.unpack_from("<IiiHHII", data, 0)
    stride = ((w * bpp + 31) // 32) * 4
    return {"hdr": hs, "w": w, "h": abs(h), "bottom_up": h > 0, "bpp": bpp,
            "comp": comp, "stride": stride, "pixels": stride * abs(h),
            "tail": len(data) - hs - stride * abs(h)}


def bmp_to_array(data: bytes):
    """RT_BITMAP payload -> (H,W,3) uint8 RGB array, top-down."""
    import numpy as np
    m = bmp_info(data)
    assert m["bpp"] == 24 and m["comp"] == 0, "only 24bpp BI_RGB supported"
    px = np.frombuffer(data, dtype=np.uint8, count=m["pixels"], offset=m["hdr"])
    px = px.reshape(m["h"], m["stride"])[:, :m["w"] * 3].reshape(m["h"], m["w"], 3)
    px = px[:, :, ::-1]                                   # BGR -> RGB
    return np.ascontiguousarray(px[::-1] if m["bottom_up"] else px)


def array_to_bmp(arr, template: bytes) -> bytes:
    """(H,W,3) RGB top-down -> a payload byte-compatible with `template`."""
    import numpy as np
    m = bmp_info(template)
    a = np.asarray(arr, dtype=np.uint8)
    assert a.shape == (m["h"], m["w"], 3), f"{a.shape} != {(m['h'], m['w'], 3)}"
    if m["bottom_up"]:
        a = a[::-1]
    a = a[:, :, ::-1]                                     # RGB -> BGR
    # start from the TEMPLATE and overwrite only the pixel bytes, so the header,
    # each row's stride PADDING and the 2 spare trailing bytes Bethesda's bitmaps
    # carry are preserved verbatim (that is what makes a no-op round-trip exact).
    out = bytearray(template)
    w3 = m["w"] * 3
    for y in range(m["h"]):
        o = m["hdr"] + y * m["stride"]
        out[o:o + w3] = a[y].tobytes()
    assert len(out) == len(template), f"{len(out)} != {len(template)}"
    return bytes(out)


# ------------------------------------------------------------------- selftest
def selftest(exe, tmp) -> bool:
    """A no-op patch must reproduce byte-identical resource data."""
    s0, b0 = read_strings(exe), read_bitmaps(exe)
    patch(exe, tmp, strings={k: v for k, v in s0.items() if 10000 <= k <= 10063},
          bitmaps={k: v for k, v in b0.items() if k in (105, 107, 119, 261)})
    s1, b1 = read_strings(tmp), read_bitmaps(tmp)
    ok = True
    if s0 != s1:
        diff = [k for k in set(s0) | set(s1) if s0.get(k) != s1.get(k)]
        print(f"  STRING drift on {len(diff)} ids: {diff[:8]}")
        ok = False
    bad = [k for k in b0 if b0[k] != b1.get(k)]
    if bad:
        print(f"  BITMAP drift on {len(bad)} ids: {bad[:8]}")
        ok = False
    # array round-trip
    import numpy as np
    for k in (105, 119):
        a = bmp_to_array(b0[k])
        if array_to_bmp(a, b0[k]) != b0[k]:
            print(f"  bitmap {k}: array round-trip NOT byte-identical")
            ok = False
        if a.dtype != np.uint8:
            ok = False
    print(f"selftest: {'PASS' if ok else 'FAIL'} "
          f"({len(s0)} strings, {len(b0)} bitmaps)")
    return ok


if __name__ == "__main__":
    import sys
    exe = sys.argv[1] if len(sys.argv) > 1 else \
        r"D:\Games\TES - Skyrim - Anniversary Edition\SkyrimSELauncher.exe"
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        selftest(exe, Path(td) / "t.exe")
