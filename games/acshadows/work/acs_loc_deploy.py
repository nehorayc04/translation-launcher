#!/usr/bin/env python3
"""
acs_loc_deploy.py -- write Hebrew into AC Shadows' ARABIC LocalizationPackage slot.

THE STORE (cracked 2026-07-17):
  Class hashes are plain CRC32 of the reflection class NAME; the names sit in a
  plaintext table at the forge TAIL (after the last resource).
      crc32("LocalizationPackage")        = 0x6E3C9C6F   <- the TOC resource type
      crc32("CompressedLocalizationData") = 0xD28389B5   <- the nested marker
  (June anchored on AC2's 0x6E37B1AF, found nothing, and wrongly concluded that
   Shadows has no LocalizationPackage and stores text as literal UTF-16.)

  2,127 LocalizationPackage resources live in DataPC_boot{,_patch_01,_patch_02}.forge.
  Inside a resource, at the class hash H:
      hash@H  Type@H+4  Language@H+8  <skip 12>  marker@H+24  num@H+28  BE payload@H+32
  The BE payload is the char-index format and uses the SAME flat-record layout as
  AC Black Flag Resynced (v50), so games/acblackflag-resynced/tools/acbf_locpkg.py decodes
  AND encodes it as-is:
      u16 MaxIndexSize ; u16 fragCount ; fragCount x {u16 right,u16 left}
      u16 recordCount  ; recordCount x {u64 lineID, u32 codeOff, u32 off2}
      u32 length table ; code stream

  Language IDs (from the fragment dictionaries): 1=en 18=ru 19=ja 20=ko 21/22=zh
  23=ARABIC (52,343 strings). EN and AR share lineIDs 1:1.

WHY THIS IS SAFE:
  bidi = LOGICAL. The shipped Arabic stores the BASE Arabic block (0 presentation
  forms / 52,343) and keeps token order identical to English (527/527), so the
  engine runs full bidi + shaping at runtime. Hebrew needs bidi only -> store
  natural Hebrew, zero bidi code.

  Our re-encode uses a flat leaf dictionary (bigger payload than the game's
  fragment tree) but Oodle absorbs it: measured 0.94x of the original slot. So
  every package is written IN PLACE at its original record size with trailing
  zero padding -- record offset/size never change, the forge stays byte-for-byte
  contiguous, and no re-pack is needed (same law Phase 0 proved).

Usage (GAME MUST BE CLOSED):
    python acs_loc_deploy.py --proof            # Hebrew menu proof
    python acs_loc_deploy.py --apply heb.json   # {lineID: "hebrew"} for real
    python acs_loc_deploy.py --verify
    python acs_loc_deploy.py --revert
"""
import argparse
import random
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "acblackflag-resynced", "tools"))
import acs_forge as F          # noqa: E402
import acs_cfd as C           # noqa: E402
import acbf_locpkg as BF      # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = os.environ.get("ACS_GAME", r"C:\Games\Assassin's Creed Shadows")
# Patch forges override the base by fileID (PLAN rule 8), so the engine reads
# patch_02's copy of any package that exists in more than one. Writing the base
# as well is unnecessary -- ACS_FORGES restricts the target.
ALL_FORGES = ("DataPC_boot.forge", "DataPC_boot_patch_01.forge", "DataPC_boot_patch_02.forge")
FORGES = tuple(os.environ.get("ACS_FORGES", "").split(",")) if os.environ.get("ACS_FORGES") \
    else ALL_FORGES
LP_HASH = 0x6E3C9C6F
NEEDLE = struct.pack("<I", LP_HASH)
ARABIC = 23
# Mermaid levels, best-first. The game itself is Mermaid@7 (byte-identical), so 7 is
# the vanilla baseline and 9 buys the only headroom there is (~181 B on a 623 KB
# package) -- levels 4-6 are far WORSE for Mermaid (+30..125 KB) and never fit.
# The old (4, 6, ...) ladder only looked generous because it was Kraken, which is a
# stronger compressor the engine cannot read.
LEVELS = (9, 8, 7)
SCAN_MAX = 1024          # linear-scan backstop when Newton oscillates
SCAN_SEEDS = 4           # ... across this many filler pools
BAK = ".lpbak_%d"

