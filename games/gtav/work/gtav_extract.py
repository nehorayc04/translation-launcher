#!/usr/bin/env python3
"""gtav_extract.py — pull the UI spine global.gxt2 out of the game and write the
agent's to_translate.json {joaat_hex: english}.

GTA V text lives in NG-encrypted RPF7 archives, so extraction needs a .NET tool that
ships the GTA5 NG keys. Path (recommended): **gtautil** (indilo53/gizzdev) —
    gtautil extractarchive --input "<GAME>\\mods\\update\\update.rpf" --output work\\rpf\\
then the nested american_rel.rpf is itself an RPF7 -> extract it too -> global.gxt2.
This script automates the call if gtautil is on PATH (or at GTAUTIL env), parses the
gxt2 with our own codec, and emits to_translate.json. If gtautil is missing it prints
the exact manual steps (OpenIV/CodeWalker GUI export of global.gxt2) and exits 2.

UI vs subtitles: global.gxt2 == the entire UI/HUD/menu spine (~23,136). MISSION.gxt2 +
per-DLC gxt2 == story subtitles, EXCLUDED here by design (UI-first).
"""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gtav_gxt2 as G  # noqa
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = r"F:\Games\Grand Theft Auto V Legacy"
HANDOFF = os.path.normpath(os.path.join(HERE, "..", "agent_handoff"))
WORK = os.path.join(HERE, "_rpf")
# global.gxt2 path inside update.rpf (American/English LTR slot we hijack).
GXT2_REL = r"x64\data\lang\american_rel.rpf\global.gxt2"


def find_gtautil():
    for c in (os.environ.get("GTAUTIL"), shutil.which("gtautil"),
              os.path.join(GAME, "gtautil.exe"),
              os.path.join(HERE, "..", "tools", "gtautil.exe")):
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return None


def extract_global_gxt2():
    """Return the raw bytes of global.gxt2, or None if extraction couldn't run."""
    gt = find_gtautil()
    if not gt:
        return None
    os.makedirs(WORK, exist_ok=True)
    upd = os.path.join(GAME, "mods", "update", "update.rpf")
    # gtautil can extract a single nested file by relative path.
    subprocess.run([gt, "extractarchive", "--input", upd, "--output", WORK],
                   check=True)
    # walk the extracted tree for global.gxt2 under american_rel
    for root, _, files in os.walk(WORK):
        for f in files:
            if f.lower() == "global.gxt2" and "american" in root.lower():
                return open(os.path.join(root, f), "rb").read()
    return None


def main():
    raw = extract_global_gxt2()
    if raw is None:
        print("gtautil not found / extraction did not run.\n"
              "MANUAL: open mods/update/update.rpf in OpenIV or CodeWalker, export\n"
              f"  {GXT2_REL}\n"
              "to games/gtav/work/_rpf/global.gxt2, then re-run this script (it will\n"
              "read that file directly).", file=sys.stderr)
        # allow a manually-exported file as fallback
        man = os.path.join(WORK, "global.gxt2")
        if os.path.exists(man):
            raw = open(man, "rb").read()
            print("(found a manually-exported global.gxt2 — using it)")
        else:
            sys.exit(2)

    entries = G.read_gxt2(raw)                      # {hash:int -> english}
    out = {("0x%08x" % h): s for h, s in entries.items()}
    os.makedirs(HANDOFF, exist_ok=True)
    dst = os.path.join(HANDOFF, "to_translate.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
    # keep a pristine copy of the source dict for the build step (round-trip base)
    with open(os.path.join(HERE, "global_en.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True)
    print(f"wrote {len(out)} UI strings -> {dst}")


if __name__ == "__main__":
    main()
