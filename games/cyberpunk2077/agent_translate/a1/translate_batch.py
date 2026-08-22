"""
translate_batch.py — קורא את current_batch.json, מתרגם כל שורה, כותב current_batch_he.json.
מטרגם inline עם מגדר נכון.
אין שימוש ב-API, Google Translate, או deep_translator.
"""
import json, re, os

CTRL = "".join(chr(c) for c in range(0x20))
NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$")
FOREIGN = re.compile(r"[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]")
LOWER = re.compile(r"[a-z]{2,}")
STRUCT = re.compile(r"<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;")

def is_namey(en):
    en_c = en.lstrip(CTRL).strip()
    ws = en_c.split()
    return bool(ws) and len(ws) <= 4 and all(NAMEWORD.match(w) for w in ws)

def get_ctrl(en):
    """Return the control-char prefix of en."""
    return en[: len(en) - len(en.lstrip(CTRL))]

HERE = os.path.dirname(os.path.abspath(__file__))
cb = json.load(open(os.path.join(HERE, "current_batch.json"), encoding="utf-8"))

# ---------- TRANSLATION TABLE ----------
# Fill in translations below after reading the batch.
# Format: key -> (f_translation, m_translation)
# If f==m, just provide one string.
TRANSLATIONS = {}

for k, en_raw in cb.items():
    ctrl = get_ctrl(en_raw)
    en = en_raw.lstrip(CTRL).strip()
    
    # Default: use English as-is for names, skip for untranslatable
    if k in TRANSLATIONS:
        val = TRANSLATIONS[k]
        if isinstance(val, str):
            f, m = val, val
        else:
            f, m = val
        # Preserve ctrl prefix in translation
        result = {"f": ctrl + f, "m": ctrl + m}
    elif is_namey(en) and not FOREIGN.search(en):
        # Name — keep as-is (will pass validator)
        result = {"f": en_raw, "m": en_raw}
    else:
        # Needs real translation — mark as TODO
        result = None
    
    if result:
        print(f"OK  {k}: {repr(result['f'][:40])}")
    else:
        print(f"TODO {k}: {repr(en_raw[:60])}")

print("\n--- Keys needing translation ---")
for k, en_raw in cb.items():
    en = en_raw.lstrip(CTRL).strip()
    if not is_namey(en) or FOREIGN.search(en):
        print(f"  {k!r}: {repr(en_raw[:80])}")
