#!/usr/bin/env python3
r"""
unc_swf.py — DefineFont3 code-table patcher for UNCHARTED's `flash1.psarc` SWF font libs.

WHY: proof #3 showed that remapping the code tables inside `fontlib.iggy` changed NOTHING
on screen (all 12 ladder positions stayed tofu), so either the Iggy code table is not the
engine's lookup, or `iggy1.psarc` is not where the UI fonts come from.

The strongest remaining hypothesis is the SWF side, on three pieces of evidence:
  * `flash1.psarc` ships **five** fontlib variants — `fontlib`, `fontlib-universal`,
    `fontlib-sceasia`, `fontlib-scechina`, `fontlib-scej` — while `iggy1.psarc` has only a
    single `fontlib.iggy`.  A game that ships Japanese/Korean/Chinese must load the
    per-region libraries, and those exist ONLY as `.swf`.
  * the exe's `IggyFileImage` loader carries both pak names plus the `swf` extension and a
    `hashMatches` check, and `%s.swf` is a literal format string.
  * `flash1.psarc`'s last-access time moved during a real play session.

Format: SWF `CWS` = 8-byte header + zlib body.  Tag 75 = DefineFont3:
    u16 fontId | u8 flags | u8 langCode | u8 nameLen | name
    u16 numGlyphs | offset table (u16 or u32 per FontFlagsWideOffsets)
    | codeTableOffset | glyph shapes | **code table (u16 per glyph, ASCENDING)**
Only the code table is touched, so the patch is delta-0 inside the decompressed body.

CLI:
    python unc_swf.py fonts <file.swf>
    python unc_swf.py plan  <file.swf> --cp 0x05D0
"""
import zlib
import struct
import argparse


def decompress(d):
    """-> (body, kind).  body is always an uncompressed 'FWS' image."""
    if d[:3] == b"CWS":
        return b"FWS" + d[3:8] + zlib.decompress(d[8:]), "CWS"
    if d[:3] == b"FWS":
        return d, "FWS"
    raise ValueError(f"not a SWF: {d[:4]!r}")


def recompress(body, kind, level=9):
    if kind == "FWS":
        return body
    return b"CWS" + body[3:8] + zlib.compress(body[8:], level)


