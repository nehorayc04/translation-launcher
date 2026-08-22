"""Qt .qm (Qt Linguist compiled translation) reader + writer — pure Python, no Qt.

Built for SignalRGB, but the format is Qt-generic and reusable for ANY Qt app.

FILE LAYOUT
    16-byte magic, then a sequence of blocks:  tag:u8, len:u32be, payload
    Block tags: Contexts=0x2f  Hashes=0x42  Messages=0x69
                NumerusRules=0x88  Dependencies=0x96  Language=0xa7
    Qt's reader stops cleanly on `tag == 0 || len == 0`, so a .qm may be
    padded with NUL bytes to an arbitrary size — that is what makes a
    delta-0 in-place patch of an embedded .qm possible.

MESSAGE ITEM TAGS (inside the Messages block)
    End=1  SourceText16=2  Translation=3  Context16=4
    Obsolete1=5  SourceText=6  Context=7  Comment=8
    Tag 3 payload = QDataStream QString  -> u32 byte-length (0xFFFFFFFF = null) + UTF-16BE
    Tags 6/7/8    = QDataStream QByteArray -> u32 byte-length + UTF-8
    Tags 2/4      = u32 byte-length + UTF-16BE  (legacy, unused by modern lrelease)

    Qt writes the items of one message in this exact order:
        Translation* , [Comment] , [SourceText] , [Context] , End
    Which of Comment/SourceText/Context are present is the message's
    "prefix" — chosen by lrelease per message. We record what we read and
    re-emit exactly that, which is what makes the identity round-trip
    byte-exact.

HASHES BLOCK (0x42) — REQUIRED
    Sorted array of {u32 hash, u32 offset-into-Messages-block}.
    hash = elfHash(utf8(sourceText) then utf8(comment)).
    Without it QTranslator finds nothing, so a hand-built .qm MUST have it.
"""
import struct

MAGIC = bytes([0x3C, 0xB8, 0x64, 0x18, 0xCA, 0xEF, 0x9C, 0x95,
               0xCD, 0x21, 0x1C, 0xBF, 0x60, 0xA1, 0xBD, 0xDD])

TAG_CONTEXTS, TAG_HASHES, TAG_MESSAGES = 0x2f, 0x42, 0x69
TAG_NUMERUS, TAG_DEPS, TAG_LANGUAGE = 0x88, 0x96, 0xa7
KNOWN_BLOCKS = {TAG_CONTEXTS, TAG_HASHES, TAG_MESSAGES,
                TAG_NUMERUS, TAG_DEPS, TAG_LANGUAGE}

END, SOURCETEXT16, TRANSLATION, CONTEXT16 = 1, 2, 3, 4
OBSOLETE1, SOURCETEXT, CONTEXT, COMMENT = 5, 6, 7, 8

NULL = object()   # marks a QDataStream null (length 0xFFFFFFFF)


# --------------------------------------------------------------------------
# hashing (mirrors qtranslator.cpp elfHash_continue / elfHash_finish)
# --------------------------------------------------------------------------

def elf_hash(*parts):
    h = 0
    for part in parts:
        if part is None:
            continue
        for ch in part.encode('utf-8'):
            h = ((h << 4) + ch) & 0xFFFFFFFF
            g = h & 0xF0000000
            if g:
                h ^= g >> 24
            h &= (~g) & 0xFFFFFFFF
    return h or 1


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def read_blocks(buf, start=0):
    """-> (list of (tag, payload_offset, payload_len), end_offset)."""
    if buf[start:start + 16] != MAGIC:
        raise ValueError('not a .qm (bad magic)')
    p = start + 16
    blocks = []
    while p + 5 <= len(buf):
        tag = buf[p]
        if tag == 0 or tag not in KNOWN_BLOCKS:
            break                      # Qt stops here too
        ln = struct.unpack('>I', buf[p + 1:p + 5])[0]
        if ln == 0 or p + 5 + ln > len(buf):
            break
        blocks.append((tag, p + 5, ln))
        p += 5 + ln
    return blocks, p


def _qstring(buf, p):
    n = struct.unpack('>I', buf[p:p + 4])[0]
    p += 4
    if n == 0xFFFFFFFF:
        return NULL, p
    return buf[p:p + n].decode('utf-16-be', 'replace'), p + n


