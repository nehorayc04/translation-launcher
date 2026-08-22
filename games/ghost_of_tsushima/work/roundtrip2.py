#!/usr/bin/env python3
r"""roundtrip2.py — the CORRECT deploy path: STORED inner PSARC (compress=False),
matching how GoT ships (inner stored, DSAR/LZ4 outer compresses). Isolates the
exact source of any byte-delta (manifest order vs block bytes)."""
import os, sys, struct, hashlib, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R, psarc_write as PW, dsar_write as DW
def md5(b): return hashlib.md5(b).hexdigest()

def run(path):
    r = {}
    orig = open(path, "rb").read()
    p = R.Psarc2(path)
    inner_orig = p.d.read(0, p.d.total_size)
    files = {e.path: p.extract(e) for e in p.files()}

    # original manifest, exact
    man = p._read_entry(p.entries[0]); sep=b"\x00" if b"\x00" in man else b"\n"
    man_paths = [x for x in man.split(sep) if x]

    # STORED inner rebuild (deploy-correct)
    inner_stored = PW.build(files, block_size=p.block_size, flags=p.archive_flags, compress=False)
    r["inner_orig_size"]=len(inner_orig); r["inner_stored_size"]=len(inner_stored)
    r["inner_stored_byte_identical"]= (inner_stored==inner_orig)

    # Where does it differ? compare the manifest entry bytes first.
    man_rebuilt = PW.verify_read(inner_stored)  # sanity content
    # Rebuild manifest in ORIGINAL order to test the "manifest order" hypothesis:
    #   feed build() a dict whose md5-sort equals original manifest order is not
    #   possible; instead directly diff first N bytes.
    n=min(len(inner_orig),len(inner_stored))
    firstdiff=next((i for i in range(n) if inner_orig[i]!=inner_stored[i]), n)
    r["first_byte_diff_at"]=firstdiff
    r["inner_orig_hdr"]=inner_orig[:32].hex(); r["inner_stored_hdr"]=inner_stored[:32].hex()
    # manifest content order match?
    r["manifest_order_matches_md5sort"]= (man_paths==sorted(man_paths,key=lambda x:PW._md5(x.decode('ascii'))))

    # DSAR wrap of the STORED inner, read back
    dsar=DW.wrap(inner_stored)
    outp=os.path.join(HERE,"stored_"+os.path.basename(path))
    open(outp,"wb").write(dsar)
    p2=R.Psarc2(outp); got={e.path:p2.extract(e) for e in p2.files()}; p2.d.f.close()
    r["stored_dsar_semantic_ok"]=(got==files)
    r["stored_dsar_size"]=len(dsar); r["orig_dsar_size"]=len(orig)

    # PSARC self-describing => files can GROW freely? Rebuild with the largest file
    # doubled and confirm read-back matches (proves no downstream size constraint).
    big=max(files,key=lambda k:len(files[k]))
    fg=dict(files); fg[big]=files[big]*2
    innerg=PW.build(fg,block_size=p.block_size,flags=p.archive_flags,compress=False)
    dsarg=DW.wrap(innerg); outg=os.path.join(HERE,"grow_"+os.path.basename(path))
    open(outg,"wb").write(dsarg)
    pg=R.Psarc2(outg); gg={e.path:pg.extract(e) for e in pg.files()}; pg.d.f.close()
    r["grow_semantic_ok"]=(gg==fg); r["grow_dsar_size"]=len(dsarg)
    p.d.f.close()
    return r

if __name__=="__main__":
    path=sys.argv[1] if len(sys.argv)>1 else "F:/Games/Ghost of Tsushima DC/cache_pc/psarc/gapack_misc_p.psarc"
    print(json.dumps(run(path),indent=2))
