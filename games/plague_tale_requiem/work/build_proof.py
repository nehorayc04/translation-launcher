#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_proof.py — Phase-1 MENU PROOF for A Plague Tale: Requiem.

Purpose (playbook step 6): prove the WHOLE chain end-to-end before any real
translation — that a Hebrew string, stored our way (logical + LTR-island reverse)
into the Arabic slot tt23.pc, appears in-game:
  * correct RTL order,
  * in a readable font (does BIG_ARABIC / the slot font contain Hebrew glyphs, or
    do we get tofu -> then font injection into the DPC is required),
  * with numbers on the right side, {STR_} tokens intact,
  * no crash.

The strings below are a tiny ENGINEERING SMOKE-TEST FIXTURE (universal UI words +
a number case + a token case), NOT the shippable translation — the real
translation is delegated to a second agent per the project rule. They are chosen
to be reachable in-game fast (Options + Chapter Selection) and to exercise every
render behavior at once.

Usage:
  python build_proof.py                 # non-destructive: writes work/_proof_tt23.pc
  python build_proof.py --deploy        # backs up + writes the game's tt23.pc (+ .IGN)
  python build_proof.py --revert        # restores tt23.pc/.IGN from .he_backup
  python build_proof.py --hebrew f.json # use {key: hebrew_logical} from a JSON file

Deploying overwrites a real (unused-by-you) game file; it is fully reversible via
--revert. Then launch the game, set Options -> Text language = العربية, and check.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_text as T          # noqa: E402
import pt_rtl as R           # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP_SUFFIX = ".he_backup"

# key -> LOGICAL Hebrew (engineering smoke-test fixture; NOT the real translation).
# Covers: plain glyphs, sentence w/ comma, number reversal (chapters), {STR_} token.
PROOF = {
    # --- Options submenu (easy to reach) ---
    "MENU__BACK":              "חזרה",
    "MENU__AUDIO_SETTINGS":    "שמע",
    "MENU__CAMERA_SETTINGS":   "משחקיות",
    "MENU__AUDIO_LANGUAGE":    "שפת הדיבוב",
    "MENU__AUDIO_MONO":        "מונו",
    "MENU__CHAPTER_SELECTION": "בחירת פרק",
    "MENU__CHAPTER_SELECTION_PROMPT":
        "ההתקדמות בפרק אחר תאבד. האם ברצונך לשחק בפרק זה?",
    # --- Chapter list: tests number reversal + roman numerals + Hebrew ---
    "MENU__CHAPTER1":          "I - תחת שמש חדשה",
    "MENU__CHAPTER1_1":        "1 - מסע ארוך",
    "MENU__CHAPTER2":          "II - הבאים החדשים",
    "MENU__CHAPTER2_2":        "2 - אל הזירה",
    # --- HUD prompt: tests a {STR_} button token stays intact ---
    "HUD__BUTTONS_A_CRAFT":    "החזק {STR_CRAFT} כדי לייצר",
}


# Latin-marker diagnostic (playbook 4.3): pure ASCII, written RAW (no RTL transform)
# into visible menu keys. If these APPEAR in-game -> the file IS read and the Latin
# font works, so blank Hebrew = the font lacks Hebrew glyphs (inject). If these are
# ALSO blank -> the game isn't reading tt23.pc (activation / .IGN / packed copy).
LATIN_MARKERS = {
    "MENU__BACK":              "ZZBACK",
    "MENU__AUDIO_SETTINGS":    "ZZAUDIO",
    "MENU__CAMERA_SETTINGS":   "ZZPLAY",
    "MENU__AUDIO_MONO":        "ZZMONO",
    "MENU__CHAPTER_SELECTION": "ZZCHAPTERS",
    "MENU__CHAPTER1":          "ZZ-CH-ONE",
    "MENU__CHAPTER2":          "ZZ-CH-TWO",
}


def build(values: dict[str, str], src_pc: str, out_pc: str, raw: bool = False) -> int:
    overrides = values if raw else {k: R.to_stored(v) for k, v in values.items()}
    return T.write_overrides(src_pc, out_pc, overrides)


def _deploy_one(tid_ext: str, values: dict[str, str], raw: bool = False) -> tuple[bool, int]:
    """Deploy the proof into one game file (e.g. tt23.pc), backing it up first."""
    path = os.path.join(T.TRTEXT_DIR, f"tt{T.SLOT_ID}{tid_ext}")
    if not os.path.exists(path):
        return False, 0
    bak = path + BACKUP_SUFFIX
    if not os.path.exists(bak):
        shutil.copy2(path, bak)      # capture pristine ONCE
    n = build(values, bak, path, raw=raw)   # always build from the pristine backup
    return True, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true", help="write into the game's tt23")
    ap.add_argument("--revert", action="store_true", help="restore tt23 from backup")
    ap.add_argument("--latin", action="store_true",
                    help="deploy RAW Latin markers (diagnostic: is the file read + font ok?)")
    ap.add_argument("--hebrew", help="JSON {key: hebrew_logical} to use instead of the fixture")
    ap.add_argument("--root", default=T.TRTEXT_DIR)
    args = ap.parse_args()
    T.TRTEXT_DIR = args.root

    if args.revert:
        for ext in (T.EXT_LIVE, ".IGN"):
            path = os.path.join(T.TRTEXT_DIR, f"tt{T.SLOT_ID}{ext}")
            bak = path + BACKUP_SUFFIX
            if os.path.exists(bak):
                shutil.copy2(bak, path)
                print(f"reverted {os.path.basename(path)} from backup")
            else:
                print(f"no backup for {os.path.basename(path)} (skipped)")
        return

    raw = args.latin
    values = LATIN_MARKERS if raw else PROOF
    if args.hebrew:
        values = json.load(open(args.hebrew, encoding="utf-8"))
    print(f"{'LATIN-marker' if raw else 'Hebrew'} proof strings: {len(values)}")
    for k, v in list(values.items())[:6]:
        shown = v if raw else R.to_stored(v)
        print(f"   {k}: {v!r}  ->  {shown!r}")

    if args.deploy:
        # deploy to BOTH .pc and .IGN so the proof is conclusive regardless of
        # which variant the engine loads.
        for ext in (T.EXT_LIVE, ".IGN"):
            ok, n = _deploy_one(ext, values, raw=raw)
            tag = f"tt{T.SLOT_ID}{ext}"
            print(f"{'deployed' if ok else 'MISSING '} {tag}: {n} strings"
                  + (f"  (backup: {tag}{BACKUP_SUFFIX})" if ok else ""))
        print("\nNow: launch the game -> Options -> Text language = العربية (Arabic) -> "
              "check the Options + Chapter Selection screens.\nRevert with: python build_proof.py --revert")
    else:
        src = T.lang_path(T.SLOT_ID, root=args.root)
        out = os.path.join(HERE, "_proof_tt23.pc")
        if os.path.exists(src):
            n = build(values, src, out, raw=raw)
            print(f"\nwrote non-destructive proof: {out}  ({n} strings applied)")
        else:
            print(f"\n[note] game file not found ({src}); pass --root or run on the game machine.")
        print("Deploy into the game with:  python build_proof.py --deploy [--latin]")


if __name__ == "__main__":
    main()
