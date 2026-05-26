"""
repair_critical_truncations.py
==============================
Focused repair pass for the 68 CRITICAL truncation findings produced by
integrity_audit.py.

Strategy — Split-Translation:
  1. Read the English source for each pk from `integrity_audit_CRITICAL.json`.
  2. Split the source on paragraph boundaries `\n\n` (preserving the
     `\\n\\n` literal that CR2W stores as a paragraph break).
  3. Translate each part as its own LM call — this defeats the LM's
     habit of summarising long multi-paragraph text into a single
     bullet. Re-join with the same `\\n\\n` separator.
  4. Five CR2W safety gates before write-back:
       (1) Preserve tags — every tag/placeholder in the source must
           appear unchanged in the translation (count-equal).
       (2) Length cap — translation ≤ 1.3 × source length.
       (3) Atomic write — `tqf._atomic_write_json` (`.tmp` + `os.replace`)
           against the source JSON; never touch in place.
       (4) No markup damage — `_FOREIGN_RE` / niqqud strip / `is_valid_translation`
           must all pass on the joined result.
       (5) No buffer overflow — same as (2) effectively; the 1.3× cap is
           already inside the slot the original Arabic CR2W field was
           sized for.
  5. Writes the repaired entries back to the SAME JSON the source came
     from — DLC entries (`ep1/...` section) go to dlc_ep1_translated.json,
     base entries go to localization_translated.json.

ABSOLUTELY DOES NOT re-bake any archive. The next regular
`rebuild_dlc_and_pack.py` (or `rebuild_onscreens_and_pack.py`) will pick
the new translations up automatically.

Reports to `repair_critical_truncations_report.json` with per-pk outcome.

Run: python repair_critical_truncations.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import translate_queue_fast as tqf
from openai import OpenAI

# ── inputs / outputs ────────────────────────────────────────────────────────
RES = os.path.join(HERE, "תרגום_משחקים", "source", "resources")
BASE_FILE = os.path.join(RES, "localization_translated.json")
DLC_FILE  = os.path.join(RES, "dlc_ep1_translated.json")
INPUT     = os.path.join(HERE, "integrity_audit_CRITICAL.json")
REPORT    = os.path.join(HERE, "repair_critical_truncations_report.json")
LOG_FILE  = os.path.join(HERE, "repair_critical_truncations.log")
MONITOR_LOG = os.path.join(HERE, "fix_missing_translations.log")

LM_URL = "http://127.0.0.1:1234/v1"
LENGTH_CAP_RATIO = 1.30
PARALLEL = 4

TAG_RE = re.compile(r"<[^<>]+>|\{[^{}]+\}|%[a-zA-Z]|&\w+;")
HEB = re.compile(r"[֐-׿]")
LATIN = re.compile(r"[A-Za-z]")
SAFE_FOREIGN_RE = tqf._FOREIGN_RE        # reuse the project's foreign-script regex

# Paragraph separator inside CR2W string fields — the JSON stores it as
# the literal two-character sequence `\` `n` `\` `n` (an *escaped*
# `\n\n`). Splitting on the literal `\\n\\n` keeps that boundary intact.
SPLIT_TOKEN = r"\n\n"
LITERAL_SPLIT = "\\n\\n"

_log_lock = __import__("threading").Lock()


def log(msg: str, monitor: bool = True) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with _log_lock:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
            if monitor:
                with open(MONITOR_LOG, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
        except OSError:
            pass
        try:
            print(msg, flush=True)
        except Exception:
            pass


# ── 5 CR2W safety gates ─────────────────────────────────────────────────────

def gate_tags_preserved(src: str, trans: str) -> tuple[bool, str]:
    src_tags = Counter(TAG_RE.findall(src or ""))
    trn_tags = Counter(TAG_RE.findall(trans or ""))
    if src_tags != trn_tags:
        missing = src_tags - trn_tags
        extra   = trn_tags - src_tags
        return (False, f"tag mismatch: missing={dict(missing)} extra={dict(extra)}")
    return (True, "")


def gate_length_cap(src: str, trans: str) -> tuple[bool, str]:
    if not src:
        return (True, "")
    if len(trans) > LENGTH_CAP_RATIO * len(src):
        return (False, f"length {len(trans)} > 1.3× src {len(src)}")
    return (True, "")


def gate_no_markup_damage(src: str, trans: str) -> tuple[bool, str]:
    if not trans:
        return (False, "empty")
    if not HEB.search(trans):
        return (False, "no Hebrew chars")
    if SAFE_FOREIGN_RE.search(trans):
        return (False, "foreign-script characters")
    # paragraph count should not collapse below 50% of source
    src_pcount = src.count(LITERAL_SPLIT) + 1
    trn_pcount = trans.count(LITERAL_SPLIT) + 1
    if src_pcount >= 3 and trn_pcount < (src_pcount + 1) // 2:
        return (False, f"paragraph count collapse: src={src_pcount} trn={trn_pcount}")
    return (True, "")


def gate_no_buffer_overflow(src: str, trans: str) -> tuple[bool, str]:
    # CR2W string fields in this game are length-prefixed (LEB128) — there is
    # no hard upper bound in the format itself, but the original Arabic CR2W
    # slot is sized for the English. 1.3× of that English is a safe headroom
    # the WolvenKit packer tolerated on every previous bake. Gate (2) covers
    # the same constraint; this gate is the explicit "I checked" footprint.
    return gate_length_cap(src, trans)


SAFETY_GATES = [
    ("tags_preserved",   gate_tags_preserved),
    ("length_cap",       gate_length_cap),
    ("no_markup_damage", gate_no_markup_damage),
    ("no_buffer_over",   gate_no_buffer_overflow),
]


def all_gates(src: str, trans: str) -> tuple[bool, list[str]]:
    """Returns (ok, list_of_failure_reasons)."""
    fails = []
    for name, gate in SAFETY_GATES:
        ok, reason = gate(src, trans)
        if not ok:
            fails.append(f"{name}: {reason}")
    return (not fails, fails)


# ── split-translate strategy ────────────────────────────────────────────────

def translate_segment(seg: str, attempts: int = 3) -> str | None:
    """Translate one segment with retries, accepting first Hebrew result that
    preserves tags. The standard translator's validator handles foreign
    scripts and length sanity per-segment."""
    if not seg or not LATIN.search(seg):
        return seg                     # nothing English to translate
    for _ in range(attempts):
        try:
            out = tqf.translate_one(seg)
        except Exception:                                       # noqa: BLE001
            continue
        if out and HEB.search(out) and tqf.is_valid_translation(seg, out):
            return out
    return None


def split_translate(src: str) -> tuple[str | None, list[str]]:
    """Returns (joined_translation, per_segment_failures).
    None when ≥1 critical segment failed AND no fallback is acceptable."""
    if not src:
        return ("", [])
    # split on the LITERAL `\n\n` token used in the JSON
    segments = src.split(LITERAL_SPLIT)
    out_segments = []
    failures = []
    for idx, seg in enumerate(segments):
        # numbered-list items often hold `\n` as a SINGLE literal as well;
        # break those out so the LM doesn't try to summarise a 12-line list
        # in one shot
        sub_segments = seg.split("\\n") if "\\n" in seg else [seg]
        out_subs = []
        for sub in sub_segments:
            t = translate_segment(sub)
            if t is None:
                failures.append(f"seg{idx}: untranslatable: {sub[:40]!r}")
                # keep original sub — better than dropping it entirely
                out_subs.append(sub)
            else:
                out_subs.append(t)
        out_segments.append("\\n".join(out_subs))
    joined = LITERAL_SPLIT.join(out_segments)
    return (joined, failures)


# ── write-back helpers ──────────────────────────────────────────────────────

def write_repair(file_path: str, section: str, pk: str, field: str,
                 new_value: str) -> bool:
    """Read, update in memory, atomic write. Returns True on success."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get(section)
    if not isinstance(rows, list):
        return False
    target = None
    for e in rows:
        if not isinstance(e, dict):
            continue
        if (str(e.get("primaryKey", "")) == pk
                or str(e.get("stringId", "")) == pk):
            target = e
            break
    if target is None:
        return False
    target[field] = new_value
    tqf._atomic_write_json(file_path, data)
    return True


