#!/usr/bin/env python3
"""
Build a Hebrew menu-proof DataPC_boot_patch_02.forge by cloning the Ukrainian #8
reference mod (work/refmods/ua/) and replacing ONLY record [0] (the English-slot
UI LocalizationPackage, fileID 0x46537fd8) with a Hebrew-patched version — 6 known
UI stringIDs -> Hebrew, the rest kept (Ukrainian) since only the 6 are inspected.

WHY the UA mod as source: its loc records decode with OUR borrowed Oodle (the base
boot forge's original Ubisoft blocks currently do NOT), it already targets the
English slot the community hijacks, and it ships NO fonts (Cyrillic already in the
shipped font) — exactly Hebrew's situation. Records [1..9] (subs + scaffold) are
copied verbatim; the 1.47 MB post-TOC tail is preserved (verified offset-free).

Deploy (game CLOSED): copy the output next to ACBlackFlag.exe, launch, in the
settings pick interface language = "English" -> the 6 menu items should read Hebrew.
This proves (a) an added patch_02 loads, (b) Hebrew renders, (c) RTL in the EN slot.
If Hebrew renders but LEFT-TO-RIGHT, the next build flips record[0]'s TOC fileID to
the Arabic UI slot (0x668047c5) and you pick Arabic instead (RTL native).

    python work/build_he_patch02.py          # builds work/refmods/he/DataPC_boot_patch_02.forge
"""
import importlib.util
import os
import sys
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")


def _load(n):
    p = os.path.join(TOOLS, n + ".py")
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


AF = _load("acbf_forge"); CFD = _load("acbf_cfd"); LP = _load("acbf_locpkg")

# repack_patch lives in this same work/ dir; reuse its natural 2-CFD rebuilder.
_rp = importlib.util.spec_from_file_location("repack_patch", os.path.join(HERE, "repack_patch.py"))
RP = importlib.util.module_from_spec(_rp); _rp.loader.exec_module(RP)

UA = os.path.join(HERE, "refmods", "ua", "DataPC_boot_patch_02.forge")
OUTDIR = os.path.join(HERE, "refmods", "he")
OUT = os.path.join(OUTDIR, "DataPC_boot_patch_02.forge")

# The community stores loc records UNCOMPRESSED (raw blocks: comp==uncomp) — the game's
# Oodle is statically linked in the exe (no loose oo2core) and rejects our re-compressed
# stream, so an Oodle-compressed override silently falls back to the base language
# ("still English"). RawOodle forces build_cfd to store raw (its compress returns the
# input unchanged -> len(comp)>=len(raw) -> build_cfd keeps it raw). Zero decode risk.
class RawOodle:
    def compress(self, data, level=0):
        return bytes(data)
    def decompress(self, data, uncomp):
        return bytes(data)


# Which language slot record[0] overrides (base-boot fileIDs). Arabic = RTL-native.
# For each slot we source record[0] CONTENT from that language's BASE package so the
# untouched strings stay in a script that matches the slot (Arabic slot -> Arabic base,
# clean; not the Ukrainian UA content). stringIDs are language-independent, so the same
# menu-item IDs (derived from the UA package by prefix) patch cleanly in any language.
SLOT_FILEID = {"arabic": 0x668047c5, "english": 0x46537fd8}
SLOT_BASE_IDX = {"arabic": 27724, "english": 27730}   # base DataPC_boot.forge record idx
SLOT = os.environ.get("ACBF_SLOT", "arabic")
GAME = os.environ.get("ACBF_GAME", r"C:\Games\Assassin's Creed Black Flag Resynced")
BOOT = os.path.join(GAME, "DataPC_boot.forge")
# the injector's oo2core_9 decodes the base's Ubisoft Kraken blocks (our BF6 one returns 0)
INJ_OODLE = os.path.join(HERE, "refmods", "injector", "oo2core_9_win64.dll")