def _qbytes(buf, p):
    n = struct.unpack('>I', buf[p:p + 4])[0]
    p += 4
    if n == 0xFFFFFFFF:
        return NULL, p
    return buf[p:p + n].decode('utf-8', 'replace'), p + n


def parse_messages(buf, off, ln):
    """-> list of message dicts.

    Each dict keeps `order` = the tag sequence actually present, so the
    writer can reproduce the file byte-for-byte.
    """
    end = off + ln
    p = off
    out = []
    cur = {'offset': p - off, 'translations': [], 'order': []}
    while p < end:
        tag = buf[p]
        p += 1
        if tag == END:
            cur['order'].append(END)
            out.append(cur)
            cur = {'offset': p - off, 'translations': [], 'order': []}
        elif tag == TRANSLATION:
            v, p = _qstring(buf, p)
            cur['translations'].append(None if v is NULL else v)
            cur['order'].append(TRANSLATION)
        elif tag in (SOURCETEXT, CONTEXT, COMMENT):
            v, p = _qbytes(buf, p)
            key = {SOURCETEXT: 'source', CONTEXT: 'context', COMMENT: 'comment'}[tag]
            cur[key] = None if v is NULL else v
            cur['order'].append(tag)
        elif tag in (SOURCETEXT16, CONTEXT16):
            v, p = _qstring(buf, p)
            key = 'source' if tag == SOURCETEXT16 else 'context'
            cur[key] = None if v is NULL else v
            cur['order'].append(tag)
        elif tag == OBSOLETE1:
            p += 4
            cur['order'].append(OBSOLETE1)
        else:
            raise ValueError('bad message tag %d at +%d' % (tag, p - 1 - off))
    return out


def load(buf, start=0):
    blocks, end = read_blocks(buf, start)
    info = {'size': end - start, 'messages': [], 'language': None,
            'deps': None, 'blocks': [(t, l) for t, _, l in blocks],
            'has_hashes': False, 'contexts': None, 'numerus': None}
    for tag, off, ln in blocks:
        if tag == TAG_MESSAGES:
            info['messages'] = parse_messages(buf, off, ln)
        elif tag == TAG_LANGUAGE:
            info['language'] = buf[off:off + ln].decode('utf-8', 'replace')
        elif tag == TAG_DEPS:
            info['deps'] = buf[off:off + ln]
        elif tag == TAG_HASHES:
            info['has_hashes'] = True
        elif tag == TAG_CONTEXTS:
            info['contexts'] = buf[off:off + ln]
        elif tag == TAG_NUMERUS:
            info['numerus'] = buf[off:off + ln]
    return info


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

def _put_qstring(s):
    if s is None:
        return struct.pack('>I', 0xFFFFFFFF)
    b = s.encode('utf-16-be')
    return struct.pack('>I', len(b)) + b


def _put_qbytes(s):
    if s is None:
        return struct.pack('>I', 0xFFFFFFFF)
    b = s.encode('utf-8')
    return struct.pack('>I', len(b)) + b


def _emit_message(msg):
    """Emit one message using its recorded `order` (or the default order)."""
    order = msg.get('order')
    if not order:
        order = [TRANSLATION] * max(1, len(msg.get('translations') or [None]))
        if msg.get('comment') is not None:
            order.append(COMMENT)
        if msg.get('source') is not None:
            order.append(SOURCETEXT)
        if msg.get('context') is not None:
            order.append(CONTEXT)
        order.append(END)
    out = bytearray()
    ti = 0
    for tag in order:
        if tag == TRANSLATION:
            tr = msg['translations'][ti] if ti < len(msg['translations']) else None
            ti += 1
            out += bytes([TRANSLATION]) + _put_qstring(tr)
        elif tag == COMMENT:
            out += bytes([COMMENT]) + _put_qbytes(msg.get('comment'))
        elif tag == SOURCETEXT:
            out += bytes([SOURCETEXT]) + _put_qbytes(msg.get('source'))
        elif tag == CONTEXT:
            out += bytes([CONTEXT]) + _put_qbytes(msg.get('context'))
        elif tag == SOURCETEXT16:
            out += bytes([SOURCETEXT16]) + _put_qstring(msg.get('source'))
        elif tag == CONTEXT16:
            out += bytes([CONTEXT16]) + _put_qstring(msg.get('context'))
        elif tag == END:
            out += bytes([END])
        elif tag == OBSOLETE1:
            out += bytes([OBSOLETE1]) + b'\0\0\0\0'
    return bytes(out)


