#!/usr/bin/env python3
"""CP2077 adapter: localization_export.json + localization_translated.json
→ normalized strings for community_translate.py import.

Usage:
    python build_ct_strings.py [--out cp2077_ct_strings.json]
"""
import json, re, sys, unicodedata
from pathlib import Path

HERE  = Path(__file__).parent
RES   = HERE.parent.parent / 'תרגום_משחקים' / 'source' / 'resources'
OUT   = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else HERE / 'cp2077_ct_strings.json'

en_d = json.loads((RES / 'localization_export.json').read_text(encoding='utf-8'))
he_d = json.loads((RES / 'localization_translated.json').read_text(encoding='utf-8'))

HE_RANGE = re.compile(r'[א-ת]')

def has_hebrew(s): return bool(HE_RANGE.search(s))

def is_translatable(val: str) -> bool:
    v = val.strip()
    if not v or len(v) < 2: return False
    if not any(c.isalpha() for c in v): return False
    # skip internal markers and CDPR dev junk
    if v.startswith('[') and v.endswith(']'): return False
    if 'IGNORE' in v or 'TO BE DELETED' in v or 'chickentest' in v: return False
    return True

def section_from_sk(sk: str) -> str:
    """Derive a display section from secondaryKey."""
    if not sk: return 'other'
    parts = sk.split('-')
    if len(parts) >= 2: return parts[1].lower()
    return parts[0].lower()

# Use onscreens_final.json only (canonical QA'd set)
SEC = 'onscreens/onscreens_final.json'
en_entries = en_d.get(SEC, [])
he_index   = {e['primaryKey']: e for e in he_d.get(SEC, [])}

rows = []
seen = set()
for en_e in en_entries:
    pk   = en_e['primaryKey']
    if pk in seen: continue
    seen.add(pk)
    src = en_e.get('femaleVariant', '').strip()
    if not is_translatable(src): continue
    he_e    = he_index.get(pk, {})
    he_fv   = he_e.get('femaleVariant', '').strip()
    current = he_fv if has_hebrew(he_fv) else ''
    rows.append({
        'string_key': str(pk),
        'source_en':  src,
        'current_he': current,
        'section':    section_from_sk(en_e.get('secondaryKey', '')),
        'context':    en_e.get('secondaryKey', ''),
    })

OUT.write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f'Wrote {len(rows)} rows -> {OUT}')
