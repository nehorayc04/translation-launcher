#!/usr/bin/env python3
"""
ROOT-FIX deploy for AC Black Flag Resynced: re-pack DataPC_boot_patch_01.forge so a
modified resource (the Arabic-UI LocalizationPackage, record 1244) becomes a 100%
NATURAL resource — re-compressed with NO pad (buffer == object, CFD0@10 == @4+51, native
block count) — while keeping the forge FULLY CONTIGUOUS by shifting every later record's
data earlier to close the freed gap and rewriting the TOC.

Why: every in-place attempt failed. A shrunk record (gap) black-screens at boot (the
loader streams the patch forge contiguously); a padded record hangs/black-screens at
menu load (the game reads CFD0@10 bytes and chokes on any trailing pad — zeros or not).
The ONLY structurally-clean option is a native resource + no gap, i.e. re-pack the tail.

Layout (verified): [header @0 .. desc@0x41a][resource data blobs ...][TOC @tocOff][footer].
Records 0..N are 24-byte <QIIII> (offset,ts,flags,size,nameHash) at tocOff. The TOC +
footer sit AFTER all resource data, so shrinking record 1244 by `delta` shifts records
1245.. AND the TOC + footer earlier by `delta`; only the TOC's offset/size fields and the
desc's tocOffset need re-derivation. Record-data blobs carry no internal file offsets.

  ACBF_PATCH=<...DataPC_boot_patch_01.forge> python repack_patch.py --identity   # natural Arabic (test)
  ...                                                              --hebrew      # Hebrew (real)
  ...                                                              --revert      # restore pristine 1244 + original layout

Builds a TEMP file, VERIFIES it (contiguous + 1244 decodes + spot-checks), then os.replace.
"""
import importlib.util
import os
import sys
import struct
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")


def _load(n):
    p = os.path.join(TOOLS, n + ".py")
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
CFD = _load("acbf_cfd"); AF = _load("acbf_forge"); LP = _load("acbf_locpkg")

PATCH = os.environ.get("ACBF_PATCH",
                       r"C:\Games\Assassin's Creed Black Flag Resynced\DataPC_boot_patch_01.forge")
UI_IDX = int(os.environ.get("ACBF_UI_IDX", "1244"))
PRISTINE = os.path.join(HERE, f"_menu_proof_{os.path.splitext(os.path.basename(PATCH))[0]}_{UI_IDX}.bin")
DESC_OFF = AF.DESC_OFF  # 0x41a

# stringID -> Hebrew (same as build_menu_proof)
PATCH_STRINGS = {
    12442499593651585653: "המשך",
    13763123497367102776: "יציאה",
    13763533535708965377: "טעינה",
    12435709294004715387: "עלילה",
    12432099737885992341: "שמירה",
    12412719127741956672: "כללי ZZ-HEB-OK",
}


def _natural_1244(pristine_blob, dec_oodle, enc_oodle, patch=None):
    """Re-encode record 1244 NATURALLY (no pad): CFD0 (descriptor) + CFD1 (loc object),
    optionally patching strings. DECODE with dec_oodle (must read the game's blocks),
    ENCODE with enc_oodle (its stream must be decodable by the game's Oodle). Returns
    the new blob (<= original size)."""
    cfds, _ = CFD.decode_resource(pristine_blob, dec_oodle)
    assert len(cfds) == 2
    cfd0_data, cinfo0 = cfds[0]
    cfd1_object, cinfo1 = bytes(cfds[1][0]), cfds[1][1]
    if patch:
        m = cfd1_object.find(LP.MARKER)
        old_num = struct.unpack_from("<i", cfd1_object, m + 4)[0]
        strs = {}
        for pk in LP.find_packages(cfd1_object):
            strs.update(pk["strings"])
        id_text = [(sid, patch.get(sid, s)) for sid, s in strs.items()]
        new_payload = LP.build_payload(id_text)
        obj = bytearray(cfd1_object[:m + 4] + struct.pack("<i", len(new_payload)) + new_payload + cfd1_object[m + 8 + old_num:])
        struct.pack_into("<I", obj, 4, (len(obj) - 51) & 0xFFFFFFFF)   # @4 = object size (invariant)
        cfd1_object = bytes(obj)
    cfd1_bytes = CFD.build_cfd(cfd1_object, cinfo1, enc_oodle, level=7)   # natural, buffer==object
    cfd0_ba = bytearray(cfd0_data); struct.pack_into("<I", cfd0_ba, 10, len(cfd1_object) & 0xFFFFFFFF)
    cfd0_bytes = CFD.build_cfd(bytes(cfd0_ba), cinfo0, enc_oodle)
    return cfd0_bytes + cfd1_bytes


def _copy(src, dst, start, end, chunk=8 << 20):
    src.seek(start)
    left = end - start
    while left > 0:
        b = src.read(min(chunk, left))
        if not b:
            break
        dst.write(b); left -= len(b)


