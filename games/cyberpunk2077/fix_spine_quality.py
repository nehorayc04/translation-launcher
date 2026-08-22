"""Deterministic quality sweep over the (english-leak-reverted) spine:
  1. mid-word FINAL letter (sofit ך ם ן ף ץ followed by a Hebrew letter) -> regular form.
  2. niqqud (vowel points) -> strip.
  3. report any remaining foreign-script (non-Hebrew/Latin) entries (not auto-fixed).
Applies to femaleVariant + maleVariant of localization_translated.json + dlc_ep1_translated.json
(backs up first). Run with --apply."""
import json, os, re, sys, time, shutil
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
FILES = [os.path.join(RES, "localization_translated.json"), os.path.join(RES, "dlc_ep1_translated.json")]
SOFIT = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'}
MID = re.compile(r'[ךםןףץ](?=[א-ת])')
NIQ = re.compile(r'[֑-ׇֽֿׁׂׅׄ]')
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿเ-๙]')
def fix(v):
    n = MID.sub(lambda x: SOFIT[x.group()], v or "")
    n = NIQ.sub("", n)
    return n
dry = "--apply" not in sys.argv
tot_sofit = tot_niq = tot_foreign = touched = 0
for path in FILES:
    d = json.load(open(path, encoding="utf-8")); changed = False
    for sec, rows in d.items():
        if not isinstance(rows, list): continue
        for e in rows:
            if not isinstance(e, dict): continue
            for fld in ("femaleVariant", "maleVariant"):
                v = e.get(fld)
                if not v: continue
                if MID.search(v): tot_sofit += 1
                if NIQ.search(v): tot_niq += 1
                if FOREIGN.search(v): tot_foreign += 1
                nv = fix(v)
                if nv != v:
                    touched += 1
                    if not dry: e[fld] = nv; changed = True
    if not dry and changed:
        ts = time.strftime("%Y%m%d_%H%M%S"); shutil.copy2(path, path + f".bak.qual.{ts}")
        tmp = path + ".tmp"; json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, path)
print(f"mid-word sofit fields: {tot_sofit} | niqqud fields: {tot_niq} | foreign-script fields (NOT auto-fixed): {tot_foreign}")
print(f"fields changed: {touched}")
print("DRY RUN (add --apply)" if dry else "APPLIED + backed up (.bak.qual.*)")
