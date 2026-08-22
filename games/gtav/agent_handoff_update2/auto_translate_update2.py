import json
import os
import re
import time
import sys
from deep_translator import GoogleTranslator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Import helpers from _tokens.py
from _tokens import tokens, has_hebrew, has_niqqud, foreign_chars, real_word

TOKEN_RE = re.compile(r"~[^~]*~|</?[A-Za-z][^>]*>|%[0-9]*[sdifx%]")
NIQQUD_RE = re.compile("[֑-ׇֽֿׁׂׅׄ]")

def translate_text_raw(text):
    """Query Google Translate using deep-translator (supports newlines)."""
    if not text.strip():
        return ""
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

def translate_batch_safe(batch_strings):
    """Chunk batch strings to keep combined payloads under 4000 characters."""
    sub_batches = []
    current_sub = []
    current_len = 0
    for s in batch_strings:
        if current_len + len(s) + 1 > 4000:
            sub_batches.append(current_sub)
            current_sub = [s]
            current_len = len(s)
        else:
            current_sub.append(s)
            current_len += len(s) + 1
    if current_sub:
        sub_batches.append(current_sub)
        
    all_translated = []
    for sb in sub_batches:
        combined = "\n".join(sb)
        translated = translate_text_raw(combined)
        if translated:
            lines = translated.split("\n")
            if len(lines) == len(sb):
                all_translated.extend(lines)
            else:
                print(f"[Sub-batch] Line count mismatch ({len(lines)} vs {len(sb)}). Fallback to individual...", flush=True)
                for item in sb:
                    all_translated.append(translate_text_raw(item))
                    time.sleep(0.05)
        else:
            print(f"[Sub-batch] Translation failed. Fallback to individual...", flush=True)
            for item in sb:
                all_translated.append(translate_text_raw(item))
                time.sleep(0.05)
                
    return all_translated

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
    if not he:
        return he
    # Case insensitive checks
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
        he = re.sub(r"(בוזבז|חוסל|מת|נרצח)", "חוסל", he)
    # Busted -> נתפס
    if re.search(r"\bbusted\b", en, re.IGNORECASE):
        he = re.sub(r"(נתפס|נעצר)", "נתפס", he)
    # Mission Passed -> המשימה הושלמה
    if re.search(r"\bmission\s+passed\b", en, re.IGNORECASE):
        he = re.sub(r"(המשימה\s+עברה|המשימה\s+הושלמה|משימה\s+הושלמה|משימה\s+עברה)", "המשימה הושלמה", he)
    # Mission Failed -> המשימה נכשלה
    if re.search(r"\bmission\s+failed\b", en, re.IGNORECASE):
        he = re.sub(r"(המשימה\s+נכשלה|משימה\s+נכשלה)", "המשימה נכשלה", he)
    # Checkpoint -> נקודת ביקורת
    if re.search(r"\bcheckpoint\b", en, re.IGNORECASE):
        he = re.sub(r"(נקודת\s+שמירה|נקודת\s+בדיקה|נקודת\s+ביקורת)", "נקודת ביקורת", he)
    # Respawn -> תחייה
    if re.search(r"\brespawn\b", en, re.IGNORECASE):
        he = re.sub(r"(תחייה|להיוולד\s+מחדש|להיווצר\s+מחדש|היוולדות\s+מחדש)", "תחייה", he)
    # Save -> שמירה
    if re.search(r"\bsave\b", en, re.IGNORECASE) and not re.search(r"\b(quick|auto)save\b", en, re.IGNORECASE):
        he = re.sub(r"(שמירה|לשמור)", "שמירה", he)
    # Autosave -> שמירה אוטומטית
    if re.search(r"\bautosave\b", en, re.IGNORECASE):
        he = re.sub(r"(שמירה\s+אוטומטית|שמירה\s+אוטומטית)", "שמירה אוטומטית", he)
    # Quick Save -> שמירה מהירה
    if re.search(r"\bquick\s+save\b", en, re.IGNORECASE):
        he = re.sub(r"(שמירה\s+מהירה|שמירה\s+מהירה)", "שמירה מהירה", he)
    # Mission -> משימה
    if re.search(r"\bmission\b", en, re.IGNORECASE) and not re.search(r"\bmission\s+(passed|failed)\b", en, re.IGNORECASE):
        he = re.sub(r"(משימה|המשימה)", lambda m: "המשימה" if m.group(0) == "המשימה" else "משימה", he)
    # Heist -> שוד
    if re.search(r"\bheist\b", en, re.IGNORECASE):
        he = re.sub(r"(שוד|השוד)", lambda m: "השוד" if m.group(0) == "השוד" else "שוד", he)
    # Objective -> יעד
    if re.search(r"\bobjective\b", en, re.IGNORECASE):
        he = re.sub(r"(מטרה|יעד|היעד)", lambda m: "היעד" if m.group(0) == "היעד" else "יעד", he)
    # Reward -> תגמול
    if re.search(r"\breward\b", en, re.IGNORECASE):
        he = re.sub(r"(פרס|תגמול|תגמולים)", "תגמול", he)
    # Livery -> צביעה/מדבקה
    if re.search(r"\blivery\b", en, re.IGNORECASE):
        he = re.sub(r"(צביעה|מדבקה|צביעה/מדבקה)", "צביעה/מדבקה", he)
    if re.search(r"\bliveries\b", en, re.IGNORECASE):
        he = re.sub(r"(צביעות|מדבקות|צביעות/מדבקות|עיצובי\s+צביעה/מדבקה)", "עיצובי צביעה/מדבקה", he)
    # Garage -> מוסך
    if re.search(r"\bgarage\b", en, re.IGNORECASE):
        he = re.sub(r"(מוסך|המוסך)", lambda m: "המוסך" if m.group(0) == "המוסך" else "מוסך", he)
    # Safehouse -> מחבוא
    if re.search(r"\bsafehouse\b", en, re.IGNORECASE):
        he = re.sub(r"(מחבוא|בית\s+בטוח|דירת\s+מסתור)", "מחבוא", he)
    # Property -> נכס
    if re.search(r"\bproperty\b", en, re.IGNORECASE):
        he = re.sub(r"(נכס|הנכס)", lambda m: "הנכס" if m.group(0) == "הנכס" else "נכס", he)
    # Apartment -> דירה
    if re.search(r"\bapartment\b", en, re.IGNORECASE):
        he = re.sub(r"(דירה|הדירה)", lambda m: "הדירה" if m.group(0) == "הדירה" else "דירה", he)
    # Weapon Wheel -> גלגל הנשק
    if re.search(r"\bweapon\s+wheel\b", en, re.IGNORECASE):
        he = re.sub(r"(גלגל\s+הנשק|גלגל\s+נשק)", "גלגל הנשק", he)
    # Map -> מפה
    if re.search(r"\bmap\b", en, re.IGNORECASE):
        he = re.sub(r"(מפה|המפה)", lambda m: "המפה" if m.group(0) == "המפה" else "מפה", he)
    # Waypoint -> נקודת ציון
    if re.search(r"\bwaypoint\b", en, re.IGNORECASE):
        he = re.sub(r"(נקודת\s+ציון|נקודת\s+ציון)", "נקודת ציון", he)
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
    # Director Mode -> מצב במאי
    if re.search(r"\bdirector\s+mode\b", en, re.IGNORECASE):
        he = re.sub(r"(מצב\s+במאי|מצב\s+הבמאי)", "מצב במאי", he)
    # Cash / Money -> מזומן / כסף
    if re.search(r"\bcash\b", en, re.IGNORECASE):
        he = re.sub(r"(כסף\s+מזומן|מזומן|כסף)", "מזומן", he)
    elif re.search(r"\bmoney\b", en, re.IGNORECASE):
        he = re.sub(r"(כסף)", "כסף", he)
    # Bank -> בנק
    if re.search(r"\bbank\b", en, re.IGNORECASE):
        he = re.sub(r"(בנק|הבנק)", lambda m: "הבנק" if m.group(0) == "הבנק" else "בנק", he)
    # Cut -> חלק
    if re.search(r"\bcut\b", en, re.IGNORECASE) and re.search(r"\b(heist|take)\b", en, re.IGNORECASE):
        he = re.sub(r"(חלק|נתח)", "חלק", he)
    # Crew -> חבורה
    if re.search(r"\bcrew\b", en, re.IGNORECASE):
        he = re.sub(r"(צוות|חבורה|הצוות|החבורה)", lambda m: "החבורה" if "ה" in m.group(0) else "חבורה", he)
    # CEO -> מנכ"ל
    if re.search(r"\bceo\b", en, re.IGNORECASE):
        he = re.sub(r"(מנכ\"ל|CEO)", "מנכ\"ל", he)
    # MC -> מועדון אופנוענים
    if re.search(r"\bmc\b", en, re.IGNORECASE):
        he = re.sub(r"(מועדון\s+אופנוענים|MC)", "מועדון אופנוענים", he)
    # Cover -> מחסה
    if re.search(r"\bcover\b", en, re.IGNORECASE):
        he = re.sub(r"(תפוס\s+מחסה|מחסה|הגנה)", "מחסה", he)
    # Aim -> כוונת
    if re.search(r"\baim\b", en, re.IGNORECASE):
        he = re.sub(r"(כוון|לכוון|כוונת)", "כוונת", he)
    # Reload -> טעינה
    if re.search(r"\breload\b", en, re.IGNORECASE):
        he = re.sub(r"(טען|טעינה|לטעון\s+מחדש|טעינה\s+מחדש)", "טעינה", he)
    # Sprint -> ריצה
    if re.search(r"\bsprint\b", en, re.IGNORECASE):
        he = re.sub(r"(ספרינט|ריצה|לרוץ)", "ריצה", he)
    # Crouch -> כריעה
    if re.search(r"\bcrouch\b", en, re.IGNORECASE):
        he = re.sub(r"(להתכופף|כריעה|להנמיך)", "כריעה", he)
    # Vehicle -> רכב
    if re.search(r"\bvehicle\b", en, re.IGNORECASE):
        he = re.sub(r"(כלי\s+רכב|רכב|כלי\s+הרכב|הרכב)", lambda m: "הרכב" if "ה" in m.group(0) else "רכב", he)
    # Engine -> מנוע
    if re.search(r"\bengine\b", en, re.IGNORECASE):
        he = re.sub(r"(מנוע|המנוע)", lambda m: "המנוע" if m.group(0) == "המנוע" else "מנוע", he)
    # Brake -> בלם
    if re.search(r"\bbrake\b", en, re.IGNORECASE):
        he = re.sub(r"(בלם|הבלם)", lambda m: "הבלם" if m.group(0) == "הבלם" else "בלם", he)
    if re.search(r"\bbrakes\b", en, re.IGNORECASE):
        he = re.sub(r"(בלמים|הבלמים)", lambda m: "הבלמים" if m.group(0) == "הבלמים" else "בלמים", he)
    # Handbrake -> בלם יד
    if re.search(r"\bhandbrake\b", en, re.IGNORECASE):
        he = re.sub(r"(בלם\s+יד|בלם\s+היד)", "בלם יד", he)
    # Nitrous -> חנקן
    if re.search(r"\bnitrous\b", en, re.IGNORECASE):
        he = re.sub(r"(נייטרוס|חנקן)", "חנקן", he)
    # Turbo -> טורבו
    if re.search(r"\bturbo\b", en, re.IGNORECASE):
        he = re.sub(r"(טורבו)", "טורבו", he)
    # Armored -> משוריין
    if re.search(r"\barmored\b", en, re.IGNORECASE):
        he = re.sub(r"(משוריין|משוריינת)", "משוריין", he)
    # Weaponized -> חמוש
    if re.search(r"\bweaponized\b", en, re.IGNORECASE):
        he = re.sub(r"(חמוש|חמושה)", "חמוש", he)
    # Upgrade -> שדרוג
    if re.search(r"\bupgrade\b", en, re.IGNORECASE):
        he = re.sub(r"(לשדרג|שדרוג)", "שדרוג", he)
    # Mod / Modification -> שיפור/התאמה
    if re.search(r"\bmodification\b", en, re.IGNORECASE):
        he = re.sub(r"(שינוי|שיפור|התאמה)", "שיפור/התאמה", he)
    elif re.search(r"\bmod\b", en, re.IGNORECASE):
        he = re.sub(r"(מוד|שיפור|שינוי)", "שיפור", he)
    # Paint -> צבע
    if re.search(r"\bpaint\b", en, re.IGNORECASE):
        he = re.sub(r"(צבע|לצבוע)", "צבע", he)
    # Pegasus -> Pegasus (keep English)
    if "Pegasus" in en:
        he = re.sub(r"(פגסוס|פגאסוס)", "Pegasus", he)
    # Workshop -> סדנה
    if re.search(r"\bworkshop\b", en, re.IGNORECASE):
        he = re.sub(r"(סדנה|הסדנה)", lambda m: "הסדנה" if m.group(0) == "הסדנה" else "סדנה", he)
    # Hangar -> האנגר
    if re.search(r"\bhangar\b", en, re.IGNORECASE):
        he = re.sub(r"(האנגר|ההאנגר)", lambda m: "ההאנגר" if m.group(0) == "ההאנגר" else "האנגר", he)
    # Bunker -> בונקר
    if re.search(r"\bbunker\b", en, re.IGNORECASE):
        he = re.sub(r"(בונקר|הבונקר)", lambda m: "הבונקר" if m.group(0) == "הבונקר" else "בונקר", he)
    # Nightclub -> מועדון לילה
    if re.search(r"\bnightclub\b", en, re.IGNORECASE):
        he = re.sub(r"(מועדון\s+לילה|המועדון\s+לילה)", "מועדון לילה", he)
        
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

    # Process in batches of 150
    batch_size = 150
    checkpoint_interval = 300
    
    merged_count = 0
    rejected_count = 0
    passthrough_count = 0
    new_skips_count = 0

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

        # 2. Chunk-safe translate in batch
        translated_lines = translate_batch_safe(batch_preprocessed)

        # 3. Postprocess, validate, and merge
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

                # Auto-skip proper nouns / street names / brand names / short codes
                if reason == "no-hebrew" and len(en.split()) <= 4:
                    skip.add(k)
                    new_skips_count += 1
                    continue

                rejected_count += 1
                print(f"REJECT {k}: {reason} | EN: {repr(en)} | HE: {repr(he)}", flush=True)

        # Periodically write to file
        if merged_count % checkpoint_interval == 0 or idx >= total_todo or new_skips_count % 50 == 0:
            tmp = hebrew_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(done, f, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(tmp, hebrew_path)
            
            tmp_skip = skip_path + ".tmp"
            with open(tmp_skip, "w", encoding="utf-8") as f:
                json.dump(sorted(list(skip)), f, ensure_ascii=False, indent=1)
            os.replace(tmp_skip, skip_path)
            
        print(f"[Progress] {idx}/{total_todo} processed | Merged in this run: {merged_count} | Rejects: {rejected_count} | Auto-skips: {new_skips_count} | Done: {len(done)}/{len(src)}", flush=True)

        # Rate limit safety pause
        time.sleep(0.2)

    print("All done!", flush=True)

if __name__ == "__main__":
    main()