def build(messages, language=None, deps=None, contexts=None, numerus=None,
          pad_to=None):
    """Build a .qm.  `messages` = dicts as produced by load()['messages'].

    Emits Hashes + Messages (+ Contexts/NumerusRules/Dependencies/Language),
    in the same block order lrelease uses.  `pad_to` NUL-pads the result to an
    exact byte length (Qt stops parsing at the first 0 tag) — this is what
    enables a delta-0 in-place patch of a .qm embedded in a binary.
    """
    msg_blob = bytearray()
    hashes = []
    for m in messages:
        off = len(msg_blob)
        msg_blob += _emit_message(m)
        src = m.get('source')
        if src is not None:
            hashes.append((elf_hash(src, m.get('comment')), off))
    hashes.sort()
    hash_blob = b''.join(struct.pack('>II', h, o) for h, o in hashes)

    buf = bytearray(MAGIC)

    def blk(tag, payload):
        buf.extend(bytes([tag]) + struct.pack('>I', len(payload)) + payload)

    # Block order as emitted by lrelease: Language, Hashes, Messages,
    # Contexts, NumerusRules, Dependencies.
    if language:
        blk(TAG_LANGUAGE, language.encode('utf-8'))
    blk(TAG_HASHES, hash_blob)
    blk(TAG_MESSAGES, bytes(msg_blob))
    if contexts:
        blk(TAG_CONTEXTS, contexts)
    if numerus:
        blk(TAG_NUMERUS, numerus)
    if deps:
        blk(TAG_DEPS, deps)

    if pad_to is not None:
        if len(buf) > pad_to:
            raise ValueError('built .qm is %d bytes, exceeds pad_to=%d'
                             % (len(buf), pad_to))
        buf.extend(b'\0' * (pad_to - len(buf)))
    return bytes(buf)


# --------------------------------------------------------------------------
# selftest — identity round-trip against the real shipped .qm files
# --------------------------------------------------------------------------

def _selftest(exe_path=None):
    import re, os
    exe_path = exe_path or os.environ.get('SIGNALRGB_EXE') or (
        r'C:/Users/Nehoray_Cohen/AppData/Local/VortxEngine/app-2.5.74'
        r'/Signal-x64/SignalRgb.exe')
    d = open(exe_path, 'rb').read()
    hits = [m.start() for m in re.finditer(re.escape(MAGIC), d)]
    print('found %d embedded .qm' % len(hits))
    ok = fail = 0
    for h in hits:
        info = load(d, h)
        orig = d[h:h + info['size']]
        rebuilt = build(info['messages'], language=info['language'],
                        deps=info['deps'], contexts=info['contexts'],
                        numerus=info['numerus'])
        # block order must match what we read
        same = rebuilt == orig
        tag = 'BYTE-IDENTICAL' if same else 'DIFFERS'
        if not same:
            # semantic fallback check
            ri = load(rebuilt)
            sem = (len(ri['messages']) == len(info['messages']) and
                   all(a.get('source') == b.get('source') and
                       a.get('context') == b.get('context') and
                       a['translations'] == b['translations']
                       for a, b in zip(ri['messages'], info['messages'])))
            tag += ' (semantic OK)' if sem else ' (SEMANTIC FAIL)'
        print('  @%-10d lang=%-7s msgs=%-5d size=%-7d -> %s (rebuilt %d)'
              % (h, info['language'], len(info['messages']), info['size'],
                 tag, len(rebuilt)))
        ok += same
        fail += (not same)
    print('byte-identical: %d/%d' % (ok, ok + fail))
    return fail == 0


if __name__ == '__main__':
    import sys
    sys.exit(0 if _selftest(*sys.argv[1:]) else 1)
