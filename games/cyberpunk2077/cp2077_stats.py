import json
import re
import sys
import os
import time

BASE = r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים\source\resources"
ORIGINAL_FILE = os.path.join(BASE, "localization_export.json")
TRANSLATED_FILE = os.path.join(BASE, "localization_translated.json")


def v(text):
    if not isinstance(text, str):
        return text
    text = text.replace("(", "TEMP_LP").replace(")", "TEMP_RP")
    text = text.replace("TEMP_LP", ")").replace("TEMP_RP", "(")
    reversed_text = text[::-1]
    return re.compile(r"[A-Za-z0-9\.\-\:\>]+").sub(
        lambda m: m.group(0)[::-1], reversed_text
    )


def format_time_v(total_seconds):
    ts = int(total_seconds)
    d = ts // 86400
    h = (ts % 86400) // 3600
    m = (ts % 3600) // 60
    s = ts % 60
    parts = []
    if d > 0:
        parts.append(f"{d} ימים")
    if h > 0:
        parts.append(f"{h} שעות")
    if m > 0:
        parts.append(f"{m} דקות")
    parts.append(f"{s} שניות")
    res = ", ".join(parts[:-1]) + " ו " + parts[-1] if len(parts) > 1 else parts[0]
    return v(res)


def print_line(label, value, width=45):
    label_v = v(label)
    dots = "." * (width - len(label_v))
    print(f" {label_v} {dots} {value}")


def needs_translation(text):
    """בודק אם הטקסט דורש תרגום. אם לא, הסטטיסטיקה לא תצפה לעברית."""
    if not isinstance(text, str) or not text.strip():
        return False
    if not re.search(r"[a-zA-Z]", text):
        return False
    letters_only = re.sub(r"[^a-zA-Z]", "", text)
    if len(letters_only) <= 1:
        return False
    return True


def classify(orig, trans):
    if not isinstance(orig, str) or not orig.strip():
        return "empty_orig"
    if "\x00" in orig or "\ufffd" in orig:
        return "garbage_orig"

    # אם הטקסט לא דורש תרגום (מקשים, סמלים), נחשיב אותו כ"הושלם" (דולג תקין)
    if not needs_translation(orig):
        return "skipped_no_translation_needed"

    if not isinstance(trans, str) or not trans.strip():
        return "missing"
    if "\x00" in trans or "\ufffd" in trans:
        return "garbage_trans"
    if not bool(re.search(r"[א-תיִ-פֿ]", trans)):
        return "no_hebrew"
    return "done"


def load_json(path, label):
    size_mb = os.path.getsize(path) / 1_048_576
    print(f" טוען {label} ({size_mb:.1f} MB)...", end="", flush=True)
    t0 = time.time()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f" {time.time()-t0:.1f}s, {len(data):,} קבצים")
    return data


def scan_stats(original, translated):
    counts = {
        k: 0
        for k in (
            "done",
            "empty_orig",
            "garbage_orig",
            "skipped_no_translation_needed",
            "missing",
            "no_hebrew",
            "garbage_trans",
        )
    }
    ALLOWED_FOLDERS = ["onscreens", "subtitles"]
    total_files = len(original)
    t_last = time.time()

    for idx, (filepath, orig_entries) in enumerate(original.items(), 1):
        if not any(folder in filepath.lower() for folder in ALLOWED_FOLDERS):
            continue

        trans_entries = translated.get(filepath, [])
        for i, orig in enumerate(orig_entries):
            t = trans_entries[i] if i < len(trans_entries) else {}
            for field in ("femaleVariant", "maleVariant"):
                ov = orig.get(field, "")
                tv = t.get(field, "") if isinstance(t, dict) else ""
                counts[classify(ov, tv)] += 1
        now = time.time()
        if now - t_last >= 0.1:
            pct_scan = 100 * idx // total_files
            print(
                f"\r  סורק... {idx:,}/{total_files:,} קבצים ({pct_scan}%)   ",
                end="",
                flush=True,
            )
            t_last = now
    print(f"\r  סריקה הסתיימה: {total_files:,} קבצים                    ")
    return counts


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def display(counts, last_mod, scan_secs):
    total = sum(counts.values())
    done = counts["done"]
    # כעת אנחנו לא מחשיבים סמלים ומקשים כ"דורשים תרגום"
    skippable = (
        counts["empty_orig"]
        + counts["garbage_orig"]
        + counts["skipped_no_translation_needed"]
    )
    actionable = total - skippable
    need = counts["missing"] + counts["no_hebrew"] + counts["garbage_trans"]
    pct = round(100 * done / actionable, 2) if actionable else 0

    clear_screen()
    print("\n" + "=" * 61)
    print(f" {v('2077 Cyberpunk          ')} :{v('תרגום המשחק')} :{v('פרויקט')}")
    print("=" * 61)

    print_line('סה"כ שדות בתיקיות המטרה', f"{total:,}")
    print_line("שדות שדורשים תרגום", f"{actionable:,}")
    print_line(
        "שדות UI (מקשים/סמלים - דולגו)", f"{counts['skipped_no_translation_needed']:,}"
    )
    print("-" * 61)
    print_line("תורגם בהצלחה", f"{done:,} ({pct}%)")
    print_line("נותר לתרגום ה-AI", f"{need:,}")
    print("=" * 61)

    if need > 0:
        # cp2077_fix_missing_translations.py — Gemma-2-27b, batch=3
        # ~5 sec/batch on RX 7900 XT → ~1.7 sec/entry
        print(f"\n {v('הערכת זמן לסיום (fix script, batch=3)')}: {format_time_v(need * 1.7)}")
    print(
        f"\n {v('זמן סריקה')}: {scan_secs:.1f}s | {v('...ממתין לשינוי בקובץ')} [{time.strftime('%H:%M:%S')}]"
    )


def main():
    try:
        original = load_json(ORIGINAL_FILE, "localization_export.json")
    except Exception as e:
        print(f"שגיאה בטעינת קובץ מקור: {e}")
        sys.exit(1)

    translated = None
    last_mtime = None
    counts = None
    scan_secs = 0.0

    try:
        while True:
            try:
                mtime = os.path.getmtime(TRANSLATED_FILE)
            except OSError:
                print(f"\r  ...ממתין לקובץ  ", end="", flush=True)
                time.sleep(2)
                continue

            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
                        translated = json.load(f)
                except Exception as e:
                    print(f"\n  שגיאה בטעינת translated: {e}")
                    time.sleep(2)
                    continue

                last_mod = time.ctime(mtime)
                t0 = time.time()
                counts = scan_stats(original, translated)
                scan_secs = time.time() - t0
                display(counts, last_mod, scan_secs)
            else:
                time.sleep(1)
                if counts is not None:
                    print(
                        f"\r יונישל ןיתממ... [{time.strftime('%H:%M:%S')}]   ",
                        end="",
                        flush=True,
                    )
    except KeyboardInterrupt:
        print(f"\n {v('המעקב הופסק לבקשת המשתמש.')}")


if __name__ == "__main__":
    main()
