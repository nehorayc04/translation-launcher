"""Build (and optionally deploy) the full Hebrew translation.

    python build_hebrew.py            # build + report, no write
    python build_hebrew.py --deploy   # patch the exe + set the locale
    python build_hebrew.py --revert   # restore the pristine Arabic slot

Refuses to build while qa_scan.py reports a defect (pass --force to override,
which you should not need).  Automatically applies the minimal-prefix
compression when the naive build does not fit the delta-0 slot.
"""
import os, sys, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import qm as Q
import patch_exe as P
from size_budget import minimize_prefixes

HANDOFF = os.path.join(ROOT, 'agent_handoff')


def run_qa():
    r = subprocess.run([sys.executable, os.path.join(HERE, 'qa_scan.py')],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    return r.returncode


# ---------------------------------------------------------------- layout pad
# The settings side-panel SECTION HEADERS are the one place the app's own
# RTL auto-alignment hurts us: QQuickText right-aligns a right-to-left string
# when no explicit alignment is set, so a header laid out with a LEFT margin
# (fine for "USER"/"BILLING") flips to the panel's right edge, where a fixed
# ~1-character band is clipped away — "משתמש" renders as "נשתמש".
#
# The amount lost is CONSTANT regardless of the header's length, which is what
# identifies it as a margin/position problem rather than "the text is too long"
# (an overflow would clip proportionally to the string).  A translation file
# cannot move the box, but it CAN put the first character further from the
# edge: a leading NBSP occupies the visual RIGHTMOST slot under RTL and pushes
# the letters back into view.  NBSP, not a plain space, so it survives even if
# the label is rendered as RichText (HTML collapses leading whitespace).
#
# Applied at BUILD time only — hebrew.json stays clean prose.
# MEASURING IT INSTEAD OF GUESSING — a RULER, the RDR2 trick.
# 2 NBSPs were not enough, and the clipped band cannot be measured from outside
# the app.  So each header gets a DIFFERENT amount, in panel order: the first
# header that renders its first letter intact says exactly how many are needed,
# from a single screenshot.
NBSP = ' '
# ANSWER (deployed 2/3/4/5/6, read off one screenshot): 2 -> still clipped;
# 3,4,5,6 -> intact AND all at the same position, i.e. 3 is the threshold and
# past it the text stops moving (the surplus is absorbed) => over-padding costs
# nothing.  4 = the measured answer plus margin.
PAD_N = 4
LAYOUT_PAD = {s: PAD_N for s in (
    'User', 'Billing', 'Application', 'System Info', 'About')}


def apply_layout_pad(hebrew):
    out = dict(hebrew)
    for key, val in hebrew.items():
        src = key.split('\x1f')[1]
        n = LAYOUT_PAD.get(src)
        if n and not val.startswith(NBSP):
            out[key] = NBSP * n + val
    return out


def main():
    if '--revert' in sys.argv:
        P.cmd_revert()
        P.cmd_lang('clear')
        return 0

    if run_qa() and '--force' not in sys.argv:
        print('\nQA FAILED — fix the defects above, or pass --force.')
        return 1

    hebrew = json.load(open(os.path.join(HANDOFF, 'hebrew.json'), encoding='utf-8'))
    hebrew = apply_layout_pad(hebrew)
    exe = P.find_exe()
    data = open(exe, 'rb').read()
    off, size, kind = P.find_slot(data)
    # ALWAYS build from the pristine slot, never from whatever is deployed —
    # otherwise a dry build silently inherits the previous build's strings.
    backup = os.path.join(P.BACKUP_DIR, 'SignalRgb_%s.orig.qm' % P.SLOT_LANG)
    if '--deploy' in sys.argv:
        pristine = P.ensure_backup(exe, data, off, size, kind=kind)
    elif os.path.isfile(backup) and os.path.getsize(backup) == size:
        pristine = open(backup, 'rb').read()   # matches the current slot
    else:
        pristine = data[off:off + size]        # stale/absent backup -> live slot

    # A compressed slot (SignalRGB 2.5.75+) means the app version may carry
    # strings we haven't translated — drop those so Qt falls back to the
    # ENGLISH source instead of leaving them Arabic.
    drop_untranslated = (kind != 'raw')
    info = Q.load(P.slot_qm(pristine, kind))
    SEP = '\x1f'
    n = 0
    kept = []
    for m in info['messages']:
        k = SEP.join([m.get('context') or '', m.get('source') or '',
                      m.get('comment') or ''])
        v = hebrew.get(k)
        if v and m['translations']:
            m['translations'][0] = v
            n += 1
            kept.append(m)
        elif not drop_untranslated:
            kept.append(m)
    info['messages'] = kept

    msgs = info['messages']
    blob = Q.build(msgs, language=info['language'], deps=info['deps'],
                   contexts=info['contexts'], numerus=info['numerus'])
    mode = 'full'
    try:
        padded = P.pack_slot(blob, size, kind)          # NUL-pad raw / zlib+pad
    except SystemExit:
        if kind == 'raw':                               # try minimal prefixes
            msgs = minimize_prefixes(msgs)
            blob = Q.build(msgs, language=info['language'], deps=info['deps'],
                           contexts=info['contexts'], numerus=info['numerus'])
            mode = 'minimal-prefix'
            try:
                padded = P.pack_slot(blob, size, kind)
            except SystemExit:
                print('OVERFLOW even with minimal prefixes — cannot fit the slot.')
                return 1
        else:
            print('OVERFLOW — compressed Hebrew .qm does not fit the slot.')
            return 1
    print('replaced   : %d / %d messages (kind=%s)' % (n, len(info['messages']), kind))
    print('built .qm  : %d bytes (%s)  ->  %d/%d on-disk  headroom %d'
          % (len(blob), mode, len(padded), size, size - len(padded)))

    chk = Q.load(P.slot_qm(padded, kind))
    heb = sum(1 for m in chk['messages'] for t in m['translations']
              if t and any(0x590 <= ord(c) <= 0x5FF for c in t))
    print('re-parse   : %d messages, %d hebrew' % (len(chk['messages']), heb))

    out = os.path.join(HERE, 'SignalRgb_he.qm')
    open(out, 'wb').write(padded)
    print('wrote      :', out)

    if '--deploy' in sys.argv:
        if P.is_running():
            # not a blocker any more — write_slot moves the locked image aside
            print('note: SignalRGB is running; patching in place (restart it to '
                  'see the change).')
        # exe string literals the .qm cannot reach (the language picker builds
        # its menu from a C table of native locale names, so without this the
        # Hebrew build would still offer "العربية").
        _, recs = P.apply_literals(open(exe, 'rb').read())
        if recs:
            json.dump(recs, open(P._literal_meta_path(), 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)
        extra = [(r['offset'], r['dst'].encode('utf-8')
                  + b'\0' * (r['span'] - len(r['dst'].encode('utf-8'))))
                 for r in recs]
        P.write_slot(exe, off, size, padded, extra=extra)
        for r in recs:
            print('literal    : %r -> %r' % (r['src'], r['dst']))
        P.cmd_lang('ar')
        print('deployed. Start SignalRGB (language is already set to the slot).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
