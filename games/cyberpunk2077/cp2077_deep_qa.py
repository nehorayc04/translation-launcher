"""
cp2077_deep_qa.py — Deep QA + Salvage pass
==========================================

Phase 1: Fix entries with broken tags ({int_0}, {DAYS}, </>, %s, etc.)
         Re-translate single-mode, 3 retries. If still broken → revert to English.

Phase 2: Deep salvage of translation_skips.json — try each skipped entry one by
         one through LM Studio. Successful translations are written back into
         localization_translated.json AND removed from the skip list.

Safe to Ctrl+C and restart at any time. Atomic save every 50 successful fixes.
Designed for unattended overnight runs (~9h).

Requires LM Studio on http://127.0.0.1:1234 with a Hebrew-capable model loaded.
"""

import json
import os
import re
import sys
import time
from openai import OpenAI

# Force UTF-8 output (Hebrew samples in logs)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ── Config ────────────────────────────────────────────────────────────────────
BASE = r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים\source\resources"
ORIGINAL_FILE = os.path.join(BASE, "localization_export.json")
TRANSLATED_FILE = os.path.join(BASE, "localization_translated.json")
SKIP_FILE = os.path.join(BASE, "translation_skips.json")

ALLOWED_FOLDERS = ["onscreens", "subtitles"]
FIELDS = ("femaleVariant", "maleVariant")
SAVE_EVERY = 50
PHASE1_RETRIES = 3
PHASE2_RETRIES = 3

client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")


# Standard prompt (Phase 2 — full creative translation)
SYSTEM_PROMPT = (
    "Translate the user's English text to Hebrew. Output the Hebrew translation only.\n"
    "No explanations, no notes, no markdown, no quotes, no prefix like 'Translation:'.\n"
    "No <think> tags. No reasoning. Just the Hebrew text on a single line.\n"
    "CRITICAL: USE ONLY HEBREW AND ENGLISH ALPHABETS. DO NOT USE RUSSIAN, ARABIC, CYRILLIC, THAI, OR ANY OTHER LANGUAGES.\n"
    "Keep tags like <n>, <br>, {0}, %s exactly as written.\n"
    "Keep proper nouns (Night City, V, Johnny, Arasaka) transliterated naturally."
)