# The same text can share MANY stringIDs; the visible menu item uses one specific ID,
# so patching a single guessed ID misses it. Instead patch EVERY short string whose
# (Ukrainian) source starts with a menu label -> its Hebrew. Length guard avoids
# hitting long sentences that merely begin with the word.
PREFIX_HE = {
    "Продовжити": "המשך",        # Continue
    "Нова гра": "משחק חדש",       # New Game
    "Завантажити": "טעינה",       # Load
    "Налаштування": "הגדרות",     # Settings
    "Система": "מערכת",           # System
    "Вийти": "יציאה",             # Exit
    "BLACK FLAG RESYNCED": "בלאק פלאג",
}
MAXLEN = 40  # menu items are short; skip long strings that merely start with the word


# In the English (LTR) slot the engine does NOT apply the bidi algorithm, so Hebrew
# comes out visually reversed. ACBF_VISUAL=1 pre-reverses each (pure-Hebrew) label so the
# LTR renderer shows the correct right-to-left order. (Proof-grade: real ship text needs
# the full Unicode Bidi Algorithm for mixed Hebrew+digits/Latin.)
VISUAL = os.environ.get("ACBF_VISUAL", "0") == "1"


def _vis(t):
    if not VISUAL:
        return t
    # reverse only if the label is pure Hebrew (+spaces); leave mixed labels alone
    if all(('א' <= c <= 'ת') or c == ' ' for c in t):
        return t[::-1]
    return t


# ACBF_PROBE=1: append a Latin tag " XZ" to each Hebrew label. On the Arabic slot this
# tells us whether the Arabic text path renders Latin (routes to a Latin font) while the
# Hebrew part tofus -> font/script-routing gap specific to Hebrew (potentially fixable);
# vs BOTH tofu -> the override text isn't reaching a usable font at all.
PROBE = os.environ.get("ACBF_PROBE", "0") == "1"

# ACBF_HIJACK=1: transliterate the Hebrew labels to Arabic carrier codepoints so the
# Arabic slot's RTL path renders them (via the font hijack). No visual reversal — the
# engine's own bidi orders the (Arabic-script) carriers right-to-left.
HIJACK = os.environ.get("ACBF_HIJACK", "0") == "1"
if HIJACK:
    from hebrew_arabic_hijack import translit


