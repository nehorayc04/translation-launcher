# -*- coding: utf-8 -*-
"""Reverts a handful of confirmed MEANING regressions from the New-Era phrasing QA (2026-07-31),
found by manually auditing a 180-entry sample of onscreens phrasing fixes (EN vs OLD vs NEW):

  * "Fire Extinguisher" -> "כבאית" (= fire TRUCK) or "מכבי אש" (= firefighters, people) at
    different pks — neither means the physical object, and they're inconsistent with each other.
    Revert to the pre-fix "כיבוי אש" (imperfect but not confusingly wrong) at every instance.
  * "LOCALIZATION DIRECTOR" -> "במאי לוקליזציה" ("במאי" = FILM director, wrong register for a
    corporate credits title). Revert to "מנהל לוקליזציה".
  * "TRADING MANAGER 3RD PARTY KEY ACCOUNTS" pk 94986 in onscreens.json got the WRONG fix
    ("מן המניין" = a longtime/regular member — unrelated meaning) while the SAME pk in
    onscreens_final.json got a correct one ("מן הצד השלישי" = from the third party). Copy the
    correct sibling value across instead of guessing a new translation.

This is a REVERT/SYNC action (restoring an already-known-good value), not a new translation
decision. Deterministic, atomic, backed up, reversible.

Run: python fix_cpqa_meaning_regressions.py [--dry]
"""
import json, os, sys, shutil, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
BASE = os.path.join(RES, "localization_translated.json")
DLC = os.path.join(RES, "dlc_ep1_translated.json")
DRY = "--dry" in sys.argv


def find(items, pk):
    for it in items:
        if it.get("primaryKey") == pk:
            return it
    return None


def set_both(it, val):
    changed = False
    if it.get("femaleVariant") != val:
        it["femaleVariant"] = val; changed = True
    if it.get("maleVariant") != val:
        it["maleVariant"] = val; changed = True
    return changed


def main():
    base = json.load(open(BASE, encoding="utf-8"))
    n = 0

    # 1) Fire Extinguisher -> revert to "כיבוי אש" (both onscreens files, all bad variants)
    BAD_FE = {"כבאית", "מכבי אש"}
    for sec in ("onscreens/onscreens.json", "onscreens/onscreens_final.json"):
        for it in base[sec]:
            fv, mv = it.get("femaleVariant"), it.get("maleVariant")
            if fv in BAD_FE or mv in BAD_FE:
                if not DRY:
                    set_both(it, "כיבוי אש")
                n += 1
                print(f"  [{sec}] pk={it.get('primaryKey')} Fire Extinguisher -> reverted to 'כיבוי אש' (was fV={fv!r} mV={mv!r})")

    # 2) LOCALIZATION DIRECTOR -> revert "במאי לוקליזציה" to "מנהל לוקליזציה"
    for sec in ("onscreens/onscreens.json", "onscreens/onscreens_final.json"):
        for it in base[sec]:
            fv, mv = it.get("femaleVariant"), it.get("maleVariant")
            if fv == "במאי לוקליזציה" or mv == "במאי לוקליזציה":
                if not DRY:
                    set_both(it, "מנהל לוקליזציה")
                n += 1
                print(f"  [{sec}] pk={it.get('primaryKey')} LOCALIZATION DIRECTOR -> reverted to 'מנהל לוקליזציה'")

    # 3) TRADING MANAGER 3RD PARTY, pk 94986: sync onscreens.json to onscreens_final.json's
    #    already-correct value instead of guessing.
    it_bad = find(base["onscreens/onscreens.json"], 94986)
    it_good = find(base["onscreens/onscreens_final.json"], 94986)
    if it_bad and it_good and it_bad.get("femaleVariant") == "מנהל סחר של לקוחות מפתח מן המניין":
        good_val = it_good.get("femaleVariant")
        if not DRY:
            set_both(it_bad, good_val)
        n += 1
        print(f"  [onscreens.json] pk=94986 TRADING MANAGER 3RD PARTY -> synced to sibling value {good_val!r}")

    print(f"\ntotal entries fixed: {n}")
    if DRY:
        print("DRY — nothing written")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = f"{BASE}.bak.meaning_regr.{ts}"
    if not os.path.exists(bak):
        shutil.copy2(BASE, bak)
    tmp = BASE + ".tmp"
    json.dump(base, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, BASE)
    print(f"wrote {os.path.basename(BASE)}  (backup {os.path.basename(bak)})")


if __name__ == "__main__":
    main()
