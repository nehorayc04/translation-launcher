"""
cross_model_watchdog.py
=======================
Real-time Linguistic Cross-Validation Watchdog.

Pairs two LM Studio models loaded simultaneously on a single server
(http://10.0.0.5:1234):

  - Worker (idle from this script's POV): "gemma-2-27b-it"
  - Judge / Critic (the one we call):      "meta-llama-3.1-8b-instruct@q4_k_m"

The watchdog walks every (section, primaryKey, field) row in:
    תרגום_משחקים/source/resources/localization_translated.json   (base game)
    תרגום_משחקים/source/resources/dlc_ep1_translated.json        (DLC)

For each row it asks the Judge to act as a strict Lead LQA Editor for
the Hebrew Cyberpunk 2077 localization. The Judge MUST output exactly
one line:

    PASS                  ← line is approved
    FAIL: <one sentence>  ← anything else flags the row

Flagged rows are appended to `cross_audit_flags.json` (JSON-Lines, one
record per line — chosen for O(1) appends; the .json extension is kept
as specified in the brief).

State / safety:
  * Source files are opened READ-ONLY. The script NEVER writes back
    fixes to localization_translated.json / dlc_ep1_translated.json.
  * Checkpoint `cross_audit_checkpoint.json` records the last processed
    flat row index. Ctrl+C finishes the current row, saves checkpoint,
    refreshes the dashboard, and exits cleanly.
  * Dashboard `cross_audit_dashboard.md` is overwritten every 10 rows
    with live throughput / progress / last-5-flags.
  * All write targets (checkpoint, dashboard, flags) use atomic writes
    or append-only — the polished 1.0.1 mod source JSONs are never
    touched.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from collections import deque
from dataclasses import dataclass, field

from openai import OpenAI

# ── Paths ───────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(HERE))   # games/<game>/ -> repo root
RES = os.path.join(_REPO_ROOT, "תרגום_משחקים", "source", "resources")

BASE_TR = os.path.join(RES, "localization_translated.json")
BASE_EN = os.path.join(RES, "localization_export.json")
DLC_TR  = os.path.join(RES, "dlc_ep1_translated.json")
DLC_EN  = os.path.join(RES, "dlc_ep1_text.json")

CHECKPOINT = os.path.join(HERE, "cross_audit_checkpoint.json")
DASHBOARD  = os.path.join(HERE, "cross_audit_dashboard.md")
FLAGS_FILE = os.path.join(HERE, "cross_audit_flags.json")

# ── LM Studio config ────────────────────────────────────────────────────────
LM_URL       = "http://10.0.0.5:1234/v1"
JUDGE_MODEL  = "meta-llama-3.1-8b-instruct@q4_k_m"
WORKER_MODEL = "gemma-2-27b-it"   # loaded concurrently; not called here

DASHBOARD_INTERVAL  = 10
CHECKPOINT_INTERVAL = 25

# ── System prompt for the Judge ─────────────────────────────────────────────
JUDGE_SYSTEM_PROMPT = (
    "You are a Hebrew localization QA reviewer for Cyberpunk 2077. Your "
    "ONLY job is to detect BROKEN output — NOT to judge stylistic quality, "
    "tone, register, or word choice.\n\n"
    "FLAG ONLY these four specific defects:\n"
    "1. TRUNCATION — the Hebrew is clearly cut mid-sentence (ends in a "
    "dangling binding word like ו / ב / ל / מ / כ / ש / של / את) AND the "
    "English source clearly continues beyond that point with more content.\n"
    "2. SEVERE CORRUPTION — the Hebrew contains garbled tokens, repeating "
    "sequences, mojibake, OR characters from forbidden scripts (Cyrillic, "
    "Arabic, Thai, CJK, Hangul, Devanagari, Armenian, Greek).\n"
    "3. MISSING TRANSLATION — the Hebrew is empty or whitespace-only while "
    "the English source has substantive content.\n"
    "4. STRUCTURAL DAMAGE — tags like <Rich>, <kiroshi>, {VALUE,...}, {0}, "
    "%s, &nbsp; appear in the English but were destroyed, mangled, or "
    "removed in the Hebrew.\n\n"
    "NEVER FLAG these — they are CORRECT and you MUST reply PASS:\n"
    "- Single-word translations ('Yes' → 'כן', 'Stop' → 'עצור', 'Grill' "
    "→ 'גריל'). Short does not mean broken.\n"
    "- Transliterations of proper nouns / brand names ('Arasaka' → "
    "'אראסאקה', 'Silverhand' → 'סילברהנד').\n"
    "- Brand names, acronyms, codes, or the protagonist's name 'V' kept "
    "in Latin script ('V', 'NCPD', 'Mk.31', 'HDR10', 'NC484').\n"
    "- Hebrew containing parentheses, brackets, or punctuation that looks "
    "unfamiliar. For example 'מיכל דלק (מתפוצץ)' is FULLY CORRECT — the "
    "parentheses are valid Hebrew syntax; do NOT claim data is missing.\n"
    "- Translations that you would personally phrase differently but that "
    "accurately convey the English meaning.\n"
    "- Word-order differences from English — Hebrew syntax differs from "
    "English by design; this is NORMAL.\n"
    "- Tone, register, or 'feel' — DO NOT judge 'gang slang vs corporate'; "
    "only flag broken text.\n\n"
    "RULE: If the Hebrew accurately represents the English meaning and is "
    "not broken in one of the four FLAG-ONLY ways above, you MUST reply "
    "PASS.\n\n"
    "When in doubt, reply PASS. Default to PASS. In this audit a false "
    "positive is worse than a false negative.\n\n"
    "OUTPUT FORMAT — EXACTLY ONE of:\n"
    "    PASS\n"
    "    FAIL: <one short English sentence naming which of the four "
    "FLAG-ONLY categories applies>\n\n"
    "Do NOT explain reasoning. Do NOT suggest a fix. Do NOT preface. Just "
    "PASS or FAIL: <reason>."
)


# ── Data classes ────────────────────────────────────────────────────────────
@dataclass
class Row:
    project: str         # "base" | "dlc"
    section: str
    pk: str
    field: str           # "femaleVariant" | "maleVariant"
    english: str
    hebrew: str


@dataclass
class Stats:
    started_at: float = field(default_factory=time.time)
    processed: int = 0
    flagged:   int = 0
    base_total: int = 0
    base_done:  int = 0
    dlc_total:  int = 0
    dlc_done:   int = 0


# ── Persistent state helpers ────────────────────────────────────────────────
def atomic_write(path: str, content: str) -> None:
    """Write `content` atomically: tmp file + os.replace."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def load_checkpoint() -> int:
    if not os.path.exists(CHECKPOINT):
        return 0
    try:
        with open(CHECKPOINT, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("last_index", 0))
    except (OSError, ValueError):
        return 0


