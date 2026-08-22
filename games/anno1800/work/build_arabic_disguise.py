#!/usr/bin/env python3
"""build_arabic_disguise.py — the FINAL Anno 1800 Hebrew mod: full Hebrew on the ENGLISH
slot, at COLD BOOT, with ZERO language switch, by disguising Hebrew as the Arabic script.

PROVEN in-game 2026-06-22 (user-confirmed): English slot, cold boot, no switch, clean
Hebrew RTL. Mechanism = ride Anno's built-in Arabic pipeline (bidi RTL + shaping is
pre-baked into the English cold-boot atlas — a fan Arabic mod proved a pure DATA mod
renders Arabic RTL at cold boot on the retail Denuvo exe). We:
  1. remap each Hebrew letter -> an Arabic carrier + ZWNJ isolation (heb_as_arabic).
  2. inject the Hebrew glyph at each carrier in the 2 Meta fonts + empty the ZWNJ glyph.
Text is stored LOGICAL (the engine bidi's it). Untranslated GUIDs stay English (readable
LTR). Deploy = loose-file mod; user keeps Text Language = English. No exe touched.

Usage:  python work/build_arabic_disguise.py [--out <mods_dir>]
"""
import argparse
import json
import os
import sys
import xml.sax.saxutils as sx

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rda_reader import RDAArchive       # noqa: E402
import heb_as_arabic as H               # noqa: E402
import anno_font                        # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _dash(s: str) -> str:
    """Normalize every long dash (em U+2014, horizontal-bar U+2015, en U+2013) to a plain ASCII
    hyphen '-' on EVERY emitted line (user request 2026-07-30: "כל '—' תהפוך ל '-'"). Applied to
    Hebrew before carrier-remap, to English fallback, and to kept-English key/entity labels."""
    return s.replace("\u2014", "-").replace("\u2015", "-").replace("\u2013", "-")


