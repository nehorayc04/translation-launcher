# -*- coding: utf-8 -*-
import json
import os
import sys
import re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_FILE = os.path.join(HERE, "sm2_remaining_subtitles.json")
OUT_FILE = os.path.join(HERE, "sm2_subtitles_he.gemini.json")
TEMP_INPUT_FILE = os.path.join(HERE, "gemini_temp_input.json")
LEFT_FILE = os.path.join(HERE, "sm2_remaining_subtitles_left.json")

# Names that must remain in English
ENGLISH_NAMES = [
    "Spider-Man", "Miles", "Peter", "MJ", "Mary Jane", "Harry", "Norman", 
    "Venom", "Anti-Venom", "Carnage", "Kraven", "Sandman", "Lizard", 
    "Electro", "Mister Negative", "Martin Li", "Wraith", "Yuri", "Rio", 
    "Jeff", "Symbiote", "Scream", "Taskmaster", "Tombstone", "Vulture",
    "New York", "Brooklyn", "Queens", "Manhattan", "Harlem", "F.E.A.S.T.", 
    "Oscorp", "Daily Bugle", "ESU", "NYPD", "S.H.I.E.L.D."
]

BAD_SCRIPTS = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]')
NIQQUD = re.compile(r'[֑-ׇ]')
TS_RE = re.compile(r'<ts="[^"]*">')
PLACEHOLDER_RE = re.compile(r'\[[A-Z0-9_]+\]|\{[A-Za-z0-9_]+\}')
FORMAT_SPEC_RE = re.compile(r'%[duisí%%f]')
TS_PH_RE = re.compile(r'@@TS(\d+)@@')   # quote-free stand-in for a <ts="..."> tag

def to_display(en):
    """Replace each <ts="..."> with a quote-free @@TSn@@ marker so the agent
    NEVER has to JSON-escape quotes (that was the whole source of friction)."""
    n = [0]
    def repl(_m):
        n[0] += 1
        return f"@@TS{n[0]}@@"
    return TS_RE.sub(repl, en)

def reattach(en, he):
    """Put the ORIGINAL <ts="..."> tags back where the @@TSn@@ markers are,
    in source order. If a marker was dropped, ts-validation later rejects it."""
    tags = TS_RE.findall(en)
    def repl(m):
        i = int(m.group(1))
        return tags[i - 1] if 1 <= i <= len(tags) else m.group(0)
    return TS_PH_RE.sub(repl, he)

# Common sound cues translation validation
SOUND_CUES_MAP = {
    "laughing": "צוחק", "laugh": "צוחק", "gasping": "נאנח", "gasp": "נאנח",
    "grunting": "נחירה", "grunt": "נחירה", "groaning": "גניחה", "groan": "גניחה",
    "sighing": "אנחה", "sigh": "אנחה", "coughing": "שיעול", "cough": "שיעול",
    "screaming": "צרחה", "scream": "צרחה", "crying": "בכי", "cry": "בכי",
    "panting": "התנשפות", "pant": "התנשפות"
}

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {path}: {e}")
    return {}

