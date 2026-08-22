#!/bin/bash
# Extract + serialize the game's RU/ES/FR/IT localization CR2W -> flat json trees, for the
# multilingual gender oracle. ar is handled separately (pristine CR2W already on disk). One
# WolvenKit call per lang to extract, one to serialize. Sequential (disk-friendly). Logs progress.
set -u
CLI="/c/Users/Nehoray_Cohen/AppData/Local/Programs/WolvenKit-CLI/WolvenKit.CLI.exe"
GAME="/c/Game Lab/Cyberpunk 2077/archive/pc/content"
OUT=/c/tmp/cpqa_lang
LOG=$OUT/extract_langs.log
mkdir -p "$OUT"
echo "=== extract_langs start $(date '+%F %T') ===" >> "$LOG"

# lang -> archive name  (ar = the GAME's Arabic, NOT the project ar-ar bake tree = our Hebrew!)
declare -A ARCH=( [ar]="lang_ar_text.archive" [ru]="lang_ru_text.archive" [es]="lang_es-es_text.archive" [fr]="lang_fr_text.archive" [it]="lang_it_text.archive" )

for L in ar ru es fr it; do
  a="$GAME/${ARCH[$L]}"
  ex="$OUT/${L}_cr2w"; sr="$OUT/$L"
  if [ ! -f "$a" ]; then echo "$(date '+%T')  $L MISSING archive" >> "$LOG"; continue; fi
  echo "$(date '+%T')  $L extract ..." >> "$LOG"
  rm -rf "$ex" "$sr"; mkdir -p "$ex" "$sr"
  "$CLI" extract "$a" -o "$ex" -w "*localization*" >> "$LOG" 2>&1
  n=$(find "$ex" -name "*.json" | wc -l)
  echo "$(date '+%T')  $L extracted $n CR2W -> serialize ..." >> "$LOG"
  # serialize the whole extracted localization tree (flat output)
  src=$(find "$ex" -type d -iname "$L" | head -1)
  [ -z "$src" ] && src="$ex"
  "$CLI" convert serialize "$src" -o "$sr" >> "$LOG" 2>&1
  m=$(find "$sr" -name "*.json" | wc -l)
  echo "$(date '+%T')  $L done: $m serialized json" >> "$LOG"
done
echo "=== extract_langs done $(date '+%F %T') ===" >> "$LOG"