REAL_HOME = r"C:\Users\Nehoray_Cohen"   # env-redirect trap: expanduser("~") -> sandbox
DEFAULT_MODS = os.path.join(REAL_HOME, "Documents", "Anno 1800", "mods")
MOD_NAME = "zzz_hebrew_translation"
HEBREW_JSON = os.path.join(HERE, "hebrew.json")
EN_FALLBACK_JSON = os.path.join(HERE, "..", "agent_handoff", "to_translate.json")
# The fan Arabic mod's Meta fonts = a PROVEN Arabic-capable base (has the Arabic cmap +
# GSUB shaping + OS/2 Arabic bits the engine's pipeline needs). We overwrite ONLY the 27
# carrier glyphs with Hebrew + empty the ZWNJ glyph; everything else is left intact.
FAN_DATA4 = r"F:/Game Lab/Anno 1800/_Arabic Localization/maindata/data4.rda"
META_FONTS = ["metaoffcpro-norm.ttf", "metaserifoffcpro-medium.ttf"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_MODS)
    args = ap.parse_args()

    hebrew = json.load(open(HEBREW_JSON, encoding="utf-8"))
    hebrew = {str(k): v for k, v in hebrew.items() if v and v.strip()}
    # merge the genuine remaining lines that were OUTSIDE the original 56k corpus
    # (New World/Isabel + Enbesa campaign narrative, controller hints, a few UI). These were
    # translated one-time (see make_remaining_hebrew.py / build_quest_hebrew.py). Only ADD lines
    # not already present so a real corpus value is never clobbered.
    nrem = 0
    rem_path = os.path.join(HERE, "remaining_hebrew.json")
    if os.path.exists(rem_path):
        for guid, he in json.load(open(rem_path, encoding="utf-8")).items():
            guid = str(guid)
            if guid not in hebrew and he and he.strip():
                hebrew[guid] = he
                nrem += 1
    if nrem:
        print(f"  merged {nrem} remaining lines (campaign narrative + controller hints + UI)")
    english = {}
    if os.path.exists(EN_FALLBACK_JSON):
        english = {str(k): v for k, v in json.load(open(EN_FALLBACK_JSON, encoding="utf-8")).items()}
    # user-editable ENTITY names (islands, cities/settlements, ships, regions) MUST stay in their
    # original English — the user names/edits these, my fixed Hebrew would clobber their edits and
    # they can't type Hebrew into those fields. Built from assets.xml templates + internal-name
    # patterns (see editable_names_exclude.json). For an excluded GUID we emit the English value.
    exclude = set()
    excl_english = {}
    exf = os.path.join(HERE, "editable_names_exclude.json")
    enf = os.path.join(HERE, "editable_names_english.json")
    if os.path.exists(exf):
        exclude = set(json.load(open(exf, encoding="utf-8")))
    if os.path.exists(enf):
        excl_english = {str(k): v for k, v in json.load(open(enf, encoding="utf-8")).items()}
    # keyboard-key LABELS (the dedicated 999xxx "Keys" pool: arrow keys, keypad, named keys,
    # letters, F-keys, symbols) are physical KEY NAMES, not content -> keep them English/Latin,
    # never carrier-Hebrew. Otherwise the Controls rebinding screen shows Hebrew where a key should
    # be (e.g. the arrow keys rendered שמאלה/ימינה/למעלה/למטה, keypad "לוח מקשים N"). We emit the
    # real English label from the source. (999260+ are crash-reporter categories, NOT keys -> stay Hebrew.)
    key_guids = set()
    kkf = os.path.join(HERE, "keyboard_keys_exclude.json")
    if os.path.exists(kkf):
        key_guids = set(str(g) for g in json.load(open(kkf, encoding="utf-8")))
    # FIXED session/REGION display names (The Old World / New World / Arctic / Enbesa / Cape Trelawney)
    # are NOT player-editable, so they SHOULD be translated (user 2026-07-30). They were over-excluded as
    # "editable names"; un-exclude them here so their corpus Hebrew shows. Renameable ISLANDS/cities/ships
    # stay excluded (English). Small explicit override subtracted from `exclude`.
    rtf = os.path.join(HERE, "region_names_translate.json")
    if os.path.exists(rtf):
        exclude -= set(str(g) for g in json.load(open(rtf, encoding="utf-8")))

    root = os.path.join(args.out, MOD_NAME)
    gui = os.path.join(root, "data", "config", "gui")
    fdir = os.path.join(root, "data", "fonts")
    os.makedirs(gui, exist_ok=True)
    os.makedirs(fdir, exist_ok=True)
    print(f"build_arabic_disguise -> {root}")

    # 1. fonts: fan Meta fonts, carriers -> Hebrew, ZWNJ emptied
    heb_src = anno_font._pick_src(None)
    print(f"  Hebrew source font: {heb_src}")
    with RDAArchive(FAN_DATA4) as a:
        for fn in META_FONTS:
            e = next(x for x in a.iter_entries() if x.name == f"data/fonts/{fn}")
            out, done = H.build_font(a.extract_entry(e), heb_src)
            open(os.path.join(fdir, fn), "wb").write(out)
            print(f"    {fn}: {done} carrier glyphs -> Hebrew, ZWNJ emptied ({len(out):,} B)")

    # 2. texts_english.xml: Hebrew-as-carrier for translated, English for the rest (100% coverage)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<ModOps>",
             '  <ModOp Type="add" Path="/TextExport/Texts">']
    seen = set()
    nheb = nexcl = nkey = 0
    for guid, he in hebrew.items():
        if guid in key_guids:                    # keyboard-key label -> keep English (Latin)
            val = english.get(guid)
            if val and val.strip():
                lines.append(f"    <Text><GUID>{guid}</GUID><Text>{sx.escape(_dash(val))}</Text></Text>")
                nkey += 1
            seen.add(guid)                       # never emit the Hebrew carrier for a key name
            continue
        if guid in exclude:                      # user-editable entity name -> keep English
            val = excl_english.get(guid)
            if val and val.strip():
                lines.append(f"    <Text><GUID>{guid}</GUID><Text>{sx.escape(_dash(val))}</Text></Text>")
                nexcl += 1
            seen.add(guid)                       # never emit the Hebrew carrier for it
            continue
        lines.append(f"    <Text><GUID>{guid}</GUID><Text>{sx.escape(H.remap_text(_dash(he)))}</Text></Text>")
        seen.add(guid)
        nheb += 1
    nfb = 0
    for guid, en in english.items():
        if guid in seen or not en or not en.strip():
            continue
        # key labels + editable names with no Hebrew value still emit English here (dash-normalized)
        lines.append(f"    <Text><GUID>{guid}</GUID><Text>{sx.escape(_dash(en))}</Text></Text>")
        seen.add(guid)
        nfb += 1
    lines += ["  </ModOp>", "</ModOps>"]
    with open(os.path.join(gui, "texts_english.xml"), "wb") as f:
        f.write(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    print(f"  texts_english.xml: {nheb} Hebrew(as-Arabic) + {nexcl} kept-English(editable names) "
          f"+ {nkey} kept-English(keyboard keys) + {nfb} English-fallback = {len(seen)} GUIDs")

    modinfo = {
        "Version": "2.0.0",
        "ModID": "nehoray_hebrew_translation",
        "Category": {"English": "Localization", "Hebrew": "תרגום"},
        "ModName": {"English": "Hebrew Translation", "Hebrew": "תרגום לעברית"},
        "Description": {
            "English": "Full Hebrew UI, rendered right-to-left at cold boot with NO language "
                       "switch. Set Text Language = English, Audio = English, and just play.\n\n"
                       "NOTE 1 — editable names stay English: island, city, ship and country/"
                       "session names are things YOU rename, so the mod never touches them (it "
                       "leaves the original English). This is on purpose — it must never overwrite "
                       "a name you already gave, and it lets you keep editing those fields.\n"
                       "NOTE 2 — typing Hebrew into a name field: the letters DO appear, but the "
                       "game lays them out left-to-right (mirror Hebrew), because the right-to-left "
                       "layout logic for live keyboard input lives in the protected game exe and a "
                       "data mod cannot reach it. Type names in English for correct order, or accept "
                       "the mirrored look.",
            "Hebrew": "תרגום ממשק מלא לעברית, מוצג מימין-לשמאל כבר מהעלייה וללא שום החלפת שפה. "
                      "הגדר שפת טקסט = English, שמע = English, ופשוט שחק.\n\n"
                      "הערה 1 — שמות שניתן לערוך נשארים באנגלית: שמות של איים, ערים, ספינות ומדינות/"
                      "אזורים הם דברים שאתה עצמך משנה, ולכן התרגום כלל לא נוגע בהם (הוא משאיר את האנגלית "
                      "המקורית). זה בכוונה — כדי שלעולם לא ידרוס שם שכבר נתת, וכדי שתוכל להמשיך לערוך "
                      "את השדות האלה.\n"
                      "הערה 2 — הקלדת עברית בשדה שם: האותיות אכן מופיעות, אבל המשחק מסדר אותן משמאל-"
                      "לימין (עברית ראי), מפני שהלוגיקה של סידור מימין-לשמאל עבור קלט מקלדת חי נמצאת "
                      "בתוך קובץ ההרצה המוגן של המשחק, ומוד-נתונים אינו יכול להגיע אליה. הקלד שמות "
                      "באנגלית לסדר תקין, או קבל את המראה ההפוך."},
        "CreatorName": "nehorayc04",
    }
    json.dump(modinfo, open(os.path.join(root, "modinfo.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("  modinfo.json written")
    print("DONE. Text Language = English, Audio = English. Full Hebrew at cold boot, no switch.")


if __name__ == "__main__":
    main()
