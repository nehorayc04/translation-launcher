"""qa_verify.py — INDEPENDENT guard-dog sweep over the agents' corrections.

Run AFTER the agents finish, BEFORE apply_corrections.py. The GoWR lesson: never
trust the agents' own merge-time check. This re-validates every accepted
correction against the full corpus PER-AGENT, with checks qa_merge can't do:
junk-pattern detection (the observed cheat: a script that appends a random "."
to clear the fix-density floor), trivial no-op edits, truncation, and cross-agent
name consistency. READ-ONLY — never writes the spine.

Per fix:
  - markup/placeholder tokens preserved vs the original (struct_tokens); parseable
  - no foreign script, no niqqud, has Hebrew (unless EN is a name/code)
  - punct_append  : new == old + only trailing punctuation  (density-gaming junk)
  - trivial       : new == old ignoring trailing punctuation/space (no real change)
  - truncated     : ends on a dangling Hebrew connector / far shorter than EN
  - inconsistent  : same EN source -> different Hebrew across agents

Per agent it prints total fixes + a JUNK fraction; a high junk fraction = a
scripted/cheating agent whose slice must be redone (don't apply it).

Usage: python qa_verify.py            (report)
       python qa_verify.py --clean    (also write verified_corrections.json =
                                        corrections minus junk/invalid, for apply)
"""
import json, os, re, sys, glob
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
CP = os.path.dirname(HERE)
sys.path.insert(0, CP)
import cp2077_markup_translate as mk

NIQQUD = re.compile(r'[֑-ׇ]')
FOREIGN = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿'
                     r'ऀ-ॿ一-鿿가-힯぀-ヿĀ-ɏ]')
HEB = re.compile(r'[א-ת]')
DANGLING = re.compile(r'(?:^|\s)(?:ו|של|את|אל|על|עם|כי|אבל|או|גם|כדי|לפני|אחרי|בגלל|ב|ל|מ|ה|ש)$')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+ ]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
TRAIL = re.compile(r'[\s.?!…:,;״"\'\-־)]+$')


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def strip_ctrl(s):
    return s[1:] if s and 0x01 <= ord(s[0]) <= 0x05 else s


def norm(s):
    return strip_ctrl(s or "").strip()


def struct_tokens(s):
    return Counter(STRUCT.findall(strip_ctrl(s or "")))


def match_newlines(old, new):
    """Preserve old's line-break convention. CP2077 multi-line strings use a LITERAL
    backslash-n; an agent that rewrote the line often turned it into a real newline
    (the GoWR \\n regression). If old used literal \\n (and no real newline), convert
    new's real newlines back to literal \\n."""
    if "\\n" in old and "\n" not in old and "\n" in new:
        return new.replace("\n", "\\n")
    return new


def is_namey(en):
    core = re.sub(r'<[^>]*>|\{[^}]*\}', "", en).strip()
    words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
    return (bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)) \
        or not re.search(r'[a-z]{2,}', core)


def visible(s):
    return re.sub(r'<[^>]*>|\{[^}]*\}|%[#0-9.lhs%d]+|&[a-zA-Z#0-9]+;', "", s).strip()


def punct_append(old, new):
    """new is old with ONLY trailing punctuation/space tacked on (the density cheat)."""
    o, n = norm(old), norm(new)
    return n != o and n.startswith(o) and bool(n[len(o):]) and \
        all(c in ".?!…:,;״\"' " for c in n[len(o):])


def trivial(old, new):
    """new differs from old only by trailing punctuation/whitespace -> no real fix."""
    return TRAIL.sub("", norm(old)) == TRAIL.sub("", norm(new))


def ws_only(old, new):
    """new differs from old ONLY by whitespace (inserted double space etc.) — junk."""
    o, n = norm(old), norm(new)
    return o != n and re.sub(r"\s+", " ", o) == re.sub(r"\s+", " ", n)


_EN_RUN = re.compile(r"[A-Za-z][A-Za-z'.\-]*(?:\s+[A-Za-z][A-Za-z'.\-]*){3,}")


def injected_english(en, old, new):
    """a 4+ word English run from the source pasted into new but absent from old."""
    o, n = strip_ctrl(old or ""), strip_ctrl(new or "")
    for m in _EN_RUN.findall(n):
        if m in en and m not in o:
            return True
    return False


