"""
build_phase1_queue.py
=====================
Builds cleanup_queue.json for PHASE 1 — base-game completion.

Targets exactly the untranslated BASE-GAME entries that cp2077_status_report.py
counts: the game-facing onscreens file (onscreens_final.json) + every base-game
subtitle section. The Phantom Liberty DLC is excluded automatically —
localization_translated.json contains no `ep1/` sections (the DLC text lives
only in dlc_ep1_text.json, which this builder never opens).

It reuses cp2077_status_report's classifier, so the queue matches the report's
count exactly. translate_cleanup_all.py (section-aware) consumes the result.

Outputs:
  cleanup_queue.json            — the queue translate_cleanup_all.py reads
  phase1_subtitle_sections.txt  — the affected subtitle sections, for the
                                  rebuild_subtitles_and_pack.py --sections-file
                                  re-bake step after translation
"""
from __future__ import annotations

import json
import os
import sys
import time

# Run-from-anywhere safety: the project convention is to run scripts from
# SCRIPTS_DIR, but make the cp2077_status_report import robust regardless.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import cp2077_status_report as rep   # reuse the EXACT classifier

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

QUEUE        = os.path.join(rep.SCRIPTS_DIR, "cleanup_queue.json")
SECTIONS_TXT = os.path.join(rep.SCRIPTS_DIR, "phase1_subtitle_sections.txt")

# A base-game entry needs work when the report classifies it as one of these.
UNTRANSLATED = {"untranslated_english", "untranslated_arabic", "missing"}


def main() -> int:
    print(f"[*] loading {rep.TRANSLATED}")
    with open(rep.TRANSLATED, "r", encoding="utf-8") as f:
        translated = json.load(f)
    print(f"[*] loading {rep.EXPORT}")
    with open(rep.EXPORT, "r", encoding="utf-8") as f:
        export = json.load(f)

    # English-source pk index for the game-facing onscreens file — needed to
    # supply the source text for entries whose translation is simply blank.
    onscreens_en: dict = {}
    for e in export.get(rep.ONSCREENS_PRIMARY, []):
        if isinstance(e, dict) and e.get("primaryKey") is not None:
            onscreens_en[e["primaryKey"]] = (e.get("femaleVariant")
                                             or e.get("maleVariant") or "")
    del export

    queue: list[dict] = []
    n_onscreens = 0
    n_subtitles = 0
    single_word = 0
    subtitle_sections: set[str] = set()

    # ── onscreens — game-facing onscreens_final.json only ───────────────────
    # The onscreens.json intermediate mirror has no player-facing role (see
    # cp2077_status_report.py) and is deliberately not queued.
    for e in translated.get(rep.ONSCREENS_PRIMARY, []):
        if not isinstance(e, dict):
            continue
        pk      = e.get("primaryKey")
        english = onscreens_en.get(pk, "")
        value   = ((e.get("femaleVariant") or "").strip()
                   or (e.get("maleVariant") or "").strip())
        if rep.classify(english, value) not in UNTRANSLATED:
            continue
        src = (english or "").strip() or value
        if not src or not rep.needs_translation(src):
            continue
        if len(rep.clean(src).split()) < 2:
            single_word += 1
        queue.append({
            "section":        rep.ONSCREENS_PRIMARY,
            "primaryKey":     pk,
            "secondaryKey":   e.get("secondaryKey") or "",
            "english_female": src,
            "english_male":   "",
        })
        n_onscreens += 1

    # ── subtitles — every base-game subtitle section ────────────────────────
    for sec, rows in translated.items():
        if not sec.startswith("subtitles/") or not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            english = e.get("secondaryKey", "")        # subtitle EN source
            value   = ((e.get("femaleVariant") or "").strip()
                       or (e.get("maleVariant") or "").strip())
            if rep.classify(english, value) not in UNTRANSLATED:
                continue
            src = (english or "").strip() or value
            if not src or not rep.needs_translation(src):
                continue
            if len(rep.clean(src).split()) < 2:
                single_word += 1
            queue.append({
                "section":        sec,
                "primaryKey":     e.get("primaryKey"),
                "secondaryKey":   e.get("secondaryKey") or "",
                "english_female": src,
                "english_male":   "",
            })
            subtitle_sections.add(sec)
            n_subtitles += 1

    # Back up any existing queue before overwriting.
    if os.path.exists(QUEUE):
        bak = QUEUE + ".bak." + time.strftime("%Y%m%d_%H%M%S")
        os.replace(QUEUE, bak)
        print(f"[*] backed up existing queue -> {os.path.basename(bak)}")

    payload = {
        "_metadata": {
            "built":     time.strftime("%Y-%m-%d %H:%M:%S"),
            "purpose":   "Phase 1 — base-game completion",
            "scope":     "base game only (onscreens_final + subtitles); "
                         "Phantom Liberty DLC excluded",
            "count":     len(queue),
            "onscreens": n_onscreens,
            "subtitles": n_subtitles,
            "single_word_proper_nouns": single_word,
        },
        "queue": queue,
    }
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(SECTIONS_TXT, "w", encoding="utf-8") as f:
        f.write(",".join(sorted(subtitle_sections)))

    print()
    print(f"[OK] Phase 1 queue: {len(queue):,} entries -> cleanup_queue.json")
    print(f"     onscreens (onscreens_final.json): {n_onscreens:,}")
    print(f"     subtitles ({len(subtitle_sections):,} sections): {n_subtitles:,}")
    print(f"     single-word / proper-noun-ish entries: {single_word:,}")
    print(f"[OK] subtitle section list -> {os.path.basename(SECTIONS_TXT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
