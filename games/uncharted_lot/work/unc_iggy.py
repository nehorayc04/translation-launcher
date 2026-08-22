#!/usr/bin/env python3
r"""
unc_iggy.py — reader/patcher for the Iggy (RAD Game Tools) UI libraries that carry
UNCHARTED: Legacy of Thieves' fonts.

WHY THIS FILE EXISTS
The first in-game proof settled it: the loc patch mounts and the text reaches the screen
with the right glyph COUNT, but every Hebrew letter draws as a tofu box while the Latin is
perfect.  So the UI is NOT rendered from the `main.fnt` bitmap atlas — it is rendered by
Iggy, RAD's compiled-Flash runtime (`iggy_w64_final.dll`).

Established by static analysis (all verified, none assumed):
  * The exe loads `.iggy`, NOT the shipped `.swf`.  Three independent proofs:
      - `iggy1.psarc` has 47 entries vs `flash1.psarc`'s 17, and UI pieces such as
        `controller-movie`, `interactables` and `menu-dynamic-window` exist ONLY as `.iggy`;
      - the font sets differ entirely — the SWFs carry Cast / Comic Sans / Arial Unicode,
        the iggy files carry Alte Haas Grotesk / IM FELL English PRO / Avant Garde /
        Albertus Medium.  The shipped SWFs are stale sources from another build.
      - `IggyFileImage` + a `hashMatches` check sit next to both pak names in the exe.
  * `u4.exe` imports `IggyFontSetIndirectUTF8` but NOT `IggyFontInstallTruetype*`, so
    there is no data-driven hook to install an external TTF — glyphs must go into the file.
  * **Only `fontlib.iggy` contains glyphs.**  All 23 other UI libraries reference fonts by
    NAME (`DrakeFont`, `DescFont`, `DescFontBold`, `PromptFont`, `DefaultLabelAltFont`) and
    contain zero code tables — that is the `IggyLibraryMakeFontsGlobal` / indirect-font
    mechanism.  ONE file to patch, and it covers subtitles too (`sp-hud.iggy` -> DrakeFont).

CONTAINER
    0x00  magic "Ig\n\xed"
    ...   u32 header fields; block1 = (len @0x24, off @0x2C), block2 = (len @0x34, off @0x3C)
    For fontlib.iggy: 64-byte header + block1 1,446,712 B + block2 3,859 B = the exact size.

FONT RECORD
Each of the 6 fonts owns an **ascending u16 code table of 116 entries** — 95 ASCII
(U+0020..U+007E) plus U+00A0, U+0107, U+02C6, U+02DC, U+2013, U+2014, U+2018..U+201E,
U+2020, U+2021, U+2022, U+2026, U+2030, U+2039, U+203A, U+20AC, U+2122 — followed by the
UTF-16 face name.  Glyph outlines are f32 vector paths (Iggy normalises SWF twips to
floats), which is why adding glyphs is a real reverse-engineering job.

THE ONE THING THAT IS FREE: the code table is a plain u16 array, so **remapping a codepoint
is a delta-0, 2-byte edit** with no pointer fix-ups.  The ordering constraint is the catch —
the table is ascending, and the ONLY gap that can host U+05D0..U+05EA is between
U+02DC (index 98) and U+2013 (index 99).  Indices 99..115 are 17 usable slots.

CLI:
    python unc_iggy.py info   <fontlib.iggy>
    python unc_iggy.py table  <fontlib.iggy> [--index N]
"""
import os
import re
import struct
import argparse

import numpy as np

MAGIC = b"Ig\n\xed"
HEBREW = list(range(0x05D0, 0x05EB))
# the tail slots that can legally become Hebrew while keeping the table ascending
TAIL_START = 99          # U+2013
TAIL_END = 116           # exclusive -> 17 slots (U+2013..U+2122)


def header(b):
    if b[:4] != MAGIC:
        raise ValueError("not an Iggy file")
    h = struct.unpack_from("<16I", b, 0)
    return dict(raw=h, b1_len=h[9], b1_off=h[11], b2_len=h[13], b2_off=h[15])


