"""Deploy / revert the Hebrew translation into SignalRgb.exe.

MECHANISM — delta-0 in-place patch of an embedded .qm
    SignalRGB loads its UI translation from `:/i18n/SignalRgb_<locale>.qm`,
    a Qt resource COMPILED INTO the exe (there is no disk override path:
    the only i18n string in the binary is the resource prefix, and nothing
    calls QResource::registerResource on an external .rcc).
    So the deploy target is the exe itself.

    Every Qt resource is stored as {u32be length}{payload}, and Qt's .qm
    reader stops cleanly at the first zero tag — therefore a Hebrew .qm that
    is NO LARGER than the shipped Arabic one can be NUL-padded to the exact
    same byte length and written in place.  Nothing moves, no offset, no
    length prefix and no other resource is touched.  (Verified: the u32
    before every embedded .qm equals its parsed size.)

    Hebrew hijacks the ARABIC slot (`ar_EG`) — SignalRGB has no Hebrew
    locale but ships a full Arabic one, which is the RTL slot the app
    already exercises.

SAFETY
    * The pristine 226,603-byte Arabic region is copied to a backup store
      OUTSIDE the app folder before the first write, together with its
      offset + SHA-256, so revert is byte-exact even after the exe moves.
    * The patch is always built FROM the pristine backup -> idempotent, and
      re-running after a SignalRGB update re-detects and re-applies.
    * The write is atomic-ish: the whole exe is copied to a temp file,
      patched there, then os.replace'd over the original.
    * The app must be closed (the exe is locked while running).

NOTE: patching invalidates the exe's Authenticode signature. SignalRGB does
not verify its own signature at launch, but a Squirrel update replaces the
whole app folder -> just run --deploy again.
"""
import os, re, sys, json, shutil, hashlib, struct, tempfile, subprocess, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qm as Q

SLOT_LANG = 'ar_EG'            # the locale slot Hebrew rides in
APP_ROOT = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'VortxEngine')
BACKUP_DIR = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                          'WhirlwindFX', 'SignalRgb', 'hebrew_backup')


# ---------------------------------------------------------------- locating

def find_exe():
    """Newest app-*/Signal-x64/SignalRgb.exe under %LOCALAPPDATA%/VortxEngine."""
    env = os.environ.get('SIGNALRGB_EXE')
    if env and os.path.isfile(env):
        return env
    if not os.path.isdir(APP_ROOT):
        raise SystemExit('SignalRGB not found (no %s)' % APP_ROOT)
    cands = []
    for name in os.listdir(APP_ROOT):
        if not name.startswith('app-'):
            continue
        p = os.path.join(APP_ROOT, name, 'Signal-x64', 'SignalRgb.exe')
        if os.path.isfile(p):
            cands.append((_ver_key(name[4:]), p))
    if not cands:
        raise SystemExit('no Signal-x64/SignalRgb.exe under %s' % APP_ROOT)
    return max(cands)[1]


def _ver_key(v):
    return tuple(int(x) if x.isdigit() else 0 for x in v.split('.'))


def _score_qm(qmbytes):
    """(arabic+hebrew char count) of a decoded .qm — the slot signature."""
    try:
        info = Q.load(qmbytes, 0)
    except Exception:
        return None, 0
    txt = ''.join(t or '' for msg in info['messages'] for t in msg['translations'])
    if not txt:
        return info, 0
    score = sum(1 for c in txt if 0x600 <= ord(c) <= 0x6FF          # arabic
                or 0x590 <= ord(c) <= 0x5FF)                        # hebrew (=already ours)
    return info, (score if score > len(txt) * 0.20 else 0)


def slot_qm(payload, kind):
    """Decode a slot's on-disk PAYLOAD -> the raw .qm bytes.

    raw  : the payload IS the .qm (NUL-padded; Qt stops at the first zero tag).
    zlib : the payload is `[u32be uncompressedSize][zlib stream]` — inflate it.
    """
    if kind == 'zlib':
        return zlib.decompress(payload[4:])
    return payload


def pack_slot(qmbytes, size, kind):
    """Encode a .qm into exactly `size` on-disk bytes for the slot (delta-0)."""
    if kind == 'zlib':
        body = struct.pack('>I', len(qmbytes)) + zlib.compress(qmbytes, 9)
        if len(body) > size:
            raise SystemExit('compressed .qm payload is %d B, exceeds the %d-byte '
                             'slot — cannot delta-0 patch' % (len(body), size))
        return body + b'\0' * (size - len(body))
    if len(qmbytes) > size:
        raise SystemExit('.qm is %d B, exceeds the %d-byte slot' % (len(qmbytes), size))
    return qmbytes + b'\0' * (size - len(qmbytes))


