import json
import os
import re
import urllib.request
import urllib.parse
import time
import sys
from deep_translator import GoogleTranslator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Token regexes from _tokens.py
TOKEN_RE = re.compile(r"~[^~]*~|</?[A-Za-z][^>]*>|%[0-9]*[sdifx%]")
HEB_RE = re.compile("[֐-׿יִ-ﭏ]")
NIQQUD_RE = re.compile("[֑-ׇֽֿׁׂׅׄ]")
FOREIGN_RE = re.compile("[Ѐ-ӿ؀-ۿ฀-๿぀-ヿ㐀-鿿가-힯]")

def tokens(s):
    return sorted(TOKEN_RE.findall(s or ""))

def has_hebrew(s):
    return bool(HEB_RE.search(s or ""))

def has_niqqud(s):
    return bool(NIQQUD_RE.search(s or ""))

def foreign_chars(s):
    return FOREIGN_RE.findall(s or "")

def real_word(en):
    return bool(re.search(r"[a-z]{2,}", en or ""))

# Glossary translation mapping
GLOSSARY = {
    r"\bWanted level\b": "דרגת מבוקש",
    r"\bwanted level\b": "דרגת מבוקש",
    r"\bHealth\b": "בריאות",
    r"\bhealth\b": "בריאות",
    r"\bArmor\b": "שריון",
    r"\barmor\b": "שריון",
    r"\bAmmo\b": "תחמושת",
    r"\bammo\b": "תחמושת",
    r"\bWasted\b": "חוסל",
    r"\bwasted\b": "חוסל",
    r"\bBusted\b": "נתפס",
    r"\bbusted\b": "נתפס",
    r"\bMission Passed\b": "המשימה הושלמה",
    r"\bmission passed\b": "המשימה הושלמה",
    r"\bMission Failed\b": "המשימה נכשלה",
    r"\bmission failed\b": "המשימה נכשלה",
    r"\bCheckpoint\b": "נקודת ביקורת",
    r"\bcheckpoint\b": "נקודת ביקורת",
    r"\bStory Mode\b": "מצב סיפור",
    r"\bstory mode\b": "מצב סיפור",
    r"\bGTA Online\b": "GTA אונליין",
    r"\bgta online\b": "GTA אונליין",
    r"\bWeapon Wheel\b": "גלגל הנשק",
    r"\bweapon wheel\b": "גלגל הנשק",
    r"\bQuick Save\b": "שמירה מהירה",
    r"\bquick save\b": "שמירה מהירה",
    r"\bAutosave\b": "שמירה אוטומטית",
    r"\bautosave\b": "שמירה אוטומטית",
    r"\bMission\b": "משימה",
    r"\bmission\b": "משימה",
    r"\bHeist\b": "שוד",
    r"\bheist\b": "שוד",
    r"\bGarage\b": "מוסך",
    r"\bgarage\b": "מוסך",
    r"\bMap\b": "מפה",
    r"\bmap\b": "מפה",
    r"\bSettings\b": "הגדרות",
    r"\bsettings\b": "הגדרות",
    r"\bCash\b": "מזומן",
    r"\bcash\b": "מזומן",
    r"\bVehicle\b": "רכב",
    r"\bvehicle\b": "רכב",
    r"\bAim\b": "כוונת",
    r"\baim\b": "כוונת",
    r"\bReload\b": "טעינה",
    r"\breload\b": "טעינה",
    r"\bSprint\b": "ריצה",
    r"\bsprint\b": "ריצה",
    r"\bCover\b": "מחסה",
    r"\bcover\b": "מחסה",
    r"\bReward\b": "תגמול",
    r"\breward\b": "תגמול",
    r"\bCrew\b": "חבורה",
    r"\bcrew\b": "חבורה",
    r"\bSuspect\b": "חשוד",
    r"\bsuspect\b": "חשוד",
}

def translate_text_raw(text):
    """Query Google Translate using deep-translator (supports newlines)."""
    backoff = 2
    for attempt in range(5):
        try:
            translated = GoogleTranslator(source='en', target='iw').translate(text)
            return translated
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                print(f"[API] 429 Too Many Requests. Sleeping {backoff}s...", flush=True)
                time.sleep(backoff)
                backoff *= 2
            else:
                print(f"[API] Error: {e}. Retrying...", flush=True)
                time.sleep(backoff)
    return None

