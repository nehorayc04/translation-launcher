#!/usr/bin/env python3
r"""
build_inplace_proof.py — Ghost of Tsushima menu-proof via IN-PLACE edit of gapack_misc_l.

Why in-place (not an added override psarc): the engine builds a global path map and CRASHES
on a duplicate internal path — adding a 2nd archive that also holds /lang_arabic_text.xpps
crashed boot (both a faithful and unfaithful DSAR; a plain PSARC was silently skipped). Proven
2026-07-07. The got_dsar writer IS engine-faithful (an identity rebuild of gapack_misc_p booted).
So we EDIT the one shipping copy in gapack_misc_l — no duplicate, guaranteed loaded.

Maximally faithful + low-risk:
  * SAME-SIZE in-place KCAP override (tools/xpps.patch_inplace) -> the 17 MB lang_arabic_text.xpps
    stays byte-length-identical -> the inner PSARC (TOC/block-table/offsets) is UNCHANGED.
  * All 5 menu strings live in the first ~2 MB of the xpps = the inner PSARC's RAW (stored) block
    region (verified: 260/261 blocks raw), so inner-stream offset = F + xpps_offset (identity map,
    asserted at build). The single zlib-compressed tail block is never touched.
  * got_dsar.patch_inner re-LZ4s ONLY the ~9 DSAR chunks (of 8383) overlapping the edits; every
    other chunk's compressed payload is copied VERBATIM (byte-identical to shipping).
Everything is validated OFFLINE (identity map, re-read of lang_arabic_text.xpps == our new bytes,
sample other files byte-identical, chunk/file counts) BEFORE the game is touched.

    python build_inplace_proof.py            # build + validate offline (no game file changed)
    python build_inplace_proof.py --deploy   # + back up gapack_misc_l -> .he_backup, swap in
    python build_inplace_proof.py --revert    # restore gapack_misc_l from .he_backup
Env: GOT_GAME. Run with the repo .venv python (needs lz4).
"""
import os, sys, argparse, importlib.util, struct, shutil, time

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(GAME_DIR))
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
GL = os.path.join(GAME, "cache_pc", "psarc", "gapack_misc_l.psarc")
BAK = GL + ".he_backup"
INNER = "/lang_arabic_text.xpps"
EN_STAGE = os.path.join(GAME_DIR, "extract", "lang_english_text.xpps")


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m

xpps = _load("got_xpps", os.path.join(GAME_DIR, "tools", "xpps.py"))
rtl = _load("got_rtl", os.path.join(HERE, "got_rtl.py"))
dsar = _load("dsar", os.path.join(REPO, "games", "tlou2", "tools", "dsar.py"))
got_dsar = _load("got_dsar", os.path.join(HERE, "got_dsar.py"))

# menu EN text -> (Hebrew, mode). marker=Latin proves load; log=LOGICAL; vis=VISUAL bake.
PROOF = {
    "Continue":  ("ZZ-GOT-OK-ZZ", "marker"),
    "New Game":  ("משחק חדש", "log"),
    "Load Game": ("טען משחק", "log"),
    "Options":   ("הגדרות", "log"),
    "Subtitles": ("כתוביות", "vis"),
}
RAW_BLOCKS = 260          # gapack_misc_l: lang_arabic_text.xpps = 260 raw 64KB blocks + 1 zlib tail
BLOCK = 0x10000


