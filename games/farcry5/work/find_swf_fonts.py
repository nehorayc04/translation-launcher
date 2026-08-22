"""FC5 stores its UI as Scaleform SWF with the FWS magic obfuscated to UEF (F,W,S -> U,E,F).
That is WHY no sfnt font exists anywhere: Scaleform embeds glyphs as VECTOR SHAPES inside
DefineFont2/3 tags, not as a TTF.

This walks every UEF resource, de-obfuscates it, parses the SWF tag stream and reports every
font tag with its glyph count + the codepoints it covers.

  python find_swf_fonts.py [archive.fat ...]
"""
import sys, os, struct, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")

TAG_DEFINEFONT   = 10
TAG_DEFINEFONT2  = 48
TAG_DEFINEFONT3  = 75
TAG_DEFINEFONTINFO  = 13
TAG_DEFINEFONTINFO2 = 62
TAG_DEFINEFONTNAME  = 88
FONT_TAGS = {TAG_DEFINEFONT, TAG_DEFINEFONT2, TAG_DEFINEFONT3,
             TAG_DEFINEFONTINFO, TAG_DEFINEFONTINFO2, TAG_DEFINEFONTNAME}

HEB = set(range(0x05D0, 0x05EB))
ARA = set(range(0x0620, 0x0650))
LAT = set(range(0x41, 0x5B))


def deobfuscate(b):
    """UEF -> FWS (Scaleform/Fire obfuscation, same trick AC Unity uses)."""
    if b[:3] == b"UEF":
        return b"FWS" + b[3:]
    if b[:3] == b"CEF":
        return b"CWS" + b[3:]
    return b


def skip_rect(b, p):
    nbits = b[p] >> 3
    total = 5 + nbits * 4
    return p + (total + 7) // 8


def tags(b):
    """Yield (code, payload) for an uncompressed FWS SWF."""
    if b[:3] != b"FWS":
        return
    p = 8
    p = skip_rect(b, p)
    p += 4                                    # frame rate + frame count
    n = len(b)
    while p + 2 <= n:
        rh = struct.unpack_from("<H", b, p)[0]; p += 2
        code = rh >> 6; ln = rh & 0x3F
        if ln == 0x3F:
            if p + 4 > n:
                return
            ln = struct.unpack_from("<I", b, p)[0]; p += 4
        if ln < 0 or p + ln > n:
            return
        yield code, b[p:p + ln]
        p += ln
        if code == 0:
            return


def font_info(code, d):
    """Return (font_id, nglyphs, codepoints, name) for a font tag."""
    try:
        if code in (TAG_DEFINEFONT2, TAG_DEFINEFONT3):
            fid = struct.unpack_from("<H", d, 0)[0]
            flags = d[2]
            wide_codes = bool(flags & 0x04)
            has_layout = bool(flags & 0x80)
            p = 4                                   # id(2) flags(1) langcode(1)
            nlen = d[p]; p += 1
            name = d[p:p + nlen].decode("latin-1", "replace"); p += nlen
            ng = struct.unpack_from("<H", d, p)[0]; p += 2
            if ng == 0:
                return fid, 0, set(), name
            wide_off = bool(flags & 0x08) or code == TAG_DEFINEFONT3
            osz = 4 if wide_off else 2
            offs = [struct.unpack_from("<I" if wide_off else "<H", d, p + i * osz)[0]
                    for i in range(ng)]
            code_off = struct.unpack_from("<I" if wide_off else "<H", d, p + ng * osz)[0]
            base = p
            cs = base + code_off
            w = 2 if wide_codes else 1
            cps = set()
            for i in range(ng):
                q = cs + i * w
                if q + w <= len(d):
                    cps.add(struct.unpack_from("<H" if w == 2 else "<B", d, q)[0])
            return fid, ng, cps, name
        if code in (TAG_DEFINEFONTINFO, TAG_DEFINEFONTINFO2):
            fid = struct.unpack_from("<H", d, 0)[0]
            nlen = d[2]
            name = d[3:3 + nlen].decode("latin-1", "replace")
            p = 3 + nlen
            flags = d[p]; p += 1
            if code == TAG_DEFINEFONTINFO2:
                p += 1
            wide = bool(flags & 0x01)
            w = 2 if wide else 1
            cps = set()
            q = p
            while q + w <= len(d):
                cps.add(struct.unpack_from("<H" if w == 2 else "<B", d, q)[0]); q += w
            return fid, len(cps), cps, name
        if code == TAG_DEFINEFONTNAME:
            fid = struct.unpack_from("<H", d, 0)[0]
            nm = d[2:].split(b"\x00")[0].decode("latin-1", "replace")
            return fid, -1, set(), nm
    except Exception:
        pass
    return None, 0, set(), ""


if __name__ == "__main__":
    archives = sys.argv[1:] or ["common.fat", "patch.fat", "worlds/installpkg.fat",
                                "worlds/farcry5.fat", "ige.fat", "igepatch.fat"]
    total = 0
    for arch in archives:
        p = os.path.join(PC, arch)
        if not os.path.exists(p):
            continue
        f = Fat(p)
        print(f"\n### {arch} ({f.count:,} entries)", flush=True)
        nswf = 0
        for e in f.entries:
            if not (64 <= e.unc <= 40_000_000):
                continue
            try:
                b = f.read_data(e)
            except Exception:
                continue
            if b[:3] not in (b"UEF", b"CEF", b"FWS", b"CWS"):
                continue
            nswf += 1
            b = deobfuscate(b)
            for code, d in tags(b):
                if code not in FONT_TAGS:
                    continue
                fid, ng, cps, name = font_info(code, d)
                if fid is None:
                    continue
                lat = len(cps & LAT); ara = len(cps & ARA); heb = len(cps & HEB)
                print(f"  {e.hash:016x} tag={code:<3} font#{fid:<4} glyphs={ng:<5} "
                      f"lat={lat:>2}/26 ara={ara:>2}/48 heb={heb:>2}/27  {name}", flush=True)
                total += 1
        print(f"### {arch}: {nswf} SWF resources", flush=True)
    print(f"\nTOTAL font tags: {total}")