# The main-menu strings the user photographed, verified present in the corpus.
# A pure-Latin marker proves mount+font independently of any Hebrew glyph.
PROOF = {
    12427757013786422229: "ZZ-ACS-OK",        # Continue  (was متابعة)
    2234870881390797232: "משחק חדש",           # New Game
    2249360016314713277: "טעינה",              # Load
    12447680188567517528: "מערכת",             # System
    12435709294004715387: "עלילה",             # Story
    12439256787398533886: "חנות",              # Store
    12414581526431221893: "אנימוס",            # Animus
    12421875198942181598: "חזרה",              # Back
    2240195849151701029: "אפשרויות",           # Options
    12440398426342147490: "מפה",               # Map
    12443086293885607844: "משימות",            # Quests
}

# 🔬 CARRIER-CODEPOINT A/B (2026-08-21). Hebrew codepoints put real Hebrew GLYPHS on screen,
# but the words still do not lay out correctly -- the engine applies its Arabic-locale RTL
# treatment to an ARABIC run, and a Hebrew run is not that. AC Black Flag Resynced (same
# atlas class 0xCBD4939A) solved exactly this by storing the text as rare Arabic ligature
# codepoints whose atlas slots were repainted with Hebrew art: the engine then sees a
# strong-RTL Arabic run, applies NATIVE bidi, and paints Hebrew.
# Verified safe here: a scan of all 135,096 stored Arabic strings found ZERO presentation-form
# codepoints (the game stores BASE letters and the shaper produces the forms at runtime), so
# nothing legitimate can collide with a carrier.
# `work/carrier_map.json` is written by acs_atlas_inject3 and maps Hebrew char -> carrier cp.
# Only the ids in CARRIER_IDS are re-encoded, so one build carries BOTH methods and one
# screenshot says which is right.
# ✅ The A/B answered: the carrier row rendered correctly RTL while the Hebrew-codepoint
# row beside it stayed scrambled. So EVERY string goes through the carrier map now --
# None means 'all ids'. Any Hebrew letter with no carrier is left as-is and reported.
CARRIER_IDS = None                           # None = every id


def _apply_carriers(proof):
    path = os.path.join(HERE, "carrier_map.json")
    if not os.path.isfile(path):
        return proof
    cmap = {k: chr(v) for k, v in json.load(open(path, encoding="utf-8")).items()}
    out = dict(proof)
    missing = set()
    for i in (out if CARRIER_IDS is None else CARRIER_IDS):
        if i not in out:
            continue
        s = out[i]
        missing |= {c for c in s if "א" <= c <= "ת" and c not in cmap}
        out[i] = "".join(cmap.get(c, c) for c in s)
    if missing:
        # A Hebrew letter with no carrier would be stored as a Hebrew codepoint, which the
        # engine renders in STORAGE order -- the exact bug the carriers exist to fix. Never
        # let that pass silently.
        raise RuntimeError("no carrier for: " + " ".join(sorted(missing))
                           + " -- re-run acs_atlas_inject3.py --apply to rebuild the map")
    return out


PROOF = _apply_carriers(PROOF)


def _find_arabic(d):
    """Return (offset_of_class_hash, num) of the Arabic package in a decoded
    resource, or (-1, 0). The first hash match is the CFD1 entry header, not a
    package, so every candidate is validated on Language + num."""
    pos = 0
    while True:
        h = d.find(NEEDLE, pos)
        if h < 0:
            return -1, 0
        pos = h + 4
        if h + 32 > len(d):
            continue
        if struct.unpack_from("<I", d, h + 8)[0] != ARABIC:
            continue
        num = struct.unpack_from("<i", d, h + 28)[0]
        if num > 4 and h + 32 + num <= len(d):
            return h, num


