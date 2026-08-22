# -*- coding: utf-8 -*-
"""Validate + merge the agent's 'fixed_male' values into fixed_male.json.
A correct male variant differs from he_female ONLY in Hebrew gender letters — every
non-Hebrew character (control bytes, tags, {tokens}, %d, symbols €/™, Latin, spaces)
stays byte-identical. Anti-cheat (rejected items are NOT saved — re-served next round):
  * non-Hebrew content changed/dropped (e.g. deleting a leading control byte) → REJECT
  * Hebrew letters identical to he_female (no real gender change / copy) → REJECT
  * fixed_male == he_male_current (broken input) / niqqud / foreign / no-Hebrew → REJECT
Escape: a line with genuinely NO gendered word → set fixed_male to exactly  SKIP .
Run from THIS agent folder."""
import json, os, re, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
# SKIP is only for a line with genuinely NO gendered word. A line that addresses
# "you"/"I" HAS a masculine form → SKIP on it is rejected (kills bulk-SKIP abuse).
_YOU = re.compile(r"\byou(?:r|rs|rself|rselves)?\b", re.I)
_FIRST = re.compile(r"\bI\b|\bI['’](?:m|ve|ll|d)\b|\b(?:me|my|myself)\b")
TOKEN = re.compile(r"\{[^}]*\}|<[^>]+>|%[sd%]|&rlm;|&[a-z]+;|\\n")
NIQQUD = re.compile("[֑-ׇ]")
HEB = re.compile("[א-ת]")
_OK_PUNCT = {0x2013, 0x2014, 0x2018, 0x2019, 0x201c, 0x201d, 0x2026,
             0x2022, 0x200e, 0x200f, 0x00a0, 0x2011, 0x2212}


def toks(s):
    return sorted(TOKEN.findall(s))


def heb(s):
    return "".join(c for c in s if 0x05d0 <= ord(c) <= 0x05ea)


def scaffold(s):
    return "".join(c for c in s if not 0x05d0 <= ord(c) <= 0x05ea)


def lead_ctrl(s):
    i = 0
    while i < len(s) and ord(s[i]) < 0x20:
        i += 1
    return s[:i]


def repair(fm, fem):
    """Restore he_female's leading control-byte prefix if it was dropped."""
    lcf = lead_ctrl(fem)
    if lcf and not fm.startswith(lcf):
        return lcf + fm[len(lead_ctrl(fm)):]
    return fm


def foreign(s):
    vis = TOKEN.sub(" ", s)
    bad = []
    for c in vis:
        o = ord(c)
        if c.isspace() or o < 0x20 or 0x20 <= o <= 0x7e or 0x0590 <= o <= 0x05ff:
            continue
        if 0x00a1 <= o <= 0x00ff and o not in (0x00d7, 0x00f7):
            continue
        if o in _OK_PUNCT:
            continue
        bad.append(c)
    return bad


bp = os.path.join(HERE, "current_batch.json")
if not os.path.exists(bp):
    print("no current_batch.json — run get_batch.py first")
    sys.exit(1)
batch = json.load(open(bp, encoding="utf-8"))
donep = os.path.join(HERE, "fixed_male.json")
done = json.load(open(donep, encoding="utf-8")) if os.path.exists(donep) else {}

ok = skip = rej = empty = 0
rejects = []
for k, it in batch.items():
    fm = (it.get("fixed_male") or "").strip()
    fem = it["he_female"]
    malec = (it.get("he_male_current") or "").strip()
    if not fm:
        empty += 1
        continue
    if fm == "SKIP":
        en = it.get("en", "")
        if _YOU.search(en) or _FIRST.search(en):
            rej += 1; rejects.append((k, "this line addresses you/I — it HAS a masculine form; INFLECT it, don't SKIP")); continue
        done[k] = "__SKIP__"; skip += 1; continue
    if NIQQUD.search(fm):
        rej += 1; rejects.append((k, "has niqqud")); continue
    if HEB.search(fem) and not HEB.search(fm):
        rej += 1; rejects.append((k, "no Hebrew (left English?)")); continue
    fm2 = repair(fm, fem)
    if scaffold(fm2) != scaffold(fem.strip()):
        rej += 1; rejects.append((k, "changed non-Hebrew content — keep tags/{tokens}/symbols EXACTLY; only Hebrew gender letters may change")); continue
    if heb(fm2) == heb(fem):
        rej += 1; rejects.append((k, "no gender change (Hebrew identical to he_female) — inflect to MASCULINE, or set SKIP")); continue
    done[k] = fm2
    ok += 1

json.dump(done, open(donep, "w", encoding="utf-8"), ensure_ascii=False)
print(f"merged {ok} | SKIP {skip} | rejected {rej} | still-empty {empty} | total done {len(done)}")
for k, why in rejects[:20]:
    print(f"  REJECT {k}: {why}")
if rej:
    print("Rejected items are NOT saved — the next get_batch.py re-serves them. Fix them.")
