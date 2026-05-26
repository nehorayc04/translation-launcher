"""
cp2077_dlc_translate.py
=======================
Translates the Phantom Liberty DLC to Hebrew — operates on
dlc_ep1_translated.json (built by cp2077_dlc_build.py).

Reuses the proven base-game translation core rather than re-implementing it:
  * plain entries  -> translate_queue_fast.translate_batch / translate_one
                      (dynamic batches, 4 concurrent LM Studio workers,
                       tag-preservation + Hebrew validation built in)
  * markup entries -> cp2077_markup_translate's FIXED/TRANS slot model
                      (<kiroshi>/<mothertongue>/<Rich> — translate only the TR
                       slots, foreign o/m attributes copied verbatim)

dlc_ep1_translated.json IS the state: an entry whose femaleVariant still holds
its English value is untranslated; one carrying Hebrew is done. So the run is
fully resumable — re-running picks up exactly where it stopped. The file is
checkpointed atomically every SAVE_EVERY entries.

Monitor: writes the marker lines cp2077_monitor.py expects to
fix_missing_translations.log, so the live TUI / website track DLC progress.

Run: python cp2077_dlc_translate.py [--markup-only] [--plain-only]
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# translate_queue_fast and cp2077_markup_translate each replace sys.stdout /
# sys.stderr with a fresh UTF-8 TextIOWrapper at import time. Importing both
# orphans the first pair — and an orphaned TextIOWrapper, once deallocated,
# CLOSES the shared underlying buffer, which would break every later print().
# Pinning the orphaned wrappers in _KEEP_STREAMS prevents that dealloc.
import translate_queue_fast as tqf
_KEEP_STREAMS = [sys.stdout, sys.stderr]
import cp2077_markup_translate as mk
_KEEP_STREAMS += [sys.stdout, sys.stderr]
from openai import OpenAI

RES = os.path.join(_HERE, "תרגום_משחקים", "source", "resources")
DLC_TRANSLATED = os.path.join(RES, "dlc_ep1_translated.json")
LOG_FILE    = os.path.join(_HERE, "cp2077_dlc_translate.log")
MONITOR_LOG = os.path.join(_HERE, "fix_missing_translations.log")

HEB    = re.compile(r"[֐-׿]")
LETTER = re.compile(r"[A-Za-z]")
MARKUP = ("<kiroshi", "<mothertongue", "<Rich")

SAVE_EVERY = 200
MARKUP_SAVE_EVERY = 50
_save_lock = threading.Lock()
_log_lock  = threading.Lock()


def log(msg: str, *, monitor: bool = True) -> None:
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


def is_markup(v: str) -> bool:
    return bool(v) and any(m in v for m in MARKUP)


def markup_done(v: str) -> bool:
    """True when every TR slot of a markup value already carries Hebrew."""
    slots = mk.parse_slots(v)
    if slots is None:
        return True                       # damaged — leave it, not our job
    tr = [t for k, t in slots if k == "TR"]
    return (not tr) or all(HEB.search(t) for t in tr)


def translate_markup(value: str) -> str | None:
    """Translate a markup value's TR slots; foreign o/m attrs stay verbatim."""
    slots = mk.parse_slots(value)
    if slots is None:
        return None
    tr_texts = [t for k, t in slots if k == "TR"]
    if not tr_texts:
        return None
    hebrew = mk.translate_pieces(tr_texts)
    rebuilt, hi = [], 0
    for kind, text in slots:
        if kind == "TR":
            he = hebrew[hi] if hi < len(hebrew) else ""
            hi += 1
            rebuilt.append(("TR", he if mk.valid_piece(text, he) else text))
        else:
            rebuilt.append((kind, text))
    return mk.reassemble(rebuilt)


def collect_work(dlc: dict):
    """[(entry, field, english)] for plain + markup, only the untranslated."""
    plain, markup = [], []
    for sec, rows in dlc.items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            for fld in ("femaleVariant", "maleVariant"):
                v = e.get(fld) or ""
                if not v or not LETTER.search(v):
                    continue                       # empty / pure code -> skip
                if is_markup(v):
                    if not markup_done(v):
                        markup.append((e, fld, v))
                elif not HEB.search(v):
                    plain.append((e, fld, v))      # English -> needs LM
    return plain, markup