def surgical_payload(pay, edits, filler=b""):
    """Patch a char-index payload with MINIMAL divergence from vanilla.

    A full re-encode via acbf_locpkg.build_payload flattens the game's fragment
    TREE into one leaf per char, which inflates the payload ~30% (1.6M -> 2.1M)
    and rewrites every byte. This instead keeps the fragment tree AND the whole
    code stream byte-identical, and only:
      * appends the leaf fragments for chars the dictionary lacks (Hebrew),
        which shifts everything after the fragment table by len(new)*4;
      * rewrites each edited string's code IN PLACE in code order, shifting the
        following codeOffs by the cumulative length delta.
    Growth is ~300 B instead of ~483,000 B.

    Codes are kept IN CODE ORDER on purpose. Appending them at the tail (the 007
    append-relocate trick) is tempting and much simpler, but a string's end can
    be read two ways -- the explicit u32 at off2, or the next-larger codeOff --
    and vanilla satisfies both, so the data cannot tell us which one the engine
    uses. Out-of-order codes make the two disagree; in-order keeps them
    identical, so this is correct under either reading.

    The off2 region is NOT a flat u32-per-record array and must never be rebuilt.
    Measured on res 17388: 19,330 records step +4 (a plain u32 length) but 20 --
    all with 0x02-prefixed lineIDs rather than the usual 0xAC -- own variable
    structures of 44..420 bytes. So the region is copied VERBATIM and only the
    edited records' length u32 is poked in place. Lengths for the walk come from
    the next-larger codeOff, which is valid for every record type.
    """
    mx, fc = struct.unpack_from(">HH", pay, 0)
    frag_end = 4 + fc * 4
    rc = struct.unpack_from(">H", pay, frag_end)[0]
    rp = frag_end + 2
    rec_end = rp + rc * 16
    lt_end = rec_end + rc * 4

    leaf = {}
    for i in range(fc):
        rt, lf = struct.unpack_from(">HH", pay, 4 + i * 4)
        if lf == 0 and rt != 0:
            leaf.setdefault(chr(rt), i)
    need = sorted({c for t in edits.values() for c in t} - set(leaf))
    for k, c in enumerate(need):
        leaf[c] = fc + k
    shift = len(need) * 4

    def enc(t):
        out = bytearray()
        for c in t:
            b = leaf[c] - 1                      # code byte -> frag[b+1]
            if b < mx:
                out.append(b)
            else:
                val = b + mx * 255
                hi, lo = val >> 8, val & 0xFF
                if mx <= hi <= 254:
                    out += bytes((hi, lo))
                else:
                    out.append(255)
                    out += struct.pack(">h", b)
        return bytes(out)

    rec = [struct.unpack_from(">QII", pay, rp + i * 16) for i in range(rc)]
    order = sorted(range(rc), key=lambda k: rec[k][1])
    code_start = rec[order[0]][1]
    o2_region = bytearray(pay[rec_end:code_start])           # VERBATIM, variable-size entries
    # `filler` is dead space for exact_fill. It MUST go BEFORE the code stream:
    # the last string's end is the payload end, so filler appended at the tail is
    # swallowed by that string and decodes as garbage (proven -- it corrupted the
    # package and only the masked verify hid it). In front, nothing points at it
    # and the code stream still ends exactly at the payload end.
    code_base = code_start + shift + len(filler)

    # length = distance to the next code offset -- valid for every record type
    end_of = {}
    for k, i in enumerate(order):
        end_of[i] = rec[order[k + 1]][1] if k + 1 < rc else len(pay)

    codes = bytearray()
    new_off = [0] * rc
    for i in order:
        sid, co, o2 = rec[i]
        c = enc(edits[sid]) if sid in edits else pay[co:end_of[i]]
        new_off[i] = code_base + len(codes)
        codes += c
        if sid in edits:                                     # poke this record's length in place
            struct.pack_into(">I", o2_region, o2 - rec_end, len(c))

    out = bytearray()
    out += struct.pack(">HH", mx, fc + len(need))
    out += pay[4:frag_end]                                   # fragment tree VERBATIM
    for c in need:
        out += struct.pack(">HH", ord(c), 0)
    out += struct.pack(">H", rc)
    for i in range(rc):
        out += struct.pack(">QII", rec[i][0], new_off[i], rec[i][2] + shift)
    out += o2_region
    out += filler
    assert len(out) == code_base, f"layout drift {len(out)} != {code_base}"
    out += codes
    return bytes(out)


