"""QA gate for agent_handoff/hebrew.json — run before every build.

Per line, against the English source:
  key           the key exists in to_translate (nothing invented)
  empty         non-empty translation
  tokens        %1..%9 multiset, literal-% count and \n count identical to EN
  numbers       every digit-run in the EN survives into the Hebrew
  identifiers   ALL-CAPS / camelCase tokens (SMBus, ARGB, DPI) survive
  niqqud        none (U+0591-U+05C7)
  foreign       no Arabic / Cyrillic / CJK / Hangul / Thai in the output
  bidi_controls no RLM/LRM/RLE/PDF — the app runs the UBA, we store LOGICAL
  untranslated  identical to the EN, allowed only for brands/identifiers
  glossary      a term in the locked glossary maps to one Hebrew term
  has_hebrew    a line with real English words must contain Hebrew

Exit code 0 = clean.  build_hebrew.py refuses to build on a non-zero exit.
"""
import os, re, sys, json, collections

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
HANDOFF = os.path.join(ROOT, 'agent_handoff')

ARG = re.compile(r'%\d')
LITERAL_PCT = re.compile(r'%(?!\d)')
NUM = re.compile(r'\d+')
NIQQUD = re.compile('[֑-ׇ]')
BIDI = re.compile('[‎‏‪-‮⁦-⁩]')
HEB = re.compile('[א-ת]')
IDENT = re.compile(r'\b(?:[A-Z]{2,}[0-9]*|[a-z]+[A-Z][A-Za-z]*)\b')
WORD = re.compile(r'[A-Za-z]{2,}')

FOREIGN = [('arabic', 0x0600, 0x06FF), ('cyrillic', 0x0400, 0x04FF),
           ('cjk', 0x4E00, 0x9FFF), ('kana', 0x3040, 0x30FF),
           ('hangul', 0xAC00, 0xD7AF), ('thai', 0x0E00, 0x0E7F)]


def load():
    src = json.load(open(os.path.join(HANDOFF, 'to_translate.json'), encoding='utf-8'))
    he = json.load(open(os.path.join(HANDOFF, 'hebrew.json'), encoding='utf-8'))
    reg = json.load(open(os.path.join(HANDOFF, 'name_registry.json'), encoding='utf-8'))
    return src, he, reg


def check(src, he, reg):
    keep = {k.lower() for k in reg['keep_latin']}
    glossary = reg['glossary']
    problems = collections.defaultdict(list)

    for k in he:
        if k not in src:
            problems['key'].append((k, 'not in to_translate'))

    for k, row in src.items():
        t = he.get(k)
        if t is None:
            continue                        # missing = coverage, reported apart
        en = row['en']
        if not t.strip():
            problems['empty'].append((k, en))
            continue

        if sorted(ARG.findall(en)) != sorted(ARG.findall(t)):
            problems['tokens'].append((k, '%s  ->  %s' % (en, t)))
        elif len(LITERAL_PCT.findall(en)) != len(LITERAL_PCT.findall(t)):
            problems['tokens'].append((k, 'literal %% count: %s -> %s' % (en, t)))
        if en.count('\n') != t.count('\n'):
            problems['tokens'].append((k, 'newline count: %r -> %r' % (en, t)))

        if sorted(NUM.findall(en)) != sorted(NUM.findall(t)):
            problems['numbers'].append((k, '%s  ->  %s' % (en, t)))

        # A fully upper-case source string is a STYLED HEADER, not a set of
        # technical identifiers - skip the survival check for those.
        styled_caps = en.upper() == en and any(c.isalpha() for c in en)
        for ident in (() if styled_caps else set(IDENT.findall(en))):
            # plain English words that merely happen to be capitalised —
            # not technical identifiers that must survive verbatim
            if ident.lower() in ('ok', 'id', 'ui', 'pc', 'tv', 'os', 'am', 'pm',
                                 'experimental', 'new', 'off', 'on', 'all'):
                continue
            if ident not in t:
                problems['identifiers'].append((k, '%s missing from: %s' % (ident, t)))

        if NIQQUD.search(t):
            problems['niqqud'].append((k, t))
        if BIDI.search(t):
            problems['bidi_controls'].append((k, repr(t)))
        for name, lo, hi in FOREIGN:
            if any(lo <= ord(c) <= hi for c in t):
                problems['foreign'].append((k, '%s in: %s' % (name, t)))
                break

        if t.strip() == en.strip():
            if en.strip().lower() not in keep and WORD.search(en):
                problems['untranslated'].append((k, en))
        elif WORD.search(en) and not HEB.search(t):
            if en.strip().lower() not in keep:
                problems['has_hebrew'].append((k, '%s  ->  %s' % (en, t)))

        want = glossary.get(en.strip())
        if want and t.strip() != want:
            problems['glossary'].append((k, '%s should be %r, got %r'
                                         % (en, want, t)))
    return problems


def main():
    src, he, reg = load()
    missing = [k for k in src if k not in he]
    problems = check(src, he, reg)

    print('strings      : %d' % len(src))
    print('translated   : %d  (%.1f%%)'
          % (len(src) - len(missing), 100.0 * (len(src) - len(missing)) / len(src)))
    print('untranslated : %d' % len(missing))
    total = sum(len(v) for v in problems.values())
    print('defects      : %d' % total)
    for kind, items in sorted(problems.items(), key=lambda kv: -len(kv[1])):
        print('\n== %s (%d)' % (kind, len(items)))
        for k, msg in items[:15]:
            print('   %-46s %s' % (k.replace('\x1f', '|')[:46], msg[:110]))
        if len(items) > 15:
            print('   ... %d more' % (len(items) - 15))
    if missing and '--show-missing' in sys.argv:
        print('\n== first missing keys')
        for k in missing[:30]:
            print('   %-50s %s' % (k.replace('\x1f', '|')[:50], src[k]['en'][:60]))
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
