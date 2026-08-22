# -*- coding: utf-8 -*-
import json, glob, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DL = r'C:\Users\Nehoray_Cohen\Downloads'
# pick the most recent answers file
cands = [f for f in os.listdir(DL) if f.endswith('.json') and 'json' and ('בחיר' in f or 'בחיר' in f)]
# fallback: match by content marker
def is_answers(p):
    try:
        d = json.load(open(p, encoding='utf-8'))
        return isinstance(d, dict) and d.get('meta', {}).get('tool') == 'faq-customization'
    except Exception:
        return False

paths = []
for f in os.listdir(DL):
    if f.endswith('.json'):
        p = os.path.join(DL, f)
        if is_answers(p):
            paths.append((os.path.getmtime(p), p))
paths.sort(reverse=True)
assert paths, 'no answers file found'
ANS_PATH = paths[0][1]
print('USING', ANS_PATH)
ans = json.load(open(ANS_PATH, encoding='utf-8'))['answers']

HERE = os.path.dirname(os.path.abspath(__file__))
cats = [json.load(open(f, encoding='utf-8')) for f in sorted(glob.glob(os.path.join(HERE, '*.json')))]

out = []
for cat in cats:
    cid = cat['categoryId']
    out.append('\n=== %s ===' % cat['categoryHe'])
    for li, q in enumerate(cat['questions']):
        key = '%s#%d' % (cid, li)
        a = ans.get(key, {})
        sel = a.get('selected', [])
        free = (a.get('free') or '').strip()
        out.append('Q%d. %s' % (li + 1, q['q']))
        if sel:
            out.append('   [V] ' + ' | '.join(sel))
        if free:
            out.append('   [free] ' + free.replace('\n', ' / '))
        if not sel and not free:
            out.append('   (no answer)')

report = '\n'.join(out)
open(os.path.join(HERE, 'ANSWERS_DECODED.txt'), 'w', encoding='utf-8').write(report)

tot = sum(len(c['questions']) for c in cats)
def has(c, li):
    a = ans.get('%s#%d' % (c['categoryId'], li), {})
    return bool(a.get('selected') or (a.get('free') or '').strip())
answered = sum(1 for c in cats for li in range(len(c['questions'])) if has(c, li))
print('total', tot, 'answered', answered)
print('WROTE', os.path.join(HERE, 'ANSWERS_DECODED.txt'))