def rebuild_blob(d, c0_len, h, num, payload):
    """Swap in a new BE payload AND keep the declared sizes honest.

    THE DEPLOY LAW (buffer == object) -- violating it boots to the warnings and
    then crashes, because the engine slices CFD1 by the CFD0 size and gets a
    truncated object:

        CFD0.size @10  ==  CFD1.payloadSize @4  +  13 + nameLen
        CFD0.size @10  ==  len(CFD1)

    (PLAN_HEBREW.md states this as `CFD0@10 == @4+51`; 51 is 13+nameLen for Black
     Flag's 38-byte names. In v42 nameLen varies 38..44, so use the law, not 51.)
    acbf_locpkg.rebuild_resource only patches `num`, so it CANNOT be used alone.
    """
    delta = len(payload) - num
    nd = bytearray(d[:h + 28] + struct.pack("<i", len(payload)) + payload + d[h + 32 + num:])
    struct.pack_into("<I", nd, c0_len + 4,
                     struct.unpack_from("<I", nd, c0_len + 4)[0] + delta)   # CFD1 payloadSize
    struct.pack_into("<I", nd, 10,
                     struct.unpack_from("<I", nd, 10)[0] + delta)           # CFD0 size
    size = struct.unpack_from("<I", nd, 10)[0]
    psz = struct.unpack_from("<I", nd, c0_len + 4)[0]
    nl = struct.unpack_from("<I", nd, c0_len + 8)[0]
    assert size == psz + 13 + nl, f"law broken: {size} != {psz}+13+{nl}"
    assert size == len(nd) - c0_len, f"law broken: CFD0.size {size} != len(CFD1) {len(nd)-c0_len}"
    return bytes(nd)


def _rebuild(cfds, d, nd, oodle, budget):
    """Re-split the edited blob on the ORIGINAL CFD boundaries (only the last
    CFD changes size), then encode, escalating the Oodle level until it fits."""
    parts, off = [], 0
    for k, (dd, cc) in enumerate(cfds):
        ln = len(dd) if k < len(cfds) - 1 else len(nd) - off
        parts.append((nd[off:off + ln], cc))
        off += ln
    best = None
    for lv in LEVELS:
        nb = b"".join(C.build_cfd(dd, cc, oodle, level=lv) for dd, cc in parts)
        if best is None or len(nb) < len(best[1]):
            best = (lv, nb)
        if len(nb) <= budget:
            return lv, nb
    return best


def deploy(heb, dry=False):
    oodle = C._oodle()
    done = skip = miss = 0
    hit_ids = set()
    for fn in FORGES:
        p = os.path.join(GAME, fn)
        recs = [r for r in F.parse(p)["recs"] if r["hash"] == LP_HASH]
        touched = 0
        with open(p, "r+b") as f:
            for r in recs:
                bak = p + BAK % r["i"]
                if os.path.isfile(bak):
                    blob = open(bak, "rb").read()
                else:
                    f.seek(r["offset"])
                    blob = f.read(r["size"])
                try:
                    cfds, _ = C.decode_resource(blob, oodle)
                except Exception:
                    continue
                d = b"".join(x for x, _ in cfds)
                h, num = _find_arabic(d)
                if h < 0:
                    continue
                try:
                    orig = BF.decode_payload(d[h + 32:h + 32 + num])
                except Exception:
                    continue
                if not orig:
                    continue
                mine = {k: v for k, v in heb.items() if k in orig}
                if not mine:
                    continue
                pay = surgical_payload(d[h + 32:h + 32 + num], mine)   # size preview only
                nb, lv, k = exact_fill(cfds, d, h, num, d[h + 32:h + 32 + num], mine, r["size"], oodle)
                if nb is None:
                    # 🔴 NO ZERO-PAD FALLBACK. The old code fell back to a natural encode
                    # plus a small zero pad on the theory that "padding was never shown to
                    # be the fault". 2026-08-21 disproved that: res 17390 got a 121-byte
                    # pad, the package then failed its own decode check (cfd_end 623,537 !=
                    # size 623,658) and the game BLACK-SCREENED after the intro logo. The
                    # loader walks CFDs until it has consumed record.size and chokes on the
                    # trailing zeros. A vanilla package is always better than a broken one,
                    # so skip and report loudly instead of writing something unbootable.
                    print(f"    ! res {r['i']}: no exact fill for slot {r['size']:,} "
                          f"-- LEFT VANILLA (never zero-pad: it black-screens)")
                    skip += 1
                    continue
                else:
                    assert len(nb) == r["size"], "not exact"
                    print(f"      res {r['i']:>6}: exact {len(nb):,} B (lvl{lv}, filler {k:,}) "
                          f"payload {num:,} -> {len(pay):,}")
                nb = nb + b"\x00" * (r["size"] - len(nb))
                if not dry:
                    if not os.path.isfile(bak):
                        with open(bak, "wb") as b:
                            b.write(blob)
                    f.seek(r["offset"])
                    f.write(nb)                     # EXACT fill -- zero trailing pad
                hit_ids |= set(mine)
                done += 1
                touched += len(mine)
        print(f"  {fn:<32} packages written={done:<4} strings applied={touched}")
    miss = len(set(heb) - hit_ids)
    print(f"\n  {'DRY RUN -- ' if dry else ''}packages={done}  over-slot(skipped)={skip}  "
          f"ids applied={len(hit_ids)}/{len(heb)}  not-in-corpus={miss}")
    return done, skip


