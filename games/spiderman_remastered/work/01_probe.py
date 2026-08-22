"""Marvel's Spider-Man Remastered (MSMR) — Phase-1 container probe.

READ-ONLY. Verifies dat1lib reads the MSMR toc (magic 0x77AF12AF, zlib-wrapped
DAT1), lists archives/assets/spans, resolves the localization asset by crc64 of
its path, extracts every variant and classifies each by Unicode script to find
the Arabic slot (= the Hebrew target) and the English source slot.

Engine family: Insomniac "Luna". Same stack already cracked for Spider-Man 2
(VERSION_RCRA 202300) and Ratchet & Clank Rift Apart. MSMR = VERSION_MSMR 202200.
"""
import os, sys, io, struct, inspect, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"D:\Games\Spider-man Remastered"
ARCH = os.path.join(GAME, "asset_archive")
TOC  = os.path.join(ARCH, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman_remastered", "extract", "loc_variants")
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import dat1lib, dat1lib.types.toc, dat1lib.crc64 as crc64

print("[*] toc:", TOC, "exists:", os.path.exists(TOC), "size:", os.path.getsize(TOC))
with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
print("[*] toc class:", type(toc).__name__, "module:", type(toc).__module__)
print("[*] declared version:", getattr(toc, "version", None))

toc.set_archives_dir(ARCH)

archs = toc.get_archives_section()
aids  = toc.get_assets_section()
sizes = toc.get_sizes_section()
try:
    spans = toc.get_spans_section()
    nspans = len(spans.entries)
except Exception as ex:
    spans, nspans = None, f"ERR {ex}"

print(f"[+] archives={len(archs.archives)} assets={len(aids.ids)} sizes={len(sizes.entries)} spans={nspans}")

print("\n=== archives ===")
for i, a in enumerate(archs.archives):
    try:
        nm = bytes(a.filename).split(b"\x00")[0].decode("ascii", "ignore")
    except Exception:
        nm = str(a)
    print(f"  [{i:3}] {nm}")

# ---------------------------------------------------------------- loc hunt
CANDS = [
    "localization/localization_all.localization",
    "localization/localization.localization",
    "localization/localization_all.localisation",
    "localization/loc_all.localization",
    "localization/english.localization",
    "localization/arabic.localization",
    "localization/localization_all",
    "loc/localization_all.localization",
]
print("\n=== resolve localization by crc64(path) ===")
loc_entries, loc_path = None, None
for p in CANDS:
    try:
        ents = [e for e in (toc.get_asset_entries_by_path(p) or []) if e is not None]
        print(f"  {crc64.hash(p):016X}  {p!r} -> {len(ents)} entries")
        if ents and loc_entries is None:
            loc_entries, loc_path = ents, p
    except Exception as ex:
        print(f"  {p!r} -> ERR {ex}")

if not loc_entries:
    print("[!] no localization path resolved — needs a path hunt (step 02)")
    sys.exit(0)

print(f"\n[+] using {loc_path!r} -> {len(loc_entries)} variants")

# ---------------------------------------------------------------- script sniff
def sniff(buf: bytes) -> dict:
    c = {k: 0 for k in ("ascii", "hebrew", "arabic", "cyrillic", "greek",
                        "latin_ext", "hiragana", "katakana", "hangul", "thai", "cjk")}
    i, n = 0, len(buf)
    while i < n:
        b = buf[i]
        if b < 0x80:
            c["ascii"] += 1; i += 1
        elif b < 0xC0:
            i += 1
        elif b < 0xE0 and i + 1 < n:
            cp = ((b & 0x1F) << 6) | (buf[i + 1] & 0x3F)
            if   0x0590 <= cp <= 0x05FF: c["hebrew"] += 1
            elif 0x0600 <= cp <= 0x06FF: c["arabic"] += 1
            elif 0x0400 <= cp <= 0x04FF: c["cyrillic"] += 1
            elif 0x0370 <= cp <= 0x03FF: c["greek"] += 1
            elif 0x0100 <= cp <= 0x024F: c["latin_ext"] += 1
            i += 2
        elif b < 0xF0 and i + 2 < n:
            cp = ((b & 0x0F) << 12) | ((buf[i + 1] & 0x3F) << 6) | (buf[i + 2] & 0x3F)
            if   0x3040 <= cp <= 0x309F: c["hiragana"] += 1
            elif 0x30A0 <= cp <= 0x30FF: c["katakana"] += 1
            elif 0xAC00 <= cp <= 0xD7AF: c["hangul"] += 1
            elif 0x0E00 <= cp <= 0x0E7F: c["thai"] += 1
            elif 0x4E00 <= cp <= 0x9FFF: c["cjk"] += 1
            i += 3
        else:
            i += 4
    return c

try:
    print("[*] extract_asset sig:", inspect.signature(toc.extract_asset))
except Exception:
    pass

# span index for each entry (variant N -> span N*8 convention on RCRA; verify here)
span_of = {}
if spans is not None:
    for si, sp in enumerate(spans.entries):
        try:
            start, cnt = sp.asset_index, sp.count
        except Exception:
            continue
        span_of[si] = (start, cnt)

results = []
for k, e in enumerate(loc_entries):
    try:
        data = toc.extract_asset(e)
    except Exception as ex:
        print(f"  [{k:02d}] extract err: {ex}")
        continue
    if not data:
        print(f"  [{k:02d}] EMPTY")
        continue
    data = bytes(data)
    outp = os.path.join(OUT, f"variant_{k:02d}_idx{e.index}.localization")
    with open(outp, "wb") as fo:
        fo.write(data)
    s = sniff(data if len(data) <= 600000 else data[:600000])
    # which span does this asset index fall in?
    sp = next((si for si, (st, cn) in span_of.items() if st <= e.index < st + cn), None)
    results.append(dict(k=k, index=e.index, span=sp, archive=e.archive,
                        offset=e.offset, size=len(data), magic=data[:4].hex(), scripts=s))
    top = {kk: vv for kk, vv in s.items() if vv > 50 and kk != "ascii"}
    print(f"  [{k:02d}] idx={e.index:<7} span={sp} arch={e.archive:<3} size={len(data):>9} "
          f"magic={data[:4].hex()} {top}")

print("\n=== ranked by ARABIC codepoints (the Hebrew-target slot) ===")
for r in sorted(results, key=lambda r: -r["scripts"]["arabic"])[:8]:
    print(f"  variant_{r['k']:02d} span={r['span']} arabic={r['scripts']['arabic']:>7} "
          f"hebrew={r['scripts']['hebrew']:>5} size={r['size']:>9}")

print("\n=== ranked by ASCII (the English source slot) ===")
for r in sorted(results, key=lambda r: -r["scripts"]["ascii"])[:8]:
    print(f"  variant_{r['k']:02d} span={r['span']} ascii={r['scripts']['ascii']:>9} "
          f"arabic={r['scripts']['arabic']:>6} size={r['size']:>9}")

with open(os.path.join(OUT, "_probe.json"), "w", encoding="utf-8") as fo:
    json.dump(dict(toc=TOC, path=loc_path, archives=len(archs.archives),
                   assets=len(aids.ids), variants=results), fo, ensure_ascii=False, indent=2)
print("\n[+] wrote", os.path.join(OUT, "_probe.json"))
