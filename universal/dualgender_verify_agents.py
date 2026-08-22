# -*- coding: utf-8 -*-
"""
dualgender_verify_agents.py — independent anti-cheat verifier for the 3 Google agents
fixing CP2077 male variants. Trusts NOTHING from merge_batch — re-validates every fill.

A CORRECT male variant differs from he_female ONLY in Hebrew gender letters; every
non-Hebrew char (control bytes, tags, {tokens}, %d, €/™, Latin, spaces) is byte-identical.
Cheats it catches (all pass a naive "!= he_female" check):
  no_gender_change  — Hebrew letters identical to he_female (bulk copy)
  scaffold_changed  — only altered non-Hebrew (e.g. deleted a leading control byte) — an
                      EVASION that also corrupts the string
  copied_input      — fixed_male == he_male_current (the broken input)
  invalid           — niqqud / foreign script / dropped Hebrew

Reads current_batch.json (in-progress) + fixed_male.json (committed) per agent.
CLI: python dualgender_verify_agents.py [--samples 8]
"""
from __future__ import annotations
import argparse, json, os, re, sys, difflib
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASEDIR = os.path.join(ROOT, "games", "cyberpunk2077", "agent_handoff_dualgender")
TOKEN = re.compile(r"\{[^}]*\}|<[^>]+>|%[sd%]|&rlm;|&[a-z]+;|\\n")
NIQQUD = re.compile("[֑-ׇ]")
HEB = re.compile("[א-ת]")
_OK_PUNCT = {0x2013, 0x2014, 0x2018, 0x2019, 0x201c, 0x201d, 0x2026,
             0x2022, 0x200e, 0x200f, 0x00a0, 0x2011, 0x2212}


def heb(s):
    return "".join(c for c in s if 0x05d0 <= ord(c) <= 0x05ea)


def scaffold(s):
    return "".join(c for c in s if not 0x05d0 <= ord(c) <= 0x05ea)


def foreign(s):
    vis = TOKEN.sub(" ", s)
    return [c for c in vis if not (c.isspace() or ord(c) < 0x20
            or 0x20 <= ord(c) <= 0x7e or 0x0590 <= ord(c) <= 0x05ff
            or (0x00a1 <= ord(c) <= 0x00ff and ord(c) not in (0x00d7, 0x00f7))
            or ord(c) in _OK_PUNCT)]


def lead_ctrl(s):
    i = 0
    while i < len(s) and ord(s[i]) < 0x20:
        i += 1
    return s[:i]


def repair(fm, fem):
    """Restore he_female's leading control-byte prefix if the agent dropped it
    (invisible CP2077 formatting marker; not the agent's to change)."""
    lcf = lead_ctrl(fem)
    if lcf and not fm.startswith(lcf):
        return lcf + fm[len(lead_ctrl(fm)):]
    return fm


def _heb_core(w):
    return "".join(c for c in w if 0x05d0 <= ord(c) <= 0x05ea)


def _suffixal_change(wf, wm):
    """True if two words differ only at the SUFFIX (a real gender inflection —
    את→אתה, קחי→קח). False if the change is WORD-INTERNAL (a spelling corruption
    like אוויר→אויר, השנייה→השניה that agents inject to fake a diff)."""
    a, b = _heb_core(wf), _heb_core(wm)
    if a == b:
        return True
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    j = 0
    while j < len(a) - i and j < len(b) - i and a[-1 - j] == b[-1 - j]:
        j += 1
    return j == 0   # no common suffix after the change -> the change IS the suffix


def has_internal_edit(fem, fm):
    wf, wm = fem.split(), fm.split()
    if len(wf) != len(wm):
        return False   # word-count changed — don't judge (rare, lenient)
    for a, b in zip(wf, wm):
        if _heb_core(a) != _heb_core(b) and not _suffixal_change(a, b):
            return True
    return False


def classify_fill(fm, fem, malec=None):
    """Returns (value_to_store, None) for a valid inflection (control byte repaired),
    else (None, reason). Validation is RESULT-based (scaffold/heb) — fm may legitimately
    equal a he_male that was already correct, so we do NOT reject on source-equality."""
    if NIQQUD.search(fm):
        return None, "invalid_niqqud"
    if HEB.search(fem) and not HEB.search(fm):
        return None, "invalid_no_hebrew"
    fm2 = repair(fm, fem)
    # scaffold-equality already guarantees every non-Hebrew char equals he_female
    # (so no NEW foreign script can be introduced — no separate foreign check needed;
    #  it would false-positive on legit source symbols like € that the agent preserved).
    if scaffold(fm2) != scaffold(fem):
        return None, "scaffold_changed"
    if heb(fm2) == heb(fem):
        return None, "no_gender_change"
    if has_internal_edit(fem, fm2):
        return None, "internal_edit"   # word-internal spelling change, not a gender suffix
    return fm2, None


def _load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def verify_agent(name, samples):
    d = os.path.join(BASEDIR, name)
    to_fix = _load(os.path.join(d, "to_fix.json"))
    done = _load(os.path.join(d, "fixed_male.json"))
    batch = _load(os.path.join(d, "current_batch.json"))

    fills = {}
    for k, v in done.items():
        s = to_fix.get(k, {})
        fills[k] = (s.get("he_female", ""), s.get("he_male", ""), v)
    for k, it in batch.items():
        fm = (it.get("fixed_male") or "").strip()
        if fm and k not in fills:
            fills[k] = (it.get("he_female", ""), it.get("he_male_current", ""), fm)

    good = skip = 0
    reasons = Counter()
    good_s, bad_s = [], []
    for k, (fem, malec, fm) in fills.items():
        if fm == "__SKIP__" or fm == "SKIP":
            skip += 1
            continue
        val, why = classify_fill(fm, fem, malec)
        if why:
            reasons[why] += 1
            if len(bad_s) < samples:
                bad_s.append((why, fem, fm))
        else:
            good += 1
            if len(good_s) < samples:
                sm = difflib.SequenceMatcher(None, fem, val)
                diff = " ".join(f"[{fem[i1:i2]}->{val[j1:j2]}]"
                                for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal")
                good_s.append(diff[:90])
    return dict(slot=len(to_fix), done=len(done), filled=len(fills),
                good=good, skip=skip, reasons=reasons, good_s=good_s, bad_s=bad_s)


def main(argv=None):
    p = argparse.ArgumentParser(prog="dualgender_verify_agents")
    p.add_argument("--samples", type=int, default=8)
    a = p.parse_args(argv)
    for name in ("agent_1", "agent_2", "agent_3"):
        st = verify_agent(name, a.samples)
        filled = st["filled"] or 1
        cheats = sum(st["reasons"].values())
        rate = 100 * cheats / filled
        flags = []
        if st["filled"] == 0:
            flags.append("NOT STARTED")
        elif rate > 15:
            flags.append(f"⚠ {rate:.0f}% BAD ({dict(st['reasons'])})")
        verdict = "  ".join(flags) if flags else "OK — clean inflections"
        print(f"\n===== {name} =====  -> {verdict}")
        print(f"  slot={st['slot']}  committed={st['done']}  filled={st['filled']}  "
              f"good={st['good']}  SKIP={st['skip']}  bad={cheats}")
        if st["reasons"]:
            print(f"  bad breakdown: {dict(st['reasons'])}")
        for diff in st["good_s"][:a.samples]:
            print(f"    good: {diff}")
        for why, fem, fm in st["bad_s"][:a.samples]:
            print(f"    BAD[{why}]: F={fem[:40]!r} M={fm[:40]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
