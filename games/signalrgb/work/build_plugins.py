"""Deploy / revert the Hebrew DEVICE-PLUGIN labels — the fourth text surface.

    python build_plugins.py            # report coverage, write nothing
    python build_plugins.py --deploy
    python build_plugins.py --revert

WHAT THIS IS
    Every supported device ships a `.js` plugin that declares its own settings
    UI as `ControllableParameters`:

        {"property":"dpi1", "group":"dpi", "label":"DPI 1", "type":"number", ...}

    Those `label`s are what the per-device Settings page renders, and — like the
    Macroscripts — they never pass through qsTr(), so no .qm can reach them.
    132 unique labels cover all 444 shipped plugins.

TWO RULES CARRIED OVER FROM THE MACROS SURFACE
    * `values` is NEVER touched (a combobox choice is the code's lookup key).
    * `this.Name` / `this.Description` is NEVER touched here — for a device
      plugin that is the PRODUCT name ("Corsair K95"), which stays Latin.
      Hence `patch_labels_only`, not `patch`.
    * `group` is NOT touched either: the four values (dpi/lighting/mouse/
      settings) are lowercase ids that the app maps through its OWN .qm
      (`ThirdpartySettings|lighting` -> תאורה), so they are already translated.

⚠️ PLUGINS ARE UPDATED FROM THE CDN
    The live set is the union of the install folder and the downloaded cache
    (`…\\WhirlwindFX\\SignalRgb\\cache\\plugin_cdn`).  Both are patched, but a
    plugin refresh from the server restores English for the refreshed files —
    re-run --deploy after one.  (The Macroscripts do not have this problem.)
"""
import os
import sys
import json
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import macro_scripts as MS
import patch_exe as PX

BACKUP = os.path.join(PX.BACKUP_DIR, 'plugins')
HE_JSON = os.path.join(HERE, 'plugins_he.json')

# Labels that stay Latin on purpose: bare technical identifiers whose Hebrew
# would be less clear than the acronym everyone already reads on the box.
KEEP_LATIN = {'DPI', 'DPI 1', 'DPI 2', 'DPI 3', 'DPI 4', 'DPI 5', 'DPI 6',
              'DPI 7', 'Smart-Reel'}


def roots():
    out = []
    inst = os.path.join(os.path.dirname(PX.find_exe()), 'Plugins')
    if os.path.isdir(inst):
        out.append(('install', inst))
    cdn = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'WhirlwindFX',
                       'SignalRgb', 'cache', 'plugin_cdn')
    if os.path.isdir(cdn):
        out.append(('cdn', cdn))
    return out


def sync_backup(tag, root, hebrew_values):
    """Capture vanilla copies; return {relpath: pristine text}."""
    store = os.path.join(BACKUP, tag)
    os.makedirs(store, exist_ok=True)
    out = {}
    for fp in MS.script_files(root):
        rel = os.path.relpath(fp, root)
        dst = os.path.join(store, rel)
        live = open(fp, encoding='utf-8', errors='replace').read()
        if not any(v in live for v in hebrew_values):      # vanilla -> capture
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(fp, dst)
        if os.path.isfile(dst):
            out[rel] = open(dst, encoding='utf-8', errors='replace').read()
    return out


def report(pristine, he):
    seen, missing = set(), set()
    for text in pristine.values():
        for kind, val in MS.extract(text):
            if kind != 'label':
                continue
            seen.add(val)
            if val not in he and val not in KEEP_LATIN:
                missing.add(val)
    print('  labels found : %d unique' % len(seen))
    print('  translated   : %d' % len(seen - missing - KEEP_LATIN))
    print('  kept Latin   : %d' % len(seen & KEEP_LATIN))
    if missing:
        print('  MISSING %d:' % len(missing))
        for m in sorted(missing):
            print('     ', m)
    return not missing


def cmd_deploy():
    if PX.is_running():
        print('note: SignalRGB is running — plugins are re-read at startup, '
              'so restart it to see the change.')
    he = json.load(open(HE_JSON, encoding='utf-8'))
    hv = set(he.values())
    ok = True
    for tag, root in roots():
        print('[%s] %s' % (tag, root))
        pristine = sync_backup(tag, root, hv)
        ok = report(pristine, he) and ok
        if not ok:
            continue
        total = 0
        for rel, text in pristine.items():
            new, n = MS.patch_labels_only(text, he)
            if n:
                open(os.path.join(root, rel), 'w', encoding='utf-8',
                     newline='').write(new)
                total += n
        print('  patched      : %d labels in %d files' % (total, len(pristine)))
        verify(root, he)
    if not ok:
        raise SystemExit('untranslated labels above — nothing was written for '
                         'that root')


def verify(root, he):
    heb = bad = 0
    for fp in MS.script_files(root):
        for kind, val in MS.extract(open(fp, encoding='utf-8',
                                         errors='replace').read()):
            if kind != 'label':
                continue
            if any('֐' <= c <= '׿' for c in val):
                heb += 1
            elif val in he:
                bad += 1
                print('     NOT patched:', os.path.relpath(fp, root), '|', val)
    print('  verify       : %d Hebrew labels on disk, %d unpatched' % (heb, bad))


def cmd_revert():
    n = 0
    for tag, root in roots():
        store = os.path.join(BACKUP, tag)
        if not os.path.isdir(store):
            continue
        for dp, _, fns in os.walk(store):
            for fn in fns:
                src = os.path.join(dp, fn)
                dst = os.path.join(root, os.path.relpath(src, store))
                if os.path.isfile(dst):
                    shutil.copy2(src, dst)
                    n += 1
    print('reverted: %d plugin files restored (byte-exact)' % n)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if a and a[0] in ('--deploy', 'deploy'):
        cmd_deploy()
    elif a and a[0] in ('--revert', 'revert'):
        cmd_revert()
    else:
        he = json.load(open(HE_JSON, encoding='utf-8'))
        hv = set(he.values())
        for tag, root in roots():
            print('[%s] %s' % (tag, root))
            report(sync_backup(tag, root, hv), he)
