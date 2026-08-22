# -*- coding: utf-8 -*-
"""דור 3 review found a real regression class: `gender_ok()` in sm2ne2_nim.py only checks
2nd-person ADDRESSEE markers (את/אתה/אתם) -- a bare 1st-person verb-suffix flip (אוהבת->אוהב)
carries none, so it sails through unguarded. Confirmed on real sentences: 10 lines where a
CANONICALLY FEMALE named character (Rio Morales, Mary Jane Watson) speaking about herself in
first person had her already-correct feminine grammar flipped to masculine.

Each one verified against the full English source + the game's own established plot beats
(MJ covering Peter's mortgage, MJ's "I always come second", Rio's "Miles, I love you..." scenes,
Rio's sigh caption) before being listed here -- not a guess.

This restores the pre-review value in BOTH hebrew.json (so it stays fixed across any future
re-pull/re-merge of the fleet's own output) and the build spine.
"""
import json, os, shutil, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WORK = os.path.join(ROOT, "games", "spiderman2", "work")

# id -> {correct: <the pre-review feminine value that must be restored>}
FIXES = {
    "subtitles:RIO_GP_A2_GAUNTLET_010": None,      # "I can't do this anymore, Miles" -- Rio
    "subtitles:RIO_GP_A2_GAUNTLET_016": None,      # "Miles, PLEASE! I love you..." -- Rio
    "subtitles:RIO_GP_A3_HAUNTS_004": None,        # "GET HERE mijo. I love you." -- Rio
    "subtitles:RIO_NYSQ_HARLEM_MUSICSHOP_005": None,  # "(my little spider) ... (Love you!)" -- Rio
    "dialogue:CCAP_GEN_RIOSIGHS": None,            # Rio's sigh caption
    "subtitles:MARY_GP_A1_QUEENS_034": None,       # "I can cover the mortgage" -- MJ
    "subtitles:MARY_GP_A3_VENOMJ_066": None,       # "Looking for answers, leads--" -- MJ
    "subtitles:MARY_GP_A2_NIGHTMARE_116": None,    # "How do I get to that house..." -- MJ
    "subtitles:SCRMJ_GP_A3_VENOMJ_118": None,      # "I always come second." -- MJ
    "subtitles:SCRMJ_GP_A3_VENOMJ_123": None,      # "Looking for answers, leads--" -- MJ (scream set)
}


def load(name):
    return json.load(open(os.path.join(WORK, name), encoding="utf-8"))


def newest_backup(prefix):
    import glob
    cands = sorted(glob.glob(os.path.join(WORK, f"{prefix}.bak.ne2review.*")))
    if not cands:
        raise SystemExit(f"no ne2review backup found for {prefix}")
    return cands[0]  # the ORIGINAL pre-review snapshot (only one was ever taken this run)


def main():
    hebrew_path = os.path.join(HERE, "hebrew.json")
    hebrew = json.load(open(hebrew_path, encoding="utf-8"))

    spine_files = {"subtitles": "subtitles_he.json", "dialogue": "dialogue_he.json"}
    spines = {k: load(fn) for k, fn in spine_files.items()}

    old_spines = {
        "subtitles": json.load(open(newest_backup("subtitles_he.json"), encoding="utf-8")),
        "dialogue": json.load(open(newest_backup("dialogue_he.json"), encoding="utf-8")),
    }

    applied = 0
    for pid in FIXES:
        kind, key = pid.split(":", 1)
        correct = old_spines[kind][key]
        cur_spine = spines[kind][key]
        cur_heb = hebrew.get(pid, {}).get("he")
        assert cur_spine == cur_heb, f"{pid}: spine/hebrew.json out of sync -- investigate"
        print(f"{pid}\n  wrong (deployed): {cur_spine!r}\n  correct (restore): {correct!r}")
        spines[kind][key] = correct
        hebrew[pid] = {"he": correct, "iss": "ok"}  # re-mark ok so a future re-pull never re-flips it
        applied += 1

    ts = time.strftime("%Y%m%d_%H%M%S")
    for kind, fn in spine_files.items():
        path = os.path.join(WORK, fn)
        shutil.copy2(path, path + f".bak.genderfix.{ts}")
        tmp = path + ".tmp"
        json.dump(spines[kind], open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    tmp = hebrew_path + ".tmp"
    json.dump(hebrew, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, hebrew_path)

    print(f"\napplied {applied} corrections; spine + hebrew.json backups/writes done")


if __name__ == "__main__":
    main()
