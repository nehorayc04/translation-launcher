"""
gtav_gxt2.py — self-contained pure-Python GTA V GXT2 codec + Hebrew VISUAL helper.

GTA V (RAGE engine) stores localized UI/subtitle text in **GXT2** files inside the
RPF7 archives (e.g. update.rpf .../global.gxt2, per-language .gxt2). There is NO
Arabic and NO Hebrew official locale — every shipped locale is LTR — so the
"Arabic-slot RTL hijack" used for CP2077/SM2/WD2 does NOT apply here. This is the
AC2 / Anno-1800 class: hijack an LTR slot and store the Hebrew **pre-reversed to
visual order** (the engine does no bidi for an LTR locale).

This module implements, per the public OpenIV / CodeWalker / gta5-mods gxt2 spec:

  * joaat(s)        -- Jenkins one-at-a-time hash (lowercase) -> uint32 (the GXT2 key).
  * read_gxt2(b)    -- bytes -> {key_hash:int -> str}. Handles the plain GXT2 layout
                       and the v2 "TABL"/"2TXG" (multi-table) container variant.
  * write_gxt2(d)   -- {key_hash:int -> str} -> bytes (plain GXT2), entries sorted
                       by hash ascending (engine requirement). read(write(d)) == d.
  * visual_line(s)  -- WD2/Anno-proven logical->visual reversal for non-bidi engines:
                       reverse each Hebrew run, flip the run order, keep Latin/digit/
                       token/tag runs FORWARD and atomic, preserve whitespace, mirror
                       brackets. Logical Hebrew in, visual Hebrew out.

GXT2 plain format (little-endian throughout):
    magic    u32  0x47585432  ('GXT2', stored as the 4 ASCII bytes "GXT2")
    count    u32  number of entries
    entries  count * (u32 hash, u32 offset)   -- sorted by hash ascending
    sentinel u32  0x47585432  ('GXT2' again)  -- marks end of the entry table
    dataLen  u32  total byte length of the data block (incl. this header pair)
    data     UTF-8 string bytes, each NUL-terminated; `offset` is absolute from the
             start of the file.

The "v2 TABL" container (some global.gxt2 builds): a top-level table directory whose
magic is 'TABL', each record = name[?]+offset, each pointing at a nested '2TXG' (the
GXT2 magic byte-reversed) sub-table. We detect it, flatten every sub-table into one
{hash->str} dict on read; write_gxt2 always emits the plain single-table form, which
the engine and OpenIV both accept for a per-language .gxt2.
"""

import re
import struct
import sys

# Make stdout UTF-8 so printing Hebrew / arrows never crashes on cp1255 (the
# universal-playbook killer gotcha #1).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GXT2_MAGIC = 0x47585432            # the magic as a uint32 value
# On disk the magic is stored as a LITTLE-ENDIAN u32, so the first 4 file bytes read
# as ASCII "2TXG" (0x32 0x54 0x58 0x47), NOT "GXT2". Verified against the real
# american_rel/global.gxt2 (1,141,267 B / 23,136 entries).
GXT2_MAGIC_BYTES = struct.pack("<I", GXT2_MAGIC)   # == b"2TXG"
TABL_MAGIC_BYTES = b"TABL"         # v2 container directory (rare; not the per-lang file)
TXG2_MAGIC_BYTES = b"2TXG"         # == GXT2_MAGIC_BYTES (kept for the TABL walker)


# --------------------------------------------------------------------------- #
# joaat — Jenkins one-at-a-time (the GXT2 key hash)
# --------------------------------------------------------------------------- #
def joaat(s):
    """Jenkins one-at-a-time hash of the lowercased ASCII label -> uint32.

    RAGE hashes the label lowercased; this is the key stored in the GXT2 table.
    """
    if isinstance(s, str):
        s = s.lower().encode("utf-8")
    else:
        s = bytes(s).lower()
    h = 0
    for b in s:
        h = (h + b) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h = (h ^ (h >> 6)) & 0xFFFFFFFF
    h = (h + (h << 3)) & 0xFFFFFFFF
    h = (h ^ (h >> 11)) & 0xFFFFFFFF
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h & 0xFFFFFFFF


