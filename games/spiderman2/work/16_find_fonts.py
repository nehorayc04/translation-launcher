"""Hunt the font/typeface assets used by the Arabic locale.
We enumerate asset entries with path-based hashes, looking for paths containing
'font' / 'typeface' / 'ttf' / 'otf' / 'noto'."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

# dat1lib provides get_asset_entries_by_path(path) -> resolves via CRC64.
# Try a battery of candidate paths.
candidates = [
    # Adobe / Insomniac internal font formats common in their engine:
    "font/ui_arabic.font",  "font/ui_arabic_main.font",
    "ui/font/arabic.font", "ui/font/notosans_arabic.font",
    "ui/font/noto_sans_arabic_ui.font",
    "font/notosans_arabic.font",
    "font/noto_sans_arabic.font",
    "fonts/arabic.ttf", "fonts/arabic.otf",
    # Generic UI fonts that *might* be the bidi-aware shared font:
    "font/ui.font", "font/ui_main.font", "font/main.font",
    "ui/font/ui.font", "ui/font/main.font",
    "ui/font/default.font",
    # Cohtml (the engine SM2 uses for UI) font names:
    "cohtml/font/arabic.font", "cohtml/font/noto_sans_arabic.font",
    "cohtml/fonts/arabic.ttf",
]
print(f"=== probing {len(candidates)} candidate paths ===")
hits = []
for p in candidates:
    es = toc.get_asset_entries_by_path(p)
    es = [e for e in (es or []) if e is not None]
    if es:
        hits.append((p, es))
        print(f"  [+] '{p}' -> {len(es)} entries")
    # else: silent

print(f"\n[*] {len(hits)} direct hits")

# Also: enumerate strings in dagstr that mention "font" / "ttf" / "otf" / "noto"
# dagstr is the global path string table — fast to grep.
DAGSTR = os.path.join(GAME, "dagstr")
data = open(DAGSTR, "rb").read()
print(f"\n[*] dagstr {len(data)} bytes — searching for font references")
needles = [b"font/", b"fonts/", b".ttf", b".otf", b"notosans", b"NotoSans",
           b"arabic_ui", b"hebrew", b"_ar.", b"_ui.font", b"typeface"]
findings = {}
for needle in needles:
    i = 0
    count = 0
    samples = []
    while True:
        j = data.find(needle, i)
        if j < 0: break
        # Walk back to start of the C-string this needle is inside
        start = j
        while start > 0 and data[start-1] not in (0,):
            start -= 1
        end = data.find(b"\x00", j)
        if end < 0: end = j + 200
        s = data[start:end].decode("utf-8", "replace")
        if len(s) < 200:
            samples.append(s)
        count += 1
        i = end + 1
        if count > 200: break
    if samples:
        findings[needle.decode(errors='replace')] = samples
        print(f"  [{needle.decode(errors='replace')!r:<20}] {count} hits, sample of {min(8,len(samples))}:")
        for s in samples[:8]:
            print(f"      {s}")

# After we know font paths, attempt to resolve at least one and find which span+archive it lives in.
print()
print("=== resolving the most promising font paths ===")
promising = []
for samples in findings.values():
    for s in samples:
        if s.endswith(".font") or s.endswith(".ttf") or s.endswith(".otf"):
            if s not in promising:
                promising.append(s)
print(f"[*] {len(promising)} unique font paths in dagstr")
for p in promising[:40]:
    es = toc.get_asset_entries_by_path(p)
    es = [e for e in (es or []) if e is not None]
    if es:
        print(f"  [+] '{p}' -> {len(es)} entries  first: idx={es[0].index} arch={es[0].archive} size={es[0].size}")
    else:
        print(f"  [-] '{p}' -> 0 entries")
