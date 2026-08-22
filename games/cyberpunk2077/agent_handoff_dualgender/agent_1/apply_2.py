import json
import re

_OK_PUNCT = {0x2013, 0x2014, 0x2018, 0x2019, 0x201c, 0x201d, 0x2026,
             0x2022, 0x200e, 0x200f, 0x00a0, 0x2011, 0x2212}

def remove_foreign(s):
    import re
    TOKEN = re.compile(r"\{[^}]*\}|<[^>]+>|%[sd%]|&rlm;|&[a-z]+;|\\n")
    vis = TOKEN.sub(" ", s)
    bad = []
    for c in vis:
        o = ord(c)
        if c.isspace() or 0x20 <= o <= 0x7e or 0x0590 <= o <= 0x05ff:
            continue
        if 0x00a1 <= o <= 0x00ff and o not in (0x00d7, 0x00f7):
            continue
        if o in _OK_PUNCT:
            continue
        bad.append(c)
    
    for c in set(bad):
        s = s.replace(c, "")
    return s

with open('current_batch.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

fixes = {
    "base|onscreens/onscreens_final.json|42197": "לחץ על <Input context=\"VehicleTankDrive\" actionName=\"ShootSecondary\" color=\"Tutorial.InputHint\"></> כדי לירות טיל מתביית.\\nהחזק את <Input context=\"VehicleTankDrive\" actionName=\"ShootSecondary\" color=\"Tutorial.InputHint\"></> כדי להינעל על מטרות.",
    "base|onscreens/onscreens_final.json|43493": "המטרה שלך היא להכניס את הרצף של ICEpick ל-Buffer.\\n\\nכדי להוסיף תו מה-Code Matrix ל-Buffer, רחף מעליו ולחץ על <Input context=\"UIMenu\" actionName=\"click\" color=\"Tutorial.InputHint\"></>.",
}

for k, v in d.items():
    if k in fixes:
        fm = fixes[k]
    else:
        fm = v['he_female']
    
    fm = remove_foreign(fm)
    v['fixed_male'] = fm

with open('current_batch.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