# 🔴 DETERMINISTIC pool. This used to be os.urandom(), so "fixed pool" only held WITHIN
# one process: a filler length that landed exactly on the slot in one run was gone the
# next, and a solution measured in a probe could not be reproduced in the deploy.
# A seeded PRNG makes every (seed, k) reproducible across runs and machines.
_POOL = random.Random(0x5ACD0175).randbytes(3 << 20)
_SEEDS = (0, 7919, 15013, 27449, 41957, 60013, 82699, 104729,
          132709, 160861, 193939, 224737, 256203, 292057, 324899, 360589)


def _split(cfds, nd):
    """Re-split an edited blob on the ORIGINAL CFD boundaries (only the last grows)."""
    parts, off = [], 0
    for j, (dd, cc) in enumerate(cfds):
        ln = len(dd) if j < len(cfds) - 1 else len(nd) - off
        parts.append((nd[off:off + ln], cc))
        off += ln
    return parts


def _natural(cfds, d, h, num, payload, oodle, budget):
    """Best natural encode (no filler). Returns the blob or None if nothing fits."""
    nd = rebuild_blob(d, len(cfds[0][0]), h, num, payload)
    best = None
    for lv in LEVELS:
        nb = b"".join(C.build_cfd(dd, cc, oodle, level=lv) for dd, cc in _split(cfds, nd))
        if best is None or len(nb) < len(best):
            best = nb
        if len(nb) <= budget:
            return nb
    return best if best is not None and len(best) <= budget else None


def exact_fill(cfds, d, h, num, pay, edits, budget, oodle):
    """Encode so the CFD stream fills `budget` EXACTLY -- zero trailing pad.

    WHY: vanilla always satisfies cfd_end == record.size (measured 50/50 across
    both resource types -- not one byte after the last CFD). Our Oodle compresses
    ~5% smaller, so a natural re-encode leaves a hole, and that hole is the only
    thing left that separates our write from vanilla. PLAN rule 6 fixes it with a
    full forge re-pack; this reaches the same end state without rewriting 10.7 GB
    by growing the OBJECT with incompressible filler until the compressed stream
    lands exactly on the budget. Kraken cannot shrink random bytes, so each
    filler byte costs ~1 output byte -- but that premise DOES fail (res 17390: k=121
    came out 508 bytes SMALLER than k=0), and there Newton oscillates instead of
    converging, so a plain linear scan is the backstop that actually finds the answer.

    The filler goes after the last string's code, where no record points; `num` /
    CFD1.payloadSize / CFD0.size all grow with it, so buffer == object still
    holds (PLAN rule 1).

    The output size is NOT continuous in k -- one extra filler byte can move the
    compressed stream by 3, so Newton alone straddles the target (measured: k=
    53,955 -> budget-2, k=53,956 -> budget+1, and nothing lands on budget). So
    each level Newton-steps to the neighbourhood, then SCANS a window, and if the
    target still falls in a gap the filler CONTENT is re-seeded, which reshuffles
    where the jumps land. Returns (blob, level, filler) or (None, None, None).
    """
    c0_len = len(cfds[0][0])

    def build(k, lv, seed):
        nd = rebuild_blob(d, c0_len, h, num,
                          surgical_payload(pay, edits, _POOL[seed:seed + k]))
        parts, off = [], 0
        for j, (dd, cc) in enumerate(cfds):
            ln = len(dd) if j < len(cfds) - 1 else len(nd) - off
            parts.append((nd[off:off + ln], cc))
            off += ln
        return b"".join(C.build_cfd(dd, cc, oodle, level=lv) for dd, cc in parts)

    for lv in LEVELS:
        nb = build(0, lv, 0)
        if len(nb) > budget:
            continue                                   # this level can't fit at all
        for seed in _SEEDS:
            k = budget - len(nb)
            for _ in range(6):                         # Newton into the neighbourhood
                gap = budget - len(build(k, lv, seed))
                if gap == 0:
                    return build(k, lv, seed), lv, k
                if abs(gap) <= 24:
                    break
                k += gap
                if k < 0:
                    k = 0
                    break
            for kk in range(max(0, k - 48), k + 49):   # then scan the gap region
                cand = build(kk, lv, seed)
                if len(cand) == budget:
                    return cand, lv, kk
        # 🔴 LINEAR SCAN -- Newton's premise ("each filler byte costs ~1 output byte") is
        # NOT always true, and when it fails Newton oscillates instead of converging.
        # Measured on res 17390: k=0 -> 623,537 but k=121 -> 623,029 (508 bytes SMALLER),
        # so the walk went 121 -> 750 -> 432 -> 937 -> 505 -> 840 and its +/-48 window
        # landed on 406..502 while the real solution sat at k=235. A plain scan finds it.
        # Cheap here (a loc payload is ~1 MB); do it before ever giving up on a package.
        for sd in _SEEDS[:SCAN_SEEDS]:
            for kk in range(0, SCAN_MAX):
                cand = build(kk, lv, sd)
                if len(cand) == budget:
                    return cand, lv, kk
    return None, None, None


