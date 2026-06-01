"""Three UI translation bug fixes for localization_translated.json:

1. Time format — replace Hebrew time labels with English H/M:
     "{var} שעות"/"{var} שעה" → "{var}H"
     "{var} דקות"/"{var} דקה" → "{var}M"
     "{var} min"               → "{var}M"
     "10ה 23מ"                 → "10H 23M"
   Applied globally (the placeholder/digit prefix prevents prose matches).

2. Enter prompt — replace past-tense / wrong-form Hebrew with imperative.
   Only applied where the ENGLISH source starts with a command verb
   (Enter/Get In/Sit/Drive/etc.) so e.g. "incoming damage" / "Incoming
   Call" / "ENTERING A NEW AREA" stay untouched.

3. Level label sanity — fix the one known mistranslation pk=1539
   "LEVEL" → "רביד" (necklace) → "רמה" (level).

After running this, audit the changes and execute
rebuild_onscreens_and_pack.py.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", write_through=True)

SCRIPTS_DIR = Path(r"C:\Users\Nehoray_Cohen\Projects\Game translator")
RES = SCRIPTS_DIR / "תרגום_משחקים" / "source" / "resources"
TRANSLATED = RES / "localization_translated.json"
ENGLISH    = RES / "localization_export.json"

SECTIONS = ("onscreens/onscreens.json", "onscreens/onscreens_final.json")

# ── Bug 1 — time format ─────────────────────────────────────────────────
# Apply globally; the `{...}` / digit prefix means we only touch real time
# format strings, not prose. Each tuple: (regex, replacement).
TIME_SUBS = [
    # `{var}` placeholder + Hebrew/English time-unit label
    (re.compile(r"(\{[^}]*\})\s*שעות\b"),    r"\1H"),
    (re.compile(r"(\{[^}]*\})\s*שעה\b"),     r"\1H"),
    (re.compile(r"(\{[^}]*\})\s*שע'"),       r"\1H"),
    (re.compile(r"(\{[^}]*\})\s*ש'"),        r"\1H"),
    (re.compile(r"(\{[^}]*\})\s*דקות\b"),    r"\1M"),
    (re.compile(r"(\{[^}]*\})\s*דקה\b"),     r"\1M"),
    (re.compile(r"(\{[^}]*\})\s*דק'"),       r"\1M"),
    (re.compile(r"(\{[^}]*\})\s*ד'"),        r"\1M"),
    (re.compile(r"(\{[^}]*\})\s*min\b"),     r"\1M"),
    (re.compile(r"(\{[^}]*\})\s*hours?\b"),  r"\1H"),
    # Literal digit time pairs ("10ה 23מ" → "10H 23M")
    (re.compile(r"(\d+)\s*ה\s+(\d+)\s*מ(?!״)\b"), r"\1H \2M"),
]


def fix_time(text: str) -> str:
    out = text
    for pat, repl in TIME_SUBS:
        out = pat.sub(repl, out)
    return out


# ── Bug 2 — Enter prompt ────────────────────────────────────────────────
# English-source filter: only entries whose English starts with a
# command verb are eligible. Word boundary required so "Enter" matches
# but "Entering" / "Encounter" don't.
ENTER_SOURCES = re.compile(
    r"^\s*("
    r"Enter\b|Mount\b|Drive\b|Sit\b|Board\b|Take\s+a\s+Seat|"
    r"Get\s+(?:In|On)\b|Hop\s+(?:In|On)\b|Climb\s+(?:In|On)\b"
    r")",
    re.IGNORECASE,
)

# Ordered longest-first — multi-char phrases beat single-word subsets so
# "הישבו כאן" gets the dedicated mapping before the plain "ישב" rule fires.
HEBREW_IMPERATIVE = [
    # Enter compounds (preserve trailing object)
    ("הכנס למצב",   "כנס למצב"),
    ("היכנס למצב",  "כנס למצב"),
    ("היכנס למערכה", "כנס למערכה"),
    ("היכנס ל",     "כנס ל"),
    ("הכנס ל",      "כנס ל"),
    ("נכנס ל",      "כנס ל"),
    ("תכנס ל",      "כנס ל"),
    ("הכנס",        "כנס"),
    ("היכנס",       "כנס"),
    ("תכנס",        "כנס"),
    ("נכנס",        "כנס"),
    # Sit
    ("הישבו כאן",   "שב כאן"),
    ("ישב פה",      "שב כאן"),
    ("ישב כאן",     "שב כאן"),
    ("הישבו",       "שב"),
    ("ישבו",        "שב"),
    ("לשבת",        "שב"),
    ("ישב",         "שב"),
    # Drive
    ("נסע ל",       "סע ל"),
    ("נסע",         "סע"),
]


def fix_enter_prompt(en_src: str, he_text: str) -> str:
    if not he_text or not en_src:
        return he_text
    if not ENTER_SOURCES.match(en_src):
        return he_text
    out = he_text
    for src, dst in HEBREW_IMPERATIVE:
        out = out.replace(src, dst)
    return out


# ── Bug 3 — pk=1539 LEVEL mistranslation ────────────────────────────────
LEVEL_FIX_PK = "1539"
LEVEL_FIX_FROM = "רביד"
LEVEL_FIX_TO   = "רמה"


# ────────────────────────────────────────────────────────────────────────
def main() -> int:
    print(f"[*] Loading {TRANSLATED.name}")
    with open(TRANSLATED, "r", encoding="utf-8") as f:
        he = json.load(f)
    print(f"[*] Loading {ENGLISH.name}")
    with open(ENGLISH, "r", encoding="utf-8") as f:
        en = json.load(f)

    en_idx: dict[str, dict[str, dict]] = {}
    for section in SECTIONS:
        en_idx[section] = {
            str(e["primaryKey"]): e
            for e in en.get(section, [])
            if isinstance(e, dict) and e.get("primaryKey") is not None
        }

    time_fixed   = 0
    enter_fixed  = 0
    level_fixed  = 0
    samples_time, samples_enter, samples_level = [], [], []

    for section in SECTIONS:
        rows = he.get(section, [])
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            pk = str(entry.get("primaryKey"))
            eng = en_idx.get(section, {}).get(pk, {})
            en_fv = (eng.get("femaleVariant") or "").strip()
            en_mv = (eng.get("maleVariant")   or "").strip()

            for field, en_src in (("femaleVariant", en_fv or en_mv),
                                  ("maleVariant",   en_mv or en_fv)):
                old = entry.get(field) or ""
                if not old:
                    continue
                new = old

                # 1. Time format (apply unconditionally — pattern self-gates)
                stage = fix_time(new)
                if stage != new:
                    if len(samples_time) < 6:
                        samples_time.append((section, pk, field, new, stage))
                    new = stage
                    time_fixed += 1

                # 2. Enter prompt (English-source-gated)
                stage = fix_enter_prompt(en_src, new)
                if stage != new:
                    if len(samples_enter) < 8:
                        samples_enter.append((section, pk, field, new, stage))
                    new = stage
                    enter_fixed += 1

                # 3. LEVEL mistranslation
                if pk == LEVEL_FIX_PK and LEVEL_FIX_FROM in new:
                    stage = new.replace(LEVEL_FIX_FROM, LEVEL_FIX_TO)
                    samples_level.append((section, pk, field, new, stage))
                    new = stage
                    level_fixed += 1

                if new != old:
                    entry[field] = new

    stamp = time.strftime("%Y%m%d_%H%M%S")
    bak = TRANSLATED.with_suffix(f".json.bak.uibugs.{stamp}")
    bak.write_bytes(TRANSLATED.read_bytes())
    print(f"[bak] {bak.name}")

    tmp = TRANSLATED.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(he, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRANSLATED)

    print()
    print(f"[*] time-format substitutions: {time_fixed}")
    print(f"[*] Enter-prompt fixes:        {enter_fixed}")
    print(f"[*] LEVEL pk=1539 mistranslation fixes: {level_fixed}")
    print()
    print("Sample time fixes:")
    for s, p, f, b, a in samples_time:
        print(f"  {s}:{p} [{f}]")
        print(f"    before: {b[:80]}")
        print(f"    after:  {a[:80]}")
    print()
    print("Sample Enter-prompt fixes:")
    for s, p, f, b, a in samples_enter:
        print(f"  {s}:{p} [{f}]")
        print(f"    before: {b[:80]}")
        print(f"    after:  {a[:80]}")
    print()
    if samples_level:
        print("Level pk=1539 fix:")
        for s, p, f, b, a in samples_level:
            print(f"  {s}:{p} [{f}] {b!r} -> {a!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
