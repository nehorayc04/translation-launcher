# -*- coding: utf-8 -*-
"""DELTA=0 marker test: replace menu strings with Latin markers padded to the
   EXACT byte length of the Arabic string they replace -> total MSGS size is
   UNCHANGED -> the blob is byte-identical to the original except the marked text.
   No downstream offset shifts at all.

   If markers show in-game  -> rendering + in-place replacement WORK; the blank-text
                               bug is purely the delta>0 downstream-offset shift.
   If still blank           -> the problem is deeper than offsets (rendering itself)."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gowr_wad as W

ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC  = os.path.join(ROOT, "extract", "r_lang_ar.wad")
LIVE = r'C:\Game Lab\God of War - Ragnarok\exec\wad\pc_le\r_lang_ar.wad'
src = SRC if os.path.exists(SRC) else (LIVE + ".he_backup")

ar = W.extract(src)
BASE = {
    "2119": "XX-NEW-GAME", "2120": "XX-CONTINUE", "2121": "XX-LOAD-GAME",
    "2118": "XX-OPTIONS",  "1060": "XX-OPTIONS2", "1061": "XX-CONTINUE2",
    "430": "XX-SETTINGS",  "438": "XX-AUDIO",     "804": "XX-LANGUAGE",
    "739": "XX-SUBTITLES", "884": "XX-VIDEO",     "74613": "XX-DISPLAY",
    "36849": "XX-CONTROLS","445": "XX-BACK",
}
markers = {}
for k, base in BASE.items():
    if k not in ar:
        continue
    tb = len(ar[k].encode("utf-8"))          # target byte length (Arabic, 2-byte chars)
    m = (base + "." * tb)[:tb]               # pad/truncate to EXACT tb bytes (ASCII=1B)
    assert len(m.encode("utf-8")) == tb, (k, tb, m)
    markers[k] = m

# verify global delta == 0
old_total = sum(len(f"*{k}*\n{ar[k]}\n".encode()) for k in ar)
new_total = sum(len(f"*{k}*\n{markers.get(k, ar[k])}\n".encode()) for k in ar)
print(f'net MSGS delta = {new_total - old_total:+,} bytes  (MUST be 0)')
for k, m in markers.items():
    print(f'  id={k:>6}  ar({len(ar[k].encode())}B) -> {m!r} ({len(m.encode())}B)')

dec_size, delta = W.pack(markers, src, LIVE)
print(f'\nDEPLOYED delta=0 marker test -> {LIVE}')
print(f'  decompressed={dec_size:,}  msgs_delta={delta:+,}  file={os.path.getsize(LIVE):,} B')
chk = W.extract(LIVE)
ok = sum(1 for k, v in markers.items() if chk.get(k) == v)
print(f'  markers present in built WAD: {ok}/{len(markers)}')
