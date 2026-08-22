"""MSMR — verify the localization ENTRY MODEL (not just the section list), and
get the engine's OWN evidence for which languages it supports.

READ-ONLY.

1. Prove the record model:  entry_count / key-offsets / value-offsets /
   hash arrays, by reconstructing key->value and checking it round-trips.
2. Prove which section is the sorted-hash lookup (sorted(hashes) == other array).
3. Dump every key that mentions LANGUAGE/LOCALE/SUBTITLE and print the ENGLISH
   value -> the game's own list of supported languages (the authoritative
   answer to "is there an Arabic TEXT slot?").
4. Definitively count Arabic/Hebrew codepoints in EVERY variant's values.
5. Probe the toc for any OTHER *.localization asset path (DLC etc.).
"""
import os, sys, io, struct, json, zlib
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOCS = os.path.join(ROOT, "games", "spiderman_remastered", "extract", "loc_variants")
GAME = r"D:\Games\Spider-man Remastered"
ARCH = os.path.join(GAME, "asset_archive")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HDR = 36
T_HASHES_ORDER = 0x06A58050
T_INDEX_U16    = 0x0CD2CFE9
T_KEYS         = 0x4D73CEBD
T_VALUES       = 0x70A382B8
T_KEY_OFFS     = 0xA4EA55B2
T_ZEROS        = 0xB0653243
T_HASHES_SORT  = 0xC43731B5
T_COUNT        = 0xD540A903
T_VAL_OFFS     = 0xF80DEEB4


class D1:
    def __init__(self, pay):
        self.pay = pay
        self.magic, self.unk1, self.size = struct.unpack_from("<III", pay, 0)
        nsec, nunk = struct.unpack_from("<HH", pay, 12)
        self.sections = [struct.unpack_from("<III", pay, 16 + 12 * i) for i in range(nsec)]

    def seg(self, tag):
        for t, o, s in self.sections:
            if t == tag:
                return self.pay[o:o + s]
        return b""


def load(fn):
    raw = open(os.path.join(LOCS, fn), "rb").read()
    return D1(raw[HDR:])


def cstr(blob, off):
    e = blob.find(b"\x00", off)
    return blob[off:e if e != -1 else len(blob)]


fns = sorted(f for f in os.listdir(LOCS) if f.endswith(".localization"))
print(f"[*] {len(fns)} variants\n")

# ------------------------------------------------------------------ 1. model
d0 = load(fns[0])
cnt_blob = d0.seg(T_COUNT)
N = struct.unpack("<I", cnt_blob)[0]
print("=" * 78)
print("1) ENTRY MODEL")
print("=" * 78)
print(f"  0xD540A903 ENTRY_COUNT       = {N}")
for tag, name, unit in ((T_KEY_OFFS, "KEY_OFFSETS", 4), (T_VAL_OFFS, "VALUE_OFFSETS", 4),
                        (T_HASHES_ORDER, "HASHES(entry order)", 4),
                        (T_HASHES_SORT, "HASHES(sorted?)", 4),
                        (T_INDEX_U16, "INDEX u16", 2), (T_ZEROS, "ZEROS", 4)):
    s = d0.seg(tag)
    print(f"  0x{tag:08X} {name:<22} {len(s):>9} B  /{unit} = {len(s)//unit}"
          f"  {'== N ✓' if len(s)//unit == N else '!= N ✗'}")

keys_blob = d0.seg(T_KEYS)
koff = struct.unpack(f"<{N}I", d0.seg(T_KEY_OFFS))
voff = struct.unpack(f"<{N}I", d0.seg(T_VAL_OFFS))
h_ord = struct.unpack(f"<{N}I", d0.seg(T_HASHES_ORDER))
h_srt = struct.unpack(f"<{N}I", d0.seg(T_HASHES_SORT))
idx16 = struct.unpack(f"<{N}H", d0.seg(T_INDEX_U16))
zeros = d0.seg(T_ZEROS)

print(f"\n  key_offsets ascending?   {all(koff[i] <= koff[i+1] for i in range(N-1))}")
print(f"  key_offsets max {max(koff)} vs keys blob {len(keys_blob)}  in-range="
      f"{max(koff) < len(keys_blob)}")
print(f"  ZEROS section all zero?  {zeros.count(0) == len(zeros)}")

print(f"\n  sorted(HASHES entry-order) == HASHES_SORT ?  "
      f"{tuple(sorted(h_ord)) == h_srt}")
print(f"  HASHES_SORT strictly ascending?              "
      f"{all(h_srt[i] < h_srt[i+1] for i in range(N-1))}")
