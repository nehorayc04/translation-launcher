#!/bin/bash
# Pull the "missing lines" run from laptop/vm4/vm5 and merge into hebrew_missing.json.
#
# Validate-before-replace at every hop: a hard-killed worker leaves a NUL-filled out.json,
# and a straight scp would propagate that over good work (CLAUDE.md silent-failure class #6).
set -u
KEY=~/.ssh/id_ed25519
H=10.0.0.49   # (per-call host now passed explicitly)
FLEET="$(cd "$(dirname "$0")" && pwd)"
BANKS="$FLEET/banks_missing"; mkdir -p "$BANKS"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=45 -o ServerAliveInterval=10"

pull() { # $1 label  $2 host  $3 port  $4 user
  for prov in groq sambanova nim; do
    local dest="$BANKS/out_$1_$prov.json" tmp
    tmp="$dest.tmp"; rm -f "$tmp"
    timeout 90 scp $SSHO -P "$3" "$4@$2:C:/rdrw/out_$prov.json" "$tmp" 2>/dev/null
    if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$dest"
    else
      rm -f "$tmp"
    fi
  done
}

# the desktop is local -- copy, don't scp
for prov in groq sambanova nim; do
  src="/c/rdrwd/out_$prov.json"; dest="$BANKS/out_desktop_$prov.json"
  if [ -s "$src" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$src" 2>/dev/null; then
    cp -f "$src" "$dest"
  fi
done

pull laptop 10.0.0.49 22   Nehoray_Cohen &
pull vm4    10.0.0.49 2225 vboxuser &
pull vm5    10.0.0.49 2226 vboxuser &
pull vm     127.0.0.1 2222 vboxuser &
pull vm2    127.0.0.1 2223 vboxuser &
pull vm3    127.0.0.1 2224 vboxuser &
wait

"$PY" - "$FLEET" <<'PY'
import glob, json, os, sys
fleet = sys.argv[1]
merged = {}
for f in sorted(glob.glob(os.path.join(fleet, "banks_missing", "out_*.json"))):
    try:
        merged.update(json.load(open(f, encoding="utf-8")))
    except Exception:
        pass
# canonical names at MERGE time, so a glossary correction fixes the whole corpus
# without re-translating a single line
reg = os.path.join(fleet, "name_fixes.json")
if os.path.exists(reg):
    # 🔴🔴 THIS WAS A SILENT NO-OP FOR THE WHOLE RUN. The code iterated `fixes.items()`, i.e.
    # it expected a FLAT {wrong: right} dict — but the file on disk is
    # {"_doc": [...], "pairs": [[wrong, right], ...]}, so the only two "pairs" it ever tried
    # were the literal strings "_doc" and "pairs", and not one of the 49 real corrections was
    # ever applied. Nothing errors, nothing logs, and the corpus simply keeps every variant
    # spelling. Accept BOTH shapes, and apply LONGEST-FIRST as the file's own doc requires
    # (so `או'דריסקולס` is normalised before the shorter `או'דריסקול` can eat its prefix).
    # UNIVERSAL: when a data file and its reader disagree about shape, the reader usually
    # fails OPEN — verify a transform by COUNTING its effect, never by reading the code.
    _raw = json.load(open(reg, encoding="utf-8"))
    if isinstance(_raw, dict) and isinstance(_raw.get("pairs"), list):
        _fixes = [(str(a), str(b)) for a, b in _raw["pairs"] if a and b]
    else:
        _fixes = [(k, v) for k, v in _raw.items()
                  if isinstance(v, str) and not str(k).startswith("_")]
    _fixes.sort(key=lambda kv: -len(kv[0]))
    _canon = 0
    for k, v in list(merged.items()):
        v0 = v
        for bad, good in _fixes:
            if bad in v:
                v = v.replace(bad, good)
        if v != v0:
            _canon += 1
        merged[k] = v
    if _canon:
        print(f"name-canon applied to {_canon} lines ({len(_fixes)} pairs)")
# DETERMINISTIC FILLS — one right answer, decided by the game's OWN localizations, so they
# never need an API call and can never be parked. English ordinal suffixes (1st / 2nd / 13th)
# have no Hebrew equivalent: a Hebrew date is "1 בינואר", bare. The game's own Russian agrees
# (1st->"1", 6th->"6"), and so do fr/po/sp modulo their own punctuation. Applied at MERGE like
# canon(), so the answer survives every re-pull without a worker ever seeing the line.
import re
_ORD = re.compile(r"^(\d+)(?:st|nd|rd|th)$", re.I)
corpus = json.load(open(os.path.join(fleet, "corpus_missing.json"), encoding="utf-8"))
_det = 0
for k, v in corpus.items():
    en = (v.get("en", "") if isinstance(v, dict) else str(v or "")).strip()
    m = _ORD.match(en)
    if m and merged.get(k, "") != m.group(1):
        merged[k] = m.group(1)
        _det += 1
if _det:
    print(f"deterministic fills applied: {_det}")

out = os.path.join(fleet, "hebrew_missing.json")
tmp = out + ".tmp"
json.dump(merged, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, out)
total = len(json.load(open(os.path.join(fleet, "corpus_missing.json"), encoding="utf-8")))
print(f"merged {len(merged):,} / {total:,}  ({100.0*len(merged)/max(total,1):.1f}%)")
PY

# 🔴 THE MERGE REBUILDS hebrew_missing.json FROM THE BANKS, so anything written straight into
# it is silently reverted on the next pull. The name-canon above survives because it runs
# INSIDE the merge; the ENGLISH-GUARDED fixes (which need the corpus to check the source line)
# must therefore be re-applied right after it, every time — not once by hand.
"$PY" "$FLEET/fix_names_guarded.py" --apply 2>/dev/null | tail -1
"$PY" "$FLEET/fix_imperative_number.py" --apply 2>/dev/null | tail -1
"$PY" "$FLEET/fix_moonshine_term.py"    --apply 2>/dev/null | grep -E "lines to fix|applied" | head -2
"$PY" "$FLEET/apply_lqa_overrides.py"   2>/dev/null | tail -1
