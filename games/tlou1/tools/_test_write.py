import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from psarc import Psarc
import psarc_write

M = r"D:\Games\The Last of Us - Part I\build\pc\main"
TMP = os.environ.get("TEMP", ".")

def content_map(path):
    p = Psarc(path)
    m = {e.path: hashlib.md5(p.extract(e)).hexdigest() for e in p.files()}
    p.f.close()
    return m

def identity(name):
    src = os.path.join(M, name)
    out = os.path.join(TMP, "id_" + name)
    print(f"\n[identity] {name}")
    orig = content_map(src)
    psarc_write.repack(src, {}, out, progress=False)
    back = content_map(out)
    same = orig == back
    print(f"  entries {len(orig)} vs {len(back)}  content-identical={same}")
    if not same:
        diff = [k for k in orig if orig.get(k) != back.get(k)][:5]
        print("  first diffs:", diff)
    os.remove(out)
    return same

def replace_test(name, target):
    src = os.path.join(M, name)
    out = os.path.join(TMP, "rep_" + name)
    print(f"\n[replace] {name}  target={target}")
    p = Psarc(src)
    newbytes = b"HELLO-TLOU-REPACK\x00" + os.urandom(50000) + b"\x00END"
    psarc_write.repack(src, {target: newbytes}, out)
    p2 = Psarc(out)
    got = p2.extract(p2.by_path[target])
    ok_new = got == newbytes
    # every OTHER file must be byte-identical
    orig = {e.path: hashlib.md5(p.extract(e)).hexdigest() for e in p.files() if e.path != target}
    back = {e.path: hashlib.md5(p2.extract(e)).hexdigest() for e in p2.files() if e.path != target}
    ok_rest = orig == back
    print(f"  replaced-ok={ok_new}  others-identical={ok_rest}")
    p.f.close(); p2.f.close()
    os.remove(out)
    return ok_new and ok_rest

if __name__ == "__main__":
    r = []
    r.append(identity("steam.psarc"))
    # pick a small target in steam.psarc
    ps = Psarc(os.path.join(M, "steam.psarc"))
    tgt = ps.files()[0].path
    r.append(replace_test("steam.psarc", tgt))
    r.append(identity("bin.psarc"))   # 4821 entries, multi-block: real stress test
    print("\nALL PASS" if all(r) else "\nSOME FAILED", r)
