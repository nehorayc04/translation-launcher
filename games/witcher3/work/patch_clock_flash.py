# -*- coding: utf-8 -*-
"""Patch the meditation-clock Flash so the TIME renders on the correct RTL side for Hebrew.

WHY: the engine bidi's Arabic script only; Hebrew (Arabic-slot) renders LTR, so the AS function
`updateCurrentTimeString` in panel_meditation_clock.redswf composes `label + " HH:MM"` and the time
lands on the read-first side. Fix = reorder the final concat to `" HH:MM" + label` (a same-length,
9-byte in-place swap of the two operand push-blocks in the AS3 bytecode).

Chain: r4gui.bundle -> panel_meditation_clock.redswf (lz4) -> CR2W -> CFX(zlib) -> GFx -> DoABC ->
patch method -> GFx -> CFX(zlib) delta-0 splice + patch CR2W diskSize -> re-pack into r4gui.bundle
(as pack=1 zlib, the proven-loadable form). Fully reversible (r4gui.bundle.he_backup).

    py patch_clock_flash.py            # dry-run: patch + verify, write nothing to the game
    py patch_clock_flash.py --deploy   # patch + repack into the live r4gui.bundle (GAME CLOSED)
    py patch_clock_flash.py --revert    # restore r4gui.bundle from .he_backup
"""
import os, sys, struct, zlib, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "release", "lib"))
import potato_bundle as PB
import abc_tool as A

GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")
BUNDLE = os.path.join(GAME, "content", "content0", "bundles", "r4gui.bundle")
CLOCK = "panel_meditation_clock.redswf"
METHOD = "updateCurrentTimeString"


def patch_gfx(gfx):
    """Reorder `label + local4` -> `local4 + label` in updateCurrentTimeString. Same length."""
    gfx = bytearray(gfx)
    i = gfx.find(b"DoABC")  # not reliable; DoABC has no ascii magic -> locate the tag properly
    # locate DoABC (code 82) by walking tags
    p = 8
    nbits = gfx[p] >> 3
    p += ((5 + nbits * 4) + 7) // 8
    p += 4
    abc_off = None
    while p < len(gfx) - 1:
        th = struct.unpack_from("<H", gfx, p)[0]; p += 2
        code = th >> 6; ln = th & 0x3f
        if ln == 0x3f:
            ln = struct.unpack_from("<I", gfx, p)[0]; p += 4
        if code == 82:                       # DoABC
            body_off = p
            q = body_off + 4                 # skip flags(u32)
            while gfx[q] != 0:               # skip null-terminated name
                q += 1
            q += 1
            abc_off = q
            break
        p += ln
        if code == 0:
            break
    assert abc_off is not None, "no DoABC tag"
    abc = A.ABC(bytes(gfx[abc_off:abc_off + ln]))
    hits = abc.method_named(METHOD)
    assert hits, f"{METHOD} not found"
    _mi, b = hits[0]
    code_abs = abc_off + b["code_off"]
    code = bytearray(gfx[code_abs:code_abs + b["code_len"]])
    ins = {o: (sz, mn) for o, sz, mn, ops, txt in A.disasm(abc, bytes(code))}
    # the final compose: 161 getlocal_0; getproperty lb; getproperty htmlText | 168 getlocal 4 | 170 add
    assert ins[161][1] == "getlocal_0" and ins[168][1] == "getlocal" and ins[170][1] == "add", \
        f"compose shape changed: {ins.get(161)},{ins.get(168)},{ins.get(170)}"
    A7 = bytes(code[161:168])                # label push
    B2 = bytes(code[168:170])                # getlocal 4 (the time)
    newcode = code[:161] + B2 + A7 + code[170:]
    assert len(newcode) == len(code)
    gfx[code_abs:code_abs + len(newcode)] = newcode
    # verify the swap re-parses
    abc2 = A.ABC(bytes(gfx[abc_off:abc_off + ln]))
    _mi2, b2 = abc2.method_named(METHOD)[0]
    d2 = {o: (mn, txt) for o, sz, mn, ops, txt in
          A.disasm(abc2, bytes(gfx[abc_off + b2["code_off"]:abc_off + b2["code_off"] + b2["code_len"]]))}
    assert d2[161][0] == "getlocal" and d2[167][0] == "getproperty" and d2[170][0] == "add", \
        "post-patch shape wrong"
    return bytes(gfx)


