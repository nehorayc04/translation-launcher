# -*- coding: utf-8 -*-
"""God of War: Ragnarök — r_lang_*.wad reader (read-only, foundation tool).

Container chain (reverse-engineered 2026-06-17, see ../RECON.md):
  r_lang_XX.wad  =  LZ4 frame  (magic 04 22 4D 18)
                      -> inner WAD: 'WTOC' table-of-contents at offset 0
                         -> 'MSGS_TXT' section holds the localization strings
                            as newline-delimited records:  *<id>*\n<value>\n
  Text encoding = UTF-8  (so Hebrew stores identically to the Arabic slot).

This module ONLY reads. Re-packing (LZ4 re-frame + WTOC offset fix-up) is a
separate, later step — see PIPELINE.md. Usage:

  python gowr_wad.py decompress <r_lang_xx.wad> [out.bin]
  python gowr_wad.py extract    <r_lang_xx.wad> <out.json>   # {id: value}
  python gowr_wad.py stats      <r_lang_xx.wad>
"""
import sys, os, re, json, struct
import lz4.frame

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # playbook gotcha #1

LZ4_MAGIC = b"\x04\x22\x4d\x18"
ID_RE = re.compile(rb"\*(\d+)\*\n")          # record key:  *372*
SECTION_END = b"MSGS_TXT"                     # the text section marker


