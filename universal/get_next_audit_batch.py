"""
get_next_audit_batch.py
=======================
Claude-in-the-loop Hebrew translation audit driver.

The strategy here is the opposite of `cross_model_watchdog.py`: instead of
asking a local 8B model to judge, this script just SERVES the data to
Claude (the foreground operator) so a much more capable model does the
LQA review.

Three subcommands:

  python get_next_audit_batch.py next [--size 10]
    Pop the next N rows off the audit corpus, advance the checkpoint
    atomically, and write the batch to `cross_audit_batch.json` (UTF-8).
    Stdout prints a one-line ASCII summary so PowerShell never trips on
    Hebrew encoding.

  python get_next_audit_batch.py flag
    Read one JSON object OR a JSON array of objects from stdin. Each
    record must carry: project / section / pk / field / english /
    hebrew / critic_feedback. Appends them to `cross_audit_flags.json`
    (JSONL — one record per line, append-only, O(1) regardless of
    file size) and refreshes `cross_audit_dashboard.md`.

  python get_next_audit_batch.py dashboard
    Refresh `cross_audit_dashboard.md` from current state without
    touching anything else.

Source files (`localization_translated.json`, `dlc_ep1_translated.json`,
`localization_export.json`, `dlc_ep1_text.json`) are opened STRICTLY
READ-ONLY. This script never mutates them — only the three audit
sidecars (checkpoint / flags / dashboard) and a working batch file.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass

# Defensive: Windows consoles can refuse to print Hebrew under cp1255.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── paths ───────────────────────────────────────────────────────────────────
HERE         = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)        # universal/ → project root
RES = os.path.join(PROJECT_ROOT, "תרגום_משחקים", "source", "resources")

BASE_TR = os.path.join(RES, "localization_translated.json")
BASE_EN = os.path.join(RES, "localization_export.json")
DLC_TR  = os.path.join(RES, "dlc_ep1_translated.json")
DLC_EN  = os.path.join(RES, "dlc_ep1_text.json")

CHECKPOINT = os.path.join(HERE, "cross_audit_checkpoint.json")
DASHBOARD  = os.path.join(HERE, "cross_audit_dashboard.md")
FLAGS_FILE = os.path.join(HERE, "cross_audit_flags.json")
BATCH_FILE = os.path.join(HERE, "cross_audit_batch.json")


@dataclass
class Row:
    project: str
    section: str
    pk: str
    field: str
    english: str
    hebrew: str


# ── small helpers ───────────────────────────────────────────────────────────
def atomic_write(path: str, content: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def load_json_ro(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _index_en(en_data: dict) -> dict:
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
    tr = load_json_ro(tr_path)
    en = load_json_ro(en_path)
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
    base_rows = _flatten_project(BASE_TR, BASE_EN, "base")
    dlc_rows  = _flatten_project(DLC_TR,  DLC_EN,  "dlc")
    return base_rows + dlc_rows, len(base_rows), len(dlc_rows)


# ── checkpoint + flags ──────────────────────────────────────────────────────
def _empty_state() -> dict:
    return {
        "last_index": 0,
        "processed":  0,
        "flagged":    0,
        "base_total": 0,
        "dlc_total":  0,
        "base_done":  0,
        "dlc_done":   0,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def load_checkpoint() -> dict:
    if not os.path.exists(CHECKPOINT):
        return _empty_state()
    try:
        return load_json_ro(CHECKPOINT)
    except (OSError, ValueError):
        return _empty_state()


def save_checkpoint(state: dict) -> None:
    state["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    atomic_write(CHECKPOINT,
                 json.dumps(state, ensure_ascii=False, indent=2))


def count_existing_flags() -> int:
    if not os.path.exists(FLAGS_FILE):
        return 0
    try:
        with open(FLAGS_FILE, "r", encoding="utf-8") as f:
            return sum(1 for ln in f if ln.strip())
    except OSError:
        return 0


def last_n_flags(n: int) -> list[dict]:
    if not os.path.exists(FLAGS_FILE):
        return []
    try:
        with open(FLAGS_FILE, "r", encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines[-n:]]
    except (OSError, ValueError):
        return []


# ── dashboard ───────────────────────────────────────────────────────────────
def _excerpt(s: str, n: int) -> str:
    s = (s or "").replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def render_dashboard(state: dict) -> None:
    base_total = state.get("base_total", 0)
    dlc_total  = state.get("dlc_total", 0)
    base_done  = state.get("base_done", 0)
    dlc_done   = state.get("dlc_done", 0)
    processed  = state.get("processed", 0)
    flagged    = state.get("flagged", 0)

    base_pct = (base_done / base_total * 100) if base_total else 0.0
    dlc_pct  = (dlc_done  / dlc_total  * 100) if dlc_total  else 0.0
    grand    = base_total + dlc_total
    total_pct = (processed / grand * 100) if grand else 0.0
    flag_rate = (flagged / processed * 100) if processed else 0.0

    L: list[str] = []
    L.append("# Cross-Validation Audit — Live Dashboard")
    L.append("")
    L.append(f"_Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}_")
    L.append("")
    L.append("**Judge:** Claude (Opus 4.7) — in-the-loop manual LQA")
    L.append("")
    L.append("## Progress")
    L.append("")
    L.append("| Project | Done | Total | % |")
    L.append("|---|---:|---:|---:|")
    L.append(f"| Base game | {base_done:,} | {base_total:,} | {base_pct:.2f}% |")
    L.append(f"| Phantom Liberty (DLC) | {dlc_done:,} | {dlc_total:,} | {dlc_pct:.2f}% |")
    L.append(f"| **Total** | **{processed:,}** | **{grand:,}** | **{total_pct:.2f}%** |")
    L.append("")
    L.append("## Flags")
    L.append("")
    L.append(f"- **Total flagged as 'Needs Review':** {flagged:,}")
    L.append(f"- **Flag rate:** {flag_rate:.2f}%")
    L.append("")
    L.append("## Last 5 Flagged Anomalies")
    L.append("")
    recent = last_n_flags(5)
    if not recent:
        L.append("_(none yet)_")
    else:
        L.append("| # | Project | Section | PK | English | Hebrew | Critic feedback |")
        L.append("|---|---|---|---|---|---|---|")
        for i, e in enumerate(reversed(recent), 1):
            sec_short = (e.get("section", "") or "").split("/")[-1]
            L.append(
                f"| {i} | {e.get('project','')} | `{_excerpt(sec_short, 28)}` | "
                f"{e.get('pk','')} | {_excerpt(e.get('english',''), 60)} | "
                f"{_excerpt(e.get('current_hebrew',''), 60)} | "
                f"{_excerpt(e.get('critic_feedback',''), 90)} |"
            )
    L.append("")
    L.append("---")
    L.append("_Generated by `get_next_audit_batch.py` — read-only audit, "
             "source JSONs untouched._")
    atomic_write(DASHBOARD, "\n".join(L) + "\n")


# ── subcommands ─────────────────────────────────────────────────────────────
def cmd_next(size: int) -> int:
    state = load_checkpoint()
    start = state.get("last_index", 0)

    corpus, base_total, dlc_total = build_corpus()
    total = len(corpus)
    end = min(start + size, total)
    slice_ = corpus[start:end]

    # initialise totals on first run (or refresh if the corpus grew)
    if not state.get("base_total"):
        state["base_total"] = base_total
        state["dlc_total"]  = dlc_total

    if not slice_:
        out = {
            "batch_index": start,
            "batch_size":  0,
            "total_rows":  total,
            "progress_pct": 100.0,
            "done":        True,
            "rows":        [],
        }
        atomic_write(BATCH_FILE,
                     json.dumps(out, ensure_ascii=False, indent=2))
        print(f"[done] no more rows — at {start:,}/{total:,}")
        return 0

    rows_out = [
        {
            "project": r.project,
            "section": r.section,
            "pk":      r.pk,
            "field":   r.field,
            "english": r.english,
            "hebrew":  r.hebrew,
        }
        for r in slice_
    ]
    new_index = start + len(slice_)

    base_in_batch = sum(1 for r in slice_ if r.project == "base")
    dlc_in_batch  = len(slice_) - base_in_batch
    state["base_done"] = state.get("base_done", 0) + base_in_batch
    state["dlc_done"]  = state.get("dlc_done",  0) + dlc_in_batch
    state["processed"] = state.get("processed", 0) + len(slice_)
    state["last_index"] = new_index
    save_checkpoint(state)
    render_dashboard(state)

    out = {
        "batch_index":  start,
        "batch_size":   len(slice_),
        "next_index":   new_index,
        "total_rows":   total,
        "progress_pct": round(new_index / total * 100, 4) if total else 0.0,
        "rows":         rows_out,
    }
    atomic_write(BATCH_FILE, json.dumps(out, ensure_ascii=False, indent=2))
    print(f"[ok] batch {start:,}..{new_index - 1:,} of {total:,} "
          f"({out['progress_pct']:.4f}%) -> {os.path.basename(BATCH_FILE)}")
    return 0


def cmd_flag(file_path: str | None = None) -> int:
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
        except OSError as e:
            print(f"ERROR: cannot read {file_path}: {e}", file=sys.stderr)
            return 1
    else:
        raw = sys.stdin.read().strip()
    if not raw:
        print("ERROR: no JSON input", file=sys.stderr)
        return 1
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 1

    records = data if isinstance(data, list) else [data]
    required = ("project", "section", "pk", "field",
                "english", "hebrew", "critic_feedback")
    appended = 0
    with open(FLAGS_FILE, "a", encoding="utf-8") as f:
        for rec in records:
            if not isinstance(rec, dict):
                print(f"ERROR: non-object record: {rec!r}", file=sys.stderr)
                return 1
            missing = [k for k in required if k not in rec]
            if missing:
                print(f"ERROR: missing fields {missing} in {rec!r}",
                      file=sys.stderr)
                return 1
            entry = {
                "ts":              time.strftime("%Y-%m-%d %H:%M:%S"),
                "project":         rec["project"],
                "section":         rec["section"],
                "pk":              rec["pk"],
                "field":           rec["field"],
                "english":         rec["english"],
                "current_hebrew":  rec["hebrew"],
                "critic_feedback": rec["critic_feedback"],
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            appended += 1

    state = load_checkpoint()
    state["flagged"] = count_existing_flags()
    save_checkpoint(state)
    render_dashboard(state)
    print(f"[ok] appended {appended} flag(s); total flagged: {state['flagged']}")
    return 0


def cmd_dashboard() -> int:
    state = load_checkpoint()
    state["flagged"] = count_existing_flags()
    save_checkpoint(state)
    render_dashboard(state)
    print(f"[ok] dashboard refreshed -> {os.path.basename(DASHBOARD)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd")
    pn = sub.add_parser("next", help="emit next batch of rows")
    pn.add_argument("--size", type=int, default=10)
    pf = sub.add_parser("flag", help="append flag(s) from stdin JSON")
    pf.add_argument("--file", default=None,
                    help="read JSON from this file instead of stdin "
                         "(avoids PowerShell console-encoding issues)")
    sub.add_parser("dashboard", help="refresh dashboard only")
    args = p.parse_args()
    if args.cmd == "next":
        return cmd_next(args.size)
    if args.cmd == "flag":
        return cmd_flag(args.file)
    if args.cmd == "dashboard":
        return cmd_dashboard()
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
