"""SignalRGB Macros — the SECOND text surface, outside the .qm.

THE FINDING
    The Macros page is DATA-DRIVEN: every trigger ("input") and action lives
    in a loose JavaScript file under
        <app>\\Signal-x64\\Macroscripts\\{Inputs,Actions,...}\\*.js
    and declares its own user-visible text:

        export function Input() {
          this.Name = "Key Pressed";
          this.Description = "Triggers when the selected key is pressed.";
          this.Options = [
            {"property":"targetKeyCombo", "label":"Target Key", ...},
            {"property":"eatOrig", "label":"Discard Original Keypress", ...},
          ];
        }

    None of it goes through qsTr(), so NONE of it is in the shipped .qm —
    a 100%-translated .qm still leaves the whole Macros page in English.
    (Proof: "Create Macro"/"Discard Original Keypress" do not occur in the
    exe at all, compressed or not; they occur only in these .js files.)

WHY THIS IS SAFE
    These are loose, uncompressed, unsigned UTF-8 files that the app reads at
    runtime.  We patch ONLY string VALUES of known metadata keys, never a
    property name, never code.  Every patch is anchored STRUCTURALLY (the
    regex match span of a specific key) — never by free-text search, because
    a label can equal a word that also appears in the script's logic.

    A pristine copy of every touched file is kept in hebrew_backup/macroscripts
    and the patch is always built FROM that copy -> idempotent, and a
    SignalRGB update (which replaces the folder) is handled by re-running
    deploy, which re-takes the backup from the new vanilla files.

UNTRANSLATABLE BY DESIGN — the `values` of a combobox
    Every dropdown choice is a LOOKUP KEY that the script's own code compares
    against, e.g.

        this.actions = { "Toggle": ..., "Enable": ..., "Disable": ... }
        "values": Object.keys(this.actions)      <- built FROM the code
        this.actions[this.TargetMode]()          <- and indexed BY the choice

        if (this.terminalType === "Windows Terminal") ...
        if (this.TargetMode === "Set") ...

    and "Target Page" ships internal page ids (dashboard/customize/devices...).
    Translating any of them yields `this.actions["החלף"]` = undefined and the
    macro dies at runtime.  So `patch()` rewrites Name/Description/label ONLY.
    This is the same class as Borderless Gaming's C# enum dropdowns.
"""
import os
import re

# `this.Name = "..."` / `this.Description = "..."`
RE_PROP = re.compile(r'(this\.(?:Name|Description)\s*=\s*")((?:[^"\\]|\\.)*)(")')
# `"label":"..."` inside an Options entry
RE_LABEL = re.compile(r'("label"\s*:\s*")((?:[^"\\]|\\.)*)(")')
# `"values":["a","b"]` — the dropdown choices shown to the user
RE_VALUES = re.compile(r'"values"\s*:\s*\[([^\]]*)\]')
RE_STR = re.compile(r'"((?:[^"\\]|\\.)*)"')


def script_files(root):
    out = []
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if fn.lower().endswith('.js'):
                out.append(os.path.join(dp, fn))
    return sorted(out)


def extract(text):
    """-> list of (kind, value) in file order, the exact user-visible strings.

    Values are UNESCAPED, so a key is the logical string the user reads
    (`C:\\Games`, not the source's `C:\\\\Games`); patch() re-escapes.
    """
    out = []
    for m in RE_PROP.finditer(text):
        out.append(('prop', _unesc(m.group(2))))
    for m in RE_LABEL.finditer(text):
        out.append(('label', _unesc(m.group(2))))
    for m in RE_VALUES.finditer(text):
        for s in RE_STR.findall(m.group(1)):
            out.append(('value', _unesc(s)))
    return out


def patch(text, mapping):
    """Replace every metadata string that has an entry in `mapping`.

    Anchored on the regex span of the metadata key, so a value is only ever
    rewritten where it is genuinely a label/name/choice — never where the same
    word appears in the script's own logic.
    """
    n = [0]

    def sub_group2(m):
        # look up the UNESCAPED text — extract() hands out logical strings, so
        # a value containing an escape (`C:\\Games`) must be unescaped here or
        # it silently never matches its translation.
        he = mapping.get(_unesc(m.group(2)))
        if not he:
            return m.group(0)
        n[0] += 1
        return m.group(1) + _esc(he) + m.group(3)

    text = RE_PROP.sub(sub_group2, text)
    text = RE_LABEL.sub(sub_group2, text)
    # NOTE: `values` is deliberately NOT patched — see UNTRANSLATABLE below.
    return text, n[0]


def patch_labels_only(text, mapping):
    """Same as patch() but touches ONLY `"label"` — for the DEVICE plugins.

    A device plugin's `this.Name` is the PRODUCT name ("Corsair K95") and must
    stay Latin, so the Name/Description rewrite must not run there.
    """
    n = [0]

    def sub(m):
        he = mapping.get(_unesc(m.group(2)))
        if not he:
            return m.group(0)
        n[0] += 1
        return m.group(1) + _esc(he) + m.group(3)

    return RE_LABEL.sub(sub, text), n[0]


def _esc(s):
    return (s.replace('\\', '\\\\').replace('"', '\\"')
             .replace('\n', '\\n').replace('\t', '\\t'))


def _unesc(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            nxt = s[i + 1]
            out.append({'n': '\n', 't': '\t', 'r': '\r'}.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


if __name__ == '__main__':
    import sys, json, collections
    sys.stdout.reconfigure(encoding='utf-8')
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.environ['LOCALAPPDATA'], 'VortxEngine', 'app-2.5.74',
        'Signal-x64', 'Macroscripts')
    files = script_files(root)
    kinds = collections.Counter()
    uniq = {}
    for fp in files:
        for kind, val in extract(open(fp, encoding='utf-8').read()):
            kinds[kind] += 1
            uniq.setdefault(val, kind)
    print('files:', len(files), '| occurrences:', dict(kinds),
          '| unique:', len(uniq))
    for v, k in sorted(uniq.items(), key=lambda x: (x[1], x[0].lower())):
        print('  [%-5s] %s' % (k, v))
