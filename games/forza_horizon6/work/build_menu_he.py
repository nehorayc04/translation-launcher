"""Forza Horizon 6 — the REAL Hebrew menu (front end + options + button prompts).

`build_menu_proof.py` was the gate proof: a digit-labelled A/B ladder that settled
mount and bidi. Those gates are closed (bidi = VISUAL, eight rows unanimous), so
this ships actual Hebrew instead of probes.

Every label was decided against the game's OWN reference languages rather than
from the English alone, which repeatedly mattered:

  * "Video"          -> ru `Графика`, pl `Obraz`  => the DISPLAY category, so
                        תצוגה — `וידאו` would have been wrong.
  * "Hud & Gameplay" -> es `Interfaz y experiencia de juego`, pl `Ekran i rozgrywka`
                        => ממשק ומשחקיות.
  * "Resume"         -> ru `Продолжить`, es `Continuar` => המשך, same as Continue.
  * "Accept"/"Confirm" stay DISTINCT in every language (Принять/Подтвердить,
                        Annehmen/Bestätigen) => קבל / אשר, never one word for both.
  * button prompts are imperative in every reference language (Выбрать,
                        Auswählen, Seleziona, Wybierz) => imperative in Hebrew too.

Stored **VISUAL** (pre-reversed) — the engine draws in storage order and runs no
bidi. One row is deliberately stored LOGICAL with a Latin tag: it must render
MIRRORED. That single control turns "this looks right" into "exactly one of these
can be right, and it is the other one", and its Latin tag makes a stale deploy
impossible to mistake for a fix.

Language NAMES on the picker are deliberately left in their own scripts (Русский,
日本語 ...) — that is what a language picker is for.

    python build_menu_he.py                 # dry run + QA
    python build_menu_he.py --deploy
    python build_menu_he.py --verify        # read back OUT of the game
    python build_menu_he.py --revert
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fh6_rtl as R                                                 # noqa: E402
import fh6_str as S                                                 # noqa: E402
import fh6_zip as Z                                                 # noqa: E402

GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
SLOT = os.path.join(GAME, "media", "Stripped", "StringTables", "EN.zip")
BACKUP = SLOT + ".he_backup"
SIDECAR = SLOT + ".he_backup.json"

# (table, id) -> Hebrew.  Stored VISUAL unless listed in LOGICAL_CONTROL below.
HE = {
    # ---- main menu -------------------------------------------------------
    ("Main", "IDS_MainMenuContinue"):            "המשך",
    ("Main", "IDS_MainMenuOptions"):             "אפשרויות",
    ("Main", "IDS_MainMenuAccessibility"):       "נגישות",
    ("Main", "IDS_MainMenuExit"):                "יציאה",
    ("Main", "IDS_MainMenuSignOut"):             "התנתקות",

    # ---- options screen --------------------------------------------------
    ("Main", "IDS_Options_Title"):               "אפשרויות",
    ("Main", "IDS_Options_AudioOptions"):        "שמע",
    ("Main", "IDS_Options_VideoOptions"):        "תצוגה",
    ("Main", "IDS_Options_GameOptions"):         "פקדים",
    ("Main", "IDS_Options_LanguageSelect"):      "בחירת שפה",
    ("Main", "IDS_Options_BenchmarkMode"):       "מצב מדידת ביצועים",

    ("ScreenTitles", "IDS_GameOptions"):             "הגדרות",
    ("ScreenTitles", "IDS_AudioOptions"):            "שמע",
    ("ScreenTitles", "IDS_VideoOptions"):            "תצוגה",
    ("ScreenTitles", "IDS_ControllerOptions"):       "פקדים",
    ("ScreenTitles", "IDS_Difficulty"):              "רמת קושי",
    ("ScreenTitles", "IDS_AccessibilitySetup"):      "נגישות",
    ("ScreenTitles", "IDS_LanguageSelect"):          "בחירת שפה",
    ("ScreenTitles", "IDS_AdvancedGraphicsOptions"): "גרפיקה וביצועים",
    ("ScreenTitles", "IDS_AdvancedControllerOptions"): "פקדים מתקדמים",

    ("TiledMenus", "IDS_Options_TileText_Audio"):          "שמע",
    ("TiledMenus", "IDS_Options_TileText_Video"):          "תצוגה",
    ("TiledMenus", "IDS_Options_TileText_LanguageSelect"): "בחירת שפה",
    ("TiledMenus", "IDS_Options_TileText_TeamCredits"):    "קרדיטים",
    ("TiledMenus", "IDS_Options_TileText_VersionInfo"):    "פרטי גרסה",
    ("TiledMenus", "IDS_Options_TileText_Controls"):       "בחרו פריסה אחרת",
    ("TiledMenus", "IDS_Options_TileText_Accessibility"):  "שפרו את חוויית המשחק",
    ("TiledMenus", "IDS_Options_TileText_Hud"):            "כוונון הגדרות המשחק",
    ("TiledMenus", "IDS_Options_TileTitle_Accessibility"): "נגישות",
    ("TiledMenus", "IDS_Options_TileTitle_Controls"):      "הגדרות פקדים",
    ("TiledMenus", "IDS_Options_TileTitle_Difficulty"):    "קושי והגדרות",
    ("TiledMenus", "IDS_Options_TileTitle_Hud"):           "ממשק ומשחקיות",

    # ---- pause menu ------------------------------------------------------
    ("PauseMenu", "IDS_CatTitle_Campaign"):   "קמפיין",
    ("PauseMenu", "IDS_CatTitle_Online"):     "מקוון",
    ("PauseMenu", "IDS_CatTitle_Store"):      "חנות",
    ("PauseMenu", "IDS_TileTitle_Settings"):  "הגדרות",

    # ---- the always-visible button prompt bar ----------------------------
    ("HelpButtons", "IDS_Select"):          "בחר",
    ("HelpButtons", "IDS_Accept"):          "קבל",
    ("HelpButtons", "IDS_Confirm"):         "אשר",
    ("HelpButtons", "IDS_Back"):            "חזור",
    ("HelpButtons", "IDS_Cancel"):          "בטל",
    ("HelpButtons", "IDS_Apply"):           "החל",
    ("HelpButtons", "IDS_Yes"):             "כן",
    ("HelpButtons", "IDS_No"):              "לא",
    ("HelpButtons", "IDS_Resume"):          "המשך",
    ("HelpButtons", "IDS_Quit"):            "יציאה",
    ("HelpButtons", "IDS_Continue"):        "המשך",
    ("HelpButtons", "IDS_LanguageSelect"):  "בחירת שפה",
    ("HelpButtons", "IDS_Advanced"):        "מתקדם",
    ("HelpButtons", "IDS_Basic"):           "בסיסי",

    # ---- our slot's own row on the language picker -----------------------
    ("InGame", "IDS_LanguageSelect_EN"):    "עברית",
}

# Deliberately stored the WRONG way round, with a Latin tag: it MUST render
# mirrored. Keeps a stale deploy from ever looking like a working one.
LOGICAL_CONTROL = {("InGame", "IDS_LanguageSelect_CZ"): "ZZ-LOG שלום"}

# Screen-reader strings are read aloud, not drawn — leave them Latin.
RAW = {("InGame", "IDS_LanguageSelect_ScreenReader_EN"): "Hebrew"}

NIQQUD = re.compile(r"[\u0591-\u05BD\u05BF-\u05C7]")
HEBREW_RE = re.compile(r"[\u05D0-\u05EA]")
TOKEN = re.compile(r"\[[A-Z0-9_:{}]+\]|\{\d+\}|<[^>]+>|%[sd]")


def qa(pristine: dict) -> bool:
    """Refuse to ship a defect. Every rule here has bitten a game in this repo."""
    bad = []
    for (tbl, idn), he in HE.items():
        d = S.parse(pristine[tbl + ".str"]).as_dict()
        en = d.get(idn)
        if en is None:
            bad.append(f"{tbl}/{idn}: id does not exist")
            continue
        if NIQQUD.search(he):
            bad.append(f"{tbl}/{idn}: niqqud")
        if not HEBREW_RE.search(he):
            bad.append(f"{tbl}/{idn}: no Hebrew")
        if he.strip() == en.strip():
            bad.append(f"{tbl}/{idn}: still English")
        for ch in he:
            n = unicodedata.name(ch, "")
            if ch.isalpha() and not n.startswith("HEBREW"):
                bad.append(f"{tbl}/{idn}: foreign letter {ch!r}")
                break
        if sorted(TOKEN.findall(en)) != sorted(TOKEN.findall(he)):
            bad.append(f"{tbl}/{idn}: token multiset changed")
        if he != he.strip():
            bad.append(f"{tbl}/{idn}: stray edge whitespace")
        # a label far longer than the English risks clipping a fixed-width tile
        if len(he) > max(14, len(en) * 1.6):
            bad.append(f"{tbl}/{idn}: {len(he)} chars vs English {len(en)}")
    seen = {}
    for k, v in HE.items():
        seen.setdefault(v, []).append(k)
    for k in bad:
        print("  QA FAIL:", k)
    print(f"QA: {len(HE)} strings, {len(bad)} defects, "
          f"{len(seen)} distinct Hebrew values")
    return not bad


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while (b := f.read(1 << 20)):
            h.update(b)
    return h.hexdigest()


def wanted() -> dict:
    """{table.str: {id: stored bytes}} — the exact thing that goes on disk."""
    out: dict[str, dict[str, str]] = {}
    for (tbl, idn), he in HE.items():
        out.setdefault(tbl + ".str", {})[idn] = R.to_visual(he)
    for (tbl, idn), he in LOGICAL_CONTROL.items():
        out.setdefault(tbl + ".str", {})[idn] = R.to_logical(he)
    for (tbl, idn), s in RAW.items():
        out.setdefault(tbl + ".str", {})[idn] = s
    return out


def build(src: str, dst: str) -> int:
    _, pay = Z.read(src)
    if not qa(pay):
        sys.exit("REFUSING to build: QA failed")
    replace, applied, missing = {}, 0, []
    for fname, edits in wanted().items():
        raw = pay.get(fname)
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
    _, pay = Z.read(path)
    ok = bad = 0
    for fname, edits in wanted().items():
        d = S.parse(pay[fname]).as_dict()
        for idn, want in edits.items():
            good = d.get(idn) == want
            ok += good
            bad += not good
            if not good:
                print(f"  BAD {fname}/{idn} = {d.get(idn)!r} (want {want!r})")
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
        if meta.get("deployed_sha") and sha(SLOT) != meta["deployed_sha"]:
            sys.exit("REFUSING: EN.zip is not what we deployed (game updated?)")
        shutil.copy2(BACKUP, SLOT)
        for p in (BACKUP, SIDECAR):
            if os.path.exists(p):
                os.remove(p)
        print("reverted EN.zip from backup")
        return

    if a.verify:
        verify(SLOT)
        return

    src = BACKUP if os.path.exists(BACKUP) else SLOT      # ALWAYS from pristine
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