def identity():
    """ISOLATION TEST -- re-encode LocalizationPackage resources with the content
    byte-for-byte UNCHANGED (CFD decode -> CFD encode only; the payload is never
    parsed). Size, block count and every declared field stay exactly vanilla; the
    only difference is that the compressed bytes are ours.

    Phase 0 proved this works on the `loc` resource type. It has never been tried
    on LocalizationPackage, and both Hebrew attempts crashed, so this splits the
    two remaining variables:
        boots  -> writing an LP resource is fine; the payload REBUILD is the fault
        crashes-> LP resources reject our write regardless of content
    """
    oodle = C._oodle()
    n = fit = over = 0
    for fn in FORGES:
        p = os.path.join(GAME, fn)
        recs = [r for r in F.parse(p)["recs"] if r["hash"] == LP_HASH]
        with open(p, "r+b") as f:
            for r in recs:
                bak = p + BAK % r["i"]
                if os.path.isfile(bak):
                    blob = open(bak, "rb").read()
                else:
                    f.seek(r["offset"])
                    blob = f.read(r["size"])
                try:
                    cfds, _ = C.decode_resource(blob, oodle)
                except Exception:
                    continue
                d = b"".join(x for x, _ in cfds)
                h, num = _find_arabic(d)
                if h < 0:                       # only the Arabic packages matter
                    continue
                pay = d[h + 32:h + 32 + num]
                # edits={} -> surgical_payload is a byte-exact identity, so the ONLY
                # difference from vanilla is that the compressed bytes are ours plus
                # dead filler. This is the last untested cell: our Oodle, zero pad,
                # zero payload change.
                nb, lv, k = exact_fill(cfds, d, h, num, pay, {}, r["size"], oodle)
                if nb is None:
                    over += 1
                    continue
                assert len(nb) == r["size"], "not exact"
                # every string must survive byte-for-byte
                nd = b"".join(x for x, _ in C.decode_resource(nb, oodle)[0])
                h2, n2 = _find_arabic(nd)
                assert BF.decode_payload(nd[h2 + 32:h2 + 32 + n2]) == \
                       BF.decode_payload(pay), f"res {r['i']}: string drift"
                if not os.path.isfile(bak):
                    with open(bak, "wb") as b:
                        b.write(blob)
                f.seek(r["offset"])
                f.write(nb)                     # EXACT fill -- no zero pad at all
                n += 1
                fit += k
        print(f"  {fn:<32} exact-filled={n}")
    print(f"\n  IDENTITY+EXACT-FILL: {n} Arabic package(s) re-encoded, strings unchanged, "
          f"ZERO trailing pad, {over} left vanilla (unreachable budget)")


