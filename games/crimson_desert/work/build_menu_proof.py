#!/usr/bin/env python3
"""build_menu_proof.py - the Crimson Desert Phase-1 menu proof.

Hijacks the English locale (package group 0020) with a one-build,
multi-mode test: a pure-Latin mount marker, a LOGICAL-vs-VISUAL Hebrew A/B
pair + a 4-letter direction control, the full 27-letter Hebrew alphabet
(glyph coverage), a punctuation/parens/digit/Latin-island paragraph in
both bidi modes, and real semantic translations of common dialog buttons
for redundant coverage across whichever screen actually gets a
screenshot. Also deploys the 4 Hebrew-injected UI fonts (package group
0012) so the glyphs have somewhere to render from.

Every candidate label ("Continue", "New Game", "Settings", "Save", ...)
has MULTIPLE duplicate key instances in the real corpus (different UI
contexts reusing the same English source string) -- we don't know a
priori which specific key ID is the one on the actual title screen, so
every duplicate instance of a chosen label gets its own distinct piece
of proof content. Whichever screen ends up in the user's screenshot,
something legible should be on it.

Usage:
    build_menu_proof.py --deploy    apply the proof (backs up nothing --
                                     caller already backed up _HE_BACKUP/)
    build_menu_proof.py --revert    restore _HE_BACKUP/ verbatim
    build_menu_proof.py --dry-run   print the plan, write nothing
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import cd_container as cd  # noqa: E402
from bidi.algorithm import get_display  # noqa: E402

GAME_ROOT = r"C:\Games\Crimson Desert"
BACKUP_ROOT = os.path.join(GAME_ROOT, "_HE_BACKUP")
LOC_GROUP = "0020"
LOC_FILENAME = "localizationstring_eng.paloc"
FONT_GROUP = "0012"
FONT_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "extract", "fonts_he")
FONT_FILES = ["basefont.ttf", "basefont_eng.ttf", "creditfont.ttf", "minigamefont.ttf"]

MARKER = "ZZ-CD-OK-ZZ"
ALPHABET = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"  # all 27 Hebrew letter-forms
PARAGRAPH_LOGICAL = "בדיקה: (משפט עם NVIDIA ו-12345) — האם זה עובד? כן!"


def visual(s: str) -> str:
    return get_display(s, base_dir="R")


def find_candidates(entries, target_lower: str) -> list:
    return [e.key for e in entries if e.value.strip().lower() == target_lower]


def build_plan(entries) -> dict:
    """Returns {key: new_hebrew_value}."""
    plan: dict = {}

    def take(label: str, n: int) -> list:
        ks = find_candidates(entries, label)
        if len(ks) < n:
            print(f"  [warn] wanted {n} '{label}' keys, found {len(ks)}")
        return ks[:n]

    # -- Continue: mount marker + real "Continue" translation --------
    k = take("continue", 2)
    if len(k) >= 1:
        plan[k[0]] = MARKER
    if len(k) >= 2:
        plan[k[1]] = "המשך"

    # -- Main Menu: redundant Latin marker ----------------------------
    k = take("main menu", 1)
    if k:
        plan[k[0]] = MARKER

    # -- New Game: LOGICAL/VISUAL A/B + direction control -------------
    k = take("new game", 4)
    if len(k) >= 1:
        plan[k[0]] = "שלום"
    if len(k) >= 2:
        plan[k[1]] = visual("שלום")
    if len(k) >= 3:
        plan[k[2]] = "אבגד"
    if len(k) >= 4:
        plan[k[3]] = visual("אבגד")

    # -- Settings: punctuation/parens/digit/Latin-island paragraph -----
    k = take("settings", 3)
    if len(k) >= 1:
        plan[k[0]] = PARAGRAPH_LOGICAL
    if len(k) >= 2:
        plan[k[1]] = visual(PARAGRAPH_LOGICAL)
    if len(k) >= 3:
        plan[k[2]] = "שלום"

    # -- Save: alphabet coverage + a second LOGICAL/VISUAL word pair --
    k = take("save", 4)
    if len(k) >= 1:
        plan[k[0]] = ALPHABET
    if len(k) >= 2:
        plan[k[1]] = "שמור"
    if len(k) >= 3:
        plan[k[2]] = visual("שמור")
    if len(k) >= 4:
        plan[k[3]] = "שלום"

    # -- Semantic dialog-button translations (redundant coverage) -----
    for label, val, n in [
        ("resume", "המשך", 1),
        ("options", "אפשרויות", 1),
        ("confirm", "אישור", 1),
        ("cancel", "ביטול", 1),
        ("back", "חזרה", 1),
        ("apply", "החל", 1),
        ("yes", "כן", 1),
    ]:
        k = take(label, n)
        if k:
            plan[k[0]] = val

    return plan


def deploy(dry_run: bool = False):
    pamt = cd.parse_pamt(os.path.join(GAME_ROOT, LOC_GROUP, "0.pamt"))
    entry = next(e for e in pamt.file_entries if e.path.lower().endswith(LOC_FILENAME))
    raw = cd.read_file(entry)
    entries = cd.parse_paloc(raw)
    print(f"loaded {len(entries)} paloc entries from {LOC_FILENAME}")

    plan = build_plan(entries)
    print(f"\nplan: {len(plan)} keys\n")
    for key, val in plan.items():
        print(f"  {key:>22}  ->  {val!r}")

    if dry_run:
        print("\n[dry-run] nothing written.")
        return

    print("\n--- patching localization (group 0020) ---")
    result = cd.patch_paloc_values(GAME_ROOT, LOC_GROUP, LOC_FILENAME, plan)
    print(f"  success={result.success}  {result.message}")
    if result.errors:
        for e in result.errors:
            print(f"  ! {e}")
    if not result.success:
        raise SystemExit(1)
    print(f"  paz_crc=0x{result.paz_crc:08X} pamt_crc=0x{result.pamt_crc:08X} "
          f"papgt_crc=0x{result.papgt_crc:08X}")

    print("\n--- patching UI fonts (group 0012) ---")
    for fname in FONT_FILES:
        src = os.path.join(FONT_SRC_DIR, fname)
        if not os.path.exists(src):
            print(f"  [skip] {fname}: not found in {FONT_SRC_DIR}")
            continue
        with open(src, "rb") as f:
            data = f.read()
        r = cd.patch_raw_file(GAME_ROOT, FONT_GROUP, fname, data)
        status = "OK" if r.success else "FAIL"
        print(f"  {fname}: {status}  {r.message}")
        if not r.success:
            for e in r.errors:
                print(f"    ! {e}")
            raise SystemExit(1)

    print("\n--- verifying by re-reading the LIVE deployed archive ---")
    pamt2 = cd.parse_pamt(os.path.join(GAME_ROOT, LOC_GROUP, "0.pamt"))
    entry2 = next(e for e in pamt2.file_entries if e.path.lower().endswith(LOC_FILENAME))
    raw2 = cd.read_file(entry2)
    entries2 = cd.parse_paloc(raw2)
    by_key2 = {e.key: e.value for e in entries2}
    mismatches = 0
    for key, expected in plan.items():
        got = by_key2.get(key)
        ok = (got == expected)
        if not ok:
            mismatches += 1
        print(f"  {'OK ' if ok else 'BAD'}  {key:>22}  {got!r}")
    print(f"\n{len(plan) - mismatches}/{len(plan)} verified byte-identical on disk.")
    if mismatches:
        raise SystemExit(1)

    ok_pamt, _, _ = cd.verify_pamt_checksum(os.path.join(GAME_ROOT, LOC_GROUP, "0.pamt"))
    ok_papgt, _, _ = cd.verify_papgt_checksum(os.path.join(GAME_ROOT, "meta", "0.papgt"))
    print(f"\npamt checksum valid: {ok_pamt}   papgt checksum valid: {ok_papgt}")
    print("\nDEPLOYED. Launch the game (English locale, no user action needed)")
    print("and screenshot: main menu, and if reachable Settings + Save/Load.")


def revert():
    pairs = [
        (os.path.join(BACKUP_ROOT, "0020", "0.pamt"), os.path.join(GAME_ROOT, "0020", "0.pamt")),
        (os.path.join(BACKUP_ROOT, "0020", "0.paz"), os.path.join(GAME_ROOT, "0020", "0.paz")),
        (os.path.join(BACKUP_ROOT, "0012", "0.pamt"), os.path.join(GAME_ROOT, "0012", "0.pamt")),
        (os.path.join(BACKUP_ROOT, "0012", "2.paz"), os.path.join(GAME_ROOT, "0012", "2.paz")),
        (os.path.join(BACKUP_ROOT, "0012", "5.paz"), os.path.join(GAME_ROOT, "0012", "5.paz")),
        (os.path.join(BACKUP_ROOT, "meta", "0.papgt"), os.path.join(GAME_ROOT, "meta", "0.papgt")),
    ]
    for src, dst in pairs:
        if not os.path.exists(src):
            print(f"  [skip] no backup at {src}")
            continue
        shutil.copyfile(src, dst)
        print(f"  restored {dst}")
    print("revert complete.")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "--dry-run" in sys.argv:
        deploy(dry_run=True)
    elif "--deploy" in sys.argv:
        deploy(dry_run=False)
    else:
        print(__doc__)
        raise SystemExit(2)
