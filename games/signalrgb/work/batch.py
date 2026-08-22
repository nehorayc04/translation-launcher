"""Translation batch loop (New-Era: every line decided against the shipped langs).

    python batch.py get [N]      -> next N untranslated rows, compact view
    python batch.py put          -> merge work/current_batch_he.json into hebrew.json
    python batch.py stat         -> progress

`current_batch.json` maps the printed index -> the real \x1f key, so the
translation file I write is just {index: "hebrew"} and can never carry a
malformed key.
"""
import os, sys, json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
HANDOFF = os.path.join(ROOT, 'agent_handoff')
SRC = os.path.join(HANDOFF, 'to_translate.json')
HEB = os.path.join(HANDOFF, 'hebrew.json')
CUR = os.path.join(HERE, 'current_batch.json')
CUR_HE = os.path.join(HERE, 'current_batch_he.json')

REFS = ('ar', 'sr', 'ru', 'ja')      # ar = closest to Hebrew; sr = gendered Slavic


def load():
    src = json.load(open(SRC, encoding='utf-8'))
    he = json.load(open(HEB, encoding='utf-8')) if os.path.isfile(HEB) else {}
    return src, he


def cmd_get(n=100):
    src, he = load()
    todo = [k for k in src if k not in he]
    batch = todo[:n]
    mapping = {}
    lines = []
    for i, k in enumerate(batch, 1):
        r = src[k]
        mapping[str(i)] = k
        en = r['en'].replace('\n', '\\n')
        lines.append('%03d [%s] %s' % (i, r['context'], en))
        refs = []
        for L in REFS:
            v = r['refs'].get(L)
            if v:
                refs.append('%s: %s' % (L, v.replace('\n', ' ')[:90]))
        if refs:
            lines.append('     ' + ' | '.join(refs))
    json.dump(mapping, open(CUR, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('\n'.join(lines))
    print('\n--- batch of %d | %d/%d done, %d left ---'
          % (len(batch), len(he), len(src), len(todo)))


import re
# This target stores LOGICAL and the app runs the UBA itself, so a bidi
# control is always a defect.  Strip on merge - writing one is a reflex that
# recurs on every line starting with a Latin brand name.
BIDI = re.compile('[‎‏‪-‮⁦-⁩]')


def cmd_put():
    src, he = load()
    mapping = json.load(open(CUR, encoding='utf-8'))
    new = json.load(open(CUR_HE, encoding='utf-8'))
    added = bad = stripped = 0
    for i, v in new.items():
        if isinstance(v, str):
            nv = BIDI.sub('', v)
            if nv != v:
                stripped += 1
                new[i] = v = nv
        k = mapping.get(str(i))
        if k is None:
            print('!! index %s not in the current batch' % i)
            bad += 1
            continue
        if not isinstance(v, str) or not v.strip():
            print('!! index %s empty' % i)
            bad += 1
            continue
        he[k] = v
        added += 1
    json.dump(he, open(HEB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('merged %d  (rejected %d, bidi-stripped %d)  total %d/%d'
          % (added, bad, stripped, len(he), len(src)))


def cmd_stat():
    src, he = load()
    import collections
    done = collections.Counter()
    tot = collections.Counter()
    for k, r in src.items():
        tot[r['context']] += 1
        if k in he:
            done[r['context']] += 1
    print('translated %d / %d  (%.1f%%)' % (len(he), len(src), 100.0 * len(he) / len(src)))


if __name__ == '__main__':
    a = sys.argv[1:] or ['stat']
    if a[0] == 'get':
        cmd_get(int(a[1]) if len(a) > 1 else 100)
    elif a[0] == 'put':
        cmd_put()
    else:
        cmd_stat()
