#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_hebrew.py — LOCAL build of the Hogwarts Hebrew mod (no publish).

Extract the live enUS skeleton -> decode -> merge work/hebrew.json (LOGICAL, strip the
MAIN:/SUB: prefix, keep locale-only extras untouched) -> hl_bin.encode -> repak V11 ->
deploy pakchunk111-WindowsNoEditor_P.pak into the game's ~mods.

The ARABIC (arAE) slot is deliberately LEFT UNTOUCHED (user decision, 2026-08-09): the
Hebrew rides ONLY the English text slot, so a player must explicitly pick
Settings -> Text Language -> English to see it (correct clock/number formatting, correct
boot logo); leaving Text Language unset/Arabic shows the game's own vanilla Arabic.

    python build_hebrew.py                # build + deploy (enUS only)
    python build_hebrew.py --also-arabic  # + ALSO write Hebrew into MAIN/SUB-arAE.bin (testing)
    python build_hebrew.py --revert       # remove the mod pak
"""
import argparse, json, subprocess, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "universal"))
import hl_bin
import text_norm   # IRON RULE: normalize every long dash -> plain hyphen at the build gate

HERE = Path(__file__).resolve().parent
GAME = Path(r"E:\SteamLibrary\steamapps\common\Hogwarts Legacy")
PAKS = GAME / "Phoenix" / "Content" / "Paks"
SRC_PAK = PAKS / "pakchunk0-WindowsNoEditor.pak"
MODS = PAKS / "~mods"
MOD_PAK = MODS / "pakchunk111-WindowsNoEditor_P.pak"
REPAK = HERE.parent / "tools" / "repak.exe"
STAGE = HERE / "_stage"
WIN64 = "Phoenix/Content/Localization/WIN64"


def repak(*args):
    r = subprocess.run([str(REPAK), *args], capture_output=True, text=True,
                       cwd=str(HERE.parent / "tools"))   # cwd so oo2core_9 dll is found
    if r.returncode != 0:
        sys.exit(f"repak {args[0]} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def build(also_arabic=False):
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / WIN64).mkdir(parents=True)
    locales = ["enUS"] + (["arAE"] if also_arabic else [])
    # 1. extract fresh skeletons for every target locale
    ex = HERE / "_extract"
    if ex.exists():
        shutil.rmtree(ex)
    ex.mkdir()
    idx_args = []
    for loc in locales:
        idx_args += ["-i", f"{WIN64}/MAIN-{loc}.bin", "-i", f"{WIN64}/SUB-{loc}.bin"]
    repak("unpack", str(SRC_PAK), "-o", str(ex), "-f", *idx_args)
    he = json.loads((HERE / "hebrew.json").read_text(encoding="utf-8"))
    for loc in locales:
        for kind in ("MAIN", "SUB"):
            raw = (ex / WIN64 / f"{kind}-{loc}.bin").read_bytes()
            d = hl_bin.decode(raw)                       # authoritative ordered dict
            pref = kind + ":"
            merged = 0
            for k, v in he.items():
                if k.startswith(pref):
                    bare = k[len(pref):]
                    if bare in d:                        # never invent keys / drop locale-only extras
                        d[bare] = v; merged += 1
            # IRON RULE: force plain hyphen on EVERY value (our Hebrew + any untouched extras)
            dfix = 0
            for kk, vv in d.items():
                nv = text_norm.normalize_dashes(vv)
                if nv != vv:
                    d[kk] = nv; dfix += 1
            out = hl_bin.encode(d)
            (STAGE / WIN64 / f"{kind}-{loc}.bin").write_bytes(out)
            print(f"{kind}-{loc}: {len(d)} entries, merged {merged} Hebrew, dash-normalized {dfix} -> {len(out):,} bytes")
    # 2. pack V11 (mount ../../../)
    MODS.mkdir(exist_ok=True)
    if MOD_PAK.exists():
        MOD_PAK.unlink()
    repak("pack", str(STAGE), str(MOD_PAK), "--version", "V11", "--mount-point", "../../../")
    print(f"packed -> {MOD_PAK}  ({MOD_PAK.stat().st_size:,} bytes)")
    # 3. verify by re-reading the pak we just wrote
    print(repak("list", str(MOD_PAK)).strip())
    if also_arabic:
        print("\n✅ DEPLOYED to enUS + arAE (testing build). In-game: Settings -> Language -> English OR Arabic.")
    else:
        print("\n✅ DEPLOYED. In-game: Settings -> Language -> English. Audio stays English.")


def revert():
    if MOD_PAK.exists():
        MOD_PAK.unlink(); print(f"removed {MOD_PAK}")
    else:
        print("nothing to revert")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--also-arabic", action="store_true")
    a = ap.parse_args()
    revert() if a.revert else build(also_arabic=a.also_arabic)
