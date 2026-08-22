#!/usr/bin/env python3
r"""Categorize the residual inner byte-delta: TOC/manifest bookkeeping vs file DATA."""
import os, sys, struct, hashlib, json
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(HERE,"..","..","tlou2","tools"))
import dsar as R, psarc_write as PW

def analyze(path):
    p=R.Psarc2(path)
    inner_orig=p.d.read(0,p.d.total_size)
    files={e.path:p.extract(e) for e in p.files()}
    inner_stored=PW.build(files,block_size=p.block_size,flags=p.archive_flags,compress=False)
    # TOC size (both share header layout)
    tocSize=p.total_toc_size
    # region split
    toc_o,toc_s = inner_orig[:tocSize], inner_stored[:tocSize]
    dat_o,dat_s = inner_orig[tocSize:], inner_stored[tocSize:]
    diffs_toc = sum(1 for a,b in zip(toc_o,toc_s) if a!=b)
    diffs_dat = sum(1 for a,b in zip(dat_o,dat_s) if a!=b)
    print(f"tocSize=0x{tocSize:x} ({tocSize})")
    print(f"TOC-region differing bytes : {diffs_toc} / {tocSize}")
    print(f"DATA-region differing bytes: {diffs_dat} / {len(dat_o)}  (len match={len(dat_o)==len(dat_s)})")
    # Does the SET of file-data blocks match regardless of order? Compare md5 of each
    # file's stored bytes region is implicit via semantic (already proven). Here: is the
    # data region a permutation? Compare sorted md5 of per-file data.
    # Simpler: manifest bytes (entry0 data) — compare content as a set of paths.
    mo=p._read_entry(p.entries[0]); sep=b"\x00" if b"\x00" in mo else b"\n"
    paths_o=[x for x in mo.split(sep) if x]
    paths_s=sorted(paths_o,key=lambda x:PW._md5(x.decode('ascii')))
    print(f"manifest order == md5-sort? {paths_o==paths_s}")
    print(f"same path SET? {set(paths_o)==set(paths_s)}  count={len(paths_o)}")
    p.d.f.close()

def misc_l_header(path):
    print(f"\n== target {os.path.basename(path)}")
    p=R.Psarc2(path)
    print(f"  DSAR entries={p.d.num_entries} innerSize={p.d.total_size:,} | inner numFiles={p.num_files} flags=0x{p.archive_flags:x} blockSize=0x{p.block_size:x}")
    ar=p.find("lang_arabic_text"); en=p.find("lang_english_text")
    for e in ar+en:
        print(f"  {e.orig_size:>12,}  {e.path}")
    p.d.f.close()

if __name__=="__main__":
    analyze(sys.argv[1] if len(sys.argv)>1 else "F:/Games/Ghost of Tsushima DC/cache_pc/psarc/gapack_misc_p.psarc")
    misc_l_header("F:/Games/Ghost of Tsushima DC/cache_pc/psarc/gapack_misc_l.psarc")
