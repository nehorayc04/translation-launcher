import json
import re
import os
import subprocess
import time

_YOU = re.compile(r"\byou(?:r|rs|rself|rselves)?\b", re.I)
_FIRST = re.compile(r"\bI\b|\bI['’](?:m|ve|ll|d)\b|\b(?:me|my|myself)\b")
NIQQUD = re.compile("[֑-ׇ]")

def heb(s):
    return "".join(c for c in s if 0x05d0 <= ord(c) <= 0x05ea)

def apply_gender_fixes(s):
    # Same fixes
    s = s.replace("נראית", "נראה")
    return s

def harmless_tweak(s):
    # Same
    return s

def process_batch():
    if not os.path.exists('current_batch.json'):
        return False
        
    with open('current_batch.json', 'r', encoding='utf-8') as f:
        d = json.load(f)
        
    if not d:
        return False
        
    for k, v in d.items():
        fem = v['he_female']
        en = v.get('en', '')
        
        fm = fem.replace("נראית", "נראה")
        # Strip niqqud!
        fm = NIQQUD.sub("", fm)
        
        v['fixed_male'] = fm

    with open('current_batch.json', 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        
    return True

if __name__ == "__main__":
    while True:
        res = subprocess.run(['python', 'get_batch.py'], capture_output=True, text=True)
        print(res.stdout)
        if "All done!" in res.stdout:
            break
            
        if not process_batch():
            break
            
        res = subprocess.run(['python', 'merge_batch.py'], capture_output=True, text=True)
        print(res.stdout)
        
        if "REJECT " in res.stdout:
            print("REJECTIONS FOUND! Stopping to allow manual fix.")
            break
