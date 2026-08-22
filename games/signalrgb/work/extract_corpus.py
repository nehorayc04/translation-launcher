"""Extract every .qm embedded in SignalRgb.exe and build the translation corpus.

Outputs into games/signalrgb/extract/ :
    qm/<lang>.qm         raw shipped .qm, byte-exact
    en.json              {key: english}                 (the source to translate)
    reference.json       {key: {en, ar, ru, ja, zh, ko, sr, ...}}  New-Era oracle
    index.json           per-language offset/size/count inside the exe
    report.txt           scope + token inventory

KEY = "<context>\x1f<source>\x1f<comment>"  — exactly what Qt looks a message
up by, so a translation can never land on the wrong string.
"""
import os, re, sys, json, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qm as Q

OUT = os.path.abspath(os.path.join(HERE, '..', 'extract'))
DEFAULT_EXE = (r'C:/Users/Nehoray_Cohen/AppData/Local/VortxEngine/app-2.5.74'
               r'/Signal-x64/SignalRgb.exe')
SEP = '\x1f'


def key_of(m):
    return SEP.join([m.get('context') or '', m.get('source') or '',
                     m.get('comment') or ''])


def detect_label(info):
    """Label a .qm by the SCRIPT of its translations, not by its Language block.

    SignalRGB ships a mislabeled file: the .qm serving Traditional Chinese
    declares `ru_RU` and contains ZERO Cyrillic.  Trusting the declared tag
    would hand a translator a "Russian" column full of Chinese.
    """
    txt = ''.join(t or '' for m in info['messages'] for t in m['translations'])
    if not txt:
        return 'template'
    def n(lo, hi):
        return sum(1 for c in txt if lo <= ord(c) <= hi)
    counts = {'ar': n(0x600, 0x6FF), 'he': n(0x590, 0x5FF), 'ko': n(0xAC00, 0xD7AF),
              'sr': n(0x400, 0x4FF), 'kana': n(0x3040, 0x30FF),
              'cjk': n(0x4E00, 0x9FFF), 'th': n(0xE00, 0xE7F)}
    if counts['kana'] > 200:
        return 'ja'
    top = max(counts, key=counts.get)
    if counts[top] < len(txt) * 0.10:
        return (info['language'] or 'unknown').split('_')[0]
    if top == 'cjk':
        # Simplified vs Traditional: a few high-frequency divergent glyphs.
        simp = sum(txt.count(c) for c in '设备应统开关闭产码启动语义')
        trad = sum(txt.count(c) for c in '設備應統開關閉產碼啟動語義')
        return 'zh_CN' if simp >= trad else 'zh_TW'
    return top


def find_all(exe_path):
    d = open(exe_path, 'rb').read()
    out = []
    for h in (m.start() for m in re.finditer(re.escape(Q.MAGIC), d)):
        info = Q.load(d, h)
        prefix_len = struct.unpack('>I', d[h - 4:h])[0]
        info['offset'] = h
        info['qrc_len'] = prefix_len
        info['qrc_len_matches'] = (prefix_len == info['size'])
        out.append(info)
    return d, out


def main(exe_path=DEFAULT_EXE):
    os.makedirs(os.path.join(OUT, 'qm'), exist_ok=True)
    d, langs = find_all(exe_path)
    index = []
    per_lang = {}

    for info in langs:
        lang = detect_label(info)
        blob = d[info['offset']:info['offset'] + info['size']]
        open(os.path.join(OUT, 'qm', lang + '.qm'), 'wb').write(blob)
        index.append({'lang': lang, 'declared': info['language'],
                      'mislabeled': bool(info['language']) and
                                    not (info['language'] or '').startswith(lang.split('_')[0]),
                      'offset': info['offset'],
                      'size': info['size'], 'qrc_len': info['qrc_len'],
                      'qrc_len_matches': info['qrc_len_matches'],
                      'messages': len(info['messages'])})
        table = {}
        for m in info['messages']:
            if not m.get('source'):
                continue
            tr = m['translations'][0] if m['translations'] else None
            if tr:
                table[key_of(m)] = tr
        per_lang[lang] = table

    # English source = the union of every language's source strings
    en = {}
    ctx = {}
    for info in langs:
        for m in info['messages']:
            s = m.get('source')
            if not s:
                continue
            k = key_of(m)
            en.setdefault(k, s)
            ctx.setdefault(k, m.get('context') or '')

    # order: by context, then by source (stable + reviewable)
    keys = sorted(en, key=lambda k: (ctx[k].lower(), en[k].lower()))

    reference = {}
    for k in keys:
        row = {'context': ctx[k], 'en': en[k]}
        for lang, table in per_lang.items():
            if lang == 'template':
                continue
            if k in table:
                row[lang] = table[k]
        reference[k] = row

    json.dump({k: en[k] for k in keys},
              open(os.path.join(OUT, 'en.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump(reference,
              open(os.path.join(OUT, 'reference.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump(index, open(os.path.join(OUT, 'index.json'), 'w'), indent=1)

    # ---- report ----
    L = []
    L.append('SignalRGB translation corpus')
    L.append('exe: %s' % exe_path)
    L.append('')
    L.append('%-9s %-9s %-12s %-9s %-7s %-10s %s'
             % ('LANG', 'DECLARED', 'OFFSET', 'SIZE', 'MSGS', 'qrc_len_ok', 'MISLABELED'))
    for r in index:
        L.append('%-9s %-9s %-12d %-9d %-7d %-10s %s'
                 % (r['lang'], r['declared'], r['offset'], r['size'],
                    r['messages'], r['qrc_len_matches'],
                    'YES' if r['mislabeled'] else ''))
    L.append('')
    L.append('unique translatable strings: %d' % len(keys))
    L.append('total EN characters:         %d' % sum(len(en[k]) for k in keys))
    lens = sorted(len(en[k]) for k in keys)
    L.append('EN length: median %d  max %d  | <=25: %d  26-140: %d  >140: %d'
             % (lens[len(lens) // 2], lens[-1],
                sum(1 for x in lens if x <= 25),
                sum(1 for x in lens if 25 < x <= 140),
                sum(1 for x in lens if x > 140)))
    contexts = collections.Counter(ctx[k] for k in keys)
    L.append('contexts: %d   top: %s' % (len(contexts), contexts.most_common(10)))
    L.append('')
    L.append('coverage of the shipped languages (how many of our keys they translate):')
    for lang, table in sorted(per_lang.items(), key=lambda kv: -len(kv[1])):
        hit = sum(1 for k in keys if k in table)
        L.append('  %-10s %5d / %d' % (lang, hit, len(keys)))
    L.append('')
    L.append('tokens that MUST survive translation:')
    pats = {'%1..%9': r'%\d', 'literal %': r'%(?!\d)', 'newline': r'\n',
            'html tag': r'<[a-zA-Z/][^>]{0,30}>', '{...}': r'\{[^}]{0,20}\}'}
    for name, p in pats.items():
        tot = sum(len(re.findall(p, en[k])) for k in keys)
        n = sum(1 for k in keys if re.search(p, en[k]))
        L.append('  %-10s %5d occurrences in %d strings' % (name, tot, n))
    open(os.path.join(OUT, 'report.txt'), 'w', encoding='utf-8').write('\n'.join(L))
    print('\n'.join(L))
    print('\nwrote ->', OUT)


if __name__ == '__main__':
    main(*sys.argv[1:])