def preprocess_string(en_str):
    """Replace formatting tokens with placeholders, grouping adjacent ones."""
    matches = list(TOKEN_RE.finditer(en_str))
    if not matches:
        return en_str, {}
        
    # Group adjacent tokens
    groups = []
    current_group = [matches[0]]
    for m in matches[1:]:
        last_m = current_group[-1]
        inter_text = en_str[last_m.end():m.start()]
        if not inter_text.strip():
            current_group.append(m)
        else:
            groups.append(current_group)
            current_group = [m]
    groups.append(current_group)
    
    # Replace groups with placeholders
    placeholder_map = {}
    temp_str = ""
    last_idx = 0
    for i, g in enumerate(groups):
        start = g[0].start()
        end = g[-1].end()
        temp_str += en_str[last_idx:start]
        placeholder = f" _T{i}_ "
        temp_str += placeholder
        
        original_combined = en_str[start:end]
        placeholder_map[placeholder.strip()] = original_combined
        last_idx = end
    temp_str += en_str[last_idx:]
    
    return temp_str, placeholder_map

def postprocess_translation(he_translated, placeholder_map):
    """Restore tokens, strip niqqud, and clean spacing artifacts."""
    if not he_translated:
        return None
        
    # Strip niqqud
    he_translated = NIQQUD_RE.sub("", he_translated)
    
    # Restore tokens
    restored = he_translated
    for placeholder, original in placeholder_map.items():
        pattern = re.compile(r'\s*' + re.escape(placeholder) + r'\s*|\s*' + re.escape(placeholder.strip()) + r'\s*')
        if original == "~n~":
            restored = pattern.sub("\n", restored)
        elif "~n~" in original:
            # If the original combined placeholder contains newlines, translate them to real newlines
            restored = pattern.sub(original.replace("~n~", "\n"), restored)
        else:
            restored = pattern.sub(original, restored)

    restored = restored.replace("\n", "~n~")
    
    # Clean spacing inside tildes (e.g. ~ r ~ -> ~r~)
    def clean_tildes(m):
        inner = m.group(1).replace(" ", "")
        return f"~{inner}~"
    restored = re.sub(r"~\s*([^~]+?)\s*~", clean_tildes, restored)

    # Clean double spaces
    restored = re.sub(r' {2,}', ' ', restored).strip()

    return restored