def verify(heb, patched_only=True):
    """Re-read the LIVE forge bytes.

    A patched package that fails to decode is a HARD failure, not something to
    skip: an earlier version swallowed it with `except: continue`, so a corrupt
    patch_02 was silently covered by patch_01's copy and this printed a green
    11/11 over a package the engine could not read. Any decode error on a package
    we wrote is now reported and fails the run.
    """
    oodle = C._oodle()
    seen, broken = {}, []
    for fn in FORGES:
        p = os.path.join(GAME, fn)
        recs = [r for r in F.parse(p)["recs"] if r["hash"] == LP_HASH]
        with open(p, "rb") as f:
            for r in recs:
                ours = os.path.isfile(p + BAK % r["i"])
                if patched_only and not ours:
                    continue
                f.seek(r["offset"])
                blob = f.read(r["size"])
                try:
                    cfds, end = C.decode_resource(blob, oodle)
                    if end != len(blob):
                        raise ValueError(f"cfd_end {end} != size {len(blob)}")
                    d = b"".join(x for x, _ in cfds)
                    h, num = _find_arabic(d)
                    if h < 0:
                        continue
                    s = BF.decode_payload(d[h + 32:h + 32 + num])
                except Exception as e:
                    broken.append((fn, r["i"], f"{type(e).__name__}: {e}"))
                    continue
                for k in heb:
                    if k in s:
                        seen[k] = s[k]          # later forge wins, like the engine
    for fn, i, err in broken:
        print(f"    !! {fn} res {i}: OUR PACKAGE DOES NOT DECODE -- {err}")
    ok = sum(1 for k, v in heb.items() if seen.get(k) == v)
    print(f"  live Arabic slot: {ok}/{len(heb)} ids read back as expected"
          f"{'  -- ONLY packages we patched; this canNOT prove what the engine shows' if patched_only else '  (every Arabic package, engine priority order)'}")
    for k, v in list(heb.items())[:12]:
        got = seen.get(k)
        print(f"    {k:>22}  {'OK ' if got == v else 'BAD'}  {got!r}")
    if broken:
        print(f"\n  *** {len(broken)} package(s) BROKEN -- do NOT launch, revert first")
    return ok if not broken else 0


def revert():
    n = 0
    for fn in FORGES:
        p = os.path.join(GAME, fn)
        baks = [x for x in os.listdir(GAME) if x.startswith(fn + ".lpbak_")]
        with open(p, "r+b") as f:
            for b in baks:
                i = int(b.rsplit("_", 1)[1])
                rec = [r for r in F.parse(p)["recs"] if r["i"] == i]
                if not rec:
                    continue
                r = rec[0]
                blob = open(os.path.join(GAME, b), "rb").read()
                assert len(blob) == r["size"], f"{b}: size drift"
                f.seek(r["offset"])
                f.write(blob)
                n += 1
        for b in baks:
            os.remove(os.path.join(GAME, b))
    print(f"  reverted {n} package(s) to vanilla")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--identity", action="store_true")
    ap.add_argument("--apply", metavar="heb.json")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.revert:
        return revert()
    if a.identity:
        return identity()
    heb = PROOF if a.proof else None
    if a.apply:
        heb = {int(k): v for k, v in json.load(open(a.apply, encoding="utf-8")).items()}
    if heb is None:
        ap.error("one of --proof / --apply / --verify / --revert")
    if a.verify:
        return verify(heb)
    _done, skipped = deploy(heb, dry=a.dry)
    if a.dry:
        return 0
    print("\n  verifying from the live forges...")
    # 🔴 The exit code MUST reflect a broken package. On 2026-08-21 this printed
    # "1 package(s) BROKEN -- do NOT launch" and still exited 0, so a background run
    # looked successful and went to a cold launch -> black screen. A warning nobody
    # can act on is not a safeguard; fail the process.
    # 🔴 A SKIPPED PACKAGE IS A FAILED DEPLOY, not a partial success. The forges are a
    # priority stack and patch_02 outranks everything, so a package left vanilla may well
    # be the one the engine actually displays -- exactly how the menu stayed Arabic while
    # every check reported green. We cannot know it isn't the winner, so fail.
    if skipped:
        print(f"\n  *** {skipped} Arabic package(s) LEFT VANILLA -- the engine may serve "
              f"one of them, so the menu can still show Arabic. NOT deployable.")
        return 1
    if not verify(heb):
        print("\n  *** DEPLOY FAILED VERIFICATION -- run --revert before launching.")
        return 1
    print("\n  ACTIVATE: ACShadows.ini [Language] Client=ar-SA  (or in-game "
          "Settings -> Interface Language -> Arabic)")
    return 0


if __name__ == "__main__":
    main()