def build_patch(strs):
    patch = {}
    for pid, t in strs.items():
        for pref, he in PREFIX_HE.items():
            if t.startswith(pref) and len(t) <= MAXLEN:
                val = _vis(he)
                if PROBE:
                    val = he + " XZ"
                if HIJACK:
                    val = translit(he)          # Hebrew -> Arabic carriers
                patch[pid] = val
                break
    return patch


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    o = CFD._oodle()
    raw = RawOodle()
    # injector oodle: decodes the base forge's Ubisoft Kraken blocks
    sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))
    from acs_oodle import Oodle
    oo_inj = Oodle(INJ_OODLE)
    target_fid = SLOT_FILEID[SLOT]
    base_idx = SLOT_BASE_IDX[SLOT]
    print(f"slot={SLOT} -> record[0] fileID 0x{target_fid:08x} sourced from base idx {base_idx}; storage=RAW")
    data = open(UA, "rb").read()
    info = AF.parse(UA); recs = info["recs"]; toc = info["toc"]; count = info["count"]
    first_off = recs[0]["offset"]
    header = data[:first_off]
    tail = data[toc + count * AF.REC:]

    # --- rebuild record [0] with Hebrew (natural, no pad; @4/@10/marker-num re-derived) ---
    r0 = recs[0]
    # menu-item stringIDs are language-independent -> derive them from the UA package by
    # (Ukrainian) prefix, then apply the SAME IDs to the base package of the chosen slot.
    ua_strs = {}
    for pk in LP.find_packages(CFD.decode_all(data[r0["offset"]:r0["offset"] + r0["size"]], o)):
        ua_strs.update(pk.get("strings", {}))
    PATCH = build_patch(ua_strs)
    print(f"prefix patch: {len(PATCH)} stringIDs across {len(PREFIX_HE)} menu labels")

    # source record[0] CONTENT from the slot's BASE package (decoded with the injector oodle)
    bi = AF.parse(BOOT); br = bi["recs"][base_idx]
    with open(BOOT, "rb") as f:
        f.seek(br["offset"]); src0 = f.read(br["size"])
    cfds, consumed = CFD.decode_resource(src0, oo_inj)
    assert len(cfds) == 2 and consumed == len(src0), f"base rec not 2-CFD (got {len(cfds)}, {consumed}/{len(src0)})"
    heb0 = RP._natural_1244(src0, oo_inj, raw, patch=PATCH)
    # verify the rebuilt blob decodes and carries the Hebrew strings
    dec = CFD.decode_all(heb0, o)
    strs = {}
    for pk in LP.find_packages(dec):
        strs.update(pk.get("strings", {}))
    hit = sum(1 for pid, t in PATCH.items() if strs.get(pid) == t)
    print(f"rec[0]: {r0['size']:,} -> {len(heb0):,} B, strings={len(strs)}, Hebrew patched {hit}/{len(PATCH)}")
    if hit != len(PATCH):
        print("  !! not all Hebrew strings verified in rebuilt rec0 — aborting"); return 1

    # --- lay out the new forge: header + heb0 + rec[1..9] + newTOC + tail ---
    blobs = [heb0] + [data[recs[i]["offset"]:recs[i]["offset"] + recs[i]["size"]] for i in range(1, count)]
    new_recs = []
    off = first_off
    for i in range(count):
        b = blobs[i]
        rr = dict(recs[i]); rr["offset"] = off; rr["size"] = len(b)
        if i == 0:
            rr["ts"] = target_fid          # retarget record[0] to the chosen language slot
            rr["flags"] = br["flags"]      # MATCH the base record's flags (EN=0x204, others=0x207);
            #                                a mismatched flag makes the game ignore the override
        new_recs.append(rr); off += len(b)
    new_toc_off = off
    new_toc = bytearray()
    for rr in new_recs:
        new_toc += struct.pack("<QIIII", rr["offset"], rr["ts"], rr["flags"], rr["size"], rr["hash"])

    out = bytearray()
    out += header
    for b in blobs:
        out += b
    assert len(out) == new_toc_off, f"{len(out)} != {new_toc_off}"
    out += new_toc
    out += tail
    # patch the manifest descriptor: count unchanged, tocOffset -> new_toc_off
    struct.pack_into("<Q", out, AF.DESC_OFF + 4, new_toc_off)

    open(OUT, "wb").write(out)
    print(f"wrote {OUT}  ({len(out):,} B)")

    # --- verify the written forge ---
    v = AF.parse(OUT); g, t = AF.invariant(v["recs"])
    print(f"verify: count={v['count']} tocOff=0x{v['toc']:x} contiguity {g}/{t}")
    ok = (g == t and v["count"] == count)
    # record [0] decodes + 6 Hebrew; records [1..9] byte-identical to UA source
    vr = v["recs"]
    with open(OUT, "rb") as f:
        f.seek(vr[0]["offset"]); b0 = f.read(vr[0]["size"])
    d0 = CFD.decode_all(b0, o); s0 = {}
    for pk in LP.find_packages(d0):
        s0.update(pk.get("strings", {}))
    hit2 = sum(1 for pid, tx in PATCH.items() if s0.get(pid) == tx)
    same_rest = True
    for i in range(1, count):
        with open(OUT, "rb") as f:
            f.seek(vr[i]["offset"]); bi = f.read(vr[i]["size"])
        if bi != blobs[i]:
            same_rest = False; break
    print(f"verify: rec0 Hebrew {hit2}/{len(PATCH)}, recs[1..9] verbatim {same_rest}")
    if ok and hit2 == len(PATCH) and same_rest:
        print("  ✅ BUILD OK — ready to deploy (English slot).")
        return 0
    print("  !! verification failed"); return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
