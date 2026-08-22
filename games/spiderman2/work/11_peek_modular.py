"""Peek inside a real SM2 mod to learn the file structure."""
import zipfile, os
p = r"C:\Game Lab\Marvel's Spider-Man 2\Mods Library\Spider-Gore.modular"
print("[*] path exists:", os.path.exists(p), "size:", os.path.getsize(p))
try:
    z = zipfile.ZipFile(p)
    for info in z.infolist():
        print(f"  {info.file_size:>10}  {info.filename}")
    # extract the manifest-like files if present (info.json / spec.json / mod.json)
    names = z.namelist()
    for n in names:
        ln = n.lower()
        if ln.endswith(("info.json","mod.json","spec.json","modular.json","manifest.json")) or ln in ("info","mod","spec"):
            print(f"\n=== {n} ===")
            print(z.read(n).decode("utf-8", "replace")[:2000])
except Exception as e:
    print("zip error:", e)
    with open(p, "rb") as f:
        print("first 16 bytes:", f.read(16).hex())