# Tag-focused prompt (Phase 1 — placeholder preservation is paramount)
TAG_FOCUSED_PROMPT = (
    "Translate the user's English text to Hebrew. Output ONLY the Hebrew translation.\n"
    "ABSOLUTE RULE: every placeholder/tag in the input MUST appear UNCHANGED in your output.\n"
    "Placeholders include: {int_0}, {DAYS}, {0}, {1}, {NAME}, %s, %d, <n>, <br>, </>, etc.\n"
    "Do NOT translate words inside curly braces. Do NOT change {DAYS} to ימים.\n"
    "Do NOT change {int_0} to {0}. Copy them BYTE-FOR-BYTE.\n"
    "No <think> tags. No explanations. Hebrew only on a single line.\n"
    "USE ONLY HEBREW AND ENGLISH. NO RUSSIAN, ARABIC, OR OTHER ALPHABETS."
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def in_allowed_folder(path):
    return any(f in path.lower() for f in ALLOWED_FOLDERS)


def has_hebrew(text):
    return bool(re.search(r"[֐-׿]", text)) if isinstance(text, str) else False


def has_latin(text):
    return bool(re.search(r"[A-Za-z]", text))


def is_ui_binding(text):
    if not isinstance(text, str) or not text.strip():
        return True
    cleaned = re.sub(r"<[^>]+>", "", text)
    return len(re.sub(r"[^a-zA-Z]", "", cleaned)) <= 1


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREFIX_RE = re.compile(
    r"^\s*(?:translation|תרגום|hebrew|output|answer)\s*[:\-]\s*", re.IGNORECASE
)


def clean_response(raw):
    if not isinstance(raw, str):
        return ""
    s = _THINK_RE.sub("", raw).strip()
    s = re.sub(r"^\*+\s*(.+?)\s*\*+$", r"\1", s).strip()
    s = re.sub(r"^_+\s*(.+?)\s*_+$", r"\1", s).strip()
    s = _PREFIX_RE.sub("", s).strip()
    # Strip leading "1. " (model habit from batch mode)
    m = re.match(r"^\s*1\.\s*(.+)", s)
    if m:
        s = m.group(1).strip()
    return s


_TAG_RE = re.compile(r"<[^>]+>|\{[^}]+\}|%[a-zA-Z]")


def get_tags(text):
    return _TAG_RE.findall(text) if isinstance(text, str) else []


def check_tags_preserved(orig, trans):
    if not isinstance(orig, str) or not isinstance(trans, str):
        return False
    for tag in get_tags(orig):
        if tag not in trans:
            return False
    return True


def is_valid_translation(orig_text, trans_text):
    if not trans_text or not isinstance(trans_text, str):
        return False
    if not has_hebrew(trans_text):
        return False
    if re.search(
        r"[Ѐ-ӿ؀-ۿ฀-๿ऀ-ॿ一-鿿]",
        trans_text,
    ):
        return False
    if not check_tags_preserved(orig_text, trans_text):
        return False
    return True


def translate_one(text, system_prompt, retries):
    """Single-string translate. Returns Hebrew or empty on failure."""
    for attempt in range(1, retries + 1):
        try:
            resp = client.chat.completions.create(
                model="local-model",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                max_tokens=512,
            )
            raw = (resp.choices[0].message.content or "").strip()
            result = clean_response(raw)
            if is_valid_translation(text, result):
                return result, attempt
        except Exception as e:
            print(f"        [!] API error attempt {attempt}: {e}")
            time.sleep(2)
    return "", retries


# ── Atomic save ───────────────────────────────────────────────────────────────
def save_translated(translated):
    tmp = TRANSLATED_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(translated, f, ensure_ascii=False, indent=2)
        os.replace(tmp, TRANSLATED_FILE)
    except Exception as e:
        print(f"   [!] save_translated error: {e}")


def save_skips(skips):
    tmp = SKIP_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([list(x) for x in skips], f, ensure_ascii=False, indent=2)
        os.replace(tmp, SKIP_FILE)
    except Exception as e:
        print(f"   [!] save_skips error: {e}")


# ── Pretty printing ───────────────────────────────────────────────────────────
def banner(title):
    bar = "=" * 70
    print("\n" + bar)
    print(f"  {title}")
    print(bar)


def short(s, n=55):
    s = (s or "").replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[:n] + "..."


def fmt_secs(s):
    s = int(s)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h{m:02d}m{s:02d}s"


# ── Phase 1: Fix broken tags ──────────────────────────────────────────────────
def phase1_fix_broken_tags(original, translated):
    banner("PHASE 1 — Fix Broken Tags")
    print("  Scanning for entries where original tags were dropped/altered...")

    broken = []
    for filepath, orig_entries in original.items():
        if not in_allowed_folder(filepath):
            continue
        trans_entries = translated.get(filepath, [])
        for i, orig in enumerate(orig_entries):
            if i >= len(trans_entries):
                continue
            t = trans_entries[i]
            if not isinstance(t, dict):
                continue
            for field in FIELDS:
                ov = orig.get(field, "")
                tv = t.get(field, "")
                if not isinstance(ov, str) or not ov.strip():
                    continue
                if not isinstance(tv, str) or not tv.strip():
                    continue
                # Only entries that ARE translated (have Hebrew) but lost a tag
                if not has_hebrew(tv):
                    continue
                if not get_tags(ov):
                    continue
                if not check_tags_preserved(ov, tv):
                    broken.append((filepath, i, field, ov, tv))

    total = len(broken)
    print(f"  Found {total} entries with broken tags.\n")

    if total == 0:
        print("  [OK] Nothing to fix in Phase 1.")
        return 0, 0

    fixed = 0
    reverted = 0
    t0 = time.time()

    for idx, (filepath, i, field, ov, tv_old) in enumerate(broken, 1):
        short_fp = filepath.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        print(f"  [{idx}/{total}] {short_fp}#{i}.{field}")
        print(f"      orig:  {short(ov)!r}")
        print(f"      old:   {short(tv_old)!r}")
        print(f"      tags:  {get_tags(ov)}")

        new_trans, attempts = translate_one(ov, TAG_FOCUSED_PROMPT, PHASE1_RETRIES)

        if new_trans and check_tags_preserved(ov, new_trans):
            translated[filepath][i][field] = new_trans
            fixed += 1
            print(f"      [FIX] (attempt {attempts}): {short(new_trans)!r}")
        else:
            translated[filepath][i][field] = ov
            reverted += 1
            print(f"      [REVERT] tags still broken — fell back to English original")

        if (fixed + reverted) % SAVE_EVERY == 0:
            save_translated(translated)
            elapsed = time.time() - t0
            rate = (idx) / max(elapsed, 1)
            eta = (total - idx) / max(rate, 0.001)
            print(
                f"\n   [SAVE] {fixed} fixed, {reverted} reverted | "
                f"elapsed {fmt_secs(elapsed)} | ETA {fmt_secs(eta)}\n"
            )

    save_translated(translated)
    print(f"\n  Phase 1 complete: {fixed} fixed, {reverted} reverted.")
    return fixed, reverted


# ── Phase 2: Salvage skips ────────────────────────────────────────────────────
def phase2_salvage_skips(original, translated, skips):
    banner("PHASE 2 — Deep Salvage of Skips")
    print("  Re-attempting every entry in translation_skips.json (single-mode)...")

    # Build resolved targets (filepath, i, field, original_text)
    targets = []
    bad_keys = []
    ui_skipped = 0

    for skip_entry in list(skips):
        filepath, i_str, field = skip_entry
        try:
            i = int(i_str)
        except (TypeError, ValueError):
            bad_keys.append(skip_entry)
            continue
        if filepath not in original:
            bad_keys.append(skip_entry)
            continue
        orig_entries = original[filepath]
        if i >= len(orig_entries):
            bad_keys.append(skip_entry)
            continue
        ov = orig_entries[i].get(field, "")
        if not isinstance(ov, str) or not ov.strip():
            bad_keys.append(skip_entry)
            continue
        if is_ui_binding(ov):
            ui_skipped += 1
            continue
        if not has_latin(ov):
            ui_skipped += 1
            continue
        targets.append((filepath, i, field, ov))

    total = len(targets)
    print(f"  Skip list size:        {len(skips):,}")
    print(f"  UI-binding (ignored):  {ui_skipped:,}")
    print(f"  Stale/invalid keys:    {len(bad_keys):,}")
    print(f"  Real candidates:       {total:,}\n")

    # Drop stale keys from the in-memory set
    for k in bad_keys:
        skips.discard(k)
    if bad_keys:
        save_skips(skips)
        print(f"  [CLEAN] Removed {len(bad_keys)} stale keys from skip list.\n")

    if total == 0:
        print("  [OK] Nothing to salvage in Phase 2.")
        return 0, 0

    salvaged = 0
    failed = 0
    t0 = time.time()

    for idx, (filepath, i, field, ov) in enumerate(targets, 1):
        short_fp = filepath.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]

        # Make sure container exists
        if filepath not in translated:
            translated[filepath] = []
        trans_entries = translated[filepath]
        while len(trans_entries) <= i:
            base = original[filepath][len(trans_entries)]
            trans_entries.append(base.copy() if isinstance(base, dict) else {})

        new_trans, attempts = translate_one(ov, SYSTEM_PROMPT, PHASE2_RETRIES)

        if new_trans and is_valid_translation(ov, new_trans):
            translated[filepath][i][field] = new_trans
            skips.discard((filepath, str(i), field))
            salvaged += 1
            elapsed = time.time() - t0
            rate = idx / max(elapsed, 1)
            eta = (total - idx) / max(rate, 0.001)
            print(
                f"  [{idx}/{total}] [SALVAGE] {short_fp}#{i}.{field} "
                f"(att {attempts}) | total saved: {salvaged} | ETA {fmt_secs(eta)}"
            )
            print(f"        orig:  {short(ov)!r}")
            print(f"        heb:   {short(new_trans)!r}")
        else:
            failed += 1
            if failed % 25 == 0 or failed <= 5:
                print(
                    f"  [{idx}/{total}] [STILL-FAIL] {short_fp}#{i}.{field} "
                    f"({failed} fails so far)"
                )

        if salvaged > 0 and salvaged % SAVE_EVERY == 0 and salvaged != getattr(
            phase2_salvage_skips, "_last_save", 0
        ):
            save_translated(translated)
            save_skips(skips)
            phase2_salvage_skips._last_save = salvaged
            elapsed = time.time() - t0
            rate = idx / max(elapsed, 1)
            eta = (total - idx) / max(rate, 0.001)
            print(
                f"\n   [SAVE] salvaged {salvaged}, failed {failed}, "
                f"processed {idx}/{total} | elapsed {fmt_secs(elapsed)} | "
                f"ETA {fmt_secs(eta)}\n"
            )

    save_translated(translated)
    save_skips(skips)
    print(f"\n  Phase 2 complete: {salvaged} salvaged, {failed} still failing.")
    return salvaged, failed


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    banner("CYBERPUNK 2077 — Deep QA + Salvage Pass")
    print(f"  Original:    {ORIGINAL_FILE}")
    print(f"  Translated:  {TRANSLATED_FILE}")
    print(f"  Skip list:   {SKIP_FILE}")
    print(f"  Save every:  {SAVE_EVERY} successful fixes")
    print(f"  LM Studio:   http://127.0.0.1:1234/v1\n")

    print("  Loading source files...")
    t0 = time.time()
    with open(ORIGINAL_FILE, "r", encoding="utf-8") as f:
        original = json.load(f)
    print(f"    [OK] localization_export.json     ({len(original):,} files)")

    with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
        translated = json.load(f)
    print(f"    [OK] localization_translated.json ({len(translated):,} files)")

    skips = set()
    if os.path.exists(SKIP_FILE):
        try:
            with open(SKIP_FILE, "r", encoding="utf-8") as f:
                skips = set(tuple(x) for x in json.load(f))
            print(f"    [OK] translation_skips.json       ({len(skips):,} entries)")
        except Exception as e:
            print(f"    [!] translation_skips.json corrupt: {e}")

    print(f"  Load time: {time.time() - t0:.1f}s\n")

    run_start = time.time()

    # Phase 1
    p1_fixed, p1_reverted = phase1_fix_broken_tags(original, translated)

    # Phase 2
    p2_salvaged, p2_failed = phase2_salvage_skips(original, translated, skips)

    # Final
    banner("FINAL REPORT")
    elapsed = time.time() - run_start
    print(f"  Total runtime:                {fmt_secs(elapsed)}")
    print(f"  Phase 1 — broken tags fixed:  {p1_fixed:,}")
    print(f"  Phase 1 — reverted to EN:     {p1_reverted:,}")
    print(f"  Phase 2 — entries salvaged:   {p2_salvaged:,}")
    print(f"  Phase 2 — still untranslated: {p2_failed:,}")
    print(f"  Skip list size now:           {len(skips):,}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  [STOPPED] Caught Ctrl+C — last save is intact, safe to resume.")
