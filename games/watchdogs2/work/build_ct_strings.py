#!/usr/bin/env python3
"""WD2 adapter: ui_strings_english.txt + wd2_ui_he.json
→ normalized strings for community_translate.py import.

Usage:
    python build_ct_strings.py [--out wd2_ct_strings.json]
"""
import json, re, sys
from pathlib import Path

HERE    = Path(__file__).parent
EXTRACT = HERE.parent / 'extract'
OUT     = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else HERE / 'wd2_ct_strings.json'

# English UI strings: "id=text" per line
ui_txt = (EXTRACT / 'ui_strings_english.txt').read_text(encoding='utf-8', errors='replace')

# Hebrew translations checkpoint
he_path = Path('C:/tmp/wd2_ui_he.json')
he_d    = json.loads(he_path.read_text(encoding='utf-8')) if he_path.exists() else {}

HE_RANGE = re.compile(r'[א-ת]')
def has_hebrew(s): return bool(HE_RANGE.search(s or ''))

SKIP_VALUES = {
    'NAVIGATE', 'Take', 'CONFIRM', 'EXIT', 'CANCEL', 'OK', 'YES', 'NO',
    'N/A', 'NULL', 'NONE', 'TRUE', 'FALSE',
}

def is_translatable(val: str) -> bool:
    v = val.strip()
    if not v or len(v) < 2: return False
    if not any(c.isalpha() for c in v): return False
    if v.upper() in SKIP_VALUES: return False
    # placeholder-only like "{0}" or "%d"
    if re.fullmatch(r'[\{\}%\d\s\[\]\.]+', v): return False
    return True

rows = []
for line in ui_txt.strip().split('\n'):
    line = line.strip()
    if not line or '=' not in line: continue
    idx = line.index('=')
    key = line[:idx].strip()
    val = line[idx+1:].strip()
    if not key.isdigit(): continue
    if not is_translatable(val): continue
    he_val  = he_d.get(key, '')
    current = he_val.strip() if has_hebrew(str(he_val)) else ''
    rows.append({
        'string_key': key,
        'source_en':  val,
        'current_he': current,
        'section':    'ui',
    })

OUT.write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f'Wrote {len(rows)} rows -> {OUT}')