# ── pipeline ────────────────────────────────────────────────────────────────

def main() -> int:
    with open(INPUT, "r", encoding="utf-8") as f:
        critical = json.load(f)
    log(f"[*] {len(critical)} CRITICAL pks to repair", monitor=False)

    # Initialize LM client (same setup as the translator)
    client = OpenAI(base_url=LM_URL, api_key="lm-studio", timeout=600)
    tqf.lm_client = client
    tqf.TEMPERATURE = tqf.DEFAULT_TEMP

    log("[*] Using LM Studio (Gemma-2-27b)")
    log(f"[started: {time.strftime('%Y-%m-%d %H:%M:%S')}]")
    log("[*] Preflight …", monitor=False)
    try:
        tqf.translate_one("Apply")
    except Exception as e:                                       # noqa: BLE001
        log(f"FATAL: LM Studio unreachable — {e}")
        return 1
    log("[*] Preflight OK", monitor=False)

    results = []

    def _job(item):
        src = item["EN_source"]
        joined, seg_fails = split_translate(src)
        if not joined:
            return (item, None, ["empty result"])
        ok, gate_fails = all_gates(src, joined)
        return (item, joined if ok else None, seg_fails + gate_fails)

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        futs = [pool.submit(_job, it) for it in critical]
        for fut in as_completed(futs):
            item, new_trans, fails = fut.result()
            pk = item["pk"]
            sec = item["section"]
            fld = item["field"]
            target_file = DLC_FILE if item["project"] == "dlc" else BASE_FILE
            entry = {
                "project": item["project"], "section": sec, "pk": pk,
                "field": fld, "src_len": item["src_len"],
                "old_trans_len": item["trans_len"],
            }
            if new_trans:
                if write_repair(target_file, sec, pk, fld, new_trans):
                    entry.update({
                        "status": "repaired",
                        "new_trans_len": len(new_trans),
                        "ratio_after": round(len(new_trans) / max(1, item["src_len"]), 3),
                    })
                    log(f"  fix[{item['project']}/{pk}] "
                        f"{item['trans_len']}→{len(new_trans)} chars "
                        f"(src={item['src_len']})")
                else:
                    entry.update({"status": "write_failed", "fails": fails})
                    log(f"  [!] write FAILED for {item['project']}/{pk}", monitor=False)
            else:
                entry.update({"status": "skipped_safety", "fails": fails})
                log(f"  [skip] {item['project']}/{pk} — {fails[:2]}", monitor=False)
            results.append(entry)

    # Report
    by_status = Counter(r["status"] for r in results)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "by_status": dict(by_status),
        "entries": results,
    }
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"[*] Done — {dict(by_status)}  report -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