def save_json(data, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def validate_entry(key, en_item, translated):
    orig_en = en_item["en"]
    rlm_required = en_item["rlm"]
    
    if not translated or not translated.strip():
        return False, "Translation is empty"

    # Must contain Hebrew, UNLESS the source is essentially a name/code that
    # legitimately stays Latin (catches an untranslated English line slipping in).
    if not re.search(r'[א-ת]', translated):
        core = TS_RE.sub("", orig_en)
        core = PLACEHOLDER_RE.sub("", core)
        core = re.sub(r'&[a-zA-Z#0-9]+;|<[^>]+>', '', core).strip()
        words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
        is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
        no_real_word = not re.search(r'[a-z]{2,}', core)
        if core and not (is_namey or no_real_word):
            return False, "No Hebrew letters (looks untranslated)"

    # Check for bad scripts
    if BAD_SCRIPTS.search(translated):
        return False, "Contains invalid characters/scripts (Arabic/Cyrillic/CJK/etc.)"
        
    # Check for niqqud
    if NIQQUD.search(translated):
        return False, "Contains Hebrew niqqud (vowel points)"
        
    # Verify timing tags <ts="...">
    orig_ts = sorted(TS_RE.findall(orig_en))
    trans_ts = sorted(TS_RE.findall(translated))
    if orig_ts != trans_ts:
        return False, f"Timing tags mismatch. Original: {orig_ts}, Translated: {trans_ts}"
        
    # Verify placeholders
    orig_placeholders = sorted(PLACEHOLDER_RE.findall(orig_en))
    trans_placeholders = sorted(PLACEHOLDER_RE.findall(translated))
    if orig_placeholders != trans_placeholders:
        return False, f"Placeholders mismatch. Original: {orig_placeholders}, Translated: {trans_placeholders}"
        
    # Verify format specs
    # Note: %d, %u, %s, %i, %f, %%
    # Let's extract format specifiers
    orig_specs = sorted(re.findall(r'%d|%u|%s|%i|%f|%%', orig_en))
    trans_specs = sorted(re.findall(r'%d|%u|%s|%i|%f|%%', translated))
    if orig_specs != trans_specs:
        return False, f"Format specs mismatch. Original: {orig_specs}, Translated: {trans_specs}"
        
    # Verify trailing &rlm;
    if rlm_required:
        if not translated.rstrip().endswith("&rlm;"):
            return False, "Missing required trailing &rlm;"
    else:
        if translated.rstrip().endswith("&rlm;"):
            # If the user didn't ask for &rlm; in the input json, but they specified in the translation rules:
            # "If rlm is false -> do not add &rlm;"
            return False, "Should not end with &rlm; (rlm is False)"
            
    # Verify English names are preserved
    for name in ENGLISH_NAMES:
        # Check if name is in English source
        # Use simple word boundary case-insensitively
        pattern = r'\b' + re.escape(name) + r'\b'
        if re.search(pattern, orig_en, re.IGNORECASE):
            # Verify name is in translation (case-insensitively)
            if not re.search(pattern, translated, re.IGNORECASE):
                # Also check if maybe it's without boundary if it's attached to hebrew (e.g. ב-Spider-Man)
                # Let's just check if the name is in the translation as a substring
                if name.lower() not in translated.lower():
                    return False, f"Preserved English name '{name}' missing in translation"
                    
    # Verify bracketed sound cues
    orig_cues = re.findall(r'\[([a-zA-Z\s]+)\]', orig_en)
    trans_cues = re.findall(r'\[([^\]]+)\]', translated)
    if len(orig_cues) != len(trans_cues):
        return False, f"Bracketed sound cue count mismatch. Original: {orig_cues}, Translated: {trans_cues}"
    for oc in orig_cues:
        oc_clean = oc.strip().lower()
        if oc_clean in SOUND_CUES_MAP:
            expected_heb = SOUND_CUES_MAP[oc_clean]
            if not any(expected_heb in tc for tc in trans_cues):
                print(f"Warning: Expected translation '{expected_heb}' for sound cue '[{oc}]' not found in translation '{translated}'")
                
    # Accented Latin characters
    for c in re.findall(r'[\u00C0-\u024F]', translated):
        if c not in orig_en:
            return False, f"Contains unapproved accented Latin character '{c}'"
            
    return True, ""

def get_batch(n):
    src = load_json(SRC_FILE)
    out = load_json(OUT_FILE)
    
    untrans = [k for k in src if k not in out]
    batch_keys = untrans[:n]
    
    if not batch_keys:
        print("All done!")
        return
        
    print(f"Remaining to translate: {len(untrans)}")
    print(f"Batch size: {len(batch_keys)}")
    
    # value = the English text with every <ts="..."> swapped to a @@TSn@@ marker,
    # so the agent edits a quote-free string (no JSON-escaping pain). It keeps the
    # @@TSn@@ markers in place and writes Hebrew around them; `put` restores the tags.
    batch_data = {k: to_display(src[k]["en"]) for k in batch_keys}

    # Save to temp input file
    save_json(batch_data, TEMP_INPUT_FILE)
    print(f"Saved next batch to {TEMP_INPUT_FILE}")
    print("Edit each VALUE to its Hebrew translation. Keep @@TSn@@ markers exactly "
          "(they are the timing tags — do NOT type <ts=...> yourself). Then run: put")

    # Also print keys + clean text + rlm for easy viewing
    for idx, k in enumerate(batch_keys, 1):
        print(f"[{idx}] {k} (rlm={src[k]['rlm']}): {batch_data[k]}")

def put_batch():
    if not os.path.exists(TEMP_INPUT_FILE):
        print(f"Temp input file {TEMP_INPUT_FILE} not found!")
        return
        
    temp_in = load_json(TEMP_INPUT_FILE)
    out = load_json(OUT_FILE)
    
    # We expect a file containing key -> Hebrew translation
    # The agent will write their translation directly to TEMP_INPUT_FILE under a "translation" field,
    # or write a new JSON file. Let's make it look for gemini_temp_input.json, but with translated values.
    # To make it super simple: the agent will save a JSON to gemini_temp_input.json where it maps key -> Hebrew string.
    # Let's read TEMP_INPUT_FILE as key -> translated_string OR key -> {"he": ...} or similar.
    # If the file is still the source format, we prompt the agent.
    # Let's support both formats:
    # 1. key -> translated_string
    # 2. key -> {"he": translated_string}
    
    translations = {}
    for k, v in temp_in.items():
        if isinstance(v, str):
            translations[k] = v
        elif isinstance(v, dict) and "he" in v:
            translations[k] = v["he"]
        elif isinstance(v, dict) and "en" in v:
            # Not translated yet, skip or warn
            continue
            
    if not translations:
        print("No translations found in temp input file.")
        return
        
    src = load_json(SRC_FILE)
    left = load_json(LEFT_FILE)
    success_count = 0
    errors = []
    
    for k, trans in translations.items():
        if k not in src:
            errors.append(f"Key {k} not found in source file")
            continue

        # restore the real <ts="..."> tags from the @@TSn@@ markers
        trans = reattach(src[k]["en"], trans)
        ok, reason = validate_entry(k, src[k], trans)
        if ok:
            out[k] = trans
            if k in left:
                del left[k]
            success_count += 1
        else:
            errors.append(f"Validation failed for key {k}: {reason}\nSource: {src[k]['en']}\nTranslation: {trans}")
            
    if errors:
        print("Validation errors encountered:")
        for err in errors[:20]:
            print(f" - {err}")
        if len(errors) > 20:
            print(f" ... and {len(errors) - 20} more errors.")
        print(f"Saved {success_count} successfully validated translations. {len(errors)} failed.")
    else:
        print(f"All {success_count} translations validated successfully!")
        
    save_json(out, OUT_FILE)
    if success_count > 0:
        save_json(left, LEFT_FILE)
    print(f"Saved updated translations to {OUT_FILE}")
    print(f"Total translated so far: {len(out)} / {len(src)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gemini_translate_helper.py <get/put> [batch_size]")
        sys.exit(1)
        
    cmd = sys.argv[1].lower()
    if cmd == "get":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        get_batch(n)
    elif cmd == "put":
        put_batch()
    else:
        print(f"Unknown command: {cmd}")
