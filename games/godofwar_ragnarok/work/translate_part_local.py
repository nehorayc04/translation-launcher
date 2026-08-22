# -*- coding: utf-8 -*-
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LM_URL = "http://localhost:1234/v1/chat/completions"
MODEL = "gemma-4-31b-it@q2_k_xl"
TIMEOUT = 300

GLOSSARY = {
    "Kratos": "קרייטוס", "Atreus": "אטראוס", "Mimir": "מימיר", "Freya": "פריה",
    "Brok": "ברוק", "Sindri": "סינדרי", "Tyr": "טיר", "Thor": "ת'ור",
    "Odin": "אודין", "Angrboda": "אנגרבודה", "Heimdall": "היימדל",
    "Svartalfheim": "סוורטלפהיים", "Midgard": "מידגארד", "Asgard": "אסגארד",
    "Ragnarok": "ראגנארוק", "Valhalla": "ולהאלה", "Faye": "פיי",
    "Thrud": "ת'רוד", "Garm": "גארם", "Surtr": "סורטר", "Nidavellir": "נידאווליר",
    "Helheim": "הלהיים", "Vanaheim": "ואנהיים", "Jotunheim": "יוטנהיים",
    "Muspelheim": "מוספלהיים", "Niflheim": "ניפלהיים", "Alfheim": "אלפהיים"
}

SYSTEM = """You are a professional localizer for God of War: Ragnarök translating English to Hebrew.
HARD RULES:
1. Output Hebrew. Latin letters are allowed only for untranslatable brand names, codes, or runes.
2. NEVER use niqqud (vowel points).
3. Copy EVERY tag/placeholder EXACTLY, same count, same order, same spelling: [[S:...]] voice cues, [style=...]/[/style], [i]/[/i], [Icons:...], [...Button] glyphs, %d, %s, \\n (literal backslash+n), and \\p.
4. Do NOT translate the text inside [[S:...]] — it is an audio reference.
5. Character & realm names use their fixed Hebrew spelling:
   Kratos=קרייטוס, Atreus=אטראוס, Mimir=מימיר, Freya=פריה, Brok=ברוק, Sindri=סינדרי, Tyr=טיר, Thor=ת'ור, Odin=אודין, Angrboda=אנגרבודה, Heimdall=היימדל, Svartalfheim=סוורטלפהיים, Midgard=מידגארד, Asgard=אסגארד, Ragnarok=ראגנארוק, Valhalla=ולהאלה, Faye=פיי, Thrud=ת'רוד, Garm=גארם, Surtr=סורטר, Nidavellir=נידאווליר, Helheim=הלהיים, Vanaheim=ואנהיים, Jotunheim=יוטנהיים, Muspelheim=מוספלהיים, Niflheim=ניפלהיים, Alfheim=אלפהיים.
6. A line/string that is entirely runes, Latin code, numbers, or basic punctuation must be returned unchanged.
7. Maintain actual newlines (\\n in Python string) and literal newlines (\\\\n in Python string representation) exactly. Do not convert one to the other.

Output the translations using the exact format:
Key: {key}
Translation: {translation}
---"""

TOK_RE = re.compile(r"\[\[S:[^\]]*\]\]|\[\[D:[^\]]*\]\]|\[/?style[^\]]*\]|\[/?i\]|\[Icons:[^\]]*\]|\[[A-Za-z][^\]]*Button\]|%d|%s|\\n|\\p")

def validate(orig, trans):
    if not trans or not trans.strip():
        return False
    # Check if niqqud is present
    if re.search(r"[\u0591-\u05C7]", trans):
        return False
    # Check if tags match
    ot = TOK_RE.findall(orig)
    tt = TOK_RE.findall(trans)
    if ot != tt:
        return False
    # Check if actual newlines count matches
    if orig.count("\n") != trans.count("\n"):
        return False
    return True

def lm_call(prompt):
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }).encode("utf-8")
    req = urllib.request.Request(LM_URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        res = json.loads(r.read().decode("utf-8"))
    return res["choices"][0]["message"]["content"]

def parse_response(raw):
    results = {}
    pattern = r"Key:\s*(\d+)\s*\nTranslation:\s*(.*?)(?=\n-*\s*Key:\s*\d+|\Z)"
    for m in re.finditer(pattern, raw, re.DOTALL | re.IGNORECASE):
        key = m.group(1)
        trans = m.group(2).strip()
        trans = trans.rstrip('-').strip()
        results[key] = trans
    return results

def translate_batch(batch_dict):
    prompt = ""
    for k, src in batch_dict.items():
        prompt += f"Key: {k}\nSource: {src}\n---\n"
    
    try:
        raw = lm_call(prompt)
        parsed = parse_response(raw)
        return parsed
    except Exception as e:
        print(f"API Error: {e}")
        return {}

def main():
    if len(sys.argv) < 3:
        print("Usage: python translate_part_local.py <input_json> <output_json>")
        sys.exit(1)
        
    in_file = sys.argv[1]
    out_file = sys.argv[2]
    
    if not os.path.exists(in_file):
        print(f"Input file {in_file} does not exist!")
        sys.exit(1)
        
    batch = json.load(open(in_file, encoding="utf-8"))
    print(f"Loaded {len(batch)} strings from {in_file}.")
    
    success = {}
    failed = {}
    
    # Process in chunks of 5
    chunk_size = 5
    keys = list(batch.keys())
    for idx in range(0, len(keys), chunk_size):
        chunk_keys = keys[idx : idx + chunk_size]
        chunk_dict = {k: batch[k] for k in chunk_keys}
        print(f"Translating chunk {idx//chunk_size + 1}/{((len(keys)-1)//chunk_size)+1} ({len(chunk_dict)} strings)...")
        
        translated = translate_batch(chunk_dict)
        for k, src in chunk_dict.items():
            cand = translated.get(k, "")
            if validate(src, cand):
                success[k] = cand
            else:
                failed[k] = src
                
    print(f"First-pass: {len(success)} succeeded, {len(failed)} failed/skipped.")
    
    # Retry failed items individually (robust singleton mode)
    if failed:
        print(f"Retrying {len(failed)} failed items individually...")
        for k, src in failed.items():
            time.sleep(0.5)
            single_res = translate_batch({k: src})
            cand = single_res.get(k, "")
            if validate(src, cand):
                success[k] = cand
                print(f"  Retry key {k} -> SUCCEEDED")
            else:
                # If still failed, try a very simple fallback: replace character names from glossary and copy the rest
                fallback = src
                for eng_name, heb_name in GLOSSARY.items():
                    fallback = re.sub(r'\b' + eng_name + r'\b', heb_name, fallback)
                success[k] = fallback
                print(f"  Retry key {k} -> FAILED (using glossary fallback)")
                
    # Save the output
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(success, f, ensure_ascii=False, indent=2)
    print(f"Saved {out_file} with {len(success)} entries.")

if __name__ == "__main__":
    main()
