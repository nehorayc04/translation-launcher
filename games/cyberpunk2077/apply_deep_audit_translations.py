"""
apply_deep_audit_translations.py
=================================
One-shot patcher: applies the 5 manual Hebrew translations for the entries
flagged in cp2077_deep_english_audit category A (fixable_missing).

No LM Studio. The translations were written by hand, preserving every CR2W
tag (`<Rich color="..."/>`, `<Input actionName="..."/>`) and placeholder
(`{float_0}`) byte-for-byte. Backs the spine file up before modifying it.
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

SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
TRANSLATED  = os.path.join(SCRIPTS_DIR, "תרגום_משחקים", "source", "resources",
                           "localization_translated.json")

# (section, primaryKey)  ->  Hebrew femaleVariant
# pk=77919 and pk=87898 source texts came from the LIVE extract of
# lang_en_text.archive (the project's localization_export.json had them
# truncated). The Hebrew matches the FULL English source, not the truncated
# one — that's the real game text the player sees.
PATCHES: dict[tuple[str, str], str] = {
    ("onscreens/onscreens.json", "77919"):
        # Hazards are highlighted in <Red>. Hackable in <Green>. Useful in <Blue>.
        # Release <Input> to exit the scanner.
        'סכנות מודגשות ב<Rich color="MainColors.Red" style="Bold">אדום</>.\\n\\n'
        'עצמים פריצים מודגשים ב<Rich color="MainColors.Hacking" style="Bold">ירוק</>.\\n\\n'
        'עצמים שימושיים אחרת מודגשים ב<Rich color="MainColors.Blue" style="Bold">כחול</>.\\n\\n'
        '<Rich color="MainColors.Gold">שחרר</> '
        '<Input actionName="VisionHold" color="Tutorial.InputHint"></> '
        '<Rich color="MainColors.Gold">כדי לצאת מהסורק.</>',

    ("onscreens/onscreens.json", "87898"):
        # Unlocks <Focus> mode. Auto-activates while aiming at full Stamina.
        # No Stamina cost for shooting; -{float_1} Stamina; Duration {float_0} sec.
        'פותח את מצב <Rich color="TooltipText.cyberwareDescriptionHighlightColor" style="Semi-Bold">פוקוס</>. '
        'המצב מופעל אוטומטית כאשר אתה מכוון עם סטמינה מלאה.\\n\\n'
        'כשפעיל:\\n'
        '<Rich color="TooltipText.cyberwareDescriptionHighlightColor" style="Semi-Bold">אין עלות סטמינה לירי</>, '
        'מאפשר יריות מדויקות יותר.\\n\\n'
        'כשמסתיים:\\n'
        '<Rich color="TooltipText.cyberwareDescriptionHighlightColor" style="Semi-Bold">-{float_1} סטמינה</>\\n\\n'
        '<Rich color="TooltipText.cyberwareDescriptionHighlightColor" style="Semi-Bold">משך:</> {float_0} שנ\'.',

    # GPS shard email title — a 2-word UI label, blank in both mirror files.
    ("onscreens/onscreens.json",        "95358"): "חתימת GPS",
    ("onscreens/onscreens_final.json",  "95358"): "חתימת GPS",

    # Player dialogue option — the player chooses to remain silent.
    ("subtitles/quest/mq028/mq028_02_park.json", "1975313822573043712"):
        "[להישאר בשקט]",
}


def main() -> int:
    if not os.path.exists(TRANSLATED):
        print(f"FATAL: {TRANSLATED} not found", flush=True)
        return 1

    backup = f"{TRANSLATED}.bak.deep_audit_a.{time.strftime('%Y%m%d_%H%M%S')}"
    print(f"backing up: {TRANSLATED}")
    print(f"        -> {backup}")
    shutil.copy2(TRANSLATED, backup)

    with open(TRANSLATED, "r", encoding="utf-8") as f:
        data = json.load(f)

    applied: list[tuple[str, str, str, str]] = []
    misses: list[tuple[str, str]] = []
    for (section, pk), new_fv in PATCHES.items():
        entries = data.get(section)
        if not isinstance(entries, list):
            misses.append((section, pk))
            continue
        found = False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("primaryKey")) != pk:
                continue
            old_fv = entry.get("femaleVariant", "") or ""
            entry["femaleVariant"] = new_fv
            applied.append((section, pk, old_fv, new_fv))
            found = True
            break
        if not found:
            misses.append((section, pk))

    # Atomic write — temp file + os.replace.
    tmp = f"{TRANSLATED}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRANSLATED)

    print(f"\napplied: {len(applied)}/{len(PATCHES)}")
    for section, pk, old_fv, new_fv in applied:
        old_disp = (old_fv[:60] + "…") if len(old_fv) > 60 else old_fv
        new_disp = (new_fv[:60] + "…") if len(new_fv) > 60 else new_fv
        print(f"  + {section} pk={pk}")
        print(f"      OLD: {old_disp!r}")
        print(f"      NEW: {new_disp!r}")

    if misses:
        print(f"\nMISSES ({len(misses)}):")
        for section, pk in misses:
            print(f"  - {section} pk={pk}")
        return 2

    new_size = os.path.getsize(TRANSLATED)
    print(f"\nsaved: {TRANSLATED}  ({new_size:,} bytes)")
    print("\nNext step: re-bake the onscreens + the one subtitle file:")
    print("  python rebuild_onscreens_and_pack.py")
    print("  python rebuild_subtitles_and_pack.py --sections subtitles/quest/mq028/mq028_02_park.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