def tags(body):
    nb = body[8] >> 3
    pos = 8 + ((5 + nb * 4 + 7) // 8) + 4
    while pos + 2 <= len(body):
        (th,) = struct.unpack_from("<H", body, pos)
        pos += 2
        code, ln = th >> 6, th & 0x3F
        if ln == 0x3F:
            (ln,) = struct.unpack_from("<I", body, pos)
            pos += 4
        if pos + ln > len(body):
            break
        yield code, pos, ln
        pos += ln
        if code == 0:
            break


def fonts(body):
    """-> list of dicts describing every DefineFont3 (tag 75)."""
    out = []
    for code, pos, ln in tags(body):
        if code != 75:
            continue
        fid, = struct.unpack_from("<H", body, pos)
        flags = body[pos + 2]
        wide_codes = bool(flags & 0x04)
        wide_off = bool(flags & 0x08)
        q = pos + 4
        nl = body[q]
        name = body[q + 1:q + 1 + nl].decode("utf-8", "replace")
        q += 1 + nl
        ng, = struct.unpack_from("<H", body, q)
        q += 2
        osz = 4 if wide_off else 2
        fmt = "<I" if wide_off else "<H"
        ct = q + struct.unpack_from(fmt, body, q + ng * osz)[0]
        cw = 2 if wide_codes else 1
        codes = [struct.unpack_from("<H", body, ct + 2 * i)[0] if cw == 2 else body[ct + i]
                 for i in range(ng)]
        # glyph offset table: ng entries, each RELATIVE to the table's own start (`q`)
        offs = [struct.unpack_from(fmt, body, q + i * osz)[0] for i in range(ng)]
        ct_rel = struct.unpack_from(fmt, body, q + ng * osz)[0]
        sizes = [e - o for o, e in zip(offs, offs[1:] + [ct_rel])]
        out.append(dict(id=fid, name=name, n=ng, wide=wide_codes,
                        code_off=ct, code_w=cw, codes=codes, tag_pos=pos, tag_len=ln,
                        off_base=q, off_w=osz, off_fmt=fmt, offs=offs, sizes=sizes))
    return out


def repoint(body, font, dst_index, src_index):
    """🔴 DO NOT USE — kept only so the failure is documented at the call site.

    The idea was: two entries sharing one shape offset is "legal" because a SWF shape
    record is self-terminating, so a reader never needs the entry's length.  That is true
    of a strict spec reader and FALSE of this engine.

    IT BLACK-SCREENED THE GAME (2026-07-24).  The glyph offset table is MONOTONIC, and
    pointing a low slot at a later glyph's offset makes the implied length
    `offs[i+1] - offs[i]` **negative** (measured: -1,230 on fontlib.swf id5) — a
    length-by-subtraction reader dies on it and the UI never comes up.

    To give a slot a real outline, INSERT the shape and recompute the whole offset table
    (`insert_glyph`, below) — the SWF body does NOT have to stay delta-0, because the whole
    psarc is repacked anyway.
    """
    raise RuntimeError(
        "repoint() breaks glyph-offset monotonicity and black-screens the game; "
        "use insert_glyph() instead")


def validate(body, where=""):
    """Structural gate — run on EVERY modified SWF body BEFORE it reaches the game.

    Cheap, and it catches exactly the damage that only surfaces as a black screen minutes
    later: a non-monotonic offset table, an unsorted/duplicated code table, or a glyph
    offset that escapes into the code table.  Returns a list of problem strings ([] = ok).
    """
    problems = []
    for f in fonts(body):
        tag = f"{where}{f['name']}(id{f['id']})"
        o = f["offs"]
        bad = [i for i in range(len(o) - 1) if o[i] > o[i + 1]]
        if bad:
            problems.append(f"{tag}: offset table NOT monotonic at {bad[:4]} "
                            f"(implied length {o[bad[0] + 1] - o[bad[0]]})")
        if f["codes"] != sorted(f["codes"]):
            problems.append(f"{tag}: code table not ascending")
        if len(set(f["codes"])) != len(f["codes"]):
            problems.append(f"{tag}: duplicate codepoints")
        ct_rel = f["code_off"] - f["off_base"]
        if o and o[-1] > ct_rel:
            problems.append(f"{tag}: last glyph offset {o[-1]} past the code table {ct_rel}")
    return problems


def insert_glyph(body, font, dst_index, src_index):
    """Give glyph `dst_index` a REAL outline by COPYING `src_index`'s shape bytes in.

    This is the correct replacement for repoint(): instead of aliasing an offset (which
    breaks monotonicity), the donor's shape record is spliced in right after the
    destination glyph's current slot, and EVERY later offset — plus the code-table
    offset — is shifted by the inserted length.  The tag length field is grown to match.
    The result stays a structurally valid DefineFont3; it is not delta-0, but the psarc
    is repacked regardless.

    Handles both u16 and u32 offset tables.  Monotonicity is PRESERVED: dst's own start
    offset is unchanged, and every offset after it — plus the code-table offset — shifts
    by exactly the length delta.  For a u16 table the shifted code-table offset must still
    fit in 16 bits, or the field wraps and corrupts the font — asserted below.
    """
    if font["tag_len"] < 0x3F:
        raise ValueError("short-form font tag; unexpected for this game")
    base, ng, ow, ofmt = font["off_base"], font["n"], font["off_w"], font["off_fmt"]
    offs = font["offs"]
    ct_rel = font["code_off"] - base                       # code table start, relative to base

    def span(i):
        return offs[i], (offs[i + 1] if i + 1 < ng else ct_rel)

    ds, de = span(dst_index)
    ss, se = span(src_index)
    shape = bytes(body[base + ss:base + se])               # the donor's real outline
    delta = len(shape) - (de - ds)                         # >0 grow, <0 shrink

    fieldmax = (1 << (8 * ow)) - 1
    if ct_rel + delta > fieldmax:                          # u16 overflow guard
        raise ValueError(f"insert_glyph: code-table offset {ct_rel + delta} exceeds the "
                         f"{ow*8}-bit field ({fieldmax}); would corrupt the font")

    out = bytearray(body)
    # 1. replace dst's shape region IN PLACE (its start offset never moves)
    out[base + ds:base + de] = shape
    # 2. shift every offset strictly after dst, and the code-table offset (entry ng)
    for i in range(dst_index + 1, ng):
        struct.pack_into(ofmt, out, base + i * ow, offs[i] + delta)
    struct.pack_into(ofmt, out, base + ng * ow, ct_rel + delta)
    # 3. grow the tag RECORDLENGTH (long form: u32 at tag_pos-4)
    ln, = struct.unpack_from("<I", out, font["tag_pos"] - 4)
    struct.pack_into("<I", out, font["tag_pos"] - 4, ln + delta)
    return bytes(out)


def index_of(font, cp):
    return font["codes"].index(cp) if cp in font["codes"] else None


def free_code_above(font, cp):
    """Smallest unused codepoint > cp that keeps the table ascending (or None).

    Used for the DISAPPEARANCE control: move a codepoint that is known to render
    onto an unused neighbour, so the character must vanish if this exact font is
    the one the engine draws with.  A pure lookup test — it needs no glyph work.
    """
    i = index_of(font, cp)
    if i is None:
        return None
    hi = font["codes"][i + 1] if i + 1 < font["n"] else 0x10FFFF
    s = set(font["codes"])
    for c in range(cp + 1, min(hi, cp + 64)):
        if c not in s:
            return c
    return None


def plan_slot(codes, new_cp):
    """Index whose replacement by `new_cp` keeps the table ascending, or None.

    The SWF code table is sorted so the player can binary-search it, so a codepoint can
    only be swapped into a slot whose NEIGHBOURS still bracket it.
    """
    for i in range(len(codes)):
        lo = codes[i - 1] if i else -1
        hi = codes[i + 1] if i + 1 < len(codes) else 0x10FFFF
        if lo < new_cp < hi and codes[i] != new_cp:
            return i
    return None


def patch(body, font, index, new_cp):
    """delta-0: rewrite one code-table entry (2-byte wide codes only)."""
    if font["code_w"] != 2:
        raise ValueError("narrow (u8) code table — cannot hold a Hebrew codepoint")
    out = bytearray(body)
    off = font["code_off"] + 2 * index
    old, = struct.unpack_from("<H", out, off)
    struct.pack_into("<H", out, off, new_cp)
    return bytes(out), old


def _cmd_fonts(a):
    body, kind = decompress(open(a.file, "rb").read())
    print(f"{a.file}  {kind}  body={len(body):,}")
    for f in fonts(body):
        s = set(f["codes"])
        print(f"  id={f['id']:<4} {f['name']:26s} n={f['n']:<6,} wide={f['wide']} "
              f"latin={len([c for c in s if 32<=c<127]):>3} cyr={len([c for c in s if 0x400<=c<0x500]):>3} "
              f"cjk={len([c for c in s if c>=0x2e80]):>5,} max=U+{max(s):04X}")


def _cmd_plan(a):
    body, _ = decompress(open(a.file, "rb").read())
    cp = int(a.cp, 0)
    for f in fonts(body):
        i = plan_slot(f["codes"], cp)
        if i is None:
            print(f"  id={f['id']:<4} {f['name']:26s} NO order-safe slot")
        else:
            c = f["codes"]
            print(f"  id={f['id']:<4} {f['name']:26s} slot {i}: U+{c[i]:04X} -> U+{cp:04X}  "
                  f"(between U+{c[i-1]:04X} and U+{c[i+1] if i+1<len(c) else 0x10FFFF:04X})")


def main():
    ap = argparse.ArgumentParser(description="UNCHARTED SWF font-library patcher")
    s = ap.add_subparsers(dest="cmd", required=True)
    q = s.add_parser("fonts"); q.add_argument("file")
    q = s.add_parser("plan");  q.add_argument("file"); q.add_argument("--cp", default="0x05D0")
    a = ap.parse_args()
    {"fonts": _cmd_fonts, "plan": _cmd_plan}[a.cmd](a)


if __name__ == "__main__":
    main()
