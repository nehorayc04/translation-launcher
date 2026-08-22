import json
import os
import re
import urllib.request
import urllib.parse
import time
import sys

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

# Glossary translation mapping (strictly enforce whole word/phrase match)
GLOSSARY = {
    r"\bWanted [Ll]evel\b": "דרגת מבוקש",
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

def translate_text_google(text):
    """Fallback Google Translate call."""
    try:
        data = urllib.parse.urlencode({'q': text}).encode('utf-8')
        url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=he&dt=t'
        req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        res_data = json.loads(res)
        translated = "".join([part[0] for part in res_data[0] if part[0]])
        return translated
    except Exception as e:
        print(f"[Google Fallback Error]: {e}", flush=True)
        return None

def translate_batch_ollama(batch_dict):
    """Query local Gemma model to translate a batch of strings in JSON format."""
    url = "http://localhost:11434/api/generate"
    prompt = (
        "You are a professional game translator. Translate the following GTA V UI strings from English to Hebrew.\n"
        "Rules:\n"
        "1. Translate to logical, standard Hebrew (standard reading direction, no visual reversal).\n"
        "2. Do not use any niqqud (vocalization points).\n"
        "3. Do not translate formatting placeholders like _T0_, _T1_, _T2_. Keep them exactly as they are in the source, including spacing and underscores.\n"
        "4. Keep names and brands in English: Michael, Franklin, Trevor, Lester, Lamar, Los Santos, Blaine County, Ammu-Nation, LSPD, FIB, Lifeinvader, Social Club.\n"
        "5. Return the translations as a JSON object matching the format: { \"key\": \"Hebrew translation\" }.\n"
        "6. Output ONLY the raw JSON block, nothing else. Do not wrap in markdown tags.\n\n"
        f"Input:\n{json.dumps(batch_dict, indent=2)}\n\n"
        "Output JSON:"
    )
    payload = {
        "model": "gemma4:latest",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        res = urllib.request.urlopen(req, timeout=45).read().decode('utf-8')
        data = json.loads(res)
        resp = data["response"].strip()
        
        # Clean markdown code block wraps if model used them anyway
        if resp.startswith("```json"):
            resp = resp[7:]
        if resp.startswith("```"):
            resp = resp[3:]
        if resp.endswith("```"):
            resp = resp[:-3]
        resp = resp.strip()
        
        return json.loads(resp)
    except Exception as e:
        print(f"[Ollama Batch Error]: {e}", flush=True)
        return {}

def preprocess_string(en_str):
    """Replace formatting tokens with placeholders, grouping adjacent ones."""
    matches = list(TOKEN_RE.finditer(en_str))
    if not matches:
        return en_str, {}
        
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
    """Apply the glossary terms strictly in Hebrew if present in the English source."""
    he_clean = he
    for eng_pattern, heb_term in GLOSSARY.items():
        if re.search(eng_pattern, en):
            # If the translated string has a variation but not the exact term, we can enforce it.
            # E.g. replace "דרגת החיפוש" with "דרגת מבוקש"
            he_clean = re.sub(r"רמת חיפוש|דרגת חיפוש", "דרגת מבוקש", he_clean)
            he_clean = re.sub(r"נקודת שמירה|נקודת בדיקה", "נקודת ביקורת", he_clean)
    return he_clean

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
    google_fallback_count = 0

    idx = 0
    while idx < total_todo:
        current_batch_keys = todo_keys[idx:idx+batch_size]
        idx += batch_size

        # 1. Preprocess batch
        batch_preprocessed = {}
        batch_maps = {}
        for k in current_batch_keys:
            en = src[k]
            prep_str, p_map = preprocess_string(en)
            batch_preprocessed[k] = prep_str
            batch_maps[k] = p_map

        # 2. Local Ollama translate in batch
        translations_raw = translate_batch_ollama(batch_preprocessed)

        # 3. Postprocess, validate, and merge (with fallback)
        for k in current_batch_keys:
            en = src[k]
            he_raw = translations_raw.get(k)
            
            # Postprocess
            he = postprocess_translation(he_raw, batch_maps[k])
            if he:
                he = enforce_glossary(en, he)

            # Validate
            ok, reason = validate_translation(k, en, he)
            
            # 4. Fallback if Ollama translation failed or was invalid
            if not ok:
                # print(f"[Local fallback] {k} failed validation: {reason}. Trying Google Translate...", flush=True)
                he_raw_gb = translate_text_google(batch_preprocessed[k])
                he_gb = postprocess_translation(he_raw_gb, batch_maps[k])
                if he_gb:
                    he_gb = enforce_glossary(en, he_gb)
                ok_gb, reason_gb = validate_translation(k, en, he_gb)
                if ok_gb:
                    he = he_gb
                    ok = True
                    google_fallback_count += 1
                else:
                    reason = f"Ollama failed ({reason}) & Google failed ({reason_gb})"

            if ok:
                done[k] = he
                merged_count += 1
                if reason == "passthrough":
                    passthrough_count += 1
            else:
                # Auto-skip proper nouns / street names / brand names
                if reason.endswith("no-hebrew") and len(en.split()) <= 4:
                    skip.add(k)
                    new_skips_count += 1
                    # print(f"[Auto-Skip] Adding {k} ({repr(en)}) to skip.json", flush=True)
                    continue

                rejected_count += 1
                print(f"REJECT {k}: {reason} | EN: {repr(en)} | HE: {repr(he_raw)}", flush=True)

        # Write to file and print progress on every batch
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
            
        print(f"[Progress] Batch done. Total processed: {idx}/{total_todo} | Merged in this run: {merged_count} (Google fallbacks: {google_fallback_count}) | Rejects: {rejected_count} | Auto-skips: {new_skips_count} | Total done: {len(done)}/{len(src)}", flush=True)

        # Brief rate limit safety pause (shorter because local is primary)
        time.sleep(0.1)

    print("All done!", flush=True)

if __name__ == "__main__":
    main()
