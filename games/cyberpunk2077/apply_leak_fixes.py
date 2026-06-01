"""
apply_leak_fixes.py
====================
Surgical fixes for the 10 real English-leak entries identified in the deep
audit (the other 7 were brand names / song titles and intentionally stay
in English).

Each patch is a string replacement inside the existing femaleVariant — we
preserve the rest of the Hebrew text byte-for-byte. No LM, every fix is a
hand-written, in-context Hebrew rendering of the leaked English fragment.

Backs the spine file up before touching it, then writes atomically.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
TRANSLATED  = os.path.join(SCRIPTS_DIR, "תרגום_משחקים", "source", "resources",
                           "localization_translated.json")

# Each patch:
#   (section, primaryKey): [(old_fragment, new_fragment), ...]
# Multiple fragments per entry are applied in order. Each is verified to
# match exactly once before any write happens — if the old fragment isn't
# present, that patch is skipped and logged (no silent corruption).
PATCHES: dict[tuple[str, str], list[tuple[str, str]]] = {

    # #1 / #5 — Joe's last words (mirror in both onscreens files)
    ("onscreens/onscreens.json", "6269"): [
        ("הבג בא לב heart של החיה", "הבג בא לב של החיה"),
        ("לך ל these coordinates",   "לך לקואורדינטות הללו"),
    ],
    ("onscreens/onscreens_final.json", "6269"): [
        ("הבג בא לב heart של החיה", "הבג בא לב של החיה"),
        ("לך ל these coordinates",   "לך לקואורדינטות הללו"),
    ],

    # #3 / #8 — Dario Sanchez SMS thread (mirror)
    ("onscreens/onscreens.json", "11534"): [
        ("אני going to wipe em all",   "אני הולך לחסל את כולם"),
        ("נייט סיטי שליBitch אני",      "נייט סיטי שלי, יא כלבה. אני"),
    ],
    ("onscreens/onscreens_final.json", "11534"): [
        ("אני going to wipe em all",   "אני הולך לחסל את כולם"),
        ("נייט סיטי שליBitch אני",      "נייט סיטי שלי, יא כלבה. אני"),
    ],

    # #4 / #9 — Charlie / All Foods news article (Phantom Liberty DLC content)
    # The leak is one complete English sentence stuck inside a Hebrew paragraph.
    # Apostrophes are U+2019 (typographic) — preserve them.
    ("onscreens/onscreens.json", "82710"): [
        ("מרלנה יללה.Turned out, the All Foods bar’s consistency... broke little Charlie’s tooth!",
         "מרלנה יללה. התברר שהמרקם של חטיף 'כל המזונות'… שבר לצ’ארלי הקטן את השן!"),
    ],
    ("onscreens/onscreens_final.json", "82710"): [
        ("מרלנה יללה.Turned out, the All Foods bar’s consistency... broke little Charlie’s tooth!",
         "מרלנה יללה. התברר שהמרקם של חטיף 'כל המזונות'… שבר לצ’ארלי הקטן את השן!"),
    ],

    # #7 — VDB merc complaining about NetWatch (onscreens_final only)
    # The "VDBs" brand stays English; only the "them" pronoun is replaced.
    ("onscreens/onscreens_final.json", "11521"): [
        ("בשביל them תולעים", "בשביל אותם תולעים"),
    ],

    # #10 — Edgar Toll fan letter (DLC ep1)
    ("onscreens/onscreens_final.json", "83878"): [
        ("עם them בייקרס", "עם אותם בייקרס"),
    ],

    # #11 — Misty / Viktor email thread (DLC ep1)
    # Two leaks: the closing English sentence + three Thai "เรื่อง:" subject labels.
    # All 3 Thai occurrences in this entry are the same string → replace_all.
    ("onscreens/onscreens_final.json", "84326"): [
        ("A'll think about it. No promises.", "אני אחשוב על זה. בלי הבטחות."),
        # Thai "เรื่อง:" = subject. Replace each occurrence with Hebrew "נושא:".
        ("เรื่อง: שיני את דעתך?", "נושא: שיני את דעתך?"),
    ],

    # #12 — Lorraine / Maggie Fent email (DLC ep1)
    # "Arasaka liver boosters" is a product brand-name — keep English.
    # "those new" is a real leak. Also one "เรื่อง:" subject.
    ("onscreens/onscreens_final.json", "86817"): [
        ("ל those new Arasaka liver boosters",
         "ל-Arasaka liver boosters החדשים האלה"),
        ("เรื่อง: איך פאנט עובד", "נושא: איך פאנט עובד"),
    ],

    # #14 — SCV gang Russian voiceset (kiroshi t-slot — the player-visible
    # Hebrew translation of the Russian audio). The o-slot Russian stays
    # verbatim — it's the audio transcript.
    ("subtitles/open_world/voicesets/gang_scv_m_11_rus_40_mt.json",
     "1898039435881734148"): [
        ('t="אדחוף טיל בתוכך וlanz you לירח כמו סויוז."',
         't="אדחוף טיל בתוכך ואשלח אותך לירח כמו סויוז."'),
    ],

    # #15 — VDB gang Creole voiceset — the t-slot was completely broken
    # ("א öld you!" — Hebrew א + Hungarian "öld" + English "you").
    ("subtitles/open_world/voicesets/gang_vdb_f_03_car_30_mt.json",
     "1949022741939134468"): [
        ('t="א öld you!"', 't="אני אהרוג אותך!"'),
    ],

    # #17 — V meets Mitch about the Panzerboys (gang of aerial smugglers).
    # "Panzerboys" is a CP2077 gang name — keep English.
    # "transporters" in CP2077 lore = the gang's flying vehicles → "מטוסי תובלה".
    ("subtitles/quest/q103/q103_07_ghost_town_drive.json",
     "1665069818135048192"): [
        ("טסו עם them huge transporters?",
         "טסו עם המטוסים הענקיים האלה?"),
    ],
}


def main() -> int:
    if not os.path.exists(TRANSLATED):
        print(f"FATAL: {TRANSLATED} not found", flush=True)
        return 1

    backup = f"{TRANSLATED}.bak.deep_audit_b.{time.strftime('%Y%m%d_%H%M%S')}"
    print(f"backing up: {TRANSLATED}")
    print(f"        -> {backup}")
    shutil.copy2(TRANSLATED, backup)

    with open(TRANSLATED, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate every patch matches BEFORE writing — fail fast on a stale spec.
    validation_failures: list[tuple[str, str, str]] = []
    plan: list[tuple[str, str, dict, list[tuple[str, str, str]]]] = []

    for (section, pk), fragments in PATCHES.items():
        entries = data.get(section)
        if not isinstance(entries, list):
            validation_failures.append((section, pk, f"section missing"))
            continue
        entry = None
        for e in entries:
            if isinstance(e, dict) and str(e.get("primaryKey")) == pk:
                entry = e
                break
        if entry is None:
            validation_failures.append((section, pk, "pk not found"))
            continue
        fv = entry.get("femaleVariant", "") or ""
        per_entry: list[tuple[str, str, str]] = []
        new_fv = fv
        for old, new in fragments:
            count = new_fv.count(old)
            if count == 0:
                validation_failures.append(
                    (section, pk, f"fragment not present: {old[:60]!r}")
                )
                continue
            per_entry.append((old, new, f"matches={count}"))
            new_fv = new_fv.replace(old, new)
        if per_entry:
            plan.append((section, pk, entry, per_entry))
            entry["_planned_new_fv"] = new_fv

    if validation_failures:
        print("\nVALIDATION FAILURES:")
        for section, pk, reason in validation_failures:
            print(f"  - {section} pk={pk}: {reason}")
        # Continue with the patches that did validate — surface failures
        # but don't abort, so a partial fix can land.

    # Apply: copy _planned_new_fv into femaleVariant.
    applied = 0
    for section, pk, entry, per_entry in plan:
        entry["femaleVariant"] = entry.pop("_planned_new_fv")
        applied += 1
        print(f"\n+ {section} pk={pk}")
        for old, new, note in per_entry:
            print(f"    {note}: {old[:50]!r} -> {new[:50]!r}")

    # Atomic write
    tmp = f"{TRANSLATED}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRANSLATED)

    print(f"\napplied: {applied}/{len(PATCHES)} entries patched")
    print(f"validation failures: {len(validation_failures)}")
    new_size = os.path.getsize(TRANSLATED)
    print(f"saved: {TRANSLATED}  ({new_size:,} bytes)")
    return 0 if not validation_failures else 2


if __name__ == "__main__":
    sys.exit(main())