def main() -> int:
    markup_only = "--markup-only" in sys.argv
    plain_only  = "--plain-only" in sys.argv

    if not os.path.exists(DLC_TRANSLATED):
        sys.exit(f"FATAL: missing {DLC_TRANSLATED} — run cp2077_dlc_build.py first.")

    client = OpenAI(base_url=tqf.LM_URL, api_key="lm-studio", timeout=600)
    tqf.lm_client = client
    tqf.TEMPERATURE = tqf.DEFAULT_TEMP
    mk.lm_client = client

    log("[*] Using LM Studio (Gemma-2-27b)")
    log(f"[started: {time.strftime('%Y-%m-%d %H:%M:%S')}]")
    log("[*] Preflight: pinging LM Studio …", monitor=False)
    try:
        tqf.translate_one("Apply")
    except Exception as e:                                  # noqa: BLE001
        sys.exit(f"FATAL: cannot reach LM Studio — {e}")
    log("[*] Preflight OK", monitor=False)

    log(f"[*] Loading {DLC_TRANSLATED}", monitor=False)
    with open(DLC_TRANSLATED, "r", encoding="utf-8") as f:
        dlc = json.load(f)

    plain, markup = collect_work(dlc)

    # --limit N : cap each pass (verification runs before the full ~50h run)
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
    if limit is not None:
        plain, markup = plain[:limit], markup[:limit]
        log(f"[*] --limit {limit}: capped to {len(plain)} plain + "
            f"{len(markup)} markup", monitor=False)

    total = len(plain) + len(markup)
    log(f"[*] Global queue: {total:,} pending items "
        f"({len(plain):,} plain + {len(markup):,} markup)")
    if total == 0:
        log("[*] Done. Fixed 0 fields (nothing to do).")
        return 0

    done = 0

    def checkpoint(tag: str) -> None:
        with _save_lock:
            tqf._atomic_write_json(DLC_TRANSLATED, dlc)
        log(f"  [~] Saved — {done:,} fixed, ~{total - done:,} remaining")

    # ── markup pass (4 workers — same pool size as the plain pass) ───────
    # translate_markup runs in worker threads (4 concurrent LM calls); the
    # result handling (done++, entry write, checkpoint) stays in the main
    # thread via as_completed, so no lock is needed around it.
    if not plain_only and markup:
        log(f"[*] Markup pass: {len(markup):,} entries — "
            f"{tqf.PARALLEL_WORKERS} workers")

        def _do_markup(item):
            try:
                return item, translate_markup(item[2])
            except Exception:                               # noqa: BLE001
                return item, None

        with ThreadPoolExecutor(max_workers=tqf.PARALLEL_WORKERS) as pool:
            futs = [pool.submit(_do_markup, it) for it in markup]
            for fut in as_completed(futs):
                (entry, fld, _eng), out = fut.result()
                if out and HEB.search(out):
                    entry[fld] = out
                    # per-entry arrow line — the monitor counts these for a
                    # smooth live rate (it can't, off the ~18-min checkpoints)
                    log(f"  dlc-mk {_eng[:30]!r} → {out[:46]!r}")
                done += 1
                if done % MARKUP_SAVE_EVERY == 0:
                    checkpoint("markup")
        checkpoint("markup-done")

    # ── plain pass (bulk — dynamic batches, 4 workers) ───────────────────
    if not markup_only and plain:
        log(f"[*] Plain pass: {len(plain):,} entries — dynamic batches, "
            f"{tqf.PARALLEL_WORKERS} workers", monitor=False)
        batches = list(tqf.build_dynamic_batches(plain, lambda it: it[2]))
        log(f"[*] Phase 3: {len(batches):,} batches, "
            f"{tqf.PARALLEL_WORKERS} concurrent workers")

        def do_batch(batch):
            texts = [eng for _e, _f, eng in batch]
            if len(texts) == 1:
                return [tqf.translate_one(texts[0])]
            return tqf.translate_batch(texts)

        with ThreadPoolExecutor(max_workers=tqf.PARALLEL_WORKERS) as pool:
            futs = {pool.submit(do_batch, b): b for b in batches}
            for fut in as_completed(futs):
                batch = futs[fut]
                try:
                    res = fut.result()
                except Exception as e:                      # noqa: BLE001
                    log(f"  [!] batch error: {e}", monitor=False)
                    res = [eng for _e, _f, eng in batch]
                with _save_lock:
                    for k, (entry, fld, eng) in enumerate(batch):
                        he = res[k] if k < len(res) else eng
                        if tqf.is_valid_translation(eng, he):
                            entry[fld] = he
                            # per-entry arrow line — gives the monitor a
                            # smooth live rate instead of 18-min checkpoint jumps
                            log(f"  dlc {eng[:34]!r} → {he[:46]!r}")
                        done += 1
                if done % SAVE_EVERY < len(batch):          # crossed a boundary
                    checkpoint("plain")

    with _save_lock:
        tqf._atomic_write_json(DLC_TRANSLATED, dlc)
    log(f"[*] Done. Fixed {done:,} fields.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
