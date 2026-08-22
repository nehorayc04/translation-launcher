#!/usr/bin/env python3
"""extract_vanilla.py - pull GTA V **Enhanced**'s vanilla text + fonts out of the
OpenIV-decrypted `mods\\` folder.

Every archive GTA V ships - Legacy *and* Enhanced - is NG-encrypted, and the NG keys
were rotated for the 2025 builds (only OpenIV holds them). So this script does NOT
decrypt anything: it reads the **OPEN** copies that OpenIV writes into `mods\\`, which
the user creates once (see PIPELINE.md "bootstrap").

It **discovers** the paths instead of hard-coding Legacy's, because the Enhanced data
layout is not assumed to match. Legacy's, for reference, is:
    update2.rpf : x64/data/lang/american_rel.rpf          <- the real base table (610 gxt2)
    update.rpf  : x64/patch/data/lang/american_rel.rpf    <- a small patch delta
    update.rpf  : x64/data/cdimages/scaleform_platform_pc.rpf  <- font_lib_efigs_pc.gfx

Outputs (under games/gtav_enhanced/extract/):
    vanilla/<archive>/<nested>/<name>.gxt2   every English gxt2, byte-exact
    fonts/<name>.gfx                         every Scaleform font library
    layout.json                              where each artefact came from

    python work/extract_vanilla.py                     # default Enhanced path
    python work/extract_vanilla.py --game "E:\\Games\\..."
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rpf_lazy as R  # noqa: E402

DEFAULT_GAME = r"E:\Games\Grand Theft Auto V Enhanced"
OUT = os.path.join(ROOT, "extract")

# Font libraries that carry the UI faces. GTA V's native SET_TEXT_FONT draws from the
# Scaleform GFx font libraries, NOT a separate bitmap system - see games/gtav notes.
FONT_NAMES = ("font_lib_efigs.gfx", "font_lib_efigs_pc.gfx", "font_lib_web.gfx")


def find_archives(game):
    """Return the .rpf files under mods\\ that we may need, or [] if not bootstrapped."""
    mods = os.path.join(game, "mods")
    if not os.path.isdir(mods):
        return []
    found = []
    for dirpath, _, files in os.walk(mods):
        for fn in files:
            if fn.lower().endswith(".rpf"):
                found.append(os.path.join(dirpath, fn))
    return sorted(found)


def scan_archive(path):
    """Open an archive and report (rpf, mm, f, lang_entries, font_entries)."""
    rpf, mm, f = R.open_file(path)
    ents = rpf.entries()
    langs = [e for e in ents
             if e.path.lower().endswith(".rpf") and "/lang/" in ("/" + e.path.lower())]
    fonts = [e for e in ents
             if e.path.lower().endswith(".rpf") and "scaleform" in e.path.lower()]
    return rpf, mm, f, langs, fonts


def dump_gxt2(nested, outdir, report, origin):
    """Extract every readable gxt2. A file whose payload is still encrypted (older
    vanilla archives keep per-file encryption even under an OPEN table-of-contents) is
    counted and reported, never fatal - those archives are not what the mod touches."""
    os.makedirs(outdir, exist_ok=True)
    n = skipped = 0
    for e in nested.entries():
        if not e.path.lower().endswith(".gxt2"):
            continue
        try:
            data = nested.read(e)
        except Exception:
            skipped += 1
            continue
        dst = os.path.join(outdir, e.path.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(data)
        n += 1
    if not n:
        try:
            os.removedirs(outdir)
        except OSError:
            pass
    report.append({"kind": "gxt2", "origin": origin, "count": n, "unreadable": skipped,
                   "out": os.path.relpath(outdir, ROOT)})
    return n, skipped


def dump_fonts(nested, outdir, report, origin):
    os.makedirs(outdir, exist_ok=True)
    n = 0
    for e in nested.entries():
        low = e.name.lower()
        if not low.endswith(".gfx") or low not in FONT_NAMES:
            continue
        try:
            data = nested.read(e)
        except Exception:
            continue                      # still-encrypted payload - reported by the caller
        with open(os.path.join(outdir, e.name), "wb") as fh:
            fh.write(data)
        report.append({"kind": "font", "origin": f"{origin}/{e.path}", "name": e.name,
                       "bytes": len(data)})
        n += 1
    return n


# Where Enhanced keeps its text + fonts, verified on this install (2026-08-02). The base
# table is byte-identical in update.rpf and update2.rpf (md5 06e01d53...), so BOTH are
# patched - the game's load order decides which copy wins.
ENHANCED_TABLES = [
    ("update2", "update/update2.rpf", "x64/data/lang/american_rel.rpf"),
    ("update", "update/update.rpf", "x64/data/lang/american_rel.rpf"),
]


def ingest_export(src, out):
    """Ingest an OpenIV **export** (loose files) instead of reading OPEN archives.

    OpenIV exports an outer archive as a folder tree but copies every nested .rpf out
    still NG-encrypted, so the gxt2 have to be exported from inside `american_rel.rpf`
    itself. This takes that folder - any tree containing the .gxt2 (and optionally the
    font .gfx) - and lays it out the way build_hebrew.py/build_oiv.py expect.
    """
    gxt2, fonts = [], []
    for dirpath, _, files in os.walk(src):
        for fn in files:
            low = fn.lower()
            if low.endswith(".gxt2"):
                gxt2.append(os.path.join(dirpath, fn))
            elif low in FONT_NAMES:
                fonts.append(os.path.join(dirpath, fn))
    if not gxt2:
        print(f"no .gxt2 found under {src}")
        return 1

    report = []
    for tag, arch_rel, inner in ENHANCED_TABLES:
        outdir = os.path.join(out, "vanilla", tag, inner.replace("/", "__"))
        os.makedirs(outdir, exist_ok=True)
        for p in gxt2:
            with open(p, "rb") as fh:
                data = fh.read()
            with open(os.path.join(outdir, os.path.basename(p)), "wb") as fh:
                fh.write(data)
        report.append({"kind": "gxt2", "origin": f"{arch_rel}/{inner}",
                       "count": len(gxt2), "unreadable": 0,
                       "out": os.path.relpath(outdir, ROOT)})
        print(f"  gxt2 {len(gxt2):>4}  -> {tag}/{inner}")

    if fonts:
        fdir = os.path.join(out, "fonts")
        os.makedirs(fdir, exist_ok=True)
        for p in fonts:
            with open(p, "rb") as fh:
                data = fh.read()
            with open(os.path.join(fdir, os.path.basename(p)), "wb") as fh:
                fh.write(data)
            report.append({"kind": "font", "origin": p, "name": os.path.basename(p),
                           "bytes": len(data)})
        print(f"  font {len(fonts):>4}  -> fonts/")
    else:
        print("  font    0  (none in the export - fonts can be added later)")

    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "layout.json"), "w", encoding="utf-8") as fh:
        json.dump({"game": DEFAULT_GAME, "source": "openiv-export", "items": report},
                  fh, ensure_ascii=False, indent=2)
    print(f"\nTOTAL gxt2={len(gxt2)} (x{len(ENHANCED_TABLES)} tables)  fonts={len(fonts)}")
    return 0


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--out", default=OUT,
                    help="output dir (override to validate against another install)")
    ap.add_argument("--from-export", default=None, metavar="DIR",
                    help="ingest an OpenIV export folder of loose .gxt2/.gfx instead of "
                         "walking OPEN archives")
    a = ap.parse_args()
    OUT = os.path.abspath(a.out)

    if a.from_export:
        print(f"ingesting OpenIV export: {a.from_export}")
        return ingest_export(a.from_export, OUT)

    archives = find_archives(a.game)
    if not archives:
        print("NOT BOOTSTRAPPED - no mods\\ folder found under:")
        print("   ", a.game)
        print("\nEvery shipped archive is NG-encrypted and the keys are OpenIV-only, so the")
        print("OPEN copies have to be created once with OpenIV + ZEnhanced + OpenRPF.")
        print("See games/gtav_enhanced/PIPELINE.md -> 'One-time bootstrap'.")
        return 2

    print(f"game    : {a.game}")
    print(f"archives: {len(archives)} under mods\\")
    report, tot_gxt2, tot_font = [], 0, 0

    for path in archives:
        rel = os.path.relpath(path, a.game)
        try:
            enc, ec, nl = R.encryption_of(open(path, "rb").read(16))
        except Exception as e:
            print(f"  !! {rel}: {e}")
            continue
        if enc != "OPEN":
            print(f"  -- {rel}: {enc}-encrypted, skipped (OpenIV must rewrite it as OPEN)")
            continue
        try:
            rpf, mm, f, langs, fonts = scan_archive(path)
        except Exception as e:
            print(f"  !! {rel}: {e}")
            continue
        tag = os.path.splitext(os.path.basename(path))[0]
        print(f"  == {rel}  entries={rpf.entry_count} lang={len(langs)} scaleform={len(fonts)}")

        for e in langs:
            if "american" not in e.path.lower():
                continue
            try:
                nested = rpf.nested(e.path)
            except Exception as ex:
                print(f"      !! {e.path}: {ex}")
                continue
            outdir = os.path.join(OUT, "vanilla", tag, e.path.replace("/", "__"))
            n, skipped = dump_gxt2(nested, outdir, report, f"{rel}/{e.path}")
            tot_gxt2 += n
            note = f"  ({skipped} still-encrypted, skipped)" if skipped else ""
            print(f"      gxt2 {n:>4}  <- {e.path}{note}")

        for e in fonts:
            try:
                nested = rpf.nested(e.path)
            except Exception:
                continue
            n = dump_fonts(nested, os.path.join(OUT, "fonts"), report, f"{rel}/{e.path}")
            tot_font += n
            if n:
                print(f"      font {n:>4}  <- {e.path}")

        mm.close()
        f.close()

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "layout.json"), "w", encoding="utf-8") as fh:
        json.dump({"game": a.game, "items": report}, fh, ensure_ascii=False, indent=2)
    print(f"\nTOTAL gxt2={tot_gxt2}  fonts={tot_font}  -> {os.path.relpath(OUT, ROOT)}")
    return 0 if tot_gxt2 else 1


if __name__ == "__main__":
    sys.exit(main())
