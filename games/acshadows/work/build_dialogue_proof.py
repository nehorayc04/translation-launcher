#!/usr/bin/env python3
"""
build_dialogue_proof.py — Phase 1 ENGLISH-SLOT proof for AC Shadows (v42).

This install is English-text-only (no Arabic in the forges — the in-game Arabic
comes from an unidentified runtime source). So the pragmatic path is the
English-slot hijack: overwrite the English FADE9F44 dialogue → Hebrew, user keeps
Text=en-US. The one open question is BIDI (does the engine RTL-reorder Hebrew in
the LTR English slot?). This proof patches a batch of dialogue lines with a MIX:
  - LOGICAL Hebrew (natural order)     tagged  L:
  - VISUAL Hebrew  (pre-reversed run)  tagged  V:
  - both carry the Latin marker  ZZ-ACS-OK  (proves mount + font, script-independent)
Whichever tag reads correctly in-game tells us the bidi mode. Same-charLen, in-place,
via the PROVEN Phase-0 mechanism (natural re-encode + zero pad, structural-drift guard).

Deploys to DataPC_boot_patch_02.forge (the TU forge that wins by fileID), and mirrors
the same lineIDs in patch_01 + boot so whichever the game loads shows the proof.

    python build_dialogue_proof.py --deploy   # backup + patch + write (game CLOSED, Text=en-US)
    python build_dialogue_proof.py --revert    # restore every .locbak_* sidecar
    python build_dialogue_proof.py --list      # dry-run: show the target lines, no write
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_forge as F  # noqa: E402
import acs_cfd as C  # noqa: E402

G = r"C:\Games\Assassin's Creed Shadows"
FORGES = ["DataPC_boot_patch_02.forge", "DataPC_boot_patch_01.forge", "DataPC_boot.forge"]
LOC = 0xa5b3bea0
TAG = struct.pack("<I", 0xFADE9F44)
MARK = "ZZ-ACS-OK"
LOGICAL = "שלום זה מבחן"   # "שלום זה מבחן"
LEVELS = (4, 6, 7, 8, 9)


def visual(s):
    """reverse each maximal Hebrew run in place; keep ASCII/space order (VISUAL bake)."""
    out = []
    run = []
    for ch in s:
        if "֐" <= ch <= "׿":
            run.append(ch)
        else:
            if run:
                out.extend(reversed(run)); run = []
            out.append(ch)
    if run:
        out.extend(reversed(run))
    return "".join(out)


def fade_records(d):
    """yield (lineID, charLen, text_off) for each FADE9F44 record in decoded bytes."""
    pos = 0
    while True:
        m = d.find(TAG, pos)
        if m < 0:
            break
        pos = m + 4
        if m < 8 or m + 21 > len(d):
            continue
        lid = struct.unpack_from("<Q", d, m - 8)[0]
        clen = struct.unpack_from("<I", d, m + 17)[0]
        if 0 < clen < 4000 and m + 21 + clen * 2 <= len(d):
            yield (lid, clen, m + 21)


def build_edits_from_ids(idfile):
    """Use an explicit lineID list (e.g. June's PROVEN-SAFE ambient-bark set at
    C:/tmp/acs_flood.json — that flood loaded + played with NO crash, unlike the
    full 4,257-line flood which crashed at startup). Barks trigger just by walking
    around the world => guaranteed visible. Assigns L:/V: alternating."""
    import json
    ids = [int(k) for k in json.load(open(idfile, encoding="utf-8")).keys()]
    edits = {}
    for n, lid in enumerate(sorted(ids)):
        edits[lid] = (f"L: {LOGICAL} {MARK}" if n % 2 == 0
                      else f"V: {visual(LOGICAL)} {MARK}")
    return edits


def build_edits(limit=0):
    """Collect dialogue lineIDs across ALL 3 forges (limit=0 => every line) and
    assign each L: (logical) or V: (visual). FADE9F44 records are pure DISPLAY
    text (spoken lines) — not keys/paths — so replacing them is safe even in
    startup-loaded resources (the June crash came from flooding NON-dialogue
    strings). Returns {lineID: hebrew_string}."""
    o = C._oodle()
    edits = {}
    for fname in FORGES:
        p = os.path.join(G, fname)
        info = F.parse(p)
        lr = [r for r in info["recs"] if r["hash"] == LOC][::-1]
        with open(p, "rb") as f:
            for r in lr:
                if r["size"] > 8_000_000 or (limit and len(edits) >= limit):
                    continue
                f.seek(r["offset"]); blob = f.read(r["size"])
                try:
                    cfds, _ = C.decode_resource(blob, o)
                except Exception:
                    continue
                d = b"".join(x for x, _ in cfds)
                if TAG not in d:
                    continue
                for lid, clen, _off in fade_records(d):
                    if lid in edits or clen < 24:
                        continue
                    # alternate logical / visual
                    if len(edits) % 2 == 0:
                        s = f"L: {LOGICAL} {MARK}"
                    else:
                        s = f"V: {visual(LOGICAL)} {MARK}"
                    edits[lid] = s
                    if limit and len(edits) >= limit:
                        break
        print(f"  collected {len(edits)} lineIDs after {fname}", flush=True)
    return edits


def inject_into(data, edits):
    """replace each FADE9F44 target text with the Hebrew padded/truncated to its
    charLen (same byte size). Returns (new_bytes, applied)."""
    out = bytearray(data)
    applied = 0
    for lid, clen, toff in fade_records(data):
        if lid in edits:
            padded = (edits[lid] + " " * clen)[:clen]
            rep = padded.encode("utf-16-le")
            out[toff:toff + clen * 2] = rep
            applied += 1
    return bytes(out), applied


def natural(cfds, oodle, budget):
    for lv in LEVELS:
        blob = b"".join(C.build_cfd(d, ci, oodle, level=lv) for d, ci in cfds)
        if len(blob) <= budget:
            return blob, lv
    return None, None


def deploy(edits, do_write):
    o = C._oodle()
    want = set(edits)
    total = 0
    for name in FORGES:
        p = os.path.join(G, name)
        info = F.parse(p)
        good, tot = F.invariant(info["recs"])
        if good != tot:
            print(f"  {name}: not contiguous ({good}/{tot}) — SKIP")
            continue
        lr = [r for r in info["recs"] if r["hash"] == LOC]
        hit = 0
        with open(p, "rb") as f:
            recs_to_write = []
            for r in lr:
                if r["size"] > 8_000_000:
                    continue
                f.seek(r["offset"]); blob = f.read(r["size"])
                try:
                    cfds, _ = C.decode_resource(blob, o)
                except Exception:
                    continue
                d = b"".join(x for x, _ in cfds)
                present = [lid for lid, _, _ in fade_records(d) if lid in want]
                if not present:
                    continue
                # edit each CFD on its own data
                new_datas = []
                applied = 0
                for (cd, _ci) in cfds:
                    nd, a = inject_into(cd, edits)
                    new_datas.append(nd); applied += a
                if not applied:
                    continue
                recs_to_write.append((r, cfds, new_datas, applied))
        for r, cfds, new_datas, applied in recs_to_write:
            if not do_write:
                hit += applied
                continue
            new_cfds = [C.build_cfd(new_datas[i], ci, o) for i, (_d, ci) in enumerate(cfds)]
            blob = b"".join(new_cfds)
            back, _ = C.decode_resource(blob, o)
            if len(back) != len(cfds) or any(back[i][0] != new_datas[i] for i in range(len(cfds))):
                print(f"    idx {r['i']}: structural drift — SKIP")
                continue
            if len(blob) > r["size"]:
                # try harder levels on the whole resource
                blob2, _lv = natural([(new_datas[i], cfds[i][1]) for i in range(len(cfds))], o, r["size"])
                if blob2 is None:
                    print(f"    idx {r['i']}: re-encode {len(blob)} > {r['size']} — SKIP")
                    continue
                blob = blob2
            padded = blob + b"\x00" * (r["size"] - len(blob))
            bak = f"{p}.locbak_{r['i']}"
            if not os.path.isfile(bak):
                with open(p, "rb") as f:
                    f.seek(r["offset"]); open(bak, "wb").write(f.read(r["size"]))
            with open(p, "r+b") as f:
                f.seek(r["offset"]); f.write(padded)
            hit += applied
        print(f"  {name}: patched {hit} line-instances in {len(recs_to_write)} resources"
              f"{' (dry-run)' if not do_write else ''}")
        total += hit
    return total


def revert():
    import glob
    n = 0
    for name in FORGES:
        p = os.path.join(G, name)
        info = F.parse(p)
        for bak in glob.glob(p + ".locbak_*"):
            i = int(bak.rsplit("_", 1)[1])
            r = info["recs"][i]
            with open(bak, "rb") as f:
                orig = f.read()
            if len(orig) != r["size"]:
                print(f"  {name} idx {i}: size mismatch — SKIP"); continue
            with open(p, "r+b") as f:
                f.seek(r["offset"]); f.write(orig)
            n += 1
    print(f"reverted {n} resource(s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = ALL dialogue lines")
    ap.add_argument("--ids", default=None,
                    help="lineID-list json (use C:/tmp/acs_flood.json = the PROVEN-SAFE bark set)")
    a = ap.parse_args()
    if a.revert:
        return revert()
    edits = build_edits_from_ids(a.ids) if a.ids else build_edits(a.limit)
    print(f"built {len(edits)} edits (L:/V: mix + {MARK} marker)")
    n = deploy(edits, do_write=a.deploy)
    print(f"\n{'DEPLOYED' if a.deploy else 'dry-run'}: {n} line-instances "
          f"across {len(FORGES)} forges")
    if a.deploy:
        print("Next: set ACShadows.ini [Language] Text=en-US, launch, load a save / start "
              "New Game, trigger any dialogue, screenshot a subtitle.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