def find_code_tables(b, min_len=60):
    """Ascending u16 runs of plausible codepoints = the per-font code tables."""
    a = np.frombuffer(b[:len(b) // 2 * 2], dtype="<u2")
    out, i, s = [], 1, 0
    while i < len(a):
        if a[i] > a[i - 1] and 0x20 <= a[i] <= 0xFFFD and 0x20 <= a[i - 1] <= 0xFFFD:
            i += 1
            continue
        if i - s >= min_len:
            out.append(s * 2)
        s = i
        i += 1
    if i - s >= min_len:
        out.append(s * 2)
    return out


def read_table(b, off, cap=200):
    v = [struct.unpack_from("<H", b, off + 2 * i)[0] for i in range(cap)]
    n = 1
    while n < len(v) and v[n] > v[n - 1]:
        n += 1
    return v[:n]


def all_face_names(b):
    """Every UTF-16 string that really looks like a typeface name, with its offset.

    ⚠️ A bare "printable UTF-16 run" filter is NOT enough — the f32 glyph paths produce
    plenty of accidental runs like 'xAxzA' / 'VidWixYi'.  A real face name here always
    contains a space (they are multi-word: 'Alte Haas Grotesk Bold', 'IM FELL English PRO
    Roman', 'Albertus Medium', 'Avant Garde'), so require one and reject vowel-less noise.
    """
    out = []
    for m in re.finditer(rb'(?:[\x20-\x7e]\x00){6,44}', b):
        s = m.group(0).decode("utf-16-le")
        if " " not in s or not re.fullmatch(r'[A-Za-z][A-Za-z0-9 \-]{5,43}', s):
            continue
        if not re.search(r'[aeiouAEIOU]', s):
            continue
        out.append((m.start(), s))
    return out


def face_name(b, off, window=40000):
    """The face name that follows a code table (nearest plausible name within `window`)."""
    cands = [(o, s) for o, s in all_face_names(b) if off <= o <= off + window]
    return cands[0][1] if cands else "?"


def remap_unchecked(b, table_off, index, new_cp):
    """delta-0 rewrite of ONE u16 with NO ordering guard.

    Only for the deliberate ordering EXPERIMENT: violating the ascending invariant is the
    whole point of that probe, and it is aimed at the LAST table element so a binary
    search over the low/ASCII range cannot be disturbed.
    """
    out = bytearray(b)
    old = struct.unpack_from("<H", out, table_off + 2 * index)[0]
    struct.pack_into("<H", out, table_off + 2 * index, new_cp)
    return bytes(out), old


def remap(b, table_off, index, new_cp):
    """delta-0: rewrite ONE u16 in a code table, asserting the table stays ascending."""
    tbl = read_table(b, table_off)
    if not (0 <= index < len(tbl)):
        raise IndexError(index)
    lo = tbl[index - 1] if index else 0
    hi = tbl[index + 1] if index + 1 < len(tbl) else 0xFFFF
    if not (lo < new_cp < hi):
        raise ValueError(f"U+{new_cp:04X} breaks ascending order at {index} "
                         f"(needs U+{lo:04X} < x < U+{hi:04X})")
    out = bytearray(b)
    struct.pack_into("<H", out, table_off + 2 * index, new_cp)
    return bytes(out), tbl[index]


def _cmd_info(a):
    b = open(a.file, "rb").read()
    h = header(b)
    print(f"{os.path.basename(a.file)}  size={len(b):,}")
    print(f"  block1 off={h['b1_off']} len={h['b1_len']}   block2 off={h['b2_off']} len={h['b2_len']}"
          f"   sum={h['b1_off']+h['b1_len']+h['b2_len']}")
    for off in find_code_tables(b):
        t = read_table(b, off)
        print(f"  code table @{off:>9,}  n={len(t)}  face={face_name(b, off + 2*len(t))!r}")


def _cmd_table(a):
    b = open(a.file, "rb").read()
    tabs = find_code_tables(b)
    for k, off in enumerate(tabs):
        if a.index is not None and k != a.index:
            continue
        t = read_table(b, off)
        print(f"--- table {k} @{off:,}  n={len(t)}  face={face_name(b, off+2*len(t))!r}")
        for i in range(TAIL_START, min(len(t), TAIL_END + 2)):
            print(f"     [{i}] U+{t[i]:04X} {chr(t[i])!r}")


def main():
    ap = argparse.ArgumentParser(description="Iggy UI-library font tool")
    s = ap.add_subparsers(dest="cmd", required=True)
    q = s.add_parser("info");  q.add_argument("file")
    q = s.add_parser("table"); q.add_argument("file"); q.add_argument("--index", type=int)
    a = ap.parse_args()
    {"info": _cmd_info, "table": _cmd_table}[a.cmd](a)


if __name__ == "__main__":
    main()