def decompress(path: str) -> bytes:
    """Return the decompressed inner WAD bytes of an r_lang_*.wad."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:4] != LZ4_MAGIC:
        # already decompressed (.bin) — pass through
        return raw
    return lz4.frame.decompress(raw)


def _msgs_region(blob: bytes):
    """Return (start, end) byte offsets of the MSGS_TXT record stream.

    Start = the first '*<id>*\\n' record after the MSGS_TXT marker.
    End   = MSGS_TXT section end (from WTOC size field), so the last record's
            value slice never bleeds into the binary sections that follow.
    """
    mark = blob.find(SECTION_END)
    base = mark if mark >= 0 else 0
    first = ID_RE.search(blob, base)
    if not first:
        return None
    # Compute hard section end from WTOC (DATA_BASE + 1024-byte offset + size)
    msgs_size = struct.unpack_from("<I", blob, _MSGS_ENTRY + 4)[0]
    section_end = _DATA_BASE + _SECTION_OFF + msgs_size
    return first.start(), section_end


def extract(path: str) -> "dict[str, str]":
    """Parse MSGS_TXT into {numeric_id: string_value}.

    Values may span multiple lines and carry in-game markup ([style=...],
    [Icons:LUCK], [SquareButton], literal \\n, {VALUE} tokens) — preserved verbatim.
    """
    blob = decompress(path)
    region = _msgs_region(blob)
    if not region:
        return {}
    start, end = region
    markers = list(ID_RE.finditer(blob, start, end))
    out = {}
    for i, m in enumerate(markers):
        key = m.group(1).decode("ascii")
        v_start = m.end()
        v_end = markers[i + 1].start() if i + 1 < len(markers) else end
        raw = blob[v_start:v_end]
        # the value is the text up to the trailing newline that precedes the next *id*
        raw = raw.rstrip(b"\x00")
        if raw.endswith(b"\n"):
            raw = raw[:-1]
        try:
            val = raw.decode("utf-8")
        except UnicodeDecodeError:
            # tail of the section bleeding into binary -> stop cleanly
            try:
                val = raw.split(b"\x00", 1)[0].decode("utf-8")
            except UnicodeDecodeError:
                break
        # a value that is mostly non-printable means we've run past the text region
        if val and sum((ord(c) < 32 and c not in "\n\t") for c in val) > len(val) * 0.3:
            break
        out[key] = val
    return out


# ---------- WTOC layout constants (reverse-engineered 2026-06-17/18) ----------
# WTOC entries occupy 0x40 + 47*0x90 = 6832 bytes.  The data section follows
# immediately (DATA_BASE = 6832).  The engine uses MULTIPLE independent streams;
# each entry's +0x78 is an offset within its stream, and each stream's base
# address in the blob = 6832 + sum(sizes of preceding streams).
#
# WTOC header fields (relative to blob offset 0):
#   +0x14 (20): u32 LE  — total size of STREAM-0 (type-7: MSGS_TXT + SMF data)
#   +0x18 (24): u32 LE  — total size of STREAM-1 (type-0x80A2001D: atlas textures)
#   Remaining stream sizes follow at +28, +52, …
#
# When MSGS_TXT grows by DELTA:
#   1. WTOC header +0x14 (stream-0 total size) += DELTA
#   2. Entry 31 size field (+0x04) = new MSGS_TXT size
#   3. Entries 43-46 (SMF, also in stream-0) +0x78 each += DELTA
#
# All subsequent streams (1, 2, 3, 4) shift right by DELTA in the blob because
# their base is derived from stream-0 size; their internal +0x78 offsets are
# unchanged (they still describe positions within their own stream).
_DATA_BASE     = 0x1AB0            # = 6832 (right after 47 WTOC entries)
_MSGS_ENTRY    = 0x40 + 31 * 0x90 # = 0x11B0  (WTOC entry for MSGS_TXT)
_SECTION_OFF   = 1024              # MSGS_TXT section offset within stream-0
_HDR_BYTES     = 22                # ASCII stats header before text records
_SMF_ENTRIES   = (43, 44, 45, 46)  # WTOC entry indices whose +0x78 needs DELTA
_STREAM0_SIZE  = 0x14              # WTOC header offset: total size of stream-0

# DESCENDER REMAP (2026-07-03).  DECISIVE finding: the engine honors the +18 vertical-offset
# field PER CODEPOINT RANGE — the native Arabic range (0x600) + Arabic-presentation-forms
# (0xFE80) drop with y_off 90-174, but the Hebrew range (U+05xx) IGNORES the field entirely
# (a 99 on the Hebrew match record had ZERO in-game effect while the same value drops Arabic).
# So the 5 Hebrew descender finals are RENDERED at spaced Arabic-pres codepoints (which DO drop)
# — those are RTL-strong like Hebrew, so the logical storage + bidi are unchanged; the glyph
# side (gowr_font.DESC_PRESFORM, MUST match) puts each Hebrew descender glyph on the matching
# pres-form record with a real tail y_off.  Applied to the TEXT here at build; source stays
# Hebrew.  (chr>=0xFE80 is 3 UTF-8 bytes vs 2 for Hebrew -> may push into the delta>0 path.)
# Targets = BASIC Arabic (0x600) RIGHT-JOINING letters with a native descender y_off (ؤ122 ا87
# ذ92 ز90 ى174). Basic Arabic is the range PROVEN to honor y_off (native ج=120 drops, خ=0 doesn't,
# same height); presentation-forms (0xFE80) do NOT (tested: y_off=30 there moved nothing).
# Right-joining letters never join to a FOLLOWING glyph and here sit between Hebrew (non-Arabic) ->
# isolated, so no cursive shaping corrupts placement. 2 UTF-8 bytes (like Hebrew) -> no byte growth.
# IDENTITY: plain Hebrew. Descender finals are rendered FULL-SIZE and RAISED (their tail shown above
# the baseline) entirely in our own atlas cell — no engine drop, no Arabic hijack, no artifacts.
DESC_REMAP = str.maketrans({})


def pack_blob(hebrew_dict: "dict[str,str]", source_wad: str) -> bytearray:
    """Build a new decompressed WAD blob with Hebrew text substituted.

    Reads the source Arabic WAD, replaces the MSGS_TXT section with Hebrew
    (falling back to Arabic for untranslated IDs), updates the WTOC size field
    and SMF virtual offsets.  Returns the raw decompressed bytes; the caller
    may apply font injection then LZ4-compress.

    hebrew_dict: {id_str: translated_hebrew_string}
    source_wad:  path to the original r_lang_ar.wad (or any *.wad)
    """
    blob = bytearray(decompress(source_wad))

    section_start = _DATA_BASE + _SECTION_OFF   # = 7856
    old_size = struct.unpack_from("<I", blob, _MSGS_ENTRY + 4)[0]
    section_end = section_start + old_size       # exclusive, = sony_ar start

    header22 = bytes(blob[section_start:section_start + _HDR_BYTES])  # keep unchanged

    # Read every Arabic ID in sorted numeric order; substitute Hebrew where available
    arabic = extract(source_wad)
    lines = []
    for id_str in sorted(arabic, key=lambda x: int(x)):
        value = hebrew_dict.get(id_str, arabic[id_str])
        value = value.translate(DESC_REMAP)   # descender finals -> Arabic-pres cps that DROP
        lines.append(f"*{id_str}*\n{value}\n")
    # CONSTANT-SIZE strategy (proven in-game 2026-06-18).  The engine relocates the
    # downstream streams (font atlas + SMF glyph metrics) by their original byte
    # layout, so GROWING MSGS_TXT shifts the font and corrupts it -> ALL text renders
    # blank.  Hebrew is more compact than the Arabic slot, so pad MSGS_TXT back to the
    # EXACT original byte size with trailing NUL: the 1st NUL terminates the record
    # list (as in the original), the rest is inert padding the runtime parser ignores.
    # delta == 0 -> nothing downstream moves -> byte-stable.  (An empty-dict rebuild
    # is then byte-identical to the source.)  Only if the translation OVERFLOWS the
    # Arabic slot do we fall back to growing + fixing offsets (delta>0 path below).
    records = "".join(lines).encode("utf-8")
    content = header22 + records
    if len(content) < old_size:
        new_section = content + b"\x00" * (old_size - len(content))
    else:
        # delta>0 (the translation OVERFLOWS the Arabic slot).  The engine locates
        # every downstream resource by CUMULATIVE size in entry-index order and then
        # re-applies each resource's byte ALIGNMENT (the atlas at entry 41 is exactly
        # 16-aligned: 6,953,648 = 16*434,603).  A flat blob-splice shifts every
        # downstream resource by exactly `delta`, so it lands where the engine
        # recomputes it ONLY when `delta` is a multiple of that alignment.  Prior
        # builds grew by 303,526 (mod16 = 6) -> the atlas/SMF landed a few bytes off
        # the engine's re-aligned position -> read garbage -> LOAD CRASH.  Pad `delta`
        # up to a 256-byte multiple (a safe superset of the 16-byte alignment); the
        # extra NUL is inert (the record parser stops at the first NUL) and
        # LZ4-compresses away.  This is the ONLY change needed for a working grow —
        # only entry-31 size (+0x04) and stream-0 size (+0x14) are size fields the
        # engine reads; +0x0c is a 12 MB capacity ceiling the grown blob stays under.
        ALIGN = 256
        need = len(content) + 1 - old_size                # minimum grow (+1 terminator)
        grow = ((need + ALIGN - 1) // ALIGN) * ALIGN       # round up to ALIGN
        new_section = content + b"\x00" * (old_size + grow - len(content))
    new_size = len(new_section)
    delta = new_size - old_size
    assert delta <= 0 or delta % 256 == 0, f"delta {delta} not 256-aligned"

    # Rebuild blob: [WTOC+data-preamble] + [new MSGS_TXT section] + [everything after]
    new_blob = bytearray(blob[:section_start]) + new_section + blob[section_end:]

    # Update MSGS_TXT size field in WTOC
    struct.pack_into("<I", new_blob, _MSGS_ENTRY + 4, new_size)

    # Update stream-0 total size in WTOC header (used for buffer sizing / validation)
    old_s0 = struct.unpack_from("<I", new_blob, _STREAM0_SIZE)[0]
    struct.pack_into("<I", new_blob, _STREAM0_SIZE, old_s0 + delta)

    # --- Stream-0 post-MSGS resources: their +0x78 MUST shift by DELTA -------------
    # FULL layout mapped 2026-07-02 from the pristine ar WAD (c:\tmp\gowr_layout.py):
    # stream-0 is laid out in +0x78 order as one contiguous chain ending EXACTLY at the
    # stream-0 size (5,284,428):
    #     [1024-byte header]  MSGS(31)  ->  SMF(43) -> 44 -> 45 -> 46
    # The font-metric entries 43-46 sit AFTER MSGS in the SAME stream, so growing MSGS
    # by DELTA slides each of them right by DELTA -> their +0x78 (offset WITHIN stream-0)
    # must be incremented by DELTA, or the engine reads the glyph table from stale bytes
    # and CRASHES.  (The texture chain 35->38->41=atlas is a SEPARATE stream-1: its base
    # = DATA_BASE + stream-0 size, so it relocates automatically when +0x14 grows and its
    # internal +0x78 stays fixed -> do NOT touch it.  Entries 0-30/32-42 live in the
    # 1024-byte header BEFORE MSGS -> unaffected.)  This is why BOTH prior fixes crashed:
    # attempt #1 patched 43-46 but left DELTA mod16=6 (broke the SMF's 16-byte alignment);
    # attempt #3 aligned DELTA to 256 but dropped the 43-46 patch (SMF offset stale).  The
    # correct grow needs BOTH — the 256-aligned DELTA (above) AND these offset shifts.
    # (For the delta==0 fit-down path DELTA is 0, so this loop is a no-op.)
    for e in _SMF_ENTRIES:
        fld = 0x40 + e * 0x90 + 0x78
        struct.pack_into("<I", new_blob, fld,
                         struct.unpack_from("<I", new_blob, fld)[0] + delta)

    return new_blob


def pack(hebrew_dict: "dict[str,str]", source_wad: str, out_path: str,
         font_injector=None) -> tuple:
    """Build a complete r_lang_ar.wad with Hebrew text (+ optional font).

    font_injector: callable(blob: bytearray) -> None  (edits in place)
                   e.g. lambda b: gowr_font.inject_hebrew(b, pick_font(), px=56)
                   Applied AFTER text resize so font finds sections at new offsets.
    Returns (decompressed_size_bytes, msgs_txt_delta_bytes).
    """
    orig_blob = bytearray(decompress(source_wad))
    orig_msgs_size = struct.unpack_from("<I", orig_blob, _MSGS_ENTRY + 4)[0]

    new_blob = pack_blob(hebrew_dict, source_wad)
    new_msgs_size = struct.unpack_from("<I", new_blob, _MSGS_ENTRY + 4)[0]
    delta = new_msgs_size - orig_msgs_size

    if font_injector is not None:
        font_injector(new_blob)

    # compression_level=0: the game's own packer used LZ4 frame level-0 — a
    # level-0 recompress of the original is byte-IDENTICAL (same MD5). The engine's
    # loader rejects level-9 frames (different block layout) -> blank text + crash.
    # Keep level-0 so the frame matches what the engine expects. (FLG 0x6c / BD 0x40,
    # 64KB independent blocks, content-size + content-checksum.)
    compressed = lz4.frame.compress(
        bytes(new_blob), block_size=lz4.frame.BLOCKSIZE_MAX64KB,
        block_linked=False, content_checksum=True,
        store_size=True, compression_level=0,
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(compressed)
    return len(new_blob), delta


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, path = argv[1], argv[2]
    if cmd == "decompress":
        out = argv[3] if len(argv) > 3 else path + ".bin"
        data = decompress(path)
        with open(out, "wb") as f:
            f.write(data)
        print(f"{os.path.basename(path)}: -> {len(data):,} bytes -> {out}")
    elif cmd == "extract":
        if len(argv) < 4:
            print("usage: extract <wad> <out.json>"); return 2
        d = extract(path)
        with open(argv[3], "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=0)
        print(f"{os.path.basename(path)}: {len(d):,} strings -> {argv[3]}")
    elif cmd == "stats":
        d = extract(path)
        total = len(d)
        empty = sum(1 for v in d.values() if not v.strip())
        # heuristic dev-junk / metadata
        junk = sum(1 for v in d.values() if v.startswith("Design#") or v in ("OBSOLETE", "CUT"))
        chars = sum(len(v) for v in d.values())
        ids = [int(k) for k in d]
        print(f"file        : {os.path.basename(path)}")
        print(f"strings     : {total:,}")
        print(f"empty       : {empty:,}")
        print(f"dev-meta    : {junk:,}")
        print(f"total chars : {chars:,}")
        print(f"id range    : {min(ids)}..{max(ids)}")
        print("--- sample (first 12 non-empty) ---")
        shown = 0
        for k, v in d.items():
            if v.strip() and not v.startswith("Design#"):
                print(f"  *{k}* = {v!r}")
                shown += 1
            if shown >= 12:
                break
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