def find_slot(data, lang=SLOT_LANG):
    """-> (payload_offset, payload_size, kind) of the Arabic-slot .qm.

    Selected by CONTENT (the one blob whose translations are dominantly
    Arabic script — or already Hebrew, i.e. ours), NOT by the internal
    Language block: SignalRGB ships at least one .qm whose Language block is
    wrong (the file served for zh_TW declares `ru_RU`).

    The slot may be stored UNCOMPRESSED (`kind='raw'`, SignalRGB <=2.5.74) or
    ZLIB-COMPRESSED in the qrc (`kind='zlib'`, 2.5.75+).  Both are handled;
    the returned (offset,size) is always the exact on-disk span to overwrite
    delta-0, and `slot_qm`/`pack_slot` translate to/from the .qm.
    """
    # ── raw: a bare .qm magic whose translations are Arabic/Hebrew ──
    best = None
    for m in re.finditer(re.escape(Q.MAGIC), data):
        h = m.start()
        info, score = _score_qm(data[h:])
        if info and score:
            if best is None or score > best[3]:
                best = (h, info['size'], info['language'], score)
    if best is not None:
        h, parsed, declared, _ = best
        prefix = struct.unpack('>I', data[h - 4:h])[0]   # authoritative slot size
        if parsed > prefix:
            raise SystemExit('parsed .qm (%d B) overruns its qrc slot (%d B) — '
                             'layout changed, refusing to patch' % (parsed, prefix))
        if declared != lang:
            print('note: slot .qm declares language=%r (expected %r)' % (declared, lang))
        return h, prefix, 'raw'

    # ── zlib: a compressed resource that inflates to an Arabic/Hebrew .qm ──
    # A qrc compressed record is [u32be dataLength][u32be uncompressedSize][zlib].
    # There are ~14k stray `78 xx` bytes in the exe, so PRE-FILTER on the two
    # length fields (a real record has a plausible on-disk size and inflates
    # LARGER) before the expensive decompress, and use a memoryview so the
    # per-candidate window slice does not copy megabytes.
    mv = memoryview(data)
    zbest = None
    CAP = 2_000_000
    for m in re.finditer(rb'\x78[\x01\x9c\xda]', data):
        z = m.start()
        if z < 8:
            continue
        dlen = struct.unpack('>I', data[z - 8:z - 4])[0]     # on-disk data length
        usz = struct.unpack('>I', data[z - 4:z])[0]          # inflated size
        if not (4096 <= dlen <= 4_000_000 and dlen < usz <= 40_000_000):
            continue
        try:
            d = zlib.decompressobj()
            out = d.decompress(mv[z:z + CAP], CAP)
        except Exception:
            continue
        if out[:16] != Q.MAGIC:
            continue
        info, score = _score_qm(out)
        if not (info and score):
            continue
        clen = (min(len(data) - z, CAP)) - len(d.unused_data)   # zlib stream length
        # qrc record: [u32be dataLength][u32be uncompressedSize][zlib][NUL pad]
        payload_off = z - 4                       # the u32be uncompressedSize
        dlen = struct.unpack('>I', data[z - 8:z - 4])[0]
        # A pristine slot fills the record exactly (4+clen == dlen); an already
        # DEPLOYED Hebrew slot compresses smaller and is NUL-padded, so its
        # stream is SHORTER (4+clen < dlen) — expected, not corruption.  Reject
        # only if the stream OVERRUNS the record, or the record is implausibly
        # small (a stray zlib stream that is not a qrc resource).
        if 4 + clen > dlen or dlen < 4 + 32:
            continue
        if zbest is None or score > zbest[3]:
            zbest = (payload_off, dlen, info['language'], score)
    if zbest is not None:
        po, dlen, declared, _ = zbest
        if declared != lang:
            print('note: slot .qm declares language=%r (expected %r)' % (declared, lang))
        return po, dlen, 'zlib'

    raise SystemExit('no Arabic/Hebrew .qm slot found in the exe')


# ---------------------------------------------------------------- backup

def _meta_path():
    return os.path.join(BACKUP_DIR, 'slot.json')


