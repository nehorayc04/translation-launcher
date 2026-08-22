#!/usr/bin/env python3
r"""
build_isolation.py — find WHAT inside the Hebrew mod crashes TLOU2R.

Both the DSAR and the plain-PSARC builds of the full mod crash the game, while
ndmodloader alone (empty mods\) boots fine. So the culprit is the mod CONTENT, not
the DSAR-vs-plain choice. This splits the mod into isolated variants (all plain
PSARC — the format that at least reaches the loader):

  A = identity   {text2/eng.common: ORIGINAL bytes}      -> tests PSARC struct + ndml partial-override mount
  B = fonts-only {ORIGINAL eng.common + Heebo seriffont}  -> tests the DINPro->Heebo font swap
  C = loc-only   {Hebrew-patched eng.common, NO fonts}    -> tests tlou_loc.encode
  full = C + fonts (the real mod)

Whichever isolated variant crashes points at the culprit:
  A crashes            -> partial-override mount / psarc_write struct  -> Plan B (full core.psarc repack, like Part I)
  A ok, B crashes      -> the font swap
  A ok, C crashes      -> tlou_loc.encode
  A/B/C all ok         -> a B+C interaction (rare)

  python build_isolation.py build        # build iso_A/B/C/full.psarc into proof/  (needs .venv: fontTools+lz4)
  python build_isolation.py set A|B|C|full   # copy the chosen variant into mods\  (pure copy, any python)
"""
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.environ.get("TLOU2_GAME", r"F:\Games\The Last of Us - Part II Remastered")
MODS = os.environ.get("TLOU2_MODS", os.path.join(GAME, "mods"))
PROOF = os.path.join(HERE, "..", "proof")
MOD_NAME = "zzz-hebrew-proof.psarc"


def build():
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, "..", "tools"))
    import tlou_loc, psarc_write            # noqa: E402
    import build_menu_proof as B            # noqa: E402

    os.makedirs(PROOF, exist_ok=True)
    core = B.Psarc2(B.CORE)
    orig = core.extract(core.by_path["text2/eng.common"])
    heb = tlou_loc.encode(orig, B._overrides())

    fonts = {}
    fdir = os.path.join(HERE, "fonts")
    edir = os.path.join(HERE, "..", "extract", "fonts")
    for face, weight in B.FACES.items():
        fonts["fonts/" + face] = B._build_font(
            face, os.path.join(fdir, weight), os.path.join(edir, face))

    # (files, compress).  core.psarc holds eng.common STORED (block-table [0*16, 38282],
    # not zlib) because it is a DSAR (LZ4 outer). A zlib inner block is decoded WRONG by
    # the engine -> "UNKNOWN STRING". So the STORED variants (compress=False) are the fix.
    variants = {
        "A":     ({"text2/eng.common": orig}, True),
        "B":     ({"text2/eng.common": orig, **fonts}, True),
        "C":     ({"text2/eng.common": heb}, True),
        "full":  ({"text2/eng.common": heb, **fonts}, True),
        "As":    ({"text2/eng.common": orig}, False),           # identity, STORED, NO font
        "Bs":    ({"text2/eng.common": orig, **fonts}, False),  # identity + Heebo font, STORED (font A/B)
        "Cs":    ({"text2/eng.common": heb}, False),            # hebrew loc, STORED, no font
        "fulls": ({"text2/eng.common": heb, **fonts}, False),   # the real mod, STORED
    }
    for name, (files, comp) in variants.items():
        blob = psarc_write.build(files, compress=comp)
        rb = psarc_write.verify_read(blob)
        assert all(rb.get(k) == v for k, v in files.items()), f"{name} read-back mismatch"
        out = os.path.join(PROOF, f"iso_{name}.psarc")
        with open(out, "wb") as f:
            f.write(blob)
        tag = "STORED" if not comp else "zlib  "
        print(f"[{name:5} {tag}] {out}  ({len(blob):>8,} B, {len(files)} files: {', '.join(files)})")
    print("\nbuilt. deploy one at a time:  python build_isolation.py set As   (then launch)")


def setmod(which):
    src = os.path.join(PROOF, f"iso_{which}.psarc")
    if not os.path.isfile(src):
        print(f"[!] {src} missing — run `python build_isolation.py build` first (with the .venv python)")
        return
    os.makedirs(MODS, exist_ok=True)
    dst = os.path.join(MODS, MOD_NAME)
    shutil.copyfile(src, dst)
    print(f"[set {which}] -> {dst}  ({os.path.getsize(dst):,} B)   now launch the game")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        build()
    elif len(sys.argv) >= 3 and sys.argv[1] == "set":
        setmod(sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
