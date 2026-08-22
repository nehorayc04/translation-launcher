"""MSMR — DEPLOY GATE probe #6: engine-side evidence.
  * the ArchiveFileSystem / 'Archive TOC' RTTI-ish field-name blob (names every
    toc section the engine actually consumes)
  * the DSAR magic compare site in code (proves the raw-archive branch)
  * contexts for -archive / -assets / -path / -archivetrace (any alternate
    asset-dir switch = a cleaner deploy?)
READ-ONLY.
"""
import os, re, sys
GAME = r"D:\Games\Spider-man Remastered"
EXE  = os.path.join(GAME, "Spider-Man.exe")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
data = open(EXE, "rb").read()

def show(off, back=120, fwd=420):
    a, b = max(0, off-back), min(len(data), off+fwd)
    s = re.sub(rb"[^\x20-\x7e]", b".", data[a:b]).decode("ascii")
    return s

print("=== 'Archive TOC' / ArchiveFileSystem field-name blob ===")
for m in re.finditer(rb"Archive TOC", data):
    print(f"@0x{m.start():08X}\n  {show(m.start(), 60, 900)}\n")

print("=== every 'Archive TOC ...' style section label in the exe ===")
for pat in [rb"Archive TOC[ -~]{0,40}", rb"ArchiveFileSystem", rb"m_[A-Za-z]{3,30}"]:
    hits = sorted({h for h in re.findall(pat, data)})
    if pat.startswith(rb"m_"):
        hits = [h for h in hits if any(k in h.lower() for k in
                (b"asset", b"file", b"size", b"archive", b"span", b"offset", b"batch", b"handle", b"toc"))]
    print(f"\n  pattern {pat!r}: {len(hits)} unique")
    for h in hits[:60]:
        print("   ", h.decode("ascii", "replace"))

print("\n=== DSAR magic compare in CODE (raw-vs-compressed branch) ===")
for m in re.finditer(rb"DSAR", data):
    print(f"  @0x{m.start():08X} bytes={data[m.start()-16:m.start()+16].hex()}")
    print(f"      {show(m.start(), 48, 48)}")

print("\n=== switch contexts: could we point the game at another asset dir? ===")
for sw in (b"-archivetrace", b"-archive", b"-assets", b"-asset", b"-path", b"-localized", b"-lang"):
    for m in list(re.finditer(re.escape(sw) + rb"[\x00\x20]", data))[:3]:
        print(f"  {sw.decode():14} @0x{m.start():08X}: {show(m.start(), 150, 250)}")
    print()

print("=== any string that looks like an alternate asset-root / mod dir ===")
for pat in [rb"[ -~]{0,30}asset_archive[ -~]{0,40}", rb"[ -~]{0,20}\bmod(dir|path|s_dir)[ -~]{0,20}"]:
    for h in sorted({x for x in re.findall(pat, data)}):
        print("   ", h.decode("ascii", "replace"))
