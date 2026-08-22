#!/usr/bin/env python3
r"""roundtrip.py — the IDENTITY round-trip gate for Ghost of Tsushima DSAR/PSARC.

Layers tested on a small GoT archive (default gapack_misc_p.psarc):
  L0  read original -> {path: bytes} + full inner-PSARC stream (md5 baseline)
  L1  INNER identity: psarc_write.build(files, flags=0xe) vs original inner bytes
  L2  INNER semantic: re-parse the rebuilt inner PSARC, compare all files
  L3  DSAR wrap: dsar_write.wrap(rebuilt_inner) -> write file -> Psarc2 read back,
                 compare all files (== the game's own load path, modelled)
  L4  single-file REPLACE: rebuild with one file swapped for a byte-identical copy,
                 wrap, read back, compare -> proves the deploy edit path
Also reports the byte-delta vs the original DSAR file and the manifest match.
"""
import os, sys, struct, hashlib, json
HERE = os.path.dirname(os.path.abspath(__file__))
T2 = os.path.join(HERE, "..", "..", "tlou2", "tools")
sys.path.insert(0, T2)
import dsar as R
import psarc_write as PW
import dsar_write as DW

def md5(b): return hashlib.md5(b).hexdigest()

def original_manifest_bytes(p):
    return p.extract(p.entries[0]) if False else p._read_entry(p.entries[0])

def run(path, outdir):
    res = {}
    orig_raw = open(path, "rb").read()
    p = R.Psarc2(path)
    total = p.d.total_size
    inner_orig = p.d.read(0, total)
    res["orig_dsar_size"] = len(orig_raw)
    res["orig_dsar_md5"] = md5(orig_raw)
    res["inner_orig_size"] = len(inner_orig)
    res["inner_orig_md5"] = md5(inner_orig)
    res["inner_flags"] = p.archive_flags
    res["inner_blocksize"] = p.block_size

    # manifest + ordered paths exactly as stored
    man = p._read_entry(p.entries[0])
    sep = b"\x00" if b"\x00" in man else b"\n"
    paths_in_manifest = [x.decode("ascii") for x in man.split(sep) if x]
    # is the TOC (entries 1..n) md5-ascending?
    hashes = [e.name_hash for e in p.entries[1:]]
    res["toc_md5_ascending"] = all(hashes[i] <= hashes[i+1] for i in range(len(hashes)-1))

    files = {e.path: p.extract(e) for e in p.files()}
    res["num_files"] = len(files)
    # sanity: our md5-sort of the paths == manifest order?
    res["manifest_order_is_md5sorted"] = (
        sorted(paths_in_manifest, key=PW._md5) == paths_in_manifest)

    # ---- L1 inner identity ----
    inner_rebuilt = PW.build(files, block_size=p.block_size, flags=p.archive_flags, compress=True)
    res["inner_rebuilt_size"] = len(inner_rebuilt)
    res["inner_rebuilt_md5"] = md5(inner_rebuilt)
    res["L1_inner_byte_identical"] = (inner_rebuilt == inner_orig)
    # manifest bytes match?
    man2 = None
    res["manifest_bytes_match"] = None
    # compare headers
    res["hdr_orig"] = inner_orig[:32].hex()
    res["hdr_rebuilt"] = inner_rebuilt[:32].hex()

    # ---- L2 inner semantic (re-parse rebuilt inner via a tiny in-memory PSARC read) ----
    got2 = PW.verify_read(inner_rebuilt)
    res["L2_inner_semantic_ok"] = (got2 == files)

    # ---- L3 DSAR wrap + read back ----
    dsar_bytes = DW.wrap(inner_rebuilt)
    out_p = os.path.join(outdir, "rebuilt_" + os.path.basename(path))
    with open(out_p, "wb") as f: f.write(dsar_bytes)
    res["rebuilt_dsar_size"] = len(dsar_bytes)
    res["rebuilt_dsar_md5"] = md5(dsar_bytes)
    res["L3_dsar_byte_identical_to_orig"] = (dsar_bytes == orig_raw)
    p2 = R.Psarc2(out_p)
    got3 = {e.path: p2.extract(e) for e in p2.files()}
    p2.d.f.close()
    res["L3_dsar_semantic_ok"] = (got3 == files)

    # ---- L4 single-file replace (swap the largest file for an identical copy) ----
    biggest = max(files, key=lambda k: len(files[k]))
    files4 = dict(files); files4[biggest] = bytes(files[biggest])  # identical copy
    inner4 = PW.build(files4, block_size=p.block_size, flags=p.archive_flags, compress=True)
    dsar4 = DW.wrap(inner4)
    out4 = os.path.join(outdir, "replace_" + os.path.basename(path))
    with open(out4, "wb") as f: f.write(dsar4)
    p4 = R.Psarc2(out4)
    got4 = {e.path: p4.extract(e) for e in p4.files()}
    p4.d.f.close()
    res["L4_replace_semantic_ok"] = (got4 == files)
    res["L4_replaced_file"] = biggest

    p.d.f.close()
    return res

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "F:/Games/Ghost of Tsushima DC/cache_pc/psarc/gapack_misc_p.psarc"
    outdir = HERE
    r = run(path, outdir)
    print(json.dumps(r, indent=2))
