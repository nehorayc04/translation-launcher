#!/usr/bin/env python3
r"""Engine-level faithfulness test for got_dsar: identity-rebuild the SMALL gapack_misc_p
(unchanged content) and replace the real file, so a boot proves the GoT engine accepts a
got_dsar-produced DSAR (isolated from the duplicate-path question). --restore puts the
original back. Game must be CLOSED."""
import os, sys, shutil, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__)); REPO=os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
GAME=os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
TGT=os.path.join(GAME,"cache_pc","psarc","gapack_misc_p.psarc"); BAK=TGT+".he_backup"
def L(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
dsar=L("dsar",os.path.join(REPO,"games","tlou2","tools","dsar.py")); gd=L("got_dsar",os.path.join(HERE,"got_dsar.py"))
if len(sys.argv)>1 and sys.argv[1]=="--restore":
    if os.path.exists(BAK): shutil.move(BAK,TGT); print("restored gapack_misc_p from backup")
    else: print("no backup to restore")
    sys.exit()
if not os.path.exists(BAK): shutil.copyfile(TGT,BAK); print(f"backed up -> {BAK}")
ps=dsar.Psarc2(TGT); inner=ps.d.read(0,ps.d.total_size); ps.d.f.close()
bnds=gd.chunk_boundaries(TGT); rebuilt=gd.wrap(inner,bnds)
# validate re-read equal before writing
open(TGT+".tmp","wb").write(rebuilt); p2=dsar.Psarc2(TGT+".tmp")
ok=all(p2.extract(e)==dsar.Psarc2(BAK).extract(next(x for x in dsar.Psarc2(BAK).files() if x.path==e.path)) for e in p2.files())
p2.d.f.close()
assert ok,"re-read mismatch"
shutil.move(TGT+".tmp",TGT)
print(f"identity-rebuilt gapack_misc_p in place ({len(rebuilt):,} B, orig {os.path.getsize(BAK):,} B). Boot the game.")
print("If it BOOTS -> got_dsar is engine-faithful. Restore: python dsar_engine_test.py --restore")
