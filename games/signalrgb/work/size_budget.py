"""Size budget for the delta-0 slot, and the lever that guarantees a fit.

The Arabic .qm exactly fills its 226,603-byte qrc slot, so a Hebrew build
that is even one character longer than the Arabic would not fit.  Hebrew is
usually a bit longer than this vendor's Arabic, so we need headroom.

THE LEVER — minimal message prefix (what lrelease itself does).
    QTranslator looks a message up by elfHash(source + comment) and then
    only VERIFIES with whatever of Comment/SourceText/Context the message
    happens to carry.  Those fields are optional: a message whose hash is
    unique in the file needs none of them, and one that collides needs only
    enough to disambiguate.  Dropping the redundant ones is lossless for
    lookup and frees a large amount of space.

This script reports the current cost, the free-able bytes, and simulates a
full Hebrew build at a range of expansion ratios.
"""
import os, sys, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qm as Q
import patch_exe as P


def minimize_prefixes(messages):
    """Return a copy of `messages` carrying the smallest safe verification prefix.

    hash collides on (source, comment) only -> keep Context when the hash is
    shared, keep SourceText too when context is also shared.
    """
    by_hash = collections.defaultdict(list)
    for m in messages:
        if m.get('source') is None:
            continue
        by_hash[Q.elf_hash(m.get('source'), m.get('comment'))].append(m)

    out = []
    for m in messages:
        m = dict(m)
        if m.get('source') is None:
            out.append(m)                       # leave odd entries untouched
            continue
        group = by_hash[Q.elf_hash(m.get('source'), m.get('comment'))]
        n_tr = sum(1 for t in m.get('order', []) if t == Q.TRANSLATION) or \
            len(m['translations'])
        order = [Q.TRANSLATION] * n_tr
        if len(group) > 1:
            ctxs = {g.get('context') for g in group}
            order.append(Q.CONTEXT)
            if len(ctxs) < len(group):          # context alone is not enough
                order.append(Q.SOURCETEXT)
                order[-2:] = [Q.SOURCETEXT, Q.CONTEXT]
        order.append(Q.END)
        m['order'] = order
        out.append(m)
    return out


def main():
    exe = P.find_exe()
    data = open(exe, 'rb').read()
    off, size = P.find_slot(data)
    info = Q.load(data, off)
    msgs = info['messages']

    ar_chars = sum(len(t) for m in msgs for t in m['translations'] if t)
    en_chars = sum(len(m['source']) for m in msgs if m.get('source'))
    print('slot                : %d bytes (exactly filled by the Arabic .qm)' % size)
    print('messages            : %d' % len(msgs))
    print('arabic translation  : %d chars  = %d bytes UTF-16' % (ar_chars, ar_chars * 2))
    print('english source      : %d chars' % en_chars)

    minimal = minimize_prefixes(msgs)
    slim = Q.build(minimal, language=info['language'], deps=info['deps'],
                   contexts=info['contexts'], numerus=info['numerus'])
    print()
    print('current .qm         : %d bytes' % size)
    print('minimal-prefix .qm  : %d bytes   -> FREES %d bytes'
          % (len(slim), size - len(slim)))
    kept = collections.Counter()
    for m in minimal:
        kept[tuple(t for t in m['order'] if t in (Q.SOURCETEXT, Q.CONTEXT))] += 1
    print('prefix mix          : %s' % dict(
        {('hash only' if not k else '+'.join(
            {Q.SOURCETEXT: 'src', Q.CONTEXT: 'ctx'}[x] for x in k)): v
         for k, v in kept.items()}))

    # sanity: the slim file must still resolve every message
    ok = Q.load(slim)
    assert len(ok['messages']) == len(msgs), 'message count changed!'
    print('slim re-parse       : %d messages OK' % len(ok['messages']))

    print()
    print('simulated full Hebrew build (Hebrew chars = ratio x English chars):')
    for ratio in (0.85, 0.95, 1.00, 1.10, 1.25):
        he_chars = int(en_chars * ratio)
        delta = (he_chars - ar_chars) * 2
        full = size + delta
        slimmed = len(slim) + delta
        print('   ratio %.2f -> %6d he chars | as-is %8d (%s) | minimal-prefix %8d (%s)'
              % (ratio, he_chars, full, 'FITS' if full <= size else 'OVERFLOW',
                 slimmed, 'FITS' if slimmed <= size else 'OVERFLOW'))


if __name__ == '__main__':
    main()
