"""
cp2077_status_report.py
=======================
Comprehensive translation-completeness report for the Cyberpunk 2077
Hebrew project. READ-ONLY — never touches archives, never re-packs.

It scans `localization_translated.json` — the spine file that gets packed
into `z_hebrew_translation.archive` — classifies every text entry, and
groups results into logical categories so we know exactly what is done
and what still needs work.

It ALSO scans the Phantom Liberty DLC (`dlc_ep1_text.json`, built by
`cp2077_consolidate_dlc.py`) when that file is present, and reports the DLC
as a separate section plus a base+DLC grand total.

CATEGORIES
  Onscreens (UI text — keyed by the entry's hierarchical secondaryKey):
    UI — Menus / HUD / Settings
    Story — Quests / Journal / Dialogue
    Devices — Computers / Shards / Terminals
    NPCs — Names / Bio
    Items & Equipment
    RPG — Stats / Perks / Quickhacks
    Gameplay — Misc
    Other / Debug / Obsolete
    Onscreens — Uncategorized (numeric-only keys)
  Subtitles (dialogue — keyed by folder):
    Subtitles — Quests / Story        (subtitles/quest/)
    Subtitles — Open World / Ambient  (subtitles/open_world/)
    Subtitles — Media / TV / Radio    (subtitles/media/)
    Subtitles — Overlays              (DLC overlay folders only)

ENTRY CLASSIFICATION (per entry; judged on femaleVariant, maleVariant as
fallback when female is blank):
    translated             value contains Hebrew
    untranslated (English)  Latin text, no Hebrew — line left in English
    untranslated (Arabic)   Arabic chars, no Hebrew — base AR skeleton leaked
    untranslated (missing)  English source exists, translation blank
    no-translation-needed   source empty / pure symbols-numbers-keys

    % complete = translated / (total - no-translation-needed)

ENGLISH SOURCE (to tell "missing" from "not-applicable"):
    subtitles  -> the entry's own secondaryKey holds the English line
    onscreens  -> matched by primaryKey against localization_export.json

DLC TRANSLATION STATUS
  Phantom Liberty ships its text in a SEPARATE archive (ep1/lang_*_text.archive).
  The DLC scan cross-checks every DLC stringId against the base strings already
  translated to Hebrew (CP2077 stringIds are global identifiers). A match means
  a Hebrew translation already exists for that string — it is shared with the
  base game and needs no new work. A DLC stringId with no match is genuinely
  untranslated and is the real Phantom Liberty translation gap.

OUTPUT
    console summary table
    cp2077_translation_status_report.txt  (full per-category detail + samples)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
RES         = os.path.join(SCRIPTS_DIR, "תרגום_משחקים", "source", "resources")
TRANSLATED  = os.path.join(RES, "localization_translated.json")
EXPORT      = os.path.join(RES, "localization_export.json")
DLC         = os.path.join(RES, "dlc_ep1_text.json")
REPORT_TXT  = os.path.join(SCRIPTS_DIR, "cp2077_translation_status_report.txt")
ARCHIVE     = os.path.join(SCRIPTS_DIR, "Cyberpunk 2077",
                           "archive", "pc", "mod", "z_hebrew_translation.archive")

ONSCREENS_PRIMARY = "onscreens/onscreens_final.json"   # the game-facing file
ONSCREENS_MIRROR  = "onscreens/onscreens.json"          # intermediate mirror

# ── character-class detectors ───────────────────────────────────────────────
HEB     = re.compile(r"[֐-׿]")
ARAB    = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿ]")
LETTERS = re.compile(r"[A-Za-z]")
TAG     = re.compile(r"<[^<>]*>|\{[^{}]*\}")            # CR2W markup / placeholders
CTRL    = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# secondaryKey second-component groupings for onscreens "Gameplay-*" keys
ITEM_SUBS = {"Clothing", "Clothing_EP1", "Cyberware", "Cyberware_EP1", "Weapons",
             "Weapon", "Vehicles", "Vehicle", "Consumables", "Items", "Item",
             "Parts", "Crafting", "Gadgets", "Mods", "Grenades", "Attachments",
             "Ammo", "Junk"}
RPG_SUBS  = {"RPG", "StatusEffects", "QuickHacks", "Scanning", "Perks",
             "Attributes", "Skills", "Proficiencies", "Stats"}

# canonical display order for the report
ONSCREENS_ORDER = [
    "UI — Menus / HUD / Settings",
    "Story — Quests / Journal / Dialogue",
    "NPCs — Names / Bio",
    "Devices — Computers / Shards / Terminals",
    "Items & Equipment",
    "RPG — Stats / Perks / Quickhacks",
    "Gameplay — Misc",
    "Other / Debug / Obsolete",
    "Onscreens — Uncategorized (numeric keys)",
]
SUBTITLE_ORDER = [
    "Subtitles — Quests / Story",
    "Subtitles — Open World / Ambient",
    "Subtitles — Media / TV / Radio",
]
DLC_SUBTITLE_ORDER = SUBTITLE_ORDER + ["Subtitles — Overlays"]


def clean(s: str) -> str:
    return CTRL.sub("", s) if s else ""


def needs_translation(text: str) -> bool:
    """A source string is worth translating only if it carries real words —
    >= 2 Latin letters after CR2W markup/placeholders are stripped."""
    core = TAG.sub(" ", text or "")
    return len(LETTERS.findall(core)) >= 2


def classify(english: str, value: str) -> str:
    """english = source line; value = the translated-file display value."""
    val  = clean(value).strip()
    core = TAG.sub(" ", val)
    eng  = clean(english).strip()

    if not eng or not needs_translation(eng):
        # No usable source. Judge by the value itself.
        if HEB.search(val):              # raw value — catches Hebrew inside
            return "translated"          # <kiroshi>/<mothertongue> t/b/a attrs
        if val and ARAB.search(core):
            return "untranslated_arabic"
        if val and needs_translation(val):
            return "untranslated_english"
        return "no_translation_needed"

    # Source needs translating.
    if not val:
        return "missing"
    if HEB.search(val):              # raw value — catches Hebrew inside
        return "translated"          # <kiroshi>/<mothertongue> t/b/a attrs
    if ARAB.search(core):
        return "untranslated_arabic"
    return "untranslated_english"


def onscreens_category(secondary_key: str) -> str:
    s = clean(secondary_key).strip()
    if not s:
        return "Onscreens — Uncategorized (numeric keys)"
    parts = [p.strip() for p in s.split("-")]
    head  = parts[0]
    sub   = parts[1] if len(parts) > 1 else ""
    if head == "UI":
        return "UI — Menus / HUD / Settings"
    if head == "Story":
        return "Story — Quests / Journal / Dialogue"
    if head == "Gameplay":
        if sub == "Devices":
            return "Devices — Computers / Shards / Terminals"
        if sub == "NPC":
            return "NPCs — Names / Bio"
        if sub in ITEM_SUBS:
            return "Items & Equipment"
        if sub in RPG_SUBS:
            return "RPG — Stats / Perks / Quickhacks"
        return "Gameplay — Misc"
    return "Other / Debug / Obsolete"


def dlc_sub_category(section: str) -> str:
    """DLC subtitle section -> category. section = `ep1/subtitles/<top>/...`."""
    parts = section.split("/")
    top = parts[2] if len(parts) > 2 else ""
    if top == "quest":
        return "Subtitles — Quests / Story"
    if top == "open_world":
        return "Subtitles — Open World / Ambient"
    if top == "media":
        return "Subtitles — Media / TV / Radio"
    return "Subtitles — Overlays"          # overlays_quest, overlay_media, overlay_open_world


def new_bucket() -> dict:
    return dict(translated=0, t_latin=0, eng_multi=0, eng_single=0,
                arabic=0, missing=0, na=0)


def tally(bucket: dict, english: str, fem: str, mal: str) -> tuple[str, str]:
    """Classify one base-game entry into `bucket`. Returns (class, text)."""
    value = (fem or "").strip() or (mal or "").strip()
    cls   = classify(english, value)
    if cls == "translated":
        bucket["translated"] += 1
        if len(LETTERS.findall(TAG.sub(" ", clean(value)))) >= 3:
            bucket["t_latin"] += 1
        return cls, value
    if cls == "untranslated_english":
        if len(clean(value).split()) >= 2:
            bucket["eng_multi"] += 1
        else:
            bucket["eng_single"] += 1
        return cls, value
    if cls == "untranslated_arabic":
        bucket["arabic"] += 1
        return cls, value
    if cls == "missing":
        bucket["missing"] += 1
        return cls, (english or "")
    bucket["na"] += 1
    return cls, value


def tally_dlc(bucket: dict, english: str, is_translated: bool) -> tuple[str, str]:
    """Classify one DLC entry into `bucket`. `english` is the DLC archive's
    own (English) value; `is_translated` is True when the entry's stringId is
    shared with a base-game string already rendered in Hebrew."""
    e = clean(english).strip()
    if is_translated:
        bucket["translated"] += 1
        return "translated", e
    if not e or not needs_translation(e):
        bucket["na"] += 1
        return "na", e
    if len(e.split()) >= 2:
        bucket["eng_multi"] += 1
    else:
        bucket["eng_single"] += 1
    return "pending", e


def b_total(b: dict) -> int:
    return (b["translated"] + b["eng_multi"] + b["eng_single"]
            + b["arabic"] + b["missing"] + b["na"])


def b_untranslated(b: dict) -> int:
    return b["eng_multi"] + b["eng_single"] + b["arabic"] + b["missing"]


def b_pct(b: dict) -> float:
    actionable = b_total(b) - b["na"]
    return 100.0 * b["translated"] / actionable if actionable else 100.0


def load(path: str, label: str) -> dict:
    mb = os.path.getsize(path) / 1_048_576
    print(f"  loading {label} ({mb:.1f} MB) ...", end="", flush=True)
    t0 = time.time()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f" {time.time() - t0:.1f}s, {len(data):,} sections")
    return data


def scan_dlc(translated_ids: set) -> dict | None:
    """Scan dlc_ep1_text.json (Phantom Liberty). Returns a result dict, or
    None when the DLC data file is absent."""
    if not os.path.exists(DLC):
        print("\n  [DLC] dlc_ep1_text.json not found — skipping DLC section.")
        return None
    dlc = load(DLC, "dlc_ep1_text.json (Phantom Liberty DLC)")

    buckets: dict[str, dict] = {}
    samples: dict[str, list] = {}
    order:   list[str] = []

    def bk(name: str) -> dict:
        if name not in buckets:
            buckets[name] = new_bucket()
            samples[name] = []
            order.append(name)
        return buckets[name]

    print("  scanning DLC onscreens + subtitles ...")
    # DLC onscreens — onscreens_final.json is the game-facing file.
    for e in dlc.get("ep1/onscreens/onscreens_final.json", []):
        if not isinstance(e, dict):
            continue
        cat = onscreens_category(e.get("secondaryKey", ""))
        b   = bk(cat)
        is_tr = str(e.get("primaryKey")) in translated_ids
        cls, txt = tally_dlc(b, e.get("femaleVariant") or e.get("maleVariant"), is_tr)
        if cls == "pending" and len(samples[cat]) < 8 and len(clean(txt).split()) >= 2:
            samples[cat].append((str(e.get("primaryKey")), txt[:130]))

    # DLC subtitles.
    sub_gaps: list[tuple[str, int]] = []
    for sec in sorted(k for k in dlc if k.startswith("ep1/subtitles/")):
        cat = dlc_sub_category(sec)
        b   = bk(cat)
        gap = 0
        for e in dlc[sec]:
            if not isinstance(e, dict):
                continue
            is_tr = str(e.get("stringId")) in translated_ids
            cls, txt = tally_dlc(b, e.get("femaleVariant") or e.get("maleVariant"), is_tr)
            if cls == "pending":
                gap += 1
                if len(samples[cat]) < 8 and len(clean(txt).split()) >= 2:
                    samples[cat].append((sec.split("/")[-1], txt[:130]))
        if gap:
            sub_gaps.append((sec, gap))

    # DLC onscreens.json mirror (excluded from the DLC global).
    mirror = new_bucket()
    for e in dlc.get("ep1/onscreens/onscreens.json", []):
        if isinstance(e, dict):
            is_tr = str(e.get("primaryKey")) in translated_ids
            tally_dlc(mirror, e.get("femaleVariant") or e.get("maleVariant"), is_tr)

    GLOBAL = new_bucket()
    for b in buckets.values():
        for k in GLOBAL:
            GLOBAL[k] += b[k]

    return dict(buckets=buckets, samples=samples, order=order,
                sub_gaps=sub_gaps, mirror=mirror, GLOBAL=GLOBAL)


def main() -> int:
    print("=" * 72)
    print("CYBERPUNK 2077 HEBREW TRANSLATION — STATUS REPORT")
    print("=" * 72)
    for p in (TRANSLATED, EXPORT):
        if not os.path.exists(p):
            print(f"FATAL: missing {p}")
            return 1

    translated = load(TRANSLATED, "localization_translated.json")
    export     = load(EXPORT, "localization_export.json (English source)")

    # English-source pk index for the two onscreens files.
    export_idx: dict[str, dict] = {}
    for sec in (ONSCREENS_PRIMARY, ONSCREENS_MIRROR):
        m = {}
        for e in export.get(sec, []):
            if isinstance(e, dict) and e.get("primaryKey") is not None:
                m[e["primaryKey"]] = (e.get("femaleVariant")
                                      or e.get("maleVariant") or "")
        export_idx[sec] = m
    del export  # free ~500 MB

    buckets: dict[str, dict] = {}                 # category -> counters
    samples: dict[str, list] = {}                 # category -> sample lines
    order:   list[str] = []                       # stable display order
    onscreens_unmatched = 0
    section_gaps: list[tuple[str, int]] = []      # (subtitle section, untranslated)

    def bucket_for(name: str) -> dict:
        if name not in buckets:
            buckets[name] = new_bucket()
            samples[name] = []
            order.append(name)
        return buckets[name]

    print("\n  scanning onscreens (UI text) ...")
    for sec in (ONSCREENS_PRIMARY, ONSCREENS_MIRROR):
        rows = translated.get(sec, [])
        idx  = export_idx.get(sec, {})
        for e in rows:
            if not isinstance(e, dict):
                continue
            pk = e.get("primaryKey")
            if pk in idx:
                english = idx[pk]
            else:
                english = ""
                if sec == ONSCREENS_PRIMARY:
                    onscreens_unmatched += 1
            if sec == ONSCREENS_PRIMARY:
                cat = onscreens_category(e.get("secondaryKey", ""))
            else:
                cat = "Onscreens.json (intermediate mirror file)"
            b = bucket_for(cat)
            cls, text = tally(b, english, e.get("femaleVariant"),
                              e.get("maleVariant"))
            if cls in ("missing", "untranslated_english") and len(samples[cat]) < 8:
                if cls == "missing" or len(clean(text).split()) >= 2:
                    samples[cat].append((str(pk), text[:130]))

    print("  scanning subtitles (dialogue) ...")
    FOLDER_NAMES = {
        "quest":      "Subtitles — Quests / Story",
        "open_world": "Subtitles — Open World / Ambient",
        "media":      "Subtitles — Media / TV / Radio",
    }
    for sec, rows in translated.items():
        if not sec.startswith("subtitles/") or not isinstance(rows, list):
            continue
        folder = sec.split("/")[1] if len(sec.split("/")) > 2 else "(direct)"
        cat = FOLDER_NAMES.get(folder, f"Subtitles — {folder}")
        b = bucket_for(cat)
        sec_untrans = 0
        for e in rows:
            if not isinstance(e, dict):
                continue
            english = e.get("secondaryKey", "")     # subtitle EN source
            cls, text = tally(b, english, e.get("femaleVariant"),
                              e.get("maleVariant"))
            if cls in ("missing", "untranslated_english"):
                sec_untrans += 1
                if len(samples[cat]) < 8 and (
                        cls == "missing" or len(clean(text).split()) >= 2):
                    samples[cat].append((sec.split("/")[-1], text[:130]))
        if sec_untrans:
            section_gaps.append((sec, sec_untrans))

    # ── canonical scope = onscreens_final + subtitles (mirror file excluded) ──
    GLOBAL = new_bucket()
    for name, b in buckets.items():
        if name == "Onscreens.json (intermediate mirror file)":
            continue
        for k in GLOBAL:
            GLOBAL[k] += b[k]

    # ── DLC scan ─────────────────────────────────────────────────────────────
    # Every base stringId already rendered in Hebrew. A DLC string is "covered"
    # when its (globally-unique) stringId is in this set.
    translated_ids: set[str] = set()
    for sec, rows in translated.items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            v = (e.get("femaleVariant") or "") + " " + (e.get("maleVariant") or "")
            if HEB.search(v):
                translated_ids.add(str(e.get("primaryKey")))
    dlc = scan_dlc(translated_ids)

    # ── console summary table ────────────────────────────────────────────────
    def row(label, b):
        return (f"  {label:<44.44} {b_total(b):>8,} {b['translated']:>9,} "
                f"{b_untranslated(b):>8,} {b['na']:>7,} {b_pct(b):>7.1f}%")

    print()
    print("=" * 86)
    print(f"  {'CATEGORY':<44} {'TOTAL':>8} {'HEBREW':>9} {'UNTR.':>8} "
          f"{'N/A':>7} {'DONE':>8}")
    print("=" * 86)
    onscreens_cats = [n for n in ONSCREENS_ORDER if n in buckets]
    subtitle_cats  = [n for n in SUBTITLE_ORDER if n in buckets]
    subtitle_cats += [n for n in order
                      if n.startswith("Subtitles") and n not in subtitle_cats]

    print("  ── BASE GAME — ONSCREENS / UI TEXT " + "─" * 50)
    for n in onscreens_cats:
        print(row(n, buckets[n]))
    print("  ── BASE GAME — SUBTITLES / DIALOGUE " + "─" * 49)
    for n in subtitle_cats:
        print(row(n, buckets[n]))
    print("-" * 86)
    print(row("BASE GAME (onscreens_final + subtitles)", GLOBAL))

    if dlc:
        dlc_ons = [n for n in ONSCREENS_ORDER if n in dlc["buckets"]]
        dlc_sub = [n for n in DLC_SUBTITLE_ORDER if n in dlc["buckets"]]
        print("=" * 86)
        print("  ── PHANTOM LIBERTY DLC (ep1) — separate archive, not in the pipeline " + "─" * 17)
        for n in dlc_ons:
            print(row(n, dlc["buckets"][n]))
        for n in dlc_sub:
            print(row(n, dlc["buckets"][n]))
        print("-" * 86)
        print(row("PHANTOM LIBERTY DLC (all ep1 text)", dlc["GLOBAL"]))
        GRAND = new_bucket()
        for k in GRAND:
            GRAND[k] = GLOBAL[k] + dlc["GLOBAL"][k]
        print("=" * 86)
        print(row("GRAND TOTAL (base game + DLC)", GRAND))

    mirror = "Onscreens.json (intermediate mirror file)"
    if mirror in buckets:
        print("-" * 86)
        print(row("[mirror] base onscreens.json", buckets[mirror]))
    print("=" * 86)

    write_report(buckets, samples, order, GLOBAL, onscreens_cats,
                 subtitle_cats, section_gaps, onscreens_unmatched, dlc)
    print(f"\n  full detail written -> {REPORT_TXT}")
    if os.path.exists(ARCHIVE):
        st = os.stat(ARCHIVE)
        print(f"  deployed archive: {st.st_size:,} bytes, "
              f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}")
    return 0


def write_report(buckets, samples, order, GLOBAL, onscreens_cats,
                 subtitle_cats, section_gaps, onscreens_unmatched, dlc) -> None:
    L: list[str] = []
    L.append("=" * 78)
    L.append("CYBERPUNK 2077 HEBREW TRANSLATION — FULL STATUS REPORT")
    L.append(f"generated {time.strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("=" * 78)
    L.append("")
    L.append("Source of truth: localization_translated.json — the exact data")
    L.append("packed into z_hebrew_translation.archive. The Phantom Liberty DLC")
    L.append("is scanned from dlc_ep1_text.json. Counts are ENTRIES (one")
    L.append("displayed line each); femaleVariant is the primary value,")
    L.append("maleVariant is used as fallback when female is blank.")
    L.append("")
    L.append("Classes:  HEBREW = contains Hebrew  |  UNTR. = English/Arabic/blank")
    L.append("          N/A = no source text or pure symbols (nothing to translate)")
    L.append("          %DONE = HEBREW / (TOTAL - N/A)")
    L.append("")

    def block(title, names, bkts, smpls):
        L.append("─" * 78)
        L.append(title)
        L.append("─" * 78)
        for n in names:
            b = bkts[n]
            L.append(f"  {n}")
            L.append(f"      total entries .............. {b_total(b):>9,}")
            L.append(f"      translated to Hebrew ........ {b['translated']:>9,}"
                     f"   ({b_pct(b):.1f}% of actionable)")
            if b["t_latin"]:
                L.append(f"        of which keep a Latin word  {b['t_latin']:>9,}"
                         f"   (brand names — usually intentional)")
            L.append(f"      untranslated — English multi  {b['eng_multi']:>9,}"
                     f"   (real lines still in English)")
            L.append(f"      untranslated — English 1-word {b['eng_single']:>9,}"
                     f"   (likely proper nouns / codes)")
            if b["arabic"]:
                L.append(f"      untranslated — Arabic leaked  {b['arabic']:>9,}"
                         f"   (base skeleton showing through)")
            if b["missing"]:
                L.append(f"      untranslated — blank/missing  {b['missing']:>9,}"
                         f"   (English source exists, value empty)")
            L.append(f"      no translation needed ....... {b['na']:>9,}"
                     f"   (symbols / numbers / empty source)")
            if smpls.get(n):
                L.append(f"      sample lines needing work:")
                for key, txt in smpls[n]:
                    L.append(f"        [{key}] {txt}")
            L.append("")

    L.append("#" * 78)
    L.append("#  PART 1 — BASE GAME")
    L.append("#" * 78)
    L.append("")
    block("ONSCREENS / UI TEXT  — from onscreens_final.json",
          onscreens_cats, buckets, samples)
    block("SUBTITLES / DIALOGUE", subtitle_cats, buckets, samples)

    mirror = "Onscreens.json (intermediate mirror file)"
    if mirror in buckets:
        b = buckets[mirror]
        L.append("─" * 78)
        L.append("BASE ONSCREENS.JSON — intermediate mirror (excluded from totals)")
        L.append("─" * 78)
        L.append(f"  onscreens.json near-mirrors onscreens_final.json.")
        L.append(f"      total entries ............... {b_total(b):>9,}")
        L.append(f"      translated to Hebrew ........ {b['translated']:>9,}"
                 f"   ({b_pct(b):.1f}%)")
        L.append(f"      untranslated ................ {b_untranslated(b):>9,}")
        L.append(f"      no translation needed ....... {b['na']:>9,}")
        L.append("")

    # ── DLC section ──────────────────────────────────────────────────────────
    if dlc:
        L.append("#" * 78)
        L.append("#  PART 2 — PHANTOM LIBERTY DLC (ep1)")
        L.append("#" * 78)
        L.append("")
        L.append("Phantom Liberty ships its text in a SEPARATE archive,")
        L.append("ep1/lang_*_text.archive. The HEBREW column counts DLC strings")
        L.append("whose stringId is shared with a base-game string the project")
        L.append("already translated — stringIds are global in CP2077, so those")
        L.append("strings already HAVE a Hebrew translation and need no new work")
        L.append("(spot-verified: stringId + English match the base entry).")
        L.append("UNTR. = strings unique to the DLC archive, no Hebrew at all —")
        L.append("the genuine Phantom Liberty translation gap.")
        L.append("")
        dlc_ons = [n for n in ONSCREENS_ORDER if n in dlc["buckets"]]
        dlc_sub = [n for n in DLC_SUBTITLE_ORDER if n in dlc["buckets"]]
        block("DLC ONSCREENS / UI TEXT  — from ep1 onscreens_final.json",
              dlc_ons, dlc["buckets"], dlc["samples"])
        block("DLC SUBTITLES / DIALOGUE", dlc_sub, dlc["buckets"], dlc["samples"])
        m = dlc["mirror"]
        L.append("─" * 78)
        L.append("DLC ep1 ONSCREENS.JSON — intermediate mirror (excluded from totals)")
        L.append("─" * 78)
        L.append(f"      total entries ............... {b_total(m):>9,}")
        L.append(f"      translated to Hebrew ........ {m['translated']:>9,}"
                 f"   ({b_pct(m):.1f}%)")
        L.append(f"      untranslated ................ {b_untranslated(m):>9,}")
        L.append("")

    # ── summary table ────────────────────────────────────────────────────────
    L.append("=" * 78)
    L.append("SUMMARY TABLE")
    L.append("=" * 78)
    L.append(f"{'Category':<42}{'Total':>8}{'Hebrew':>9}{'Untr.':>8}"
             f"{'N/A':>7}{'%Done':>8}")
    L.append("-" * 78)

    def trow(label, b):
        L.append(f"{label:<42.42}{b_total(b):>8,}{b['translated']:>9,}"
                 f"{b_untranslated(b):>8,}{b['na']:>7,}{b_pct(b):>7.1f}%")

    L.append("[ BASE GAME — Onscreens / UI text ]")
    for n in onscreens_cats:
        trow("  " + n, buckets[n])
    L.append("[ BASE GAME — Subtitles / dialogue ]")
    for n in subtitle_cats:
        trow("  " + n, buckets[n])
    L.append("-" * 78)
    trow("BASE GAME  (onscreens_final + subtitles)", GLOBAL)

    if dlc:
        L.append("")
        L.append("[ PHANTOM LIBERTY DLC — Onscreens / UI text ]")
        for n in [n for n in ONSCREENS_ORDER if n in dlc["buckets"]]:
            trow("  " + n, dlc["buckets"][n])
        L.append("[ PHANTOM LIBERTY DLC — Subtitles / dialogue ]")
        for n in [n for n in DLC_SUBTITLE_ORDER if n in dlc["buckets"]]:
            trow("  " + n, dlc["buckets"][n])
        L.append("-" * 78)
        trow("PHANTOM LIBERTY DLC  (all ep1 text)", dlc["GLOBAL"])
        GRAND = new_bucket()
        for k in GRAND:
            GRAND[k] = GLOBAL[k] + dlc["GLOBAL"][k]
        L.append("=" * 78)
        trow("GRAND TOTAL  (base game + DLC)", GRAND)
        L.append("=" * 78)
        L.append(f"{'GRAND TOTAL translatable entries':<42}"
                 f"{b_total(GRAND) - GRAND['na']:>8,}")
        L.append(f"{'GRAND TOTAL translated to Hebrew':<42}{GRAND['translated']:>8,}")
        L.append(f"{'GRAND TOTAL still to translate':<42}"
                 f"{b_untranslated(GRAND):>8,}")
    else:
        L.append("-" * 78)
        L.append(f"{'GLOBAL translatable entries':<42}"
                 f"{b_total(GLOBAL) - GLOBAL['na']:>8,}")
        L.append(f"{'GLOBAL still to translate':<42}{b_untranslated(GLOBAL):>8,}")
    L.append("")

    # ── base subtitle sections with the most gaps ────────────────────────────
    section_gaps.sort(key=lambda x: -x[1])
    L.append("─" * 78)
    L.append(f"TOP 30 BASE-GAME SUBTITLE SECTIONS BY UNTRANSLATED-LINE COUNT "
             f"({len(section_gaps):,} have gaps)")
    L.append("─" * 78)
    for sec, n in section_gaps[:30]:
        L.append(f"  {n:>5,}  {sec}")
    L.append("")

    if dlc and dlc["sub_gaps"]:
        gaps = sorted(dlc["sub_gaps"], key=lambda x: -x[1])
        L.append("─" * 78)
        L.append(f"TOP 30 DLC SUBTITLE SECTIONS BY UNTRANSLATED-LINE COUNT "
                 f"({len(gaps):,} have gaps)")
        L.append("─" * 78)
        for sec, n in gaps[:30]:
            L.append(f"  {n:>5,}  {sec}")
        L.append("")

    if onscreens_unmatched:
        L.append(f"NOTE: {onscreens_unmatched:,} base onscreens_final entries had no "
                 f"primaryKey match in localization_export.json — classified "
                 f"on their value alone.")
        L.append("")
    L.append("This report measures the translation DATA. In-game rendering")
    L.append("glitches (garbled glyphs) are a separate font/packaging matter")
    L.append("and are NOT visible to a data scan.")
    L.append("=" * 78)

    with open(REPORT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