# ------------------------------------------------- exe string literals
# A handful of user-visible strings are NOT in the .qm at all: they are plain
# NUL-terminated UTF-8 literals in the binary (the language picker builds its
# menu from a C table of native locale names, so the Hebrew build would still
# offer "العربية").  Those can be patched in place as long as the replacement
# fits the ORIGINAL byte span including its NUL padding — Qt reads them with
# QString::fromUtf8(ptr), i.e. up to the first NUL, so a shorter string simply
# ends earlier and the leftover padding is never read.
#
# Hebrew is 2 bytes/char in UTF-8, so this only works where the source is long
# enough; every entry is verified against its slot before anything is written.
LITERALS = [
    ('العربية', 'עברית'),      # language picker: the slot Hebrew rides in
]


def _literal_meta_path():
    return os.path.join(BACKUP_DIR, 'literals.json')


def find_literal(data, text):
    """-> (offset, span) of a unique NUL-terminated UTF-8 literal."""
    raw = text.encode('utf-8')
    hits = []
    i = data.find(raw)
    while i != -1:
        hits.append(i)
        i = data.find(raw, i + 1)
    if len(hits) != 1:
        return None
    off = hits[0]
    span = len(raw)
    while data[off + span] == 0:            # absorb the NUL padding
        span += 1
    return off, span


def apply_literals(data):
    """-> (patched bytes, [records]) — pure, does not touch disk."""
    buf = bytearray(data)
    recs = []
    for src, dst in LITERALS:
        found = find_literal(bytes(buf), src)
        if not found:
            print('note: literal %r not found (or ambiguous) — skipped' % src)
            continue
        off, span = found
        new = dst.encode('utf-8') + b'\0'
        if len(new) > span:
            print('note: %r needs %d B but the slot is %d — skipped'
                  % (dst, len(new), span))
            continue
        recs.append({'src': src, 'dst': dst, 'offset': off, 'span': span,
                     'orig': bytes(buf[off:off + span]).hex()})
        buf[off:off + span] = new + b'\0' * (span - len(new))
    return bytes(buf), recs


