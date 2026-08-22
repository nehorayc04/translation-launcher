"""Menu proof — the ONE screenshot that closes every Phase-1 gate at once.

What each item proves:
  * ZZ-SRGB-OK-ZZ  (pure Latin marker on "About")
        the patched .qm really loads.  Font-independent: if the file did not
        load you see "About"/Arabic, if it loaded but the font had no Hebrew
        you would see boxes — the marker separates those two failures, which
        otherwise look identical.
  * short Hebrew nav labels
        Hebrew glyphs render at all (font gate).
  * "מתקין..."  (trailing ellipsis)
        bidi mode: LOGICAL if the "..." shows on the LEFT, VISUAL if on the
        right.  Never pre-reverse before this is answered.
  * "הגדרות Add-on"  (Hebrew + Latin island)
        the Latin run keeps its own direction and lands in the right place.
  * everything else stays Arabic
        proves the untouched entries still fall through to the slot's
        original content (i.e. a partial translation degrades gracefully).

Usage:
    python build_menu_proof.py            # build only -> proof_hebrew.json
    python build_menu_proof.py --deploy   # build + patch the exe (app closed)
    python build_menu_proof.py --revert   # restore the pristine Arabic slot
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qm as Q
import patch_exe as P

SEP = '\x1f'
MARKER = 'ZZ-SRGB-OK-ZZ'

# (context, english) -> hebrew
PROOF = {
    ('SettingsNavPanel', 'About'):          MARKER,          # mount proof
    ('NavPanel', 'Settings'):               'הגדרות',
    ('SettingsNavPanel', 'Language'):       'שפה',
    ('SettingsNavPanel', 'Audio'):          'שמע',
    ('SettingsNavPanel', 'Notifications'):  'התראות',
    ('SettingsNavPanel', 'My Account'):     'החשבון שלי',
    ('SettingsNavPanel', 'Privacy'):        'פרטיות',
    ('SettingsNavPanel', 'Monitoring'):     'ניטור',
    ('SettingsNavPanel', 'Fans'):           'מאווררים',
    ('SettingsNavPanel', 'Add-ons'):        'תוספים',
    ('Settings', 'Add-on Settings'):        'הגדרות Add-on',   # Latin island
    ('Main', 'Installing...'):              'מתקין...',        # bidi ruler
    ('Main', 'OK'):                         'אישור',
    ('Main', 'Help'):                       'עזרה',
    ('Main', 'Maybe Later'):                'אולי מאוחר יותר',
}


def build_map(exe=None):
    exe = exe or P.find_exe()
    data = open(exe, 'rb').read()
    off, size = P.find_slot(data)
    info = Q.load(data, off)

    # index the slot's real keys so we only emit keys the app actually has
    have = {}
    for m in info['messages']:
        if m.get('source'):
            have[(m.get('context') or '', m['source'])] = SEP.join(
                [m.get('context') or '', m['source'], m.get('comment') or ''])

    out, missing = {}, []
    for (ctx, en), he in PROOF.items():
        k = have.get((ctx, en))
        if k is None:
            missing.append((ctx, en))
        else:
            out[k] = he
    return out, missing, exe, size


def main():
    hebrew, missing, exe, size = build_map()
    path = os.path.join(HERE, 'proof_hebrew.json')
    json.dump(hebrew, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('exe    :', exe)
    print('mapped : %d / %d proof strings' % (len(hebrew), len(PROOF)))
    if missing:
        print('MISSING (context/source not in the slot):')
        for c, e in missing:
            print('   ', c, '|', e)
    # dry build to confirm it fits the delta-0 slot
    pristine_path = os.path.join(P.BACKUP_DIR, 'SignalRgb_%s.orig.qm' % P.SLOT_LANG)
    if os.path.isfile(pristine_path):
        pristine = open(pristine_path, 'rb').read()
    else:
        data = open(exe, 'rb').read()
        off, _ = P.find_slot(data)
        pristine = data[off:off + size]
    blob, n = P.build_hebrew_qm(pristine, hebrew, size,
                                layout_rtl='--rtl' in sys.argv)
    parsed = Q.load(blob)
    unpadded = Q.build(parsed['messages'], language=parsed['language'])
    print('replaced        :', n, 'strings')
    print('slot size       :', size, 'bytes')
    print('built .qm       :', len(unpadded), 'bytes  ->  headroom',
          size - len(unpadded), 'bytes')
    print('padded to slot  :', len(blob), 'OK' if len(blob) == size else 'MISMATCH')
    # prove it re-parses
    chk = Q.load(blob)
    heb = sum(1 for m in chk['messages'] for t in m['translations']
              if t and any(0x590 <= ord(c) <= 0x5FF for c in t))
    mark = any(t == MARKER for m in chk['messages'] for t in m['translations'])
    print('re-parse        : %d messages, %d hebrew, marker=%s'
          % (len(chk['messages']), heb, mark))
    print('wrote           :', path)

    if '--deploy' in sys.argv:
        P.cmd_deploy(path, layout_rtl='--rtl' in sys.argv)
        P.cmd_lang('ar')
        print('\nNow start SignalRGB and open Settings.')
    elif '--revert' in sys.argv:
        P.cmd_revert()
        P.cmd_lang('clear')


if __name__ == '__main__':
    if '--revert' in sys.argv:
        P.cmd_revert(); P.cmd_lang('clear')
    else:
        main()