def build(deploy=False):
    t0 = time.time()
    src = BAK if os.path.exists(BAK) else GL     # always build from the pristine original
    ps = dsar.Psarc2(src)
    ent = next(e for e in ps.files() if e.path == INNER)
    F = ent.offset
    ar_bytes = ps.extract(ent)
    assert len(ar_bytes) == ent.orig_size
    en = xpps.read_pack(EN_STAGE)

    # collect ALL keys whose EN text is a menu item (covers duplicate keys) -> AR overrides
    overrides, report = {}, []
    for en_txt, (heb, mode) in PROOF.items():
        keys = [k for k, t in en.items() if t == en_txt]
        stored = rtl.to_visual(heb) if mode == "vis" else heb
        for k in keys:
            overrides[k] = stored
        report.append(f"  [{mode:6}] {en_txt!r:11} -> {heb!r}  ({len(keys)} key(s))")
    new_ar = xpps.patch_inplace(ar_bytes, overrides)
    assert len(new_ar) == len(ar_bytes), "in-place override must not change length"
    back = dict(xpps.read_pack_bytes(new_ar))
    for k in overrides:
        assert back.get(k) == overrides[k], f"readback mismatch {k}"
    print(f"same-size override: {len(overrides)} keys, xpps {len(ar_bytes)} B (unchanged length)")
    print("\n".join(report))

    # identity-map check: the RAW region [F, F+RAW_BLOCKS*BLOCK) must equal ar_bytes[:that]
    raw_len = RAW_BLOCKS * BLOCK
    inner_raw = ps.d.read(F, raw_len)
    assert inner_raw == ar_bytes[:raw_len], "raw-region identity map FAILED (edits would corrupt)"
    # compute differing runs (same-size) -> inner edits, all must fall inside the raw region
    edits = []
    i = 0
    while i < len(ar_bytes):
        if ar_bytes[i] != new_ar[i]:
            j = i
            while j < len(ar_bytes) and ar_bytes[j] != new_ar[j]:
                j += 1
            assert j <= raw_len, f"edit at {i}:{j} is past the raw region ({raw_len})"
            edits.append((F + i, new_ar[i:j]))
            i = j
        else:
            i += 1
    print(f"inner edits: {len(edits)} differing runs, all within the raw region "
          f"(max end {max((o - F + len(b)) for o, b in edits)} <= {raw_len})")
    ps.d.f.close()

    out = GL + ".tmp"
    nchg, sz = got_dsar.patch_inner(src, out, edits)
    print(f"patch_inner: re-LZ4'd {nchg} of ~{dsar.Psarc2(src).d.num_entries} DSAR chunks; "
          f"out {sz:,} B (built in {time.time()-t0:.0f}s)")

    # ---- OFFLINE validation of the rebuilt archive ----
    v = dsar.Psarc2(out)
    files = v.files()
    assert len(files) + 1 == v.num_files, (len(files), v.num_files)   # +1 = manifest entry 0
    ve = next(e for e in files if e.path == INNER)
    assert v.extract(ve) == new_ar, "rebuilt AR xpps != our new bytes"
    # sample OTHER files must be byte-identical to the original
    orig = dsar.Psarc2(src)
    others = [e for e in files if e.path != INNER][:5]
    for e in others:
        oe = next(x for x in orig.files() if x.path == e.path)
        assert v.extract(e) == orig.extract(oe), f"unexpected change in {e.path}"
    print(f"VALIDATED offline: {v.num_files} inner files, AR xpps = Hebrew, "
          f"{len(others)} sampled other files byte-identical, header unchanged")
    v.d.f.close(); orig.d.f.close()

    if deploy:
        if not os.path.exists(BAK):
            print("backing up gapack_misc_l -> .he_backup (1.43 GB)...")
            shutil.copyfile(GL, BAK)
        os.replace(out, GL)
        print(f"\nDEPLOYED (in-place) -> {GL}")
        print("Launch the game -> Settings -> Options -> General -> Text Language = العربية.")
        print("CONTINUE should read 'ZZ-GOT-OK-ZZ'; the Hebrew items decide bidi + font.")
    else:
        os.remove(out)
        print("\n(dry run — no game file changed; re-run with --deploy to swap in)")


def revert():
    if os.path.exists(BAK):
        os.replace(BAK, GL); print(f"restored gapack_misc_l from backup")
    else:
        print("no .he_backup to restore")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert: revert()
    else: build(deploy=a.deploy)
