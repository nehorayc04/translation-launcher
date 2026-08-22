#!/bin/bash
# finalize.sh — the end-of-run sequence for the 28,101-line "missing lines" run, in order.
#
#   1. pull        — bank whatever the fleet has produced since the last tick
#   2. qa --apply  — structural re-check + terminology unification against the 217k lines
#                    already shipping in-game (the authority is the SHIPPED corpus, not a
#                    vote among 21 fresh streams)
#   3. build       — merge into the 217k spine, UBA logical->visual, LML override, DEPLOY
#   4. verify      — read the ARTIFACT back: entry count, font size, the four fixed keys
#
# Deliberately NOT automatic: step 2 deletes re-queued lines from the bank, so it runs once,
# at the end, when the fleet is drained — not on the 30-minute refresh loop.
set -u
REPO="/c/Users/Nehoray_Cohen/Projects/Game translator"
PY313="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
VENV="$REPO/.venv/Scripts/python.exe"     # build_full needs python-bidi; the base python fails
GAME="/c/Program Files (x86)/Steam/steamapps/common/Red Dead Redemption 2"
FLEET="$(cd "$(dirname "$0")" && pwd)"

echo "=== 1/4  pull ==="
bash "$FLEET/pull_missing.sh" | tail -3

echo; echo "=== 2a/4  purge word-by-word damage ==="
# A too-small model leaves Hebrew prefixes as separate words (`מ ה מפורסם אוניקס זאב`). It
# passes every structural guard, so it must be caught linguistically. At this point the fleet
# is drained, so a purged line falls back to ENGLISH — which is the right trade: readable
# English beats unreadable Hebrew.
"$PY313" "$FLEET/purge_wordbyword.py" --apply

echo; echo "=== 2/4  QA gate ==="
"$PY313" "$FLEET/qa_missing.py" --apply

echo; echo "=== 3/4  build + deploy ==="
"$VENV" "$REPO/games/rdr2/work/build_full.py" --deploy | tail -6

echo; echo "=== 4/4  verify the ARTIFACT ==="
gxt2="$GAME/lml/tranar/Ko Games Studio.gxt2"
gfx="$GAME/lml/KGF/asset_replace/font_lib_efigs.gfx"
printf "gxt2 %s bytes · %s keys\n" "$(stat -c%s "$gxt2")" "$(grep -c ' = ' "$gxt2")"
# ⚠️ Compare against the BUILT artifact, never a magic number: the per-face Hebrew rescale
# changed the font's size (3,341,174 -> 3,342,581) and a hardcoded constant would have reported
# the correct new font as "not the stencil build" on every run from here on.
built="$REPO/games/rdr2/work/_fontinspect/font_lib_efigs_rescaled.gfx"
if [ -f "$built" ]; then
  if [ "$(md5sum < "$gfx")" = "$(md5sum < "$built")" ]; then
    echo "font OK — byte-identical to the rescaled build ($(stat -c%s "$gfx"))"
  else
    echo "!! FONT DIFFERS from $built — re-copy it (a text --deploy reverts it)"
  fi
else
  echo "font: $(stat -c%s "$gfx") bytes (no built artifact to compare against)"
fi
echo "clock  : $(grep -m1 '^TIME_AND_TEMP_C ' "$gxt2")"
echo "AM/PM  : $(grep -m1 '^AM = ' "$gxt2") | $(grep -m1 '^PM = ' "$gxt2")"
for k in LEGAL_SPLASH_1 LEGAL_SPLASH_2; do
  echo "$k: $(grep -m1 "^$k " "$gxt2" | cut -c1-90)"
done
"$PY313" - "$FLEET" <<'PY'
import json, os, sys
f = sys.argv[1]
c = json.load(open(os.path.join(f, "corpus_missing.json"), encoding="utf-8"))
h = json.load(open(os.path.join(f, "hebrew_missing.json"), encoding="utf-8"))
print(f"missing-lines run: {len(h):,} / {len(c):,}  ({100.0*len(h)/len(c):.1f}%)")
PY
