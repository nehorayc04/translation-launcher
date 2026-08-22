"""Deploy / revert the Hebrew Macros translation (the loose Macroscripts .js).

    python build_macros.py            # report coverage, write nothing
    python build_macros.py --deploy
    python build_macros.py --revert

The patch is ALWAYS built from the pristine backup, never from what is on
disk, so a re-run can never translate an already-Hebrew string twice or
inherit a previous build.  After a SignalRGB update the app folder is new:
the backup is re-taken from the new vanilla files and the patch re-applied.
"""
import os
import sys
import json
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import macro_scripts as MS
import patch_exe as PX

BACKUP = os.path.join(PX.BACKUP_DIR, 'macroscripts')
HE_JSON = os.path.join(HERE, 'macros_he.json')

# Labels that stay Latin on purpose (identifiers / universally-known tokens).
KEEP_LATIN = {'URL'}


def macro_root():
    env = os.environ.get('SIGNALRGB_MACROSCRIPTS')
    if env:
        return env
    return os.path.join(os.path.dirname(PX.find_exe()), 'Macroscripts')


def _rel(root, fp):
    return os.path.relpath(fp, root).replace('\\', '/')


def sync_backup(root):
    """Copy every vanilla .js into the backup store; return {rel: pristine text}.

    A file is (re-)captured when it is absent from the store or when the live
    copy is NOT one of ours (i.e. the app was updated / reinstalled).
    """
    os.makedirs(BACKUP, exist_ok=True)
    he = json.load(open(HE_JSON, encoding='utf-8'))
    hebrew_values = set(he.values())
    out = {}
    for fp in MS.script_files(root):
        rel = _rel(root, fp)
        dst = os.path.join(BACKUP, rel.replace('/', os.sep))
        live = open(fp, encoding='utf-8').read()
        live_is_ours = any(v in live for v in hebrew_values)
        if not os.path.isfile(dst) or not live_is_ours:
            if not live_is_ours:                      # only ever store vanilla
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(fp, dst)
        if not os.path.isfile(dst):
            raise SystemExit('%s is already patched but has no backup — '
                             'reinstall SignalRGB, then re-run --deploy' % rel)
        out[rel] = open(dst, encoding='utf-8').read()
    return out


def report(root, pristine, he):
    seen, missing = set(), []
    values = set()
    for text in pristine.values():
        for kind, val in MS.extract(text):
            if kind == 'value':
                values.add(val)
                continue
            seen.add(val)
            if val not in he and val not in KEEP_LATIN:
                missing.append(val)
    print('files            :', len(pristine))
    print('translatable     :', len(seen), '(Name / Description / label)')
    print('translated       :', len(seen) - len(set(missing)) - len(KEEP_LATIN & seen))
    print('kept Latin       :', sorted(KEEP_LATIN & seen))
    print('combobox values  :', len(values), '(NEVER translated — code keys)')
    if missing:
        print('MISSING %d:' % len(set(missing)))
        for m in sorted(set(missing)):
            print('   ', m)
    return not missing


def cmd_deploy():
    root = macro_root()
    if PX.is_running():
        raise SystemExit('SignalRGB is running — quit it from the tray first')
    pristine = sync_backup(root)
    he = json.load(open(HE_JSON, encoding='utf-8'))
    # A SignalRGB update can ADD macro strings we have not translated yet.
    # Deploy the translated subset anyway — MS.patch only touches strings that
    # ARE in `he`, so the new ones stay English (graceful degradation, exactly
    # like the .qm and plugin surfaces).  '--strict' re-imposes the old refuse.
    if not report(root, pristine, he) and '--strict' in sys.argv:
        raise SystemExit('refusing to deploy with untranslated strings (--strict)')
    total = 0
    for rel, text in pristine.items():
        new, n = MS.patch(text, he)
        total += n
        if n:
            open(os.path.join(root, rel.replace('/', os.sep)), 'w',
                 encoding='utf-8', newline='').write(new)
    print('deployed: %d strings patched across %d files' % (total, len(pristine)))
    verify(root, he)


def verify(root, he):
    """Re-read from disk: the file must parse and hold the Hebrew we wrote."""
    bad = 0
    heb = 0
    for fp in MS.script_files(root):
        text = open(fp, encoding='utf-8').read()
        for kind, val in MS.extract(text):
            if kind == 'value':
                continue
            if any('֐' <= c <= '׿' for c in val):
                heb += 1
            elif val in he:
                bad += 1
                print('  NOT patched:', _rel(root, fp), '|', val)
    print('verify   : %d Hebrew metadata strings on disk, %d unpatched' % (heb, bad))


def cmd_revert():
    root = macro_root()
    if PX.is_running():
        raise SystemExit('SignalRGB is running — quit it from the tray first')
    if not os.path.isdir(BACKUP):
        raise SystemExit('no backup at %s' % BACKUP)
    n = 0
    for dp, _, fns in os.walk(BACKUP):
        for fn in fns:
            src = os.path.join(dp, fn)
            rel = os.path.relpath(src, BACKUP)
            dst = os.path.join(root, rel)
            if os.path.isfile(dst):
                shutil.copy2(src, dst)
                n += 1
    print('reverted: %d Macroscripts restored (byte-exact)' % n)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if a and a[0] in ('--deploy', 'deploy'):
        cmd_deploy()
    elif a and a[0] in ('--revert', 'revert'):
        cmd_revert()
    else:
        r = macro_root()
        report(r, sync_backup(r), json.load(open(HE_JSON, encoding='utf-8')))
