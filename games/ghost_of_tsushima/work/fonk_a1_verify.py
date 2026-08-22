#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_verify.py — confirm manifest→data→XTBS chain (proving .sps are textures &
fOnk is inside one), then broaden the font-name search."""
import os, struct, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
BIG  = os.path.join(EX, "game.sprig.texmeshman")
FONK_OFF = 0x156BFF7
raw = open(BIG, "rb").read()
N = len(raw)


def read_entry_at(name_off):
    """Given the file offset of a name, walk back to find its [offset][?][namelen]."""
    # namelen is a u32 right before the name; offset is 8 bytes before that.
    nl = struct.unpack_from("<I", raw, name_off-4)[0]
    dataoff = struct.unpack_from("<I", raw, name_off-12)[0]
    return dataoff, nl


def main():
    # XTBS magic occurrences (73 42 54 58 = 'sBTX' LE for 'XTBS')
    xtbs = []
    s=0
    while True:
        i = raw.find(b"XTBS", s)
        if i<0: i2 = raw.find(b"sBTX", s)
        else: i2 = i
        j = raw.find(b"sBTX", s)
        # search both
        cand = [x for x in (raw.find(b"XTBS", s), raw.find(b"sBTX", s)) if x>=0]
        if not cand: break
        k = min(cand); xtbs.append((k, raw[k:k+4])); s=k+1
        if len(xtbs) > 5: break
    print(f"== XTBS/sBTX texture-magic hits: {[(hex(o),m) for o,m in xtbs]}")

    # Verify the lang_arabic.msac.d.0.sps entry -> its data offset -> XTBS?
    for target in [b"lang_arabic.msac.d.0.sps", b"custom_ag_bowl_china_001.msac.n.0.sps",
                   b"overlay_kanji_legends.msac.d.0.sps", b"main_menu_logo_subtitle.msac.d.0.sps"]:
        no = raw.find(target)
        if no < 0:
            print(f"   {target!r}: name not found"); continue
        doff, nl = read_entry_at(no)
        magic = raw[doff:doff+8]
        print(f"   {target.decode():42s} name@0x{no:x} dataoff=0x{doff:x} "
              f"magic={magic[:4]!r}({magic[:4][::-1]!r}) hex={magic.hex()}")
        # does fOnk fall inside this one?

    # confirm fOnk containment numerically
    n_off = raw.find(b"custom_ag_bowl_china_001.msac.n.0.sps")
    doff, nl = read_entry_at(n_off)
    s_off = raw.find(b"custom_ag_bowl_china_001.msac.s.0.sps")
    sdoff, _ = read_entry_at(s_off)
    print(f"\n== CONTAINMENT: .n.0.sps data=[0x{doff:x},0x{sdoff:x}) fОnk=0x{FONK_OFF:x} "
          f"inside={doff <= FONK_OFF < sdoff}  (offset into res = {FONK_OFF-doff})")

    # Broaden name search for a vector-font resource (non-.sps, or ui/hud/type/fnt)
    print("\n== broadened resource-name search (ui/hud/type/fnt/text/sdf/vera/gothic/kaku) ==")
    names=set()
    for m in re.finditer(rb"[A-Za-z0-9_./|\\-]{5,}", raw):
        s=m.group()
        if b"." in s and len(s)<=120: names.add(s)
    pat = re.compile(rb"(^|_)(ui|hud|type|fnt|text|sdf|vera|gothic|kaku|mincho|font)", re.I)
    ext = collections.Counter()
    for s in names:
        # extension family (last non-numeric token)
        mm = re.search(rb"\.([a-z]{2,5})\.", s)
        if mm: ext[mm.group(1)] += 1
    print("   distinct middle-extensions (.<x>.):", dict(ext.most_common(20)))
    fh = sorted(s for s in names if pat.search(s))
    print(f"   {len(fh)} ui/type/font-ish names; sample:")
    for s in fh[:30]:
        print(f"     {s.decode(errors='replace')}")


if __name__ == "__main__":
    main()
