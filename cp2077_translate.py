import json
import os
import time
import re
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

INPUT_FILE = r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים\source\resources\localization_export.json"
OUTPUT_FILE = r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים\source\resources\localization_translated.json"


def needs_translation(text):
    """בודק אם הטקסט באמת דורש תרגום כדי לחסוך קריאות ל-AI"""
    if not isinstance(text, str) or not text.strip():
        return False
    if "\x00" in text or "\ufffd" in text:
        return False
    # אם אין בכלל אותיות באנגלית - אין מה לתרגם
    if not re.search(r"[a-zA-Z]", text):
        return False
    # סופר כמה אותיות (ללא סימנים ומספרים) יש בטקסט
    letters_only = re.sub(r"[^a-zA-Z]", "", text)
    # אם יש פחות מ-2 אותיות (למשל "+W" או "Q"), לדלג על זה (מקשי משחק)
    if len(letters_only) <= 1:
        return False
    return True


def clean_text_for_ai(text):
    if not isinstance(text, str):
        return ""
    cleaned_text = re.sub(r"[^\x20-\x7E\u0590-\u05FF\n\r\t]", "", text)
    return cleaned_text.strip()


# ── ניקוי תשובה מהמודל ────────────────────────────────────────────────────────
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREFIX_RE = re.compile(
    r"^\s*(?:translation|תרגום|hebrew|output|answer)\s*[:\-]\s*",
    re.IGNORECASE,
)


def clean_response(raw):
    """מסיר עטיפות שכיחות של מודלים: <think>, markdown, ציטוטים, קידומות."""
    if not isinstance(raw, str):
        return ""
    s = _THINK_RE.sub("", raw).strip()
    # ציטוטים עוטפים
    while len(s) >= 2 and s[0] == s[-1] and s[0] in ("\"", "'", "`", "“", "”", "„"):
        s = s[1:-1].strip()
    # markdown wrapping
    s = re.sub(r"^\*+\s*(.+?)\s*\*+$", r"\1", s).strip()
    s = re.sub(r"^_+\s*(.+?)\s*_+$", r"\1", s).strip()
    # קידומות שכיחות
    s = _PREFIX_RE.sub("", s).strip()
    return s


def translate_hebrew(text, retries=3):
    # שלב 1: סינון לפני ניקוי
    if not needs_translation(text):
        return text

    # שלב 2: ניקוי + סינון חוזר (אם הניקוי הוריד תווים והשאיר ≤1 אות)
    cleaned_text = clean_text_for_ai(text)
    if not cleaned_text or not needs_translation(cleaned_text):
        return text

    system_prompt = (
        "Translate the user's English text to Hebrew. "
        "Output the Hebrew translation only. "
        "No explanations, no notes, no markdown, no quotes, no prefix like 'Translation:'. "
        "No <think> tags. No reasoning. Just the Hebrew text on a single line. "
        "Keep tags like <n>, <br>, {0}, %s exactly as written. "
        "Keep proper nouns (Night City, V, Johnny, Arasaka) transliterated naturally."
    )

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="local-model",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": cleaned_text},
                ],
                temperature=0.2,
                max_tokens=512,
            )
            raw = response.choices[0].message.content
            cleaned = clean_response(raw)
            if cleaned:
                return cleaned
            print(f"    [!] Empty/garbage response attempt {attempt + 1}: {raw!r}")
        except Exception as e:
            print(f"    [-] Translation Error on attempt {attempt + 1}: {e}")
            time.sleep(2)

    print(
        f"    [!] Failed to translate after {retries} attempts: {cleaned_text[:50]}..."
    )
    return text


def main():
    print(f"[*] Loading source file: {INPUT_FILE}")
    if not os.path.exists(INPUT_FILE):
        print("[!] Input JSON not found. Check the path again.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    translated_data = {}

    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                translated_data = json.load(f)
            print("[*] Found existing output. Resuming...")
        except json.JSONDecodeError:
            print("[!] Existing output file is corrupted, starting fresh.")

    total_files = len(data)
    file_count = 0
    ALLOWED_FOLDERS = ["onscreens", "subtitles"]

    for filepath, entries in data.items():
        file_count += 1
        if not any(folder in filepath.lower() for folder in ALLOWED_FOLDERS):
            if filepath not in translated_data:
                translated_data[filepath] = entries
            continue

        if filepath not in translated_data:
            translated_data[filepath] = []

        start_index = len(translated_data[filepath])
        total_entries = len(entries)

        if start_index >= total_entries:
            continue

        print(f"\n[*] Processing file {file_count}/{total_files}: {filepath}")

        for i in range(start_index, total_entries):
            entry = entries[i]
            translated_entry = entry.copy()

            if entry.get("femaleVariant"):
                translated_entry["femaleVariant"] = translate_hebrew(
                    entry["femaleVariant"]
                )
            if entry.get("maleVariant"):
                translated_entry["maleVariant"] = translate_hebrew(entry["maleVariant"])

            translated_data[filepath].append(translated_entry)

            if (i + 1) % 20 == 0 or (i + 1) == total_entries:
                print(f"    [+] Processed {i+1}/{total_entries} entries")
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(translated_data, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    print("\n[*] Translation complete!")


if __name__ == "__main__":
    main()
