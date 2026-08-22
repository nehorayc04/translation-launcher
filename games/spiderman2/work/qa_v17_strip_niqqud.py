"""qa_v17_strip_niqqud.py — remove forbidden Hebrew niqqud/cantillation from every
*_he.json value (project hard-rule: NO niqqud). Deterministic + idempotent.

Strips ONLY nonspacing marks (Unicode category 'Mn') in the Hebrew block
U+0591..U+05C7 — i.e. vowel points + cantillation. Keeps real letters and
keeps punctuation like maqaf U+05BE (־), sof-pasuq, geresh/gershayim.

Backs up each changed file to <name>.bak.niqqud before writing.
"""
import os, sys, json, glob, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def is_niqqud(ch):
    return 0x0591 <= ord(ch) <= 0x05C7 and unicodedata.category(ch) == 'Mn'

def strip(s):
    return ''.join(c for c in s if not is_niqqud(c))

def main():
    files = sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]
    total = 0
    for fn in files:
        d = json.load(open(fn, encoding="utf-8"))
        changed = {}
        for k, v in d.items():
            if isinstance(v, str):
                nv = strip(v)
                if nv != v:
                    changed[k] = (v, nv); d[k] = nv
        if changed:
            import shutil
            shutil.copyfile(fn, fn + ".bak.niqqud")
            json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            total += len(changed)
            print(f"[{fn}] stripped niqqud in {len(changed)} values")
            for k, (o, n) in list(changed.items())[:8]:
                print(f"   {k}")
    print(f"TOTAL niqqud-stripped values: {total}")

if __name__ == "__main__":
    main()
