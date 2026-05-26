"""
filter_existing_flags.py
========================
Retroactively cleans `cross_audit_flags.json` (JSONL — one record per line)
by applying the same rejection rules that the hardened
`continuous_audit_loop.py` now applies at flag-time:

  1. Forbidden script chars  (Arabic / Cyrillic / CJK / Hangul / Thai / ...)
  2. Emoji / pictograph symbols
  3. Mixed-script words      (Hebrew letters welded to Latin in one token)

Each flag's `critic_feedback` field is the inspection target. Anything that
trips a rejection rule is dropped; clean flags are kept verbatim.

Safety:
  * The original file is backed up to `cross_audit_flags.json.bak.<ts>`
    BEFORE anything is overwritten.
  * The new file is written atomically (.tmp + os.replace).
  * Source translation JSONs are never touched.

Run:
  python filter_existing_flags.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FLAGS_FILE = os.path.join(HERE, "cross_audit_flags.json")


# ── filter logic (duplicated from continuous_audit_loop.py for independence;
#    no need to import the OpenAI SDK just to run a sweep) ──────────────────
FORBIDDEN_SCRIPT_RE = re.compile(
    "["
    "؀-ۿ"    # Arabic
    "ݐ-ݿ"    # Arabic Supplement
    "ﭐ-﷿"    # Arabic Presentation Forms-A
    "ﹰ-﻿"    # Arabic Presentation Forms-B
    "Ѐ-ӿ"    # Cyrillic
    "Ԁ-ԯ"    # Cyrillic Supplement
    "一-鿿"    # CJK Unified Ideographs
    "　-〿"    # CJK Symbols & Punctuation
    "぀-ゟ"    # Hiragana
    "゠-ヿ"    # Katakana
    "฀-๿"    # Thai
    "가-힯"    # Hangul
    "ऀ-ॿ"    # Devanagari
    "Ͱ-Ͽ"    # Greek
    "԰-֏"    # Armenian
    "]"
)

EMOJI_AND_SYMBOL_RE = re.compile(
    "[☀-⛿"
    "✀-➿"
    "\U0001F300-\U0001FAFF]"
)

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _find_mixed_script_word(text: str) -> str | None:
    for m in _WORD_RE.finditer(text or ""):
        word = m.group(0)
        has_he = any("֐" <= c <= "׿" for c in word)
        has_la = any(c.isascii() and c.isalpha() for c in word)
        if has_he and has_la:
            return word
    return None


def _reason_to_reject(text: str) -> str | None:
    """Returns short rejection label (just the category), or None if clean."""
    text = text or ""
    if FORBIDDEN_SCRIPT_RE.search(text):
        return "ForbiddenScript"
    if EMOJI_AND_SYMBOL_RE.search(text):
        return "EmojiSymbol"
    if _find_mixed_script_word(text):
        return "MixedWord"
    return None


# ── main ────────────────────────────────────────────────────────────────────
def main() -> int:
    if not os.path.exists(FLAGS_FILE):
        print(f"[!] {FLAGS_FILE} not found — nothing to do.", file=sys.stderr)
        return 0

    # Backup first — never overwrite the user's flag data without a copy.
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = FLAGS_FILE + f".bak.{ts}"
    shutil.copy2(FLAGS_FILE, backup)
    print(f"[*] backup -> {os.path.basename(backup)}")

    kept: list[dict] = []
    rejected = Counter()
    parse_errors = 0
    total_input = 0

    with open(FLAGS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_input += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            reason = _reason_to_reject(rec.get("critic_feedback", ""))
            if reason is None:
                kept.append(rec)
            else:
                rejected[reason] += 1

    # Atomic write back.
    tmp = FLAGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for rec in kept:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, FLAGS_FILE)

    # Report.
    rejected_total = sum(rejected.values())
    pct_kept = (len(kept) / total_input * 100) if total_input else 0.0
    print()
    print(f"[*] input flags    : {total_input:,}")
    print(f"[*] kept (clean)   : {len(kept):,}  ({pct_kept:.1f}%)")
    print(f"[*] rejected total : {rejected_total:,}")
    for reason, n in rejected.most_common():
        print(f"      {reason:18s} {n:,}")
    if parse_errors:
        print(f"[*] parse errors (lines skipped): {parse_errors}")
    print(f"[*] backup file    : {os.path.basename(backup)}")
    print(f"[*] flags file     : {os.path.basename(FLAGS_FILE)} (cleaned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
