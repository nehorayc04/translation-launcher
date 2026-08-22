"""Validate + merge the agent-completed current_batch.json into done_translate.json.
Anti-cheat: the result MUST have Hebrew, keep the SAME tokens (multiset of [..]/<..>/%d),
keep the \\n count, and have FEWER real English words than the partial input (i.e. the
agent actually translated the leftover English). Brand names (Sony/PlayStation) are allowed
to remain. Rejected lines stay un-merged (re-served next get_batch)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
batch = json.load(open(os.path.join(HERE, "current_batch.json"), encoding="utf-8"))
done_p = os.path.join(HERE, "done_translate.json")
done = json.load(open(done_p, encoding="utf-8")) if os.path.exists(done_p) else {}

BRANDS = {"sony","playstation","interactive","entertainment","llc","inc"}
def toks(s):
    return sorted(re.findall(r"\[[^\]]*\]|<[^>]*>|%\w", s or ""))
def strip_toks(s):
    return re.sub(r"\[[^\]]*\]|<[^>]*>|%\w", "", s or "")
def latin_words(s):
    return [w for w in re.findall(r"[A-Za-z]{3,}", strip_toks(s)) if w.lower() not in BRANDS]
def has_heb(s): return any(0x0590 <= ord(c) <= 0x05FF for c in s)
def nls(s): return (s or "").count("\\n")

ok = rej = 0; bad = []
for k, v in batch.items():
    he = (v.get("he") or "").strip()
    partial = v.get("he_partial", "")
    if not he:
        continue
    reason = None
    if not has_heb(he): reason = "no-Hebrew"
    elif toks(he) != toks(partial): reason = "tokens-changed"
    elif nls(he) != nls(partial): reason = "newline-count"
    elif len(latin_words(he)) >= len(latin_words(partial)) and latin_words(partial):
        reason = "english-not-reduced"
    if reason:
        rej += 1; bad.append((k, reason)); continue
    done[k] = he; ok += 1
tmp = done_p + ".tmp"
json.dump(done, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.replace(tmp, done_p)
print("merged %d | rejected %d | total done %d" % (ok, rej, len(done)))
for k, r in bad[:20]:
    print("   REJECT id=%s (%s)" % (k, r))