def rewrap_redswf(redswf):
    """Apply the GFx patch and re-embed it into the redswf (delta-0 splice, same total size)."""
    orig_len = len(redswf)
    cfx_off = redswf.find(b"CFX")
    assert cfx_off > 0, "no CFX"
    cfx_ver = redswf[cfx_off + 3]
    gfx_uncomp = struct.unpack_from("<I", redswf, cfx_off + 4)[0]
    gfx = b"GFX" + bytes([cfx_ver]) + struct.pack("<I", gfx_uncomp) + zlib.decompress(redswf[cfx_off + 8:])
    new_gfx = patch_gfx(gfx)
    assert len(new_gfx) == len(gfx), "gfx length changed"
    comp = zlib.compress(new_gfx[8:], 9)
    new_cfx = b"CFX" + bytes([cfx_ver]) + struct.pack("<I", len(new_gfx)) + comp
    region = orig_len - cfx_off
    if len(new_cfx) > region:
        raise SystemExit(f"CFX grew by {len(new_cfx) - region} bytes — would need a CR2W field repack")
    cr2w_head = bytearray(redswf[:cfx_off])
    struct.pack_into("<I", cr2w_head, cfx_off - 4, len(new_cfx))     # patch the embedded-buffer diskSize
    new_redswf = bytes(cr2w_head) + new_cfx + b"\x00" * (region - len(new_cfx))
    assert len(new_redswf) == orig_len
    return new_redswf


def _repack(bundle, new_map, base_bytes):
    d = bytearray(base_bytes)
    _fs, _sz, header_sz, _ds = struct.unpack_from("<IIII", d, 8)
    ents = []
    for i in range(header_sz // 320):
        base = 0x20 + i * 320
        name = d[base:base + 256].split(b"\x00", 1)[0].decode("latin-1")
        sz, zsz, offs = struct.unpack_from("<III", d, base + 256 + 16 + 4)
        pk = struct.unpack_from("<I", d, base + 320 - 4)[0]
        ents.append({"base": base, "name": name, "size": sz, "zsize": zsz, "offs": offs, "pack": pk})
    ents_off = sorted(ents, key=lambda x: x["offs"])
    data_start = ents_off[0]["offs"]
    out = bytearray(d[:data_start]); cur = data_start
    for e in ents_off:
        pad = (-cur) % 16
        out += b"\x00" * pad; cur += pad
        key = e["name"].lower()
        if key in new_map:
            payload, pack = new_map[key]
            raw = zlib.compress(payload, 9) if pack == 1 else payload
            e["ns"], e["np"] = len(payload), pack
        else:
            raw = bytes(d[e["offs"]:e["offs"] + e["zsize"]])
            e["ns"], e["np"] = e["size"], e["pack"]
        e["no"], e["nz"] = cur, len(raw)
        out += raw; cur += len(raw)
    for e in ents:
        b = e["base"]
        struct.pack_into("<III", out, b + 256 + 16 + 4, e["ns"], e["nz"], e["no"])
        struct.pack_into("<I", out, b + 320 - 4, e["np"])
    struct.pack_into("<I", out, 8, len(out))
    struct.pack_into("<I", out, 12, len(out) - data_start)
    open(bundle, "wb").write(bytes(out))


def main(deploy):
    if "--revert" in sys.argv:
        bak = BUNDLE + ".he_backup"
        if os.path.exists(bak):
            shutil.copy2(bak, BUNDLE); print("reverted r4gui.bundle from .he_backup")
        else:
            print("no .he_backup to revert")
        return
    cur = open(BUNDLE, "rb").read()
    d, ents = PB.list_entries(BUNDLE)
    e = [x for x in ents if x["name"].lower().endswith(CLOCK)][0]
    redswf = PB.extract(d, e)
    print(f"clock redswf: {len(redswf)} bytes (pack {e['pack']})")
    patched = rewrap_redswf(redswf)
    print(f"patched redswf: {len(patched)} bytes (same size: {len(patched) == len(redswf)}) — AS reorder verified")
    if not deploy:
        print("\n(dry-run) verified only. Re-run with --deploy (GAME CLOSED).")
        return
    if not os.path.exists(BUNDLE + ".he_backup"):
        shutil.copy2(BUNDLE, BUNDLE + ".he_backup")
    _repack(BUNDLE, {e["name"].lower(): (patched, 1)}, cur)   # pack=1 zlib (proven-loadable)
    # verify the live bundle re-parses + the clock decompresses with the patch
    d2, ents2 = PB.list_entries(BUNDLE)
    e2 = [x for x in ents2 if x["name"].lower().endswith(CLOCK)][0]
    r2 = PB.extract(d2, e2)
    cfx_off = r2.find(b"CFX")
    gfx = b"GFX" + r2[cfx_off + 3:cfx_off + 4] + r2[cfx_off + 4:cfx_off + 8] + zlib.decompress(r2[cfx_off + 8:])
    print(f"DEPLOYED. live clock redswf re-extracts + CFX decompresses ({len(gfx)} B GFx). Launch + check.")


if __name__ == "__main__":
    main("--deploy" in sys.argv)
