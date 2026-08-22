# -*- coding: utf-8 -*-
"""
Export the next untranslated batch as a ready-to-paste Gemini prompt.

Usage:
  python gowr_batch_export.py           # exports next 150 strings
  python gowr_batch_export.py 300       # exports next 300 strings

Output:  prompts/batch_NNN_prompt.txt   (paste this into Gemini)
         prompts/batch_NNN_ids.json     (internal — maps position -> id)
"""
import os, sys, json, re, textwrap

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE  = os.path.dirname(os.path.abspath(__file__))
EN_F  = os.path.join(HERE, "english.json")
AR_F  = os.path.join(HERE, "arabic.json")
OUT_F = os.path.join(HERE, "hebrew.json")
PDIR  = os.path.join(HERE, "prompts")
os.makedirs(PDIR, exist_ok=True)

BATCH_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 150

SYSTEM_PROMPT = textwrap.dedent("""\
    אתה מתרגם מקצועי של המשחק God of War: Ragnarök מאנגלית לעברית.

    חוקים נוקשים:
    1. תרגם לעברית. אותיות לטיניות מותרות רק עבור שמות מותג/קוד שאין להם תרגום.
    2. אל תשתמש בניקוד.
    3. שמור על כל תג/placeholder בדיוק: [[S:...]] רמזי קול, [style=...]/[/style], [i]/[/i],
       [Icons:...], [...Button], %d, %s, וגם \\n כמחרוזת מילולית.
    4. אל תתרגם את הטקסט בתוך [[S:...]] — זה רמז לאודיו.
    5. שמות דמויות ותחומות בעברית קבועה:
       Kratos=קרייטוס, Atreus=אטראוס, Mimir=מימיר, Freya=פריה, Brok=ברוק,
       Sindri=סינדרי, Tyr=טיר, Thor=ת'ור, Odin=אודין, Angrboda=אנגרבודה,
       Heimdall=היימדל, Svartalfheim=סוורטלפהיים, Midgard=מידגארד,
       Asgard=אסגארד, Ragnarok=ראגנארוק, Valhalla=ולהאלה.
    6. שמור VERBATIM (אל תתרגם/תלטין): רונות נורדיות עתיקות (ᚠᚢᚦᚨᚱ…), מילים לטיניות
       עצמאיות/קודים, ספרות 0-9, ופיסוק בסיסי ? ! @ & %.
       שורה שכולה רונות/לטינית/ספרות/פיסוק — מחזיר אותה ללא שינוי.
    7. פלט אך ורק אובייקט JSON תקני בצורה:
       {"ID": "תרגום עברי", "ID2": "תרגום אחר", ...}
       ללא טקסט לפני או אחרי ה-JSON.
""")


def is_dev_meta(v):
    return (not v.strip()) or v.startswith("Design#") or v in ("OBSOLETE", "CUT")


def next_batch_num():
    nums = []
    for f in os.listdir(PDIR):
        m = re.match(r"batch_(\d+)_prompt\.txt", f)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def main():
    en   = json.load(open(EN_F, encoding="utf-8"))
    ar   = json.load(open(AR_F, encoding="utf-8"))
    done = {}
    try:
        done = json.load(open(OUT_F, encoding="utf-8"))
    except (OSError, ValueError):
        pass

    queue = []
    for k in sorted(ar, key=lambda x: int(x)):
        if k in done:
            continue
        src = en.get(k, "")
        if not src or is_dev_meta(src):
            continue
        queue.append((k, src))

    if not queue:
        print("כל המחרוזות תורגמו!"); return 0

    batch = queue[:BATCH_SIZE]
    num   = next_batch_num()

    # Build prompt
    lines = [SYSTEM_PROMPT, "\nמחרוזות לתרגום:\n"]
    for k, src in batch:
        # escape internal newlines so the JSON stays on one line
        safe = src.replace("\\n", "\\\\n")
        lines.append(f'"{k}": "{safe}"')

    prompt_text = "\n".join(lines)

    prompt_path = os.path.join(PDIR, f"batch_{num:03d}_prompt.txt")
    ids_path    = os.path.join(PDIR, f"batch_{num:03d}_ids.json")

    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt_text)

    with open(ids_path, "w", encoding="utf-8") as f:
        json.dump([k for k, _ in batch], f)

    remaining = len(queue) - len(batch)
    print(f"באצ' {num:03d}  |  {len(batch)} מחרוזות  |  נותרו {remaining:,} אחרי באצ' זה")
    print(f"פרומפט: {prompt_path}")
    print(f"\nהעתק את תוכן הקובץ הזה ל-Gemini ב-Antigravity IDE.")
    print("לאחר שתקבל תשובה, שמור אותה ל-prompts/batch_NNN_response.txt")
    print(f"ואז הרץ:  python gowr_batch_import.py {num:03d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
