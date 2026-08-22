"""Read-only DRM/marker string scan of Anno1800.exe (streamed, low memory)."""
import sys, re

EXE = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Program Files (x86)\Steam\steamapps\common\Anno 1800\Bin\Win64\Anno1800.exe"

# markers to hunt (case-insensitive, ascii + utf-16le)
NEEDLES = [
    b"denuvo", b"Denuvo", b"DENUVO",
    b"VMProtect", b"vmprotect", b".vmp", b"vmp0", b"vmp1",
    b"Themida", b"themida", b"WinLicense",
    b"SecuROM", b"Arxan", b"irdeto", b"Irdeto",
    b"anti-tamper", b"AntiTamper", b"antitamper",
    b"Steamworks", b"steam_api", b"upc_r2", b"uplay", b"Ubisoft",
    b"CodeVirtualizer", b"Enigma",
]

CHUNK = 8 * 1024 * 1024
counts = {n: 0 for n in NEEDLES}
# also count utf-16le forms for the DRM names
u16 = {}
for n in (b"denuvo", b"VMProtect", b"Themida", b"Ubisoft"):
    u16[n] = n.decode("latin-1").encode("utf-16-le")
u16_counts = {k: 0 for k in u16}

overlap = 64
prev = b""
total = 0
with open(EXE, "rb") as f:
    while True:
        buf = f.read(CHUNK)
        if not buf:
            break
        window = prev + buf
        low = window.lower()
        for n in NEEDLES:
            counts[n] += low.count(n.lower())
        for k, v in u16.items():
            u16_counts[k] += window.count(v)
        prev = buf[-overlap:]
        total += len(buf)

print(f"scanned {total:,} bytes")
print("== ASCII marker counts (nonzero) ==")
# collapse case variants
merged = {}
for n, c in counts.items():
    key = n.lower()
    merged[key] = merged.get(key, 0) + c
for k in sorted(merged):
    if merged[k]:
        print(f"  {k.decode():<16} {merged[k]}")
print("== UTF-16LE marker counts (nonzero) ==")
for k, c in u16_counts.items():
    if c:
        print(f"  {k.decode():<16} {c}")

# section-name-style tokens present anywhere as ascii
print("== section-name tokens in file ==")
for tok in (b".vmp0", b".vmp1", b".themida", b".enigma", b".text1", b".xtls",
            b".sxdata", b".xtext", b".link"):
    print(f"  {tok.decode():<10} {open(EXE,'rb').read(0) or ''}", end="")
    # count via mmap-free re-scan of header region only (first 4KB has the table)
    hdr = open(EXE, "rb").read(0x400)
    print("hdr_hits=", hdr.count(tok))
