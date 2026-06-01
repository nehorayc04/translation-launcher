"""Extract a .stage file from inside the .modular and inspect its layout."""
import zipfile, os, io

modular = r"C:\Users\Nehoray_Cohen\Projects\Game translator\Game Lab\Marvel's Spider-Man 2\Mods Library\Spider-Gore.modular"
stage_name = "modules/00__BLOOD/00_Realistic_Small.stage"

with zipfile.ZipFile(modular) as outer:
    stage_bytes = outer.read(stage_name)

print(f"[*] inner .stage size: {len(stage_bytes)}")
print(f"[*] first 16 bytes: {stage_bytes[:16].hex(' ')}")

# Try as ZIP
try:
    z = zipfile.ZipFile(io.BytesIO(stage_bytes))
    print("[+] it's a zip!")
    for info in z.infolist():
        print(f"  {info.file_size:>10}  {info.filename}")
    # Print any small manifest-like files
    for n in z.namelist():
        ln = n.lower()
        if ln.endswith((".json","info","spec","modular.json")) and z.getinfo(n).file_size < 4096:
            print(f"\n=== {n} ===")
            print(z.read(n).decode("utf-8", "replace"))
except zipfile.BadZipFile as e:
    print(f"[!] not a zip: {e}")
    # show more bytes
    print(stage_bytes[:200].hex(' '))
