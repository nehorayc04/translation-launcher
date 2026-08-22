"""Hogwarts Legacy Hebrew groundwork — Phase-1 menu proof.

Patches a small handful of MAIN-arAE.bin (Arabic-slot UI strings) with test
markers + a few short, well-known Hebrew UI words, packs them into an
override pakchunk (repak, V11, mount "../../../"), and deploys it to the
game's `~mods` folder — the standard, non-destructive Hogwarts Legacy mod
mechanism (confirmed: additive pakchunk in Phoenix/Content/Paks/~mods,
never touches the shipped pakchunk0).

This is a TECHNICAL PROBE, not translation work: a Latin marker proves the
override pak actually loads and wins priority; the Hebrew words prove/refute
whether Unreal's native ICU bidi + the Arabic-slot font already handle Hebrew,
or whether font injection is needed (per the project's standard groundwork
playbook, universal/NEW_GAME_GROUNDWORK_PLAYBOOK.md).

Usage:
    python build_menu_proof.py --deploy   # write pakchunk111..._P.pak into ~mods
    python build_menu_proof.py --revert   # delete it
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hl_bin  # noqa: E402

GAME_ROOT = Path(r"E:\SteamLibrary\steamapps\common\Hogwarts Legacy")
PAKS_DIR = GAME_ROOT / "Phoenix" / "Content" / "Paks"
MODS_DIR = PAKS_DIR / "~mods"
MOD_PAK_NAME = "pakchunk111-WindowsNoEditor_P.pak"

REPAK_EXE = HERE.parent / "tools" / "repak.exe"

# key -> test value written into the Arabic slot (MAIN-arAE.bin)
PROOF_PATCHES = {
    "Menu_Options": "ZZ-HL-PIPELINE-OK-ZZ",   # pure Latin marker: proves override pak loads + wins priority
    "Settings_Brightness": "בהירות",           # real Hebrew UI word ("Brightness")
    "Menu_Subtitles": "כתוביות",                # real Hebrew UI word ("Subtitles")
    "Menu_LanguageSelect": "בחר שפה",           # real Hebrew UI phrase ("Select Language") — the screen the user opens
}


def build_pak(out_pak: Path):
    main_bin_src = PAKS_DIR / "pakchunk0-WindowsNoEditor.pak"
    if not main_bin_src.exists():
        raise SystemExit(f"pak not found: {main_bin_src}")

    work = HERE / "_proof_stage"
    if work.exists():
        shutil.rmtree(work)
    stage_root = work / "Phoenix" / "Content" / "Localization" / "WIN64"
    stage_root.mkdir(parents=True)

    # extract the live MAIN-arAE.bin straight from the game's own pak (not a stale copy)
    subprocess.run(
        [str(REPAK_EXE), "get", str(main_bin_src), "Phoenix/Content/Localization/WIN64/MAIN-arAE.bin"],
        check=True,
        stdout=open(stage_root / "MAIN-arAE.bin", "wb"),
    )

    raw = (stage_root / "MAIN-arAE.bin").read_bytes()
    entries = hl_bin.decode(raw)
    missing = [k for k in PROOF_PATCHES if k not in entries]
    if missing:
        raise SystemExit(f"proof keys not found in MAIN-arAE.bin: {missing}")
    for k, v in PROOF_PATCHES.items():
        print(f"  patch {k!r}: {entries[k]!r} -> {v!r}")
        entries[k] = v

    (stage_root / "MAIN-arAE.bin").write_bytes(hl_bin.encode(entries))

    pak_dir_name = out_pak.stem  # repak wants a folder matching the desired pak name convention
    pack_input = work.parent / f"_pack_input_{pak_dir_name}"
    if pack_input.exists():
        shutil.rmtree(pack_input)
    shutil.copytree(work, pack_input)

    subprocess.run(
        [str(REPAK_EXE), "pack", str(pack_input), str(out_pak), "--version", "V11"],
        check=True,
    )
    shutil.rmtree(work)
    shutil.rmtree(pack_input)


def deploy():
    MODS_DIR.mkdir(parents=True, exist_ok=True)
    out_pak = MODS_DIR / MOD_PAK_NAME
    build_pak(out_pak)
    print(f"deployed: {out_pak}  ({out_pak.stat().st_size} bytes)")
    print("Now in-game: Settings -> Select Language -> Arabic (العربية), then re-open Settings.")


def revert():
    out_pak = MODS_DIR / MOD_PAK_NAME
    if out_pak.exists():
        out_pak.unlink()
        print(f"removed: {out_pak}")
    else:
        print("nothing to remove")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    if args.revert:
        revert()
    elif args.deploy:
        deploy()
    else:
        ap.print_help()
