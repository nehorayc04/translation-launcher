#!/usr/bin/env python3
"""Adapter: GoWR english.json + hebrew.json → normalized strings for community_translate.py import.

Usage:
    python build_ct_strings.py [--out gowr_ct_strings.json]
"""
import json, sys
from pathlib import Path

HERE  = Path(__file__).parent
OUT   = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else HERE / 'gowr_ct_strings.json'

en = json.loads((HERE / 'english.json').read_text(encoding='utf-8'))
he = json.loads((HERE / 'hebrew.json').read_text(encoding='utf-8')) if (HERE / 'hebrew.json').exists() else {}
ar = json.loads((HERE / 'arabic.json').read_text(encoding='utf-8'))  if (HERE / 'arabic.json').exists() else {}

def is_translatable(val: str) -> bool:
    v = val.strip()
    if not v or len(v) < 2:
        return False
    if '#' in v and v.count('#') >= 2:
        return False  # internal marker like "Design#Text Status#Needs Review"
    # must have at least one Latin letter (not just numbers/symbols)
    if not any(c.isalpha() for c in v):
        return False
    return True

rows = []
# Use intersection of EN ∩ AR as the canonical scope (48,886 entries per FEASIBILITY.md)
scope = set(en.keys()) & set(ar.keys()) if ar else set(en.keys())
for key in sorted(scope, key=lambda k: int(k) if k.isdigit() else 0):
    src = en[key]
    if not is_translatable(src):
        continue
    row = {
        'string_key': key,
        'source_en':  src,
        'current_he': he.get(key, ''),
        'section':    'game_text',
    }
    rows.append(row)

OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=None, separators=(',', ':')), encoding='utf-8')
print(f'Wrote {len(rows)} rows -> {OUT}')
