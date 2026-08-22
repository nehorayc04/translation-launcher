#!/usr/bin/env python3
"""SM2 adapter: english.json + arabic.json + menus_he.json + dialogue_he.json
→ normalized strings for community_translate.py import.

Usage:
    python build_ct_strings.py [--out sm2_ct_strings.json]
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
OUT  = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else HERE / 'sm2_ct_strings.json'

en      = json.loads((HERE / 'english.json').read_text(encoding='utf-8'))
ar      = json.loads((HERE / 'arabic.json').read_text(encoding='utf-8'))
menus   = json.loads((HERE / 'menus_he.json').read_text(encoding='utf-8'))  if (HERE/'menus_he.json').exists()   else {}
dial_he = json.loads((HERE / 'dialogue_he.json').read_text(encoding='utf-8')) if (HERE/'dialogue_he.json').exists() else {}

HE_RANGE = re.compile(r'[א-ת]')
def has_hebrew(s): return bool(HE_RANGE.search(s or ''))

def is_translatable(val: str) -> bool:
    v = val.strip()
    if not v or len(v) < 2: return False
    if not any(c.isalpha() for c in v): return False
    # pure button/action codes like "INVALID", "NONE"
    if v in ('INVALID', 'NONE', 'NULL', 'N/A'): return False
    return True

def section_from_key(k: str) -> str:
    """Derive section from key prefix."""
    prefixes = [
        ('BTN_', 'buttons'), ('HUD_', 'hud'), ('MENU_', 'menus'),
        ('UI_', 'ui'), ('HELP_', 'help'), ('TUT_', 'tutorial'),
        ('ITEM_', 'items'), ('SKILL_', 'skills'), ('TRICK_', 'tricks'),
        ('COMM_', 'combat'), ('ENEMY_', 'enemies'), ('MAP_', 'map'),
        ('SETTING', 'settings'), ('PHOTO', 'photo'), ('STORE_', 'store'),
    ]
    ku = k.upper()
    for pfx, sec in prefixes:
        if ku.startswith(pfx): return sec
    return 'dialogue'

# Use intersection of en & ar keys as the canonical scope
scope = set(en.keys()) & set(ar.keys())
all_he = {**menus, **dial_he}   # menus overridden by dialogue if same key

rows = []
for key in sorted(scope):
    src = en[key].strip() if isinstance(en[key], str) else ''
    if not is_translatable(src): continue
    he_val  = all_he.get(key, '')
    current = he_val.strip() if has_hebrew(he_val) else ''
    rows.append({
        'string_key': key,
        'source_en':  src,
        'current_he': current,
        'section':    section_from_key(key),
    })

OUT.write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f'Wrote {len(rows)} rows -> {OUT}')