def enforce_glossary(en, he):
    """Apply the glossary terms strictly in Hebrew if present in the English source."""
    if not he:
        return he
    # We will enforce the terms if they are in the English source.
    # Wanted level -> דרגת מבוקש
    if re.search(r"\bwanted\s+level\b", en, re.IGNORECASE):
        he = re.sub(r"(רמת\s+מבוקש|דרגת\s+מבוקש|רמת\s+החיפוש|רמת\s+חיפוש|דרגת\s+החיפוש|רמת\s+רצייה|רמת\s+המבוקש|דרגת\s+המבוקש)", "דרגת מבוקש", he)
    # Health -> בריאות
    if re.search(r"\bhealth\b", en, re.IGNORECASE):
        he = re.sub(r"(חיים|מד\s+חיים|בריאות)", "בריאות", he)
    # Armor -> שריון
    if re.search(r"\barmor\b", en, re.IGNORECASE):
        he = re.sub(r"(מגן|שריון)", "שריון", he)
    # Ammo -> תחמושת
    if re.search(r"\bammo\b", en, re.IGNORECASE):
        he = re.sub(r"(תחמושת)", "תחמושת", he)
    # Stamina -> סבולת
    if re.search(r"\bstamina\b", en, re.IGNORECASE):
        he = re.sub(r"(סיבולת|סבולת)", "סבולת", he)
    # Wasted -> חוסל
    if re.search(r"\bwasted\b", en, re.IGNORECASE):
        if re.sub(r"~[^~]*~", "", en).strip().lower() == "wasted":
            he = re.sub(r"(בוזבז|חוסל|מת|נרצח)", "חוסל", he)
        else:
            he = re.sub(r"(בוזבז|נרצח)", "חוסל", he)
    # Busted -> נתפס
    if re.search(r"\bbusted\b", en, re.IGNORECASE):
        if re.sub(r"~[^~]*~", "", en).strip().lower() == "busted":
            he = re.sub(r"(נתפס|נעצר)", "נתפס", he)
        else:
            he = re.sub(r"(נעצר)", "נתפס", he)
    # Mission Passed -> המשימה הושלמה
    if re.search(r"\bmission\s+passed\b", en, re.IGNORECASE):
        he = re.sub(r"(המשימה\s+עברה|המשימה\s+הושלמה|משימה\s+הושלמה|משימה\s+עברה)", "המשימה הושלמה", he)
    # Mission Failed -> המשימה נכשלה
    if re.search(r"\bmission\s+failed\b", en, re.IGNORECASE):
        he = re.sub(r"(המשימה\s+נכשלה|משימה\s+נכשלה)", "המשימה נכשלה", he)
    # Checkpoint -> נקודת ביקורת
    if re.search(r"\bcheckpoint\b", en, re.IGNORECASE):
        he = re.sub(r"(נקודת\s+שמירה|נקודת\s+בדיקה|נקודת\s+ביקורת)", "נקודת ביקורת", he)
    # Save -> שמירה
    if re.search(r"\bsave\b", en, re.IGNORECASE) and not re.search(r"\b(quick|auto)save\b", en, re.IGNORECASE):
        he = re.sub(r"(שמירה|לשמור)", "שמירה", he)
    # Mission -> משימה
    if re.search(r"\bmission\b", en, re.IGNORECASE) and not re.search(r"\bmission\s+(passed|failed)\b", en, re.IGNORECASE):
        he = re.sub(r"(משימה|המשימה)", lambda m: "המשימה" if m.group(0) == "המשימה" else "משימה", he)
    # Heist -> שוד
    if re.search(r"\bheist\b", en, re.IGNORECASE):
        he = re.sub(r"(שוד|השוד)", lambda m: "השוד" if m.group(0) == "השוד" else "שוד", he)
    # Garage -> מוסך
    if re.search(r"\bgarage\b", en, re.IGNORECASE):
        he = re.sub(r"(מוסך|המוסך)", lambda m: "המוסך" if m.group(0) == "המוסך" else "מוסך", he)
    # Map -> מפה
    if re.search(r"\bmap\b", en, re.IGNORECASE):
        he = re.sub(r"(מפה|המפה)", lambda m: "המפה" if m.group(0) == "המפה" else "מפה", he)
    # Settings -> הגדרות
    if re.search(r"\bsettings\b", en, re.IGNORECASE):
        he = re.sub(r"(הגדרות|ההגדרות)", "הגדרות", he)
    # Story Mode -> מצב סיפור
    if re.search(r"\bstory\s+mode\b", en, re.IGNORECASE):
        he = re.sub(r"(מצב\s+הסיפור|מצב\s+סיפור)", "מצב סיפור", he)
    # GTA Online -> GTA אונליין
    if re.search(r"\bgta\s+online\b", en, re.IGNORECASE):
        he = he.replace("GTA Online", "GTA אונליין")
        he = re.sub(r"ג'י\s*טי\s*איי\s*אונליין|GTA\s+Online|ג'י\s*טי\s*איי\s+מקוון", "GTA אונליין", he)
    # Cash -> מזומן
    if re.search(r"\bcash\b", en, re.IGNORECASE):
        he = re.sub(r"(כסף\s+מזומן|מזומן|כסף)", "מזומן", he)
    # Vehicle -> רכב
    if re.search(r"\bvehicle\b", en, re.IGNORECASE):
        he = re.sub(r"(כלי\s+רכב|רכב|כלי\s+הרכב|הרכב)", lambda m: "הרכב" if "ה" in m.group(0) else "רכב", he)
    # Aim -> כוונת
    if re.search(r"\baim\b", en, re.IGNORECASE):
        he = re.sub(r"(כוון|לכוון|כוונת)", "כוונת", he)
    # Reload -> טעינה
    if re.search(r"\breload\b", en, re.IGNORECASE):
        he = re.sub(r"(טען|טעינה|לטעון\s+מחדש|טעינה\s+מחדש)", "טעינה", he)
    # Sprint -> ריצה
    if re.search(r"\bsprint\b", en, re.IGNORECASE):
        he = re.sub(r"(ספרינט|ריצה|לרוץ)", "ריצה", he)
    # Cover -> מחסה
    if re.search(r"\bcover\b", en, re.IGNORECASE):
        he = re.sub(r"(תפוס\s+מחסה|מחסה|הגנה)", "מחסה", he)
    # Reward -> תגמול
    if re.search(r"\breward\b", en, re.IGNORECASE):
        he = re.sub(r"(פרס|תגמול|תגמולים)", "תגמול", he)
    # Crew -> חבורה
    if re.search(r"\bcrew\b", en, re.IGNORECASE):
        he = re.sub(r"(צוות|חבורה|הצוות|החבורה)", lambda m: "החבורה" if "ה" in m.group(0) else "חבורה", he)
    # Suspect -> חשוד
    if re.search(r"\bsuspect\b", en, re.IGNORECASE):
        he = re.sub(r"(חשוד|החשוד)", lambda m: "החשוד" if "ה" in m.group(0) else "חשוד", he)
    return he


def validate_translation(k, en, he):
    """Return (True, '') if translation is valid, else (False, reason)."""
    if not he:
        return False, "empty translation"
    if tokens(he) != tokens(en):
        return False, "token-mismatch"
    if has_niqqud(he):
        return False, "niqqud"
    f = foreign_chars(he)
    if f:
        return False, "foreign:" + "".join(f[:4])
    if not has_hebrew(he):
        if not real_word(en):
            return True, "passthrough"
        else:
            return False, "no-hebrew"
    return True, ""

