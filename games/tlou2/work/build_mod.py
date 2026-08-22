#!/usr/bin/env python3
r"""
build_mod.py - build the FULL Hebrew mod for The Last of Us Part II Remastered.

Reads the translated spine `agent_handoff/hebrew.json` (+ any `hebrew_*.json`),
keyed by md5(EN)[:16] -> LOGICAL Hebrew. For each of the 3 loc files it maps every
translation back onto EVERY SID whose English hashes to that key, applies
`tlou_rtl.to_visual` (the RTL bake - the ND engine does NO bidi, confirmed in-game),
overrides the file via the SURGICAL `tlou_loc.encode` (unchanged strings stay
byte-identical), swaps DINPro -> Heebo (2 faces), and packs everything into a plain
**STORED** PSARC dropped into `<game>\mods\` (ndmodloader; core.psarc untouched).

    python build_mod.py            # build proof/zzz-hebrew.psarc
    python build_mod.py --deploy   # build + copy into <game>\mods\
    python build_mod.py --revert   # remove the mod from <game>\mods\
    python build_mod.py --logical  # store LOGICAL (debug only; default = VISUAL)

Env: TLOU2_GAME (game root), TLOU2_MODS (override mods dir, default <game>\mods).
Run with the repo .venv python (fontTools + lz4).
"""
import os, sys, glob, json, hashlib, argparse, io

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import tlou_loc            # noqa: E402
import tlou_rtl            # noqa: E402
import tlou_font           # noqa: E402
import psarc_write         # noqa: E402
import dsar as dsar_reader  # noqa: E402
from dsar import Psarc2    # noqa: E402

GAME = os.environ.get("TLOU2_GAME", r"F:\Games\The Last of Us - Part II Remastered")
CORE = os.path.join(GAME, "build", "pc", "main", "core.psarc")
MODS = os.environ.get("TLOU2_MODS", os.path.join(GAME, "mods"))
PROOF = os.path.join(HERE, "..", "proof")
HANDOFF = os.path.join(HERE, "..", "agent_handoff")
MOD_NAME = "zzz-hebrew.psarc"

LOC_FILES = ["text2/eng.common", "text2/eng.subtitles", "text2/eng.subtitles-systemic"]
FACES = {  # override face filename -> Heebo weight source (masquerades as DINPro)
    "seriffont-Regular.otf": "Heebo-Regular.ttf",
    "seriffont-Medium.otf":  "Heebo-Medium.ttf",
}


def _key(en: str) -> str:
    return hashlib.md5(en.encode("utf-8")).hexdigest()[:16]


def _load_hebrew():
    """Merge agent_handoff/hebrew.json + hebrew_*.json -> {md5key: LOGICAL Hebrew}."""
    he = {}
    for p in [os.path.join(HANDOFF, "hebrew.json")] + sorted(glob.glob(os.path.join(HANDOFF, "hebrew_*.json"))):
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                he.update(json.load(f))
    return {k: v for k, v in he.items() if v and v.strip()}


def _build_font(face, src_ttf, ref_otf):
    ft = tlou_font.TTFont(src_ttf)
    if os.path.isfile(ref_otf):
        ft["name"] = tlou_font.TTFont(ref_otf)["name"]   # masquerade as DINPro/seriffont
    buf = io.BytesIO(); ft.save(buf)
    return buf.getvalue()


def build(visual=True):
    os.makedirs(PROOF, exist_ok=True)
    core = Psarc2(CORE)
    he = _load_hebrew()
    V = tlou_rtl.to_visual

    files = {}
    total_ov = 0
    for path in LOC_FILES:
        data = core.extract(core.by_path[path])
        m = tlou_loc.to_map(data)                        # {sid_hex: en}
        overrides = {}
        for sid, en in m.items():
            k = _key(en)
            heb = he.get(k)
            if heb:
                overrides[sid] = V(heb) if visual else heb
        new_loc = tlou_loc.encode(data, overrides)       # SURGICAL (unchanged bytes preserved)
        # verify the overrides applied + nothing else moved
        chk = tlou_loc.to_map(new_loc)
        bad = sum(1 for s, v in overrides.items() if chk.get(s) != v)
        assert bad == 0, f"{path}: {bad} overrides did not round-trip"
        files[path] = new_loc
        total_ov += len(overrides)
        print(f"[loc] {path:32} strings={len(m):>6}  overridden={len(overrides):>6}  ({len(new_loc):,} B)")

    fdir = os.path.join(HERE, "fonts")
    edir = os.path.join(HERE, "..", "extract", "fonts")
    for face, weight in FACES.items():
        fb = _build_font(face, os.path.join(fdir, weight), os.path.join(edir, face))
        files["fonts/" + face] = fb
        print(f"[font] fonts/{face}  <- {weight}  ({len(fb):,} B)")

    inner = psarc_write.build(files, compress=False)      # STORED (proven-in-game format)
    out = os.path.join(PROOF, MOD_NAME)
    with open(out, "wb") as f:
        f.write(inner)
    rb = psarc_write.verify_read(inner)
    assert all(rb.get(k) == v for k, v in files.items()), "override read-back mismatch"
    cov = 100 * len(he) // max(len(_translatable_keys(core)), 1)
    print(f"[psarc] wrote {out}  (PLAIN STORED {len(inner):,} B, {len(files)} files, read-back OK)")
    print(f"[cover] {total_ov:,} SID overrides from {len(he):,} unique Hebrew strings")
    return out


def _translatable_keys(core):
    """Unique md5(EN) keys across the 3 loc files (for a coverage %)."""
    ks = set()
    for path in LOC_FILES:
        for en in tlou_loc.to_map(core.extract(core.by_path[path])).values():
            ks.add(_key(en))
    return ks


def deploy(visual=True):
    out = build(visual)
    if not os.path.isdir(GAME):
        print(f"\n[!] game root not found: {GAME}"); return
    os.makedirs(MODS, exist_ok=True)
    dst = os.path.join(MODS, MOD_NAME)
    import shutil
    shutil.copyfile(out, dst)
    print(f"[deploy] -> {dst}")
    print("\nActivation: Options -> Language -> Text + Subtitles = English (the hijacked slot),"
          "\nSpeech = English. (ndmodloader must be installed.)  Revert: python build_mod.py --revert")


def revert():
    dst = os.path.join(MODS, MOD_NAME)
    if os.path.isfile(dst):
        os.remove(dst); print(f"[revert] removed {dst}")
    else:
        print(f"[revert] nothing at {dst}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--logical", action="store_true", help="store LOGICAL (debug; default VISUAL)")
    a = ap.parse_args()
    if a.revert:
        revert()
    elif a.deploy:
        deploy(visual=not a.logical)
    else:
        build(visual=not a.logical)


if __name__ == "__main__":
    main()