def save_checkpoint(idx: int, stats: Stats) -> None:
    payload = {
        "last_index": idx,
        "processed":  stats.processed,
        "flagged":    stats.flagged,
        "base_done":  stats.base_done,
        "dlc_done":   stats.dlc_done,
        "saved_at":   time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    atomic_write(CHECKPOINT, json.dumps(payload, ensure_ascii=False, indent=2))


def append_flag(row: Row, feedback: str) -> None:
    """Append one JSON record per line — O(1) append, no rewrite."""
    entry = {
        "ts":              time.strftime("%Y-%m-%d %H:%M:%S"),
        "project":         row.project,
        "section":         row.section,
        "pk":              row.pk,            # primaryKey / stringId
        "field":           row.field,
        "english":         row.english,
        "current_hebrew":  row.hebrew,
        "critic_feedback": feedback,
    }
    with open(FLAGS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def count_existing_flags() -> int:
    if not os.path.exists(FLAGS_FILE):
        return 0
    try:
        with open(FLAGS_FILE, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


# ── Source loading (READ-ONLY) ──────────────────────────────────────────────
def _load_ro(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _index_en(en_data: dict) -> dict:
    """English-by-pk lookup, grouped by section."""
    idx: dict[str, dict[str, dict]] = {}
    for sec, rows in en_data.items():
        if not isinstance(rows, list):
            continue
        d: dict[str, dict] = {}
        for e in rows:
            if not isinstance(e, dict):
                continue
            for key in ("primaryKey", "stringId"):
                v = e.get(key)
                if v not in (None, ""):
                    d[str(v)] = e
        idx[sec] = d
    return idx


def _flatten_project(tr_path: str, en_path: str, project: str) -> list[Row]:
    tr = _load_ro(tr_path)
    en = _load_ro(en_path)
    en_idx = _index_en(en)
    rows: list[Row] = []
    for sec, entries in tr.items():
        if not isinstance(entries, list):
            continue
        ek = en_idx.get(sec, {})
        for e in entries:
            if not isinstance(e, dict):
                continue
            pk = str(e.get("primaryKey", "") or e.get("stringId", ""))
            if not pk:
                continue
            src_e = ek.get(pk) or {}
            for fld in ("femaleVariant", "maleVariant"):
                he = e.get(fld) or ""
                if not he or len(he.strip()) < 2:
                    continue
                en_v = (src_e.get(fld) if src_e else None) or e.get("secondaryKey") or ""
                if not en_v or len(en_v.strip()) < 2:
                    continue
                rows.append(Row(project, sec, pk, fld, en_v, he))
    return rows


def build_corpus() -> tuple[list[Row], int, int]:
    print("[*] Indexing translation corpus (read-only)...", flush=True)
    base_rows = _flatten_project(BASE_TR, BASE_EN, "base")
    dlc_rows  = _flatten_project(DLC_TR,  DLC_EN,  "dlc")
    print(f"  base: {len(base_rows):,} rows  ·  dlc: {len(dlc_rows):,} rows  "
          f"·  total: {len(base_rows) + len(dlc_rows):,}", flush=True)
    return base_rows + dlc_rows, len(base_rows), len(dlc_rows)


# ── Judge call ──────────────────────────────────────────────────────────────
def call_judge(client: OpenAI, english: str, hebrew: str) -> str:
    """Returns 'PASS', 'FAIL: <reason>', or 'ERROR: <why>'."""
    user_prompt = (
        f"ENGLISH SOURCE:\n{english}\n\n"
        f"HEBREW TRANSLATION:\n{hebrew}\n\n"
        f"Output PASS or FAIL: <reason>."
    )
    try:
        resp = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=120,
            timeout=60,
        )
        out = (resp.choices[0].message.content or "").strip()
        if not out:
            return "ERROR: empty judge response"
        first = out.splitlines()[0].strip()
        upper = first.upper()
        if upper == "PASS" or upper.startswith("PASS "):
            return "PASS"
        if upper.startswith("FAIL"):
            return first
        # Fall back to scanning the whole reply if the model was verbose.
        full_upper = out.upper()
        if "PASS" in full_upper and "FAIL" not in full_upper:
            return "PASS"
        if "FAIL" in full_upper:
            for line in out.splitlines():
                if line.strip().upper().startswith("FAIL"):
                    return line.strip()
        return f"FAIL: {first[:140] or 'ambiguous judge output'}"
    except Exception as e:                                       # noqa: BLE001
        return f"ERROR: {type(e).__name__}: {e}"


# ── Dashboard ───────────────────────────────────────────────────────────────
def _excerpt(s: str, n: int) -> str:
    s = s.replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def render_dashboard(stats: Stats,
                     recent_flags: deque,
                     current_row: Row | None) -> None:
    elapsed_min = max((time.time() - stats.started_at) / 60.0, 1 / 60)
    rate = stats.processed / elapsed_min
    base_pct = (stats.base_done / stats.base_total * 100) if stats.base_total else 0.0
    dlc_pct  = (stats.dlc_done  / stats.dlc_total  * 100) if stats.dlc_total  else 0.0
    grand_total = stats.base_total + stats.dlc_total
    total_pct = (stats.processed / grand_total * 100) if grand_total else 0.0
    flag_rate = (stats.flagged / stats.processed * 100) if stats.processed else 0.0

    L: list[str] = []
    L.append("# Cross-Model Watchdog — Live Dashboard")
    L.append("")
    L.append(f"_Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}_")
    L.append("")
    L.append("## Throughput")
    L.append("")
    L.append(f"- **Scanning speed:** {rate:.1f} rows / min")
    L.append(f"- **Elapsed:** {elapsed_min:.1f} min")
    L.append(f"- **Judge model:** `{JUDGE_MODEL}`")
    L.append(f"- **Worker model loaded (idle here):** `{WORKER_MODEL}`")
    L.append(f"- **LM Studio:** `{LM_URL}`")
    L.append("")
    L.append("## Progress")
    L.append("")
    L.append("| Project | Done | Total | % |")
    L.append("|---|---:|---:|---:|")
    L.append(f"| Base game | {stats.base_done:,} | {stats.base_total:,} | {base_pct:.2f}% |")
    L.append(f"| Phantom Liberty (DLC) | {stats.dlc_done:,} | {stats.dlc_total:,} | {dlc_pct:.2f}% |")
    L.append(f"| **Total** | **{stats.processed:,}** | **{grand_total:,}** | **{total_pct:.2f}%** |")
    L.append("")
    L.append("## Flags")
    L.append("")
    L.append(f"- **Total flagged as 'Needs Review':** {stats.flagged:,}")
    L.append(f"- **Flag rate:** {flag_rate:.2f}%")
    L.append("")
    if current_row:
        L.append(f"_Currently scanning: `{current_row.project}/"
                 f"{current_row.section}` pk={current_row.pk}_")
        L.append("")

    L.append("## Last 5 Flagged Anomalies")
    L.append("")
    if not recent_flags:
        L.append("_(none yet)_")
    else:
        L.append("| # | Project | Section | PK | English (excerpt) | Hebrew (excerpt) | Critic feedback |")
        L.append("|---|---|---|---|---|---|---|")
        for i, (row, fb) in enumerate(reversed(list(recent_flags)), 1):
            sec_short = row.section.split("/")[-1]
            L.append(
                f"| {i} | {row.project} | `{_excerpt(sec_short, 28)}` | "
                f"{row.pk} | {_excerpt(row.english, 60)} | "
                f"{_excerpt(row.hebrew, 60)} | {_excerpt(fb, 90)} |"
            )
    L.append("")
    L.append("---")
    L.append("_Generated by `cross_model_watchdog.py` — read-only audit, "
             "no source files modified._")
    atomic_write(DASHBOARD, "\n".join(L) + "\n")


# ── Signal handling ─────────────────────────────────────────────────────────
_STOP = False


def _on_sigint(_sig, _frm):
    global _STOP
    _STOP = True
    print("\n[!] Ctrl+C — finishing current row and saving checkpoint...",
          flush=True)


# ── Main loop ───────────────────────────────────────────────────────────────
def main() -> int:
    signal.signal(signal.SIGINT, _on_sigint)

    corpus, base_total, dlc_total = build_corpus()
    total = len(corpus)
    if not total:
        print("[!] no rows to audit", flush=True)
        return 1

    start_idx = load_checkpoint()
    if start_idx >= total:
        print(f"[*] checkpoint already past end ({start_idx} >= {total}); "
              f"delete {os.path.basename(CHECKPOINT)} to restart from 0",
              flush=True)
        return 0

    print(f"[*] Connecting to LM Studio at {LM_URL}", flush=True)
    client = OpenAI(base_url=LM_URL, api_key="lm-studio", timeout=120)

    # Preflight: a trivial pair — fail fast if the judge model isn't loaded.
    pre = call_judge(client, "Hello.", "שלום.")
    if pre.startswith("ERROR"):
        print(f"FATAL: judge preflight failed — {pre}", flush=True)
        return 2
    print(f"[*] Judge preflight OK ({pre})", flush=True)

    stats = Stats(base_total=base_total, dlc_total=dlc_total)

    # Replay per-project counters so the dashboard is accurate after resume.
    for r in corpus[:start_idx]:
        stats.processed += 1
        if r.project == "base":
            stats.base_done += 1
        else:
            stats.dlc_done += 1
    stats.flagged = count_existing_flags()

    recent_flags: deque = deque(maxlen=5)
    print(f"[*] Starting at index {start_idx:,} / {total:,}  "
          f"(prev flagged: {stats.flagged:,})", flush=True)

    idx = start_idx
    err_streak = 0
    for idx in range(start_idx, total):
        if _STOP:
            break
        row = corpus[idx]
        verdict = call_judge(client, row.english, row.hebrew)

        stats.processed += 1
        if row.project == "base":
            stats.base_done += 1
        else:
            stats.dlc_done += 1

        if verdict.startswith("ERROR"):
            err_streak += 1
            print(f"  [judge-err] {row.project}/{row.section}/{row.pk}: "
                  f"{verdict}", flush=True)
            if err_streak >= 10:
                print("[!] 10 consecutive judge errors — pausing 30s before "
                      "continuing (LM Studio may be hung; see CLAUDE.md for "
                      "the `lms unload --all && lms load …` recovery).",
                      flush=True)
                time.sleep(30)
                err_streak = 0
        else:
            err_streak = 0
            if not verdict.startswith("PASS"):
                stats.flagged += 1
                recent_flags.append((row, verdict))
                append_flag(row, verdict)

        if stats.processed % DASHBOARD_INTERVAL == 0:
            render_dashboard(stats, recent_flags, row)
        if stats.processed % CHECKPOINT_INTERVAL == 0:
            save_checkpoint(idx + 1, stats)

    # Final flush.
    final_idx = idx if _STOP else idx + 1
    save_checkpoint(final_idx, stats)
    render_dashboard(stats, recent_flags, None)
    print(f"[*] Done — processed {stats.processed:,}, flagged {stats.flagged:,}",
          flush=True)
    print(f"[*] Dashboard: {DASHBOARD}", flush=True)
    print(f"[*] Flags:     {FLAGS_FILE}", flush=True)
    print(f"[*] Resume by re-running this script "
          f"(checkpoint at index {final_idx:,}).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