# does INDEX map sorted position -> entry index?
ok = sum(1 for i in range(0, N, max(1, N // 500)) if h_ord[idx16[i]] == h_srt[i])
tot = len(range(0, N, max(1, N // 500)))
print(f"  h_ord[ INDEX[i] ] == h_srt[i] ?              {ok}/{tot} sampled"
      f"   -> {'INDEX = sorted->entry permutation' if ok == tot else 'NOT that'}")
print(f"  INDEX max = {max(idx16)}  (N-1 = {N-1})  u16 sufficient = {N <= 65536}")

# is the hash crc32 of the key?
def keystr(i):
    return cstr(keys_blob, koff[i])
for algo, fn_ in (("crc32", lambda b: zlib.crc32(b) & 0xFFFFFFFF),
                  ("crc32(lower)", lambda b: zlib.crc32(b.lower()) & 0xFFFFFFFF),
                  ("adler32", lambda b: zlib.adler32(b) & 0xFFFFFFFF)):
    m = sum(1 for i in range(0, min(N, 400)) if fn_(keystr(i)) == h_ord[i])
    print(f"  hash == {algo:14} on first 400 entries: {m}/400")

# ------------------------------------------------------------------ key->value
def kv(fn):
    d = load(fn)
    kb, vb = d.seg(T_KEYS), d.seg(T_VALUES)
    ko = struct.unpack(f"<{N}I", d.seg(T_KEY_OFFS))
    vo = struct.unpack(f"<{N}I", d.seg(T_VAL_OFFS))
    out = {}
    for i in range(N):
        k = cstr(kb, ko[i]).decode("utf-8", "replace")
        v = cstr(vb, vo[i]).decode("utf-8", "replace")
        out[k] = v
    return out, vb


print("\n  --- reconstruct key -> value on variant_00 ---")
m0, vb0 = kv(fns[0])
print(f"  entries reconstructed: {len(m0)} (dupes collapsed from {N})")
for k in ("ABANDON_CONFIRM_BODY", "ABANDON_CONFIRM_HEADER", "ACCESS_AIMTOGGLE_TITLE"):
    print(f"    {k:32} = {m0.get(k)!r}")
print(f"  value_offsets max {max(voff)} vs values blob {len(vb0)} in-range="
      f"{max(voff) < len(vb0)}")
dup = N - len(set(voff))
print(f"  duplicate value offsets: {dup} of {N} entries share a string "
      f"({len(set(voff))} distinct offsets)")

# ------------------------------------------------------------------ 3. lang keys
print("\n" + "=" * 78)
print("3) THE GAME'S OWN LANGUAGE LIST (keys mentioning LANGUAGE / LOCALE / SUBTITLE)")
print("=" * 78)
pats = ("LANGUAGE", "LANG_", "LOCALE", "SUBTITLE", "VOICE_OVER", "AUDIO_LANG")
hits = sorted(k for k in m0 if any(p in k.upper() for p in pats))
print(f"  {len(hits)} matching keys\n")
for k in hits:
    v = m0[k]
    if len(v) > 70:
        v = v[:70] + "…"
    print(f"    {k:46} = {v!r}")

# ------------------------------------------------------------------ 4. scripts
print("\n" + "=" * 78)
print("4) DEFINITIVE Arabic / Hebrew codepoint count in EVERY variant's VALUES")
print("=" * 78)
tot_ar = tot_he = 0
for k, fn in enumerate(fns):
    d = load(fn)
    vb = d.seg(T_VALUES)
    txt = vb.decode("utf-8", "replace")
    ar = sum(1 for c in txt if 0x0600 <= ord(c) <= 0x06FF or 0xFB50 <= ord(c) <= 0xFEFF)
    he = sum(1 for c in txt if 0x0590 <= ord(c) <= 0x05FF)
    tot_ar += ar; tot_he += he
    print(f"  variant_{k:02d}  arabic={ar:>7}  hebrew={he:>7}")
print(f"\n  TOTAL across all {len(fns)} variants:  arabic={tot_ar}  hebrew={tot_he}")
print("  => " + ("ARABIC TEXT SLOT EXISTS" if tot_ar > 200 else
                 "NO ARABIC TEXT SLOT — this is an LTR-slot-hijack game"))

# ------------------------------------------------------------------ 5. toc probe
print("\n" + "=" * 78)
print("5) OTHER *.localization ASSETS IN THE TOC?")
print("=" * 78)
try:
    import dat1lib, dat1lib.types.toc, dat1lib.crc64 as crc64
    with open(os.path.join(ARCH, "toc"), "rb") as f:
        toc = dat1lib.read(f)
    toc.set_archives_dir(ARCH)
    CANDS = [
        "localization/localization_all.localization",
        "localization/localization_dlc.localization",
        "localization/localization_dlc1.localization",
        "localization/localization_all_dlc.localization",
        "localization/localization_dlc_all.localization",
        "localization/dlc/localization_all.localization",
        "dlc/localization/localization_all.localization",
        "localization/localization_credits.localization",
        "localization/credits.localization",
        "localization/localization_all2.localization",
        "localization/localization_all_2.localization",
        "localization/localization_arabic.localization",
        "localization/arabic.localization",
    ]
    for p in CANDS:
        try:
            ents = [e for e in (toc.get_asset_entries_by_path(p) or []) if e is not None]
        except Exception as ex:
            print(f"  {p!r}: ERR {ex}"); continue
        mark = "  <== " if ents else ""
        print(f"  {crc64.hash(p):016X}  {len(ents):>3} entries  {p}{mark}")
except Exception as ex:
    print("  toc probe skipped:", ex)

print("\n[done]")
