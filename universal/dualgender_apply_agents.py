# -*- coding: utf-8 -*-
"""
dualgender_apply_agents.py — apply the verified male-variant fixes (agent inflections
+ the deterministic inflector + M=F for neutral) from the 3 agent folders back into the
CP2077 spine, with the same safety as dualgender_fix.

Per entry:
  * value "__SKIP__"  → maleVariant = femaleVariant (gender-neutral line)
  * else              → maleVariant = the validated inflection
SAFETY: writes ONLY when the CURRENT femaleVariant AND maleVariant still equal what the
scan recorded (to_fix he_female / he_male) — so a concurrent fleet write is never
clobbered. Re-validates every inflection against the current female (classify_fill) at
apply time. qa.lock + per-file .bak.dgapply.<ts> backup + atomic os.replace.

CLI: python dualgender_apply_agents.py            # dry-run
     python dualgender_apply_agents.py --apply
"""
from __future__ import annotations
import argparse, json, os, shutil, sys, time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dualgender_verify_agents import classify_fill, repair
from dualgender_fix import acquire_lock, release_lock, atomic_write_json, _entry_key

ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
SPINE = {"base": os.path.join(RES, "localization_translated.json"),
         "dlc": os.path.join(RES, "dlc_ep1_translated.json")}
BASEDIR = os.path.join(ROOT, "games", "cyberpunk2077", "agent_handoff_dualgender")


def _collect():
    """Return {src: [(section, key, target_or_SKIP, he_female, he_male), ...]}."""
    out = {"base": [], "dlc": []}
    for name in ("agent_1", "agent_2", "agent_3"):
        d = os.path.join(BASEDIR, name)
        tf = json.load(open(os.path.join(d, "to_fix.json"), encoding="utf-8"))
        fp = os.path.join(d, "fixed_male.json")
        if not os.path.exists(fp):
            continue
        done = json.load(open(fp, encoding="utf-8"))
        for cid, val in done.items():
            src, rest = cid.split("|", 1)
            section, key = rest.rsplit("|", 1)
            s = tf.get(cid, {})
            out.setdefault(src, []).append(
                (section, key, val, s.get("he_female", ""), s.get("he_male", "")))
    return out


def run(apply: bool) -> int:
    data = _collect()
    stats = dict(inflect=0, skip=0, skip_changed=0, skip_already=0, revalidate_fail=0, missing=0)
    changed_files = []
    for src, rows in data.items():
        if not rows:
            continue
        path = SPINE[src]
        spine = json.load(open(path, encoding="utf-8"))
        idx = {}
        for sec, lst in spine.items():
            if isinstance(lst, list):
                idx[sec] = {_entry_key(e): e for e in lst if isinstance(e, dict)}
        dirty = 0
        for section, key, val, he_f, he_m in rows:
            e = idx.get(section, {}).get(key)
            if e is None:
                stats["missing"] += 1
                continue
            f_cur = (e.get("femaleVariant") or "")
            m_cur = (e.get("maleVariant") or "")
            # SAFETY: only touch entries the fleet hasn't changed since the scan.
            if f_cur.strip() != (he_f or "").strip() or m_cur.strip() != (he_m or "").strip():
                stats["skip_changed"] += 1
                continue
            if val == "__SKIP__":
                target = e.get("femaleVariant")           # M = F (keep raw female)
            else:
                # re-validate the inflection against the CURRENT female
                ok, why = classify_fill(val, f_cur, "")
                if why:
                    stats["revalidate_fail"] += 1
                    continue
                target = repair(val, f_cur)
            if (e.get("maleVariant") or "") == (target or ""):
                stats["skip_already"] += 1
                continue
            if apply:
                e["maleVariant"] = target
            stats["inflect" if val != "__SKIP__" else "skip"] += 1
            dirty += 1
        if apply and dirty:
            bak = f"{path}.bak.dgapply.{time.strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(path, bak)
            atomic_write_json(path, spine)
            changed_files.append((os.path.basename(path), dirty, os.path.basename(bak)))

    print(("APPLIED" if apply else "DRY-RUN") + " — male-variant fixes:")
    print(f"    real inflections written : {stats['inflect']:,}")
    print(f"    M=F (neutral) written    : {stats['skip']:,}")
    print(f"    skipped (fleet changed)  : {stats['skip_changed']:,}")
    print(f"    skipped (already set)    : {stats['skip_already']:,}")
    print(f"    re-validate fail         : {stats['revalidate_fail']:,}")
    print(f"    missing in spine         : {stats['missing']:,}")
    for name, n, bak in changed_files:
        print(f"  wrote {name}: {n:,} entries  (backup {bak})")
    if apply:
        print("\n  reaches the game on the NEXT bake.")
    else:
        print("\n  (dry-run — re-run with --apply)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dualgender_apply_agents")
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    if a.apply:
        if not acquire_lock("dualgender_apply_agents"):
            return 1
        try:
            return run(True)
        finally:
            release_lock()
    return run(False)


if __name__ == "__main__":
    raise SystemExit(main())