# --------------------------------------------------------------------------- #
# read
# --------------------------------------------------------------------------- #
def _read_cstring(buf, off):
    """Read a NUL-terminated UTF-8 string starting at absolute offset `off`."""
    end = buf.find(b"\x00", off)
    if end < 0:
        end = len(buf)
    return buf[off:end].decode("utf-8", errors="replace")


def _read_plain_table(buf, base=0):
    """Parse one plain GXT2 table whose magic sits at absolute offset `base`.

    Entry string offsets are stored relative to the TABLE's own start (`base`);
    for a standalone file `base == 0` so they read as absolute, but for a sub-
    table embedded in a TABL container at a nonzero `base` we add `base` back.

    Returns (dict, end_offset) where end_offset is just past this table's data
    block (best-effort, for the container walker).
    """
    if buf[base:base + 4] != GXT2_MAGIC_BYTES:
        raise ValueError("not a GXT2 table at offset %d" % base)
    (count,) = struct.unpack_from("<I", buf, base + 4)
    out = {}
    pos = base + 8
    for _ in range(count):
        h, off = struct.unpack_from("<II", buf, pos)
        pos += 8
        # `off` is relative to this table's start -> add `base` for the absolute
        # position in `buf` (no-op when base == 0).
        out[h & 0xFFFFFFFF] = _read_cstring(buf, base + off)
    # After the entry table: sentinel magic + dataLen.
    end = base + 8 + count * 8
    if buf[end:end + 4] == GXT2_MAGIC_BYTES:
        (data_len,) = struct.unpack_from("<I", buf, end + 4)
        end_off = base + data_len
    else:
        # No sentinel pair (tolerant): fall back to past the last string.
        end_off = len(buf)
    return out, end_off