def ensure_backup(exe, data, off, size, kind='raw'):
    """Save the pristine slot PAYLOAD once; return it (always pristine).

    The payload is stored verbatim (raw .qm, or the compressed qrc record) so
    revert is byte-exact regardless of the slot kind.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    blob_path = os.path.join(BACKUP_DIR, 'SignalRgb_%s.orig.qm' % SLOT_LANG)
    meta_path = _meta_path()
    live = data[off:off + size]
    live_is_ours = _is_hebrew(slot_qm(live, kind))

    if os.path.isfile(blob_path) and os.path.isfile(meta_path):
        meta = json.load(open(meta_path, encoding='utf-8'))
        blob = open(blob_path, 'rb').read()
        # A backup is STALE when the slot's size OR kind changed under it — that
        # is a SignalRGB update, which replaces the whole app folder, so the live
        # slot is once again pristine and must become the new backup.  (2.5.74 was
        # a raw 226,603-byte slot; 2.5.75 is a zlib 92,141-byte one.)
        same_slot = (meta.get('size') == size and meta.get('kind', 'raw') == kind)
        if not same_slot or (not live_is_ours and blob != live):
            if live_is_ours:
                raise SystemExit('SignalRGB was updated (slot changed) but the '
                                 'live exe already holds a Hebrew .qm — reinstall '
                                 'SignalRGB, then run --deploy')
            blob = live
            open(blob_path, 'wb').write(blob)
            meta.update(exe=exe, offset=off, size=size, kind=kind,
                        sha256=hashlib.sha256(blob).hexdigest())
            json.dump(meta, open(meta_path, 'w', encoding='utf-8'), indent=1)
        return blob

    if live_is_ours:
        raise SystemExit('the exe already holds a Hebrew .qm but the backup is '
                         'missing — reinstall SignalRGB, then run --deploy')
    open(blob_path, 'wb').write(live)
    json.dump({'exe': exe, 'offset': off, 'size': size, 'kind': kind,
               'sha256': hashlib.sha256(live).hexdigest()},
              open(meta_path, 'w', encoding='utf-8'), indent=1)
    return live


def _is_hebrew(blob):
    try:
        info = Q.load(blob)
    except Exception:
        return False
    txt = ''.join(t or '' for m in info['messages'] for t in m['translations'])
    heb = sum(1 for c in txt if 0x590 <= ord(c) <= 0x5FF)
    return heb > 100


# ---------------------------------------------------------------- writing

def write_slot(exe, off, size, new_bytes, extra=()):
    """Write the .qm slot (+ optional [(offset, bytes)] literal edits) atomically."""
    if len(new_bytes) != size:
        raise SystemExit('refusing to write: %d bytes into a %d-byte slot'
                         % (len(new_bytes), size))
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(exe), suffix='.tmp')
    os.close(fd)
    try:
        shutil.copy2(exe, tmp)
        with open(tmp, 'r+b') as f:
            f.seek(off)
            f.write(new_bytes)
            for eoff, ebytes in extra:
                f.seek(eoff)
                f.write(ebytes)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.replace(tmp, exe)
        except PermissionError:
            # The exe is LOCKED while SignalRGB runs — but Windows lets you
            # RENAME a running executable (the process keeps its open handle to
            # the file, whatever its name).  So move the locked image aside and
            # drop the patched one into its place; the running instance is
            # unaffected and the next launch picks up the new build.  This is
            # the same trick Windows updaters use, and it costs the user
            # nothing: the .qm is read at STARTUP, so a restart was required
            # either way.
            old = exe + '.hebrew-old'
            if os.path.exists(old):
                try:
                    os.remove(old)          # a previous run's leftover, now free
                except OSError:
                    pass
            os.rename(exe, old)             # fails only if renaming is denied too
            try:
                os.replace(tmp, exe)
            except Exception:
                os.rename(old, exe)         # put it back, change nothing
                raise
            print('note: SignalRGB was running — patched in place by moving the '
                  'locked image to %s; restart the app to see it.'
                  % os.path.basename(old))
    except PermissionError:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise SystemExit('SignalRGB is running and its exe could not be renamed '
                         '— close it (tray -> Quit) and retry')
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def is_running():
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq SignalRgb.exe'],
                             capture_output=True, text=True, timeout=20).stdout
        return 'SignalRgb.exe' in out
    except Exception:
        return False


# ---------------------------------------------------------------- commands

def build_hebrew_qm(pristine, hebrew_map, size, kind='raw',
                    layout_rtl=False, drop_untranslated=False):
    """Build the Hebrew .qm and pack it into the slot.

    `pristine` is the slot PAYLOAD (raw .qm, or the compressed qrc record).
    hebrew_map: {key -> hebrew}, key = context\x1fsource\x1fcomment.

    `drop_untranslated` OMITS any skeleton message we have no Hebrew for, so
    Qt falls back to the SOURCE (English) instead of leaving it Arabic — used
    when the app version added strings we haven't translated (2.5.75+).
    """
    info = Q.load(slot_qm(pristine, kind))
    SEP = '\x1f'
    n = 0
    kept = []
    for m in info['messages']:
        k = SEP.join([m.get('context') or '', m.get('source') or '',
                      m.get('comment') or ''])
        he = hebrew_map.get(k)
        if he and m['translations']:
            m['translations'][0] = he
            n += 1
            kept.append(m)
        elif not drop_untranslated:
            kept.append(m)
    info['messages'] = kept
    msgs = info['messages']
    if layout_rtl:
        # Qt derives QGuiApplication::layoutDirection() from this exact string.
        msgs = msgs + [{'context': 'QGuiApplication', 'source': 'QT_LAYOUT_DIRECTION',
                        'comment': None, 'translations': ['RTL'],
                        'order': [Q.TRANSLATION, Q.SOURCETEXT, Q.CONTEXT, Q.END]}]
    qmbytes = Q.build(msgs, language=info['language'], deps=info['deps'],
                      contexts=info['contexts'], numerus=info['numerus'])
    blob = pack_slot(qmbytes, size, kind)     # NUL-pad raw / zlib-compress+pad
    return blob, n


def cmd_status():
    exe = find_exe()
    data = open(exe, 'rb').read()
    off, size, kind = find_slot(data)
    live = data[off:off + size]
    info = Q.load(slot_qm(live, kind))
    txt = ''.join(t or '' for m in info['messages'] for t in m['translations'])
    heb = sum(1 for c in txt if 0x590 <= ord(c) <= 0x5FF)
    ar = sum(1 for c in txt if 0x600 <= ord(c) <= 0x6FF)
    print('exe        :', exe)
    print('slot       : %s @ %d, %d bytes (%s)' % (SLOT_LANG, off, size, kind))
    print('messages   :', len(info['messages']))
    print('hebrew ch  :', heb, ' arabic ch:', ar)
    if heb == 0:
        state = 'no (pristine Arabic slot)'
    elif heb < 5000:
        state = 'PARTIAL — a proof/partial build is in the slot'
    else:
        state = 'YES (Hebrew)'
    print('installed  :', state)
    print('backup     :', 'yes' if os.path.isfile(_meta_path()) else 'no')
    print('running    :', is_running())


def cmd_deploy(hebrew_json, layout_rtl=False):
    exe = find_exe()
    if is_running():
        raise SystemExit('SignalRGB is running — quit it from the tray first')
    data = open(exe, 'rb').read()
    off, size, kind = find_slot(data)
    pristine = ensure_backup(exe, data, off, size, kind=kind)
    hebrew = json.load(open(hebrew_json, encoding='utf-8'))
    # A compressed slot means the app version added strings we may not have -
    # drop those so Qt falls back to English, not Arabic.
    blob, n = build_hebrew_qm(pristine, hebrew, size, kind=kind,
                              layout_rtl=layout_rtl,
                              drop_untranslated=(kind != 'raw'))

    # exe string literals the .qm cannot reach (the language picker's own name)
    _, recs = apply_literals(data)
    if recs:
        json.dump(recs, open(_literal_meta_path(), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    extra = [(r['offset'],
              r['dst'].encode('utf-8') + b'\0' * (r['span'] - len(r['dst'].encode('utf-8'))))
             for r in recs]

    write_slot(exe, off, size, blob, extra=extra)
    # verify by reading the file back
    chk = open(exe, 'rb').read()[off:off + size]
    info = Q.load(slot_qm(chk, kind))
    heb = sum(1 for m in info['messages'] for t in m['translations']
              if t and any(0x590 <= ord(c) <= 0x5FF for c in t))
    print('deployed: %d strings replaced, %d hebrew messages verified in the exe'
          % (n, heb))
    for r in recs:
        print('  literal : %r -> %r @ %d (%d B slot)'
              % (r['src'], r['dst'], r['offset'], r['span']))
    print('activate : python patch_exe.py --lang ar   (then start SignalRGB)')


def cmd_revert():
    exe = find_exe()
    if is_running():
        raise SystemExit('SignalRGB is running — quit it from the tray first')
    blob_path = os.path.join(BACKUP_DIR, 'SignalRgb_%s.orig.qm' % SLOT_LANG)
    if not os.path.isfile(blob_path):
        raise SystemExit('no backup at %s' % blob_path)
    pristine = open(blob_path, 'rb').read()
    data = open(exe, 'rb').read()
    off, size, kind = find_slot(data)
    if len(pristine) != size:
        raise SystemExit('backup is %d bytes but the slot is %d — SignalRGB was '
                         'updated; reinstall to restore vanilla'
                         % (len(pristine), size))
    extra = []
    if os.path.isfile(_literal_meta_path()):
        for r in json.load(open(_literal_meta_path(), encoding='utf-8')):
            extra.append((r['offset'], bytes.fromhex(r['orig'])))
    write_slot(exe, off, size, pristine, extra=extra)
    print('reverted: pristine %s restored (byte-exact), %d literal(s) restored'
          % (SLOT_LANG, len(extra)))


def cmd_lang(code):
    """Set / clear the UI language in the registry (HKCU UI/Locale)."""
    import winreg
    path = 'Software' + chr(92) + 'WhirlwindFX' + chr(92) + 'SignalRgb' + chr(92) + 'UI'
    k = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS)
    if code in (None, '', 'clear'):
        try:
            winreg.DeleteValue(k, 'Locale')
            print('cleared UI/Locale (app falls back to the system language)')
        except FileNotFoundError:
            print('UI/Locale was not set')
    else:
        winreg.SetValueEx(k, 'Locale', 0, winreg.REG_SZ, code)
        print('UI/Locale =', code)


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] in ('--status', 'status'):
        cmd_status()
    elif a[0] in ('--deploy', 'deploy'):
        src = a[1] if len(a) > 1 else os.path.join(HERE, 'hebrew.json')
        cmd_deploy(src, layout_rtl='--rtl' in a)
    elif a[0] in ('--revert', 'revert'):
        cmd_revert()
    elif a[0] == '--lang':
        cmd_lang(a[1] if len(a) > 1 else 'clear')
    else:
        print(__doc__)
