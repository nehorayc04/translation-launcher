# -*- coding: utf-8 -*-
"""Repack-validation test: replace high-visibility MENU strings with Latin ASCII
   markers (render in the existing font -> isolates the WTOC repack/delta-fixup
   from the Hebrew-font question). Level-0 build, deploys to the Game Lab WAD.

   If the markers show in-game (interface=Arabic) -> repack + offset fixup WORK,
   and the only remaining gate is the Hebrew font. If blank/crash -> the delta
   offset-fixup is still wrong (independent of font, independent of compression)."""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gowr_wad as W

ROOT  = os.path.normpath(os.path.join(HERE, ".."))
SRC   = os.path.join(ROOT, "extract", "r_lang_ar.wad")
LIVE  = r'C:\Game Lab\God of War - Ragnarok\exec\wad\pc_le\r_lang_ar.wad'

# id -> Latin marker (clearly artificial; reachable within seconds of launch)
MARKERS = {
    "2119": "XX-NEW-GAME",
    "2120": "XX-CONTINUE",
    "2121": "XX-LOAD-GAME",
    "2118": "XX-OPTIONS",
    "1060": "XX-OPTIONS-2",
    "1061": "XX-CONTINUE-2",
    "430":  "XX-SETTINGS",
    "438":  "XX-AUDIO",
    "804":  "XX-LANGUAGE",
    "739":  "XX-SUBTITLES",
    "884":  "XX-VIDEO",
    "74613": "XX-DISPLAY",
    "36849": "XX-CONTROLS",
    # one long marker to guarantee a clear net-positive delta exercising offset fixup
    "445":  "XX-BACK-" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" * 2,
}

# Use the live source if extract/ copy is missing
src = SRC if os.path.exists(SRC) else (LIVE + ".he_backup")
print(f'source = {src}')
ar = W.extract(src)
old_total = sum(len(f"*{k}*\n{ar[k]}\n".encode()) for k in ar)
new_total = sum(len(f"*{k}*\n{MARKERS.get(k, ar[k])}\n".encode()) for k in ar)
print(f'net MSGS delta from markers: {new_total - old_total:+,} bytes')
for k in MARKERS:
    print(f'  id={k:>6}  ar={ar.get(k,"<MISSING>")!r:24} -> {MARKERS[k]!r}')

dec_size, delta = W.pack(MARKERS, src, LIVE)   # level-0, no font injection
print(f'\nDEPLOYED marker test -> {LIVE}')
print(f'  decompressed={dec_size:,}  msgs_delta={delta:+,}  file={os.path.getsize(LIVE):,} B')

# sanity: re-extract and confirm markers are present
chk = W.extract(LIVE)
ok = sum(1 for k, v in MARKERS.items() if chk.get(k) == v)
print(f'  markers present in built WAD: {ok}/{len(MARKERS)}')