def read_gxt2(data):
    """bytes -> {key_hash:int -> str}. Handles plain GXT2 and the TABL container."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("read_gxt2 expects bytes")
    buf = bytes(data)
    if len(buf) < 8:
        raise ValueError("buffer too small to be a GXT2 file")

    magic = buf[:4]

    if magic == TABL_MAGIC_BYTES:
        # v2 container: directory of named sub-tables, each a nested 2TXG/GXT2.
        # Layout (common variant): 'TABL', u32 tableCount, then per record an
        # 8-byte name + u32 offset (absolute). We tolerate either record stride
        # by scanning for nested table magics from each declared offset.
        (table_count,) = struct.unpack_from("<I", buf, 4)
        merged = {}
        pos = 8
        offsets = []
        # name(8) + offset(4) = 12 bytes per record is the documented stride.
        for _ in range(table_count):
            if pos + 12 > len(buf):
                break
            (off,) = struct.unpack_from("<I", buf, pos + 8)
            offsets.append(off)
            pos += 12
        for off in offsets:
            sub = buf[off:off + 4]
            if sub in (GXT2_MAGIC_BYTES, TXG2_MAGIC_BYTES):
                # Normalize a 2TXG sub-table to GXT2 for the plain reader.
                if sub == TXG2_MAGIC_BYTES:
                    norm = GXT2_MAGIC_BYTES + buf[off + 4:]
                    d, _ = _read_plain_table(norm, 0)
                else:
                    d, _ = _read_plain_table(buf, off)
                merged.update(d)
        return merged

    if magic == GXT2_MAGIC_BYTES:
        d, _ = _read_plain_table(buf, 0)
        return d

    raise ValueError("unknown GXT2 magic %r (expected GXT2 or TABL)" % magic)


# --------------------------------------------------------------------------- #
# write  (plain GXT2, entries sorted by hash ascending — engine requirement)
# --------------------------------------------------------------------------- #
def write_gxt2(entries):
    """{key_hash:int -> str} -> bytes (plain GXT2). read_gxt2(write_gxt2(d)) == d.

    Reproduces the EXACT vanilla layout: entries sorted by hash ascending, and each
    entry's string written contiguously in that order so the data offsets are STRICTLY
    MONOTONICALLY INCREASING with NO de-duplication and NO padding.

    ⚠️ Do NOT de-dup shared strings. The RAGE text loader derives each string's length
    from offset[i+1] - offset[i] (the strings are contiguous in hash order). De-duping
    makes a repeated string reuse an earlier offset -> offsets stop being monotonic ->
    the loader computes a garbage/huge length -> ERR_MEM_EMBEDDEDALLOC_ALLOC at load.
    Verified on the real american_rel/global.gxt2: 0 shared offsets, strictly monotonic.
    """
    items = sorted((int(h) & 0xFFFFFFFF, s) for h, s in entries.items())
    count = len(items)

    # Header: magic + count + (count * 8 entry table) + sentinel magic + dataLen.
    header_size = 4 + 4 + count * 8 + 4 + 4

    # Data block: each string once per entry, NUL-terminated, in hash order. Offsets
    # are strictly increasing (no dedup, no padding) — byte-faithful to vanilla.
    data = bytearray()
    entry_offsets = []           # parallel to items: (hash, offset)
    for h, s in items:
        entry_offsets.append((h, header_size + len(data)))   # offset BEFORE this string
        data += s.encode("utf-8") + b"\x00"

    data_len = header_size + len(data)  # dataLen counts header pair + data, per spec.

    out = bytearray()
    out += GXT2_MAGIC_BYTES
    out += struct.pack("<I", count)
    for h, off in entry_offsets:
        out += struct.pack("<II", h, off)
    out += GXT2_MAGIC_BYTES                 # sentinel
    out += struct.pack("<I", data_len)
    out += data
    return bytes(out)


# --------------------------------------------------------------------------- #
# visual_line — logical Hebrew -> visual order (non-bidi engine)
# --------------------------------------------------------------------------- #
# A GTA token: tilde-wrapped control like ~r~ ~s~ ~a~ ~1~ ~n~ ~h~ ~BLIP_x~ etc.
# These are layout/format controls and MUST stay forward + atomic.


def _is_hebrew(ch):
    o = ord(ch)
    # Hebrew block U+0590..U+05FF + Alphabetic Presentation Forms U+FB1D..U+FB4F.
    return (0x0590 <= o <= 0x05FF) or (0xFB1D <= o <= 0xFB4F)


def _tokenize_visual(s):
    """Split `s` into runs, keeping GTA ~..~ tokens and <...> tags atomic+forward.

    Yields (kind, text) where kind in {"token", "tag", "heb", "other"}.
    """
    runs = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        # GTA tilde token: ~...~  (the inner content has no spaces in vanilla GTA).
        if ch == "~":
            j = s.find("~", i + 1)
            if j != -1:
                runs.append(("token", s[i:j + 1]))
                i = j + 1
                continue
            # lone tilde -> treat as other
            runs.append(("other", ch))
            i += 1
            continue
        # HTML-ish tag: <...>
        if ch == "<":
            j = s.find(">", i + 1)
            if j != -1 and "<" not in s[i + 1:j]:
                runs.append(("tag", s[i:j + 1]))
                i = j + 1
                continue
            runs.append(("other", ch))
            i += 1
            continue
        # Hebrew run
        if _is_hebrew(ch):
            j = i
            while j < n and _is_hebrew(s[j]):
                j += 1
            runs.append(("heb", s[i:j]))
            i = j
            continue
        # Everything else (Latin, digits, spaces, punctuation) as a single run
        j = i
        while j < n:
            c = s[j]
            if c == "~" or c == "<" or _is_hebrew(c):
                break
            j += 1
        runs.append(("other", s[i:j]))
        i = j
    return runs


_BOUNDARY_HY = "-־"   # ASCII hyphen-minus + Hebrew maqaf U+05BE


def _split_boundary_maqaf(runs):
    """Split a connecting hyphen/maqaf out of an 'other' run when it sits on a
    Hebrew<->Latin boundary, so the run-order flip in visual_line lands it BETWEEN
    the two (e.g. logical 'ל-Omega' -> visual 'Omega-ל', not '-Omegaל').

    Only a hyphen DIRECTLY at a Hebrew boundary is peeled (leading hyphen when the
    previous run is Hebrew; trailing hyphen when the next run is Hebrew). Hyphens
    inside a Latin run (URLs like warstock-cache-and-carry.com) are untouched.
    """
    out = []
    for idx, (kind, text) in enumerate(runs):
        if kind != "other":
            out.append((kind, text))
            continue
        prev_heb = bool(out) and out[-1][0] == "heb"
        next_heb = idx + 1 < len(runs) and runs[idx + 1][0] == "heb"
        lead = trail = ""
        if prev_heb:
            k = 0
            while k < len(text) and text[k] in _BOUNDARY_HY:
                k += 1
            if 0 < k < len(text):           # leave a run that is ONLY hyphens intact
                lead, text = text[:k], text[k:]
        if next_heb:
            k = len(text)
            while k > 0 and text[k - 1] in _BOUNDARY_HY:
                k -= 1
            if 0 < k < len(text):
                text, trail = text[:k], text[k:]
        if lead:
            out.append(("other", lead))
        out.append(("other", text))
        if trail:
            out.append(("other", trail))
    return out


def _visual_one(s):
    """Visual-reverse a SINGLE logical line (no newline tokens inside)."""
    if not s or not any(_is_hebrew(c) for c in s):
        return s
    runs = _split_boundary_maqaf(_tokenize_visual(s))
    rendered = []
    for kind, text in runs:
        if kind == "heb":
            rendered.append(text[::-1])           # reverse the Hebrew letters
        else:
            rendered.append(text)                 # token/tag/Latin/digits forward
    # Flip the order of the runs (RTL visual layout). Do NOT pre-mirror brackets:
    # the playbook is explicit (the engine handles L4 bracket-mirroring; pre-mirroring
    # here corrupts <...> tags and double-flips). Matches the user's proven, working
    # menyooStuff/Language/Hebrew.json, which keeps brackets/Latin forward.
    rendered.reverse()
    return "".join(rendered)


# GTA newline token ~n~ and literal newlines split a string into VISUAL lines.
_NEWLINE_SPLIT = re.compile(r"(~n~|\r\n|\n)")


def visual_line(s):
    """Logical-order Hebrew string -> visual (pre-reversed) order for a non-bidi
    LTR engine. A MULTI-LINE string is split on the ~n~/newline tokens and each line
    is reversed INDEPENDENTLY with the line ORDER preserved — reversing the whole
    string at once would flip the run order across ~n~ and print the LAST line first
    (the bottom-to-top paragraph bug). Pure-ASCII input is returned unchanged.
    """
    if not s or not any(_is_hebrew(c) for c in s):
        return s
    parts = _NEWLINE_SPLIT.split(s)
    return "".join(p if _NEWLINE_SPLIT.fullmatch(p) else _visual_one(p) for p in parts)


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"[{status}] {name}")
        if not cond:
            failures.append(name)

    # ---- joaat stability (known-good RAGE values) -------------------------- #
    # joaat("") == 0 ; joaat is deterministic. The two label hashes below are
    # recomputed live and asserted stable across calls (and to a captured value).
    j_empty = joaat("")
    check("joaat('') == 0", j_empty == 0)

    h1a, h1b = joaat("CELL_EMERGENCY"), joaat("cell_emergency")
    check("joaat is case-folded (CELL_EMERGENCY == cell_emergency)", h1a == h1b)
    check("joaat deterministic across calls", joaat("PHONE_HOME") == joaat("PHONE_HOME"))

    # Canonical RAGE joaat cross-check values (one-at-a-time, lowercased input):
    #   joaat("test") == 0x3f75ccc1 ; joaat("the") == 0x15a85bc0
    # (verified against an independent reference implementation).
    check("joaat('test') == 0x3f75ccc1", joaat("test") == 0x3F75CCC1)
    check("joaat('the')  == 0x15a85bc0", joaat("the") == 0x15A85BC0)
    # joaat of a single char is reproducible & in-range
    check("joaat('a') in uint32 range", 0 <= joaat("a") <= 0xFFFFFFFF)

    # ---- build a dict: ASCII + Hebrew + token strings ---------------------- #
    src = {
        joaat("ASCII_HELLO"):  "Hello, Los Santos!",
        joaat("HEB_PLAIN"):    "שלום עולם",  # שלום עולם
        joaat("HEB_TOKEN"):    "~r~אזהרה~s~ Wanted",        # ~r~אזהרה~s~ Wanted
        joaat("HEB_NUM"):      "יש לך 5 כוכבים",  # יש לך 5 כוכבים
        joaat("EMPTY_STR"):    "",
        joaat("PURE_TILDE"):   "~n~~h~Press ~INPUT_ENTER~~h~",
    }

    # ---- round-trip read(write(d)) == d ------------------------------------ #
    blob = write_gxt2(src)
    check("write_gxt2 emits GXT2 magic", blob[:4] == GXT2_MAGIC_BYTES)
    back = read_gxt2(blob)
    check("round-trip read(write(d)) == d", back == src)

    # entries sorted by hash ascending in the serialized table
    cnt = struct.unpack_from("<I", blob, 4)[0]
    hashes = [struct.unpack_from("<II", blob, 8 + i * 8)[0] for i in range(cnt)]
    check("entry table sorted by hash ascending", hashes == sorted(hashes))
    check("entry count matches dict size", cnt == len(src))

    # ---- TABL container read path (synthesize a 2-table container) --------- #
    def _build_tabl(dicts):
        sub_blobs = [write_gxt2(d) for d in dicts]
        # directory: 'TABL' + count + per record name[8]+offset[4]
        header = TABL_MAGIC_BYTES + struct.pack("<I", len(sub_blobs))
        dir_size = len(header) + len(sub_blobs) * 12
        body = bytearray()
        offsets = []
        cur = dir_size
        for sb in sub_blobs:
            offsets.append(cur)
            body += sb
            cur += len(sb)
        out = bytearray(header)
        for idx, off in enumerate(offsets):
            name = ("TAB%d" % idx).encode("ascii")[:8].ljust(8, b"\x00")
            out += name + struct.pack("<I", off)
        out += body
        return bytes(out)

    da = {joaat("A_ONE"): "alpha", joaat("A_TWO"): "בית"}  # בית
    db = {joaat("B_ONE"): "bravo", joaat("B_TWO"): "Charlie"}
    tabl_blob = _build_tabl([da, db])
    merged = read_gxt2(tabl_blob)
    expected_merge = {}
    expected_merge.update(da)
    expected_merge.update(db)
    check("TABL container flattens sub-tables", merged == expected_merge)

    # ---- visual_line: tokens kept, brackets mirrored, ASCII untouched ------ #
    ascii_only = "Just ASCII 123 (ok)"
    check("visual_line leaves pure-ASCII unchanged", visual_line(ascii_only) == ascii_only)

    heb = "שלום"  # שלום
    v = visual_line(heb)
    check("visual_line reverses a Hebrew run", v == heb[::-1])
    check("visual_line is idempotent-stable (reverse of reverse)", visual_line(v) == heb)

    tok = "~r~אזהרה~s~"   # ~r~אזהרה~s~
    vt = visual_line(tok)
    check("visual_line preserves ~r~ token", "~r~" in vt)
    check("visual_line preserves ~s~ token", "~s~" in vt)
    check("visual_line keeps both tokens intact", vt.count("~") == 4)

    # token order must flip (RTL): ~s~ appears before ~r~ in visual output
    check("visual_line flips run order (~s~ before ~r~)", vt.index("~s~") < vt.index("~r~"))

    # brackets are NOT pre-mirrored (engine does L4); tokens in tags survive
    import re as _re
    _tok = lambda s: sorted(_re.findall(r"~[^~]*~|</?[A-Za-z][^>]*>|%[0-9]*[sdifx%]", s))
    br = "(שלום)"   # (שלום)
    vb = visual_line(br)
    check("visual_line does NOT pre-mirror brackets", "(" in vb and ")" in vb)
    tagline = "<C>שלום</C> ~r~עולם~s~"
    vtl = visual_line(tagline)
    check("visual_line preserves <C></C> tags + ~tokens~ (no token drift)",
          _tok(vtl) == _tok(tagline))

    # digits stay forward inside a Hebrew sentence
    mixed = "יש 5 כוכבים"  # יש 5 כוכבים
    vm = visual_line(mixed)
    check("visual_line keeps digit '5' forward", "5" in vm)
    check("visual_line stable on mixed line (double-reverse heb runs)",
          visual_line(visual_line(vm)) == vm)

    # ---- summary ----------------------------------------------------------- #
    print("-" * 56)
    if failures:
        print(f"RESULT: FAIL ({len(failures)} failing): {failures}")
        sys.exit(1)
    else:
        print("RESULT: ALL PASS")
        sys.exit(0)