def classify(en, old, new):
    """Return a reason string if the fix is bad/junk, else None (genuine)."""
    if mk.parse_slots(new) is None:                 return "broken_markup"
    if struct_tokens(new) != struct_tokens(old):    return "tag_mismatch"
    if FOREIGN.search(new):                          return "foreign"
    if NIQQUD.search(new):                           return "niqqud"
    if not HEB.search(new) and not is_namey(en):     return "no_hebrew"
    if punct_append(old, new):                       return "punct_append"
    if ws_only(old, new):                            return "whitespace_only"
    if injected_english(en, old, new):               return "injected_english"
    if trivial(old, new):                            return "trivial"
    vis = visible(new)
    if vis and DANGLING.search(vis):                 return "truncated_dangling"
    if vis and len(visible(en)) > 25 and len(vis) * 2.4 < len(visible(en)):
        return "truncated_short"
    # multi-line dialogue: if NEW lost most of EN's speaker segments -> misaligned/truncated
    en_seg = en.count("\\n") + en.count("<br") + en.count("\n")
    new_seg = new.count("\\n") + new.count("<br") + new.count("\n")
    if en_seg >= 4 and new_seg * 2 < en_seg:         return "seg_mismatch"
    return None


def main():
    do_clean = "--clean" in sys.argv
    corpus = jload(os.path.join(HERE, "corpus.json"), {})
    sources = [("progress", jload(os.path.join(HERE, "progress_corrections.json"), {}))]
    for d in sorted(glob.glob(os.path.join(HERE, "agent_*"))):
        if os.path.isdir(d) and re.fullmatch(r"agent_\d+", os.path.basename(d)):
            sources.append((os.path.basename(d), jload(os.path.join(d, "corrections.json"), {})))

    by_en = defaultdict(set)
    verified = {}
    grand_good = grand_junk = nl_fixed = 0
    print("=== qa_verify : per-agent ===")
    for name, corr in sources:
        if not corr:
            continue
        reasons = Counter()
        samples = defaultdict(list)
        good = 0
        for key, new in corr.items():
            ent = corpus.get(key)
            if not ent:
                reasons["unknown_key"] += 1; continue
            r = classify(ent["en"], ent["he"], new)
            if r:
                reasons[r] += 1
                if len(samples[r]) < 4:
                    samples[r].append((key, ent["he"], new))
            else:
                good += 1
                fixed = match_newlines(ent["he"], new)
                if fixed != new:
                    nl_fixed += 1
                verified[key] = fixed
                by_en[re.sub(r'\s+', ' ', ent["en"].strip())].add(fixed.strip())
        junk = sum(reasons.values())
        grand_good += good; grand_junk += junk
        frac = junk / (good + junk) if (good + junk) else 0
        verdict = "  <<< SUSPECT (scripted/junk)" if frac >= 0.30 and (good + junk) >= 20 else ""
        print(f"\n[{name}] genuine={good}  junk/invalid={junk}  junk%={frac:.0%}{verdict}")
        for r, c in reasons.most_common():
            ex = "; ".join(f"{repr(o[:22])}->{repr(n[:22])}" for _, o, n in samples[r][:2])
            print(f"    {r}: {c}   {ex}")

    inconsistent = {e: v for e, v in by_en.items() if len(v) > 1}
    if inconsistent:
        print(f"\n[inconsistent_same_en] {len(inconsistent)} EN sources -> >1 Hebrew (across agents)")
        for e, vs in list(inconsistent.items())[:10]:
            print(f"    EN={e[:46]!r} -> {[v[:24] for v in list(vs)[:3]]}")

    print(f"\n=== TOTAL genuine={grand_good}  junk/invalid={grand_junk}  "
          f"inconsistent_en={len(inconsistent)} ===")
    if do_clean:
        out = os.path.join(HERE, "verified_corrections.json")
        json.dump(verified, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"wrote {len(verified)} verified corrections -> {os.path.basename(out)} "
              f"(normalized {nl_fixed} literal-\\n; apply_corrections prefers this file)")
    else:
        print("(run with --clean to emit verified_corrections.json for apply; "
              "investigate any SUSPECT agent before applying its slice)")


if __name__ == "__main__":
    main()