def main():
    # Load files
    src_path = os.path.join(HERE, "to_translate.json")
    hebrew_path = os.path.join(HERE, "hebrew.json")
    skip_path = os.path.join(HERE, "skip.json")

    src = json.load(open(src_path, encoding="utf-8"))
    
    done = {}
    if os.path.exists(hebrew_path):
        try:
            done = json.load(open(hebrew_path, encoding="utf-8"))
        except Exception:
            pass

    skip = set()
    if os.path.exists(skip_path):
        try:
            skip = set(json.load(open(skip_path, encoding="utf-8")))
        except Exception:
            pass

    todo_keys = [k for k in src if k not in done and k not in skip]
    total_todo = len(todo_keys)
    print(f"Total keys: {len(src)} | Done: {len(done)} | Skipped: {len(skip)} | Remaining: {total_todo}", flush=True)

    if total_todo == 0:
        print("All done!", flush=True)
        return

    # Process in batches of 40
    batch_size = 40
    checkpoint_interval = 40
    
    merged_count = 0
    rejected_count = 0
    passthrough_count = 0
    new_skips_count = 0

    # Start main loop
    idx = 0
    while idx < total_todo:
        current_batch_keys = todo_keys[idx:idx+batch_size]
        idx += batch_size

        # 1. Preprocess batch
        batch_preprocessed = []
        batch_maps = []
        for k in current_batch_keys:
            en = src[k]
            prep_str, p_map = preprocess_string(en)
            batch_preprocessed.append(prep_str)
            batch_maps.append(p_map)

        # 2. Join and translate
        combined_text = "\n".join(batch_preprocessed)
        translated_combined = translate_text_raw(combined_text)

        # 3. Parse translation
        translated_lines = []
        if translated_combined:
            translated_lines = translated_combined.split("\n")

        # 4. Check if count matches, otherwise fallback to individual translation
        if len(translated_lines) != len(current_batch_keys):
            print(f"[Batch] Line count mismatch ({len(translated_lines)} vs {len(current_batch_keys)}). Falling back to individual translation...", flush=True)
            translated_lines = []
            for prep_str in batch_preprocessed:
                translated_lines.append(translate_text_raw(prep_str))
                time.sleep(0.1)

        # 5. Postprocess, validate, and merge
        for i, k in enumerate(current_batch_keys):
            en = src[k]
            he_raw = translated_lines[i] if i < len(translated_lines) else None
            
            # Postprocess
            he = postprocess_translation(he_raw, batch_maps[i])
            if he:
                he = enforce_glossary(en, he)

            # Validate
            ok, reason = validate_translation(k, en, he)
            if ok:
                done[k] = he
                merged_count += 1
                if reason == "passthrough":
                    passthrough_count += 1
            else:
                # If batch translation failed, retry translating individually
                if he_raw and len(translated_lines) == len(current_batch_keys):
                    # Try individual retry
                    prep_str, p_map = preprocess_string(en)
                    he_raw_retry = translate_text_raw(prep_str)
                    he_retry = postprocess_translation(he_raw_retry, p_map)
                    if he_retry:
                        he_retry = enforce_glossary(en, he_retry)
                    ok_retry, reason_retry = validate_translation(k, en, he_retry)
                    if ok_retry:
                        done[k] = he_retry
                        merged_count += 1
                        if reason_retry == "passthrough":
                            passthrough_count += 1
                        continue

                # Auto-skip proper nouns / street names / brand names
                if reason == "no-hebrew" and len(en.split()) <= 4:
                    skip.add(k)
                    new_skips_count += 1
                    print(f"[Auto-Skip] Adding {k} ({repr(en)}) to skip.json", flush=True)
                    continue

                rejected_count += 1
                print(f"REJECT {k}: {reason} | EN: {repr(en)} | HE: {repr(he)}", flush=True)

        # Periodically write to file and print progress
        if merged_count % checkpoint_interval == 0 or idx >= total_todo or new_skips_count % 10 == 0:
            # Atomic write hebrew.json
            tmp = hebrew_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(done, f, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(tmp, hebrew_path)
            
            # Write skip.json
            tmp_skip = skip_path + ".tmp"
            with open(tmp_skip, "w", encoding="utf-8") as f:
                json.dump(sorted(list(skip)), f, ensure_ascii=False, indent=1)
            os.replace(tmp_skip, skip_path)
            
        print(f"[Progress] Batch done. Total processed: {idx}/{total_todo} | Merged in this run: {merged_count} | Rejects in this run: {rejected_count} | Auto-skips: {new_skips_count} | Total done: {len(done)}/{len(src)}", flush=True)

        # Brief rate limit safety pause
        time.sleep(0.5)

    print("All done!", flush=True)
    print("--- GTA V UI TRANSLATION DONE ---")
    print(f"תורגמו: {len(done)}/23136 · דולגו: {len(skip)} · מצב: הסתיים")
    print("--- END ---")

if __name__ == "__main__":
    main()
