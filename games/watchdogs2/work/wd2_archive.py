"""
WD2 FAT5 archive helpers: locate / extract / redirect a (stored) localization
file across the load-ordered archives (common < patch < patch2; higher wins).

The localization .loc/.rml entries are stored (compression scheme 0). For v11 a
stored entry must carry UncompressedSize==0 (the engine reads CompressedSize raw).

usage:
  python wd2_archive.py extract "languages\\main_arabic.loc" out.loc
  python wd2_archive.py deploy  "languages\\main_arabic.loc" new.loc      # redirect all 3
  python wd2_archive.py revert  "languages\\main_arabic.loc"              # restore from backup
"""
import struct, os, sys, shutil
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = r"F:\Games\WATCH_DOGS2\data_win64"
BACKUP = r"F:\WD2_lang_backup"
ARCHIVES = ["common", "patch", "patch2"]   # load order low->high
M64 = 0xFFFFFFFFFFFFFFFF


def fnv1a(s):
    h = 0xCBF29CE484222325
    for c in s:
        h = (h * 0x100000001B3) & M64
        h ^= ord(c)
    return h


def name_hash(path):
    h = fnv1a(path.lower())
    h &= 0x1FFFFFFFFFFFFFFF
    h |= 0xA000000000000000
    return h


def find_entry(fat_path, want_hash):
    """return (fatpos, comp, off, unc, scheme) for want_hash, or None."""
    fat = open(fat_path, "rb").read()
    cnt = struct.unpack_from("<I", fat, 24)[0]
    for i in range(cnt):
        p = 28 + i * 20
        a = struct.unpack_from("<Q", fat, p)[0]
        if a == want_hash:
            b, c, d = struct.unpack_from("<III", fat, p + 8)
            comp = b & 0x3FFFFFFF
            off = (c << 2) | ((b >> 30) & 3)
            unc = (d >> 2) & 0x3FFFFFFF
            return (p, comp, off, unc, d & 3)
    return None


def extract(rel_path, out_path):
    h = name_hash(rel_path)
    for name in reversed(ARCHIVES):            # highest-priority first
        fat = os.path.join(DATA, name + ".fat")
        e = find_entry(fat, h)
        if e:
            _, comp, off, unc, sch = e
            with open(os.path.join(DATA, name + ".dat"), "rb") as f:
                f.seek(off); data = f.read(comp)
            open(out_path, "wb").write(data)
            print(f"extracted from {name}: {comp} bytes (off={off} unc={unc} sch={sch}) -> {out_path}")
            return
    print("NOT FOUND in any archive:", rel_path)


def deploy(rel_path, new_loc_path):
    """append new file to each archive's .dat and redirect its entry (stored, unc=0).
    Backs up each .fat once + records dat origsize for revert."""
    h = name_hash(rel_path)
    payload = open(new_loc_path, "rb").read()
    L = len(payload)
    os.makedirs(BACKUP, exist_ok=True)
    tag = rel_path.replace("\\", "_").replace("/", "_")
    for name in ARCHIVES:
        fatp = os.path.join(DATA, name + ".fat")
        datp = os.path.join(DATA, name + ".dat")
        e = find_entry(fatp, h)
        if not e:
            print(f"{name}: entry absent, skip"); continue
        fatpos = e[0]
        fbk = os.path.join(BACKUP, f"{name}.fat.{tag}.bak")
        szf = os.path.join(BACKUP, f"{name}.dat.{tag}.origsize")
        if not os.path.exists(fbk):
            shutil.copy(fatp, fbk)
            open(szf, "w").write(str(os.path.getsize(datp)))
        with open(datp, "r+b") as f:
            f.seek(0, 2); pos = f.tell(); pad = (16 - (pos % 16)) % 16
            if pad: f.write(b"\x00" * pad); pos += pad
            newoff = pos; f.write(payload)
        fat = bytearray(open(fatp, "rb").read())
        a = struct.unpack_from("<Q", fat, fatpos)[0]
        nb = (L & 0x3FFFFFFF) | ((newoff & 3) << 30)
        nc = newoff >> 2
        nd = 0                                  # unc=0, scheme=None (v11 stored)
        struct.pack_into("<III", fat, fatpos + 8, nb, nc, nd)
        open(fatp, "wb").write(fat)
        print(f"{name}: redirected -> off={newoff} comp={L} (backup {os.path.basename(fbk)})")
    print("DONE deploy")


def revert(rel_path):
    tag = rel_path.replace("\\", "_").replace("/", "_")
    for name in ARCHIVES:
        fbk = os.path.join(BACKUP, f"{name}.fat.{tag}.bak")
        szf = os.path.join(BACKUP, f"{name}.dat.{tag}.origsize")
        if not (os.path.exists(fbk) and os.path.exists(szf)):
            print(f"{name}: no backup, skip"); continue
        shutil.copy(fbk, os.path.join(DATA, name + ".fat"))
        with open(os.path.join(DATA, name + ".dat"), "r+b") as f:
            f.truncate(int(open(szf).read().strip()))
        print(f"{name}: reverted")
    print("DONE revert")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "extract":
        extract(sys.argv[2], sys.argv[3])
    elif cmd == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif cmd == "revert":
        revert(sys.argv[2])
    else:
        print(__doc__)
