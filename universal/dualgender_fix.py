# -*- coding: utf-8 -*-
"""
dualgender_fix.py — deterministic (zero-LM) fixer for the dual-gender guard's
`collapse` bucket: lines whose ENGLISH is gender-NEUTRAL yet the run produced a
different maleVariant — they should never have been split, so set M = F.

SAFE against the live fleet (which writes the same spine):
  * per-entry guard — write M=F ONLY when the CURRENT maleVariant still equals the
    value the scan recorded (`he_male`). If the fleet re-translated M since the scan,
    skip it (a re-scan will re-evaluate) — never clobber concurrent progress.
  * uses the existing games/cyberpunk2077/qa.lock (best-effort serialisation).
  * per-file backup (.bak.dgfix.<ts>) + atomic write (temp + os.replace, retries)
    → a running bake reads either the whole old or the whole new file, never torn.

Does NOT touch token_only / gender_redo / stale_english_m — those need judgement or
translation (delegated). CLI: `dualgender_fix.py [--apply]` (default = dry-run).
"""
from __future__ import annotations
import argparse, json, os, shutil, sys, time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
SPINE = {
    "base": os.path.join(RES, "localization_translated.json"),
    "dlc": os.path.join(RES, "dlc_ep1_translated.json"),
}
WORKLIST = os.path.join(HERE, "cp2077_dualgender_suspects.jsonl")
LOCK_FILE = os.path.join(ROOT, "games", "cyberpunk2077", "qa.lock")
LOCK_STALE_SEC = 3 * 3600


# ── lock (compatible with cp2077_qa_defects.qa.lock format) ──────────────────
def acquire_lock(holder: str) -> bool:
    if os.path.exists(LOCK_FILE):
        try:
            info = json.load(open(LOCK_FILE, encoding="utf-8"))
            if time.time() - float(info.get("ts", 0)) < LOCK_STALE_SEC:
                print(f"  qa.lock held by {info.get('holder')!r} — aborting.")
                return False
        except Exception:
            pass
    try:
        json.dump({"holder": holder, "ts": time.time()},
                  open(LOCK_FILE, "w", encoding="utf-8"))
        return True
    except Exception as e:
        print(f"  lock write failed: {e}")
        return False


def release_lock() -> None:
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass


def atomic_write_json(path: str, data, retries: int = 6) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    for i in range(retries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.5 * (i + 1))
    os.replace(tmp, path)  # last try — let it raise


def _entry_key(e):
    pk = e.get("primaryKey")
    return str(pk) if pk is not None else str(e.get("stringId"))


def run(apply: bool) -> int:
    if not os.path.exists(WORKLIST):
        print(f"no worklist at {WORKLIST} — run dualgender_guard.py scan first.")
        return 1
    collapse = []
    with open(WORKLIST, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("bucket") == "collapse":
                collapse.append(r)
    print(f"collapse candidates in worklist: {len(collapse):,}")

    # group by src
    by_src = {"base": [], "dlc": []}
    for r in collapse:
        by_src.get(r["src"], by_src["base"]).append(r)

    stats = {"applied": 0, "skip_gone": 0, "skip_changed": 0,
             "skip_already": 0, "skip_no_f": 0}
    changed_files = []

    for src, rows in by_src.items():
        if not rows:
            continue
        path = SPINE[src]
        spine = json.load(open(path, encoding="utf-8"))
        # index: section -> {key: entry}
        idx = {}
        for sec, lst in spine.items():
            if isinstance(lst, list):
                idx[sec] = {_entry_key(e): e for e in lst if isinstance(e, dict)}
        dirty = 0
        for r in rows:
            e = idx.get(r["section"], {}).get(r["key"])
            if e is None:
                stats["skip_gone"] += 1
                continue
            f_cur = (e.get("femaleVariant") or "").strip()
            m_cur = (e.get("maleVariant") or "").strip()
            if not f_cur:
                stats["skip_no_f"] += 1
                continue
            if m_cur == f_cur:
                stats["skip_already"] += 1
                continue
            # SAFETY: only touch entries the fleet hasn't changed since the scan.
            if m_cur != (r.get("he_male") or "").strip():
                stats["skip_changed"] += 1
                continue
            if apply:
                e["maleVariant"] = e.get("femaleVariant")  # exact copy (keep raw)
            stats["applied"] += 1
            dirty += 1
        if apply and dirty:
            bak = f"{path}.bak.dgfix.{time.strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(path, bak)
            atomic_write_json(path, spine)
            changed_files.append((os.path.basename(path), dirty, os.path.basename(bak)))

    print("\n" + ("APPLIED" if apply else "DRY-RUN") + " results:")
    for k, v in stats.items():
        print(f"    {k:14s}: {v:,}")
    if apply:
        for name, n, bak in changed_files:
            print(f"  wrote {name}: {n:,} M=F  (backup {bak})")
        print("\n  NOTE: reaches the game only on the NEXT bake "
              "(rebuild_onscreens/subtitles/dlc + pack).")
    else:
        print("\n  (dry-run — re-run with --apply to write the spine)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dualgender_fix")
    p.add_argument("--apply", action="store_true", help="write the spine (default: dry-run)")
    a = p.parse_args(argv)
    if a.apply:
        if not acquire_lock("dualgender_fix"):
            return 1
        try:
            return run(True)
        finally:
            release_lock()
    return run(False)


if __name__ == "__main__":
    raise SystemExit(main())