def repack(new_blob):
    info = AF.parse(PATCH)
    recs = info["recs"]; toc = info["toc"]; count = info["count"]
    r = recs[UI_IDX]
    off = r["offset"]; old_size = r["size"]; new_size = len(new_blob)
    if new_size > old_size:
        print(f"new blob {new_size} > old {old_size} — cannot repack-shrink"); return 1
    delta = old_size - new_size
    file_size = os.path.getsize(PATCH)
    tail_start = off + old_size            # start of record UI_IDX+1 data
    old_toc_end = toc + count * AF.REC
    new_toc_off = toc - delta

    # new TOC (records after UI_IDX shift earlier by delta; UI_IDX size updated)
    new_toc = bytearray()
    for i, rr in enumerate(recs):
        o2 = rr["offset"]; sz = rr["size"]
        if i == UI_IDX:
            sz = new_size
        elif i > UI_IDX:
            o2 -= delta
        new_toc += struct.pack("<QIIII", o2, rr["ts"], rr["flags"], sz, rr["hash"])

    tmp = PATCH + ".repack.tmp"
    print(f"repack: rec {UI_IDX} {old_size}->{new_size} (delta {delta}); "
          f"toc 0x{toc:x}->0x{new_toc_off:x}; file {file_size}->{file_size-delta}")
    with open(PATCH, "rb") as src, open(tmp, "wb") as dst:
        _copy(src, dst, 0, off)             # header + records < UI_IDX data
        dst.write(new_blob)                 # new UI_IDX
        _copy(src, dst, tail_start, toc)    # records > UI_IDX data (shift earlier by delta)
        assert dst.tell() == new_toc_off, f"{dst.tell()} != {new_toc_off}"
        dst.write(new_toc)                  # rewritten TOC
        _copy(src, dst, old_toc_end, file_size)   # footer
    # patch desc tocOffset
    with open(tmp, "r+b") as f:
        f.seek(DESC_OFF + 4); f.write(struct.pack("<Q", new_toc_off))

    # VERIFY the temp file before replacing
    if not _verify(tmp, new_blob):
        print("  !! verify FAILED — leaving original untouched, temp kept at .repack.tmp"); return 1
    os.replace(tmp, PATCH)
    print(f"  REPACKED + replaced. new file size {os.path.getsize(PATCH):,}")
    return 0


def _verify(path, expect_1244_blob):
    o = CFD._oodle()
    saved = os.environ.get("ACBF_FORGE")
    try:
        info = AF.parse(path)
        g, t = AF.invariant(info["recs"])
        if g != t:
            print(f"  verify: invariant {g}/{t} — GAP!"); return False
        r = info["recs"][UI_IDX]
        with open(path, "rb") as f:
            f.seek(r["offset"]); blob = f.read(r["size"])
        if blob != expect_1244_blob:
            print(f"  verify: rec {UI_IDX} bytes != expected"); return False
        strs = {}
        for pk in LP.find_packages(CFD.decode_all(blob, o)):
            strs.update(pk["strings"])
        # spot-check three later records still decode
        ok_spot = 0
        for j in (UI_IDX + 1, UI_IDX + 5, min(len(info["recs"]) - 1, UI_IDX + 50)):
            rr = info["recs"][j]
            if rr["hash"] != 0x6e3c9c6f:
                ok_spot += 1; continue
            with open(path, "rb") as f:
                f.seek(rr["offset"]); b = f.read(rr["size"])
            try:
                CFD.decode_all(b, o); ok_spot += 1
            except Exception as e:
                print(f"  verify: later rec {j} decode failed: {e}"); return False
        print(f"  verify OK: contiguous {g}/{t}, rec {UI_IDX} {len(strs)} strings, spot {ok_spot}/3")
        return True
    finally:
        if saved is not None:
            os.environ["ACBF_FORGE"] = saved


FULL_BACKUP = PATCH + ".he_backup_full"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--identity", action="store_true")
    ap.add_argument("--hebrew", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()

    if a.revert:
        if not os.path.isfile(FULL_BACKUP):
            print(f"no full backup at {FULL_BACKUP}"); return 1
        import shutil
        print(f"restoring full backup ({os.path.getsize(FULL_BACKUP):,} B) ...")
        shutil.copyfile(FULL_BACKUP, PATCH)
        print("  restored original patch forge.")
        return 0

    if not os.path.isfile(PRISTINE):
        print(f"pristine 1244 blob missing: {PRISTINE}"); return 1
    # Safety net: full backup of the (original-layout) patch forge before the FIRST repack.
    if not os.path.isfile(FULL_BACKUP):
        import shutil
        print(f"creating full backup ({os.path.getsize(PATCH):,} B) -> {FULL_BACKUP} ...")
        shutil.copyfile(PATCH, FULL_BACKUP)
        print("  backup done.")

    dec_oodle = CFD._oodle()                       # decodes the game's own blocks (needs 2.9.x)
    enc_dll = os.environ.get("ACBF_ENC_DLL")
    if enc_dll:
        import sys as _s
        _s.path.insert(0, os.path.join(TOOLS, "..", "..", "acshadows", "tools"))
        from acs_oodle import Oodle
        enc_oodle = Oodle(enc_dll)
        print(f"ENCODE Oodle: {enc_oodle.path}")
    else:
        enc_oodle = dec_oodle
    pristine = open(PRISTINE, "rb").read()
    patch = PATCH_STRINGS if a.hebrew else None
    new_blob = _natural_1244(pristine, dec_oodle, enc_oodle, patch=patch)
    print(f"natural 1244: {len(new_blob):,} B (pristine {len(pristine):,} B)"
          f"{' [HEBREW]' if a.hebrew else ' [identity]'}")
    return repack(new_blob)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
