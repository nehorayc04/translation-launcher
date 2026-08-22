"""FH6 Phase-1 menu proof — closes mount / bidi / font / layout in ONE launch.

Hijacks the **EN ("English US")** string-table slot — the user's choice, for
ZERO-ACTION activation: English is the default, so a player who never touched the
language setting gets Hebrew on the next launch with nothing to configure.

English is NOT lost: **GB ("English UK") is left pristine** and differs from EN in
only 7,346 of 58,179 values (12.6 %) — every other language differs 77-90 % — so
"Settings -> Language -> English UK" gives a 87.4 %-identical English experience.
That is the escape hatch, and `IDS_LanguageSelect_GB` is deliberately NOT patched
so the row stays findable while the UI is in Hebrew.

⚠️ The language choice lives in a BINARY GDK profile blob
(`…\\MicrosoftStore\\RUNE\\Forza Horizon 6 […]\\SaveGames\\…\\C_ProfileData`) —
same class as GoWR's `userpreferences`. Do NOT edit it; it cannot be flipped
safely from a launcher.

All bidi/layout probes sit on the LANGUAGE-SELECT list (`Settings -> Language`),
which is reachable from the main menu — the pause menu needs a loaded save.
Rows are labelled with a leading DIGIT, which renders even when every Hebrew
letter is tofu:  **odd digit = stored LOGICAL, even digit = stored VISUAL.**

    python build_menu_proof.py --deploy    (backs up EN.zip -> EN.zip.he_backup)
    python build_menu_proof.py --verify    (reads the patch back OUT of the game)
    python build_menu_proof.py --revert
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fh6_str as S
import fh6_zip as Z
import fh6_rtl as R

GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
SLOT = os.path.join(GAME, "media", "Stripped", "StringTables", "EN.zip")
BACKUP = SLOT + ".he_backup"
SIDECAR = SLOT + ".he_backup.json"

ALEF_BET = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"
LAYOUT = 'בדיקה: "פורזה" (3 מתוך 5) — 240 קמ"ש, Forza Horizon 6. סוף!'

# (table, IDS id) -> (mode, text)   mode: raw | visual | logical
PLAN = {
    # --- MOUNT: pure Latin, so it renders even with a font that has no Hebrew
    ("HelpButtons", "IDS_Select"):                 ("raw",     "ZZ-FH6-OK-ZZ"),
    ("HelpButtons", "IDS_Accept"):                 ("raw",     "ZZ-FH6-2-ZZ"),
    # 4 boxes here = the text reached the renderer even with no Hebrew glyphs
    ("HelpButtons", "IDS_Back"):                   ("visual",  "שלום"),

    # === EVERYTHING BELOW IS ON  Settings -> Language  (one screenshot) =========
    # Our slot, so the player can see which row they are on.
    ("InGame",      "IDS_LanguageSelect_EN"):      ("logical", "עברית"),
    ("InGame",      "IDS_LanguageSelect_ScreenReader_EN"): ("raw", "Hebrew"),

    # BIDI A/B — the SAME string stored both ways, labelled by a leading DIGIT
    # (digits are real glyphs, so this is readable through total tofu):
    #   odd  = LOGICAL   even = VISUAL
    #   digit on the RIGHT on the ODD row  -> engine does bidi   -> store LOGICAL
    #   digit on the RIGHT on the EVEN row -> engine does none   -> store VISUAL
    ("InGame",      "IDS_LanguageSelect_Default"): ("logical", "1 שלום"),
    ("InGame",      "IDS_LanguageSelect_CZ"):      ("visual",  "2 שלום"),
    # LAYOUT: quotes, parens, digits and a Latin island, again both ways
    ("InGame",      "IDS_LanguageSelect_DK"):      ("logical", "3 " + LAYOUT),
    ("InGame",      "IDS_LanguageSelect_EL"):      ("visual",  "4 " + LAYOUT),
    # repeats, so ANY window of the scrolling list carries a full A/B pair
    ("InGame",      "IDS_LanguageSelect_FI"):      ("logical", "5 שלום"),
    ("InGame",      "IDS_LanguageSelect_HU"):      ("visual",  "6 שלום"),
    ("InGame",      "IDS_LanguageSelect_NL"):      ("logical", "7 שלום"),
    ("InGame",      "IDS_LanguageSelect_NO"):      ("visual",  "8 שלום"),
    ("InGame",      "IDS_LanguageSelect_PL"):      ("logical", "9 שלום"),
    # FONT: all 27 letters on one row
    ("InGame",      "IDS_LanguageSelect_TR"):      ("visual",  ALEF_BET),

    # NOTE: IDS_LanguageSelect_GB is deliberately LEFT ALONE — "English UK" must
    # stay readable so the player can always get English back.
}


def render(mode: str, text: str) -> str:
    return {"raw": lambda s: s, "visual": R.to_visual, "logical": R.to_logical}[mode](text)


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while (b := f.read(1 << 20)):
            h.update(b)
    return h.hexdigest()


def build(src: str, dst: str) -> int:
    entries, payload = Z.read(src)
    want: dict[str, dict[str, str]] = {}
    for (tbl, idn), (mode, text) in PLAN.items():
        want.setdefault(tbl + ".str", {})[idn] = render(mode, text)

    replace, applied, missing = {}, 0, []
    for fname, edits in want.items():
        raw = payload.get(fname)
        if not raw:
            missing.append(fname)
            continue
        have = S.parse(raw).as_dict()
        real = {k: v for k, v in edits.items() if k in have}
        missing += [f"{fname}:{k}" for k in edits if k not in have]
        replace[fname] = S.edit(raw, real)
        applied += len(real)

    Z.rebuild(src, dst, replace)
    if missing:
        print("  !! not found:", missing)
    return applied


def verify(path: str) -> None:
    _, payload = Z.read(path)
    ok = bad = 0
    for (tbl, idn), (mode, text) in PLAN.items():
        d = S.parse(payload[tbl + ".str"]).as_dict()
        want = render(mode, text)
        good = d.get(idn) == want
        ok += good
        bad += not good
        print(f"  {'OK ' if good else 'BAD'} {tbl}/{idn} = {d.get(idn)!r}")
    print(f"verify: {ok} ok, {bad} bad")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(SLOT):
        sys.exit(f"slot not found: {SLOT}")

    if a.revert:
        if not os.path.exists(BACKUP):
            sys.exit("no backup to revert")
        meta = json.load(open(SIDECAR)) if os.path.exists(SIDECAR) else {}
        cur = sha(SLOT)
        if meta.get("deployed_sha") and cur != meta["deployed_sha"]:
            sys.exit("REFUSING: GB.zip is not what we deployed (game updated?) — "
                     "delete the backup by hand if you are sure")
        shutil.copy2(BACKUP, SLOT)
        for p in (BACKUP, SIDECAR):
            if os.path.exists(p):
                os.remove(p)
        print("reverted GB.zip from backup")
        return

    if a.verify:
        verify(SLOT)
        return

    # --- build (always from the PRISTINE copy, never from what is deployed) ---
    src = BACKUP if os.path.exists(BACKUP) else SLOT
    tmp = SLOT + ".tmp"
    n = build(src, tmp)
    print(f"built {n} edits -> {os.path.getsize(tmp):,} bytes")

    if not a.deploy:
        print("(dry run — pass --deploy to install)")
        os.remove(tmp)
        return

    if not os.path.exists(BACKUP):
        shutil.copy2(SLOT, BACKUP)
        print(f"backed up -> {os.path.basename(BACKUP)}")
    orig = sha(BACKUP)
    os.replace(tmp, SLOT)
    json.dump({"original_sha": orig, "deployed_sha": sha(SLOT)},
              open(SIDECAR, "w"), indent=1)
    print("DEPLOYED to", SLOT)
    verify(SLOT)


if __name__ == "__main__":
    main()
