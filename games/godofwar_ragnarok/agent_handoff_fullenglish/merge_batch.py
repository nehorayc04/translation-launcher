"""Validate + merge current_batch.json into done_translate.json.
Anti-cheat: the result MUST be Hebrew, keep the SAME tokens (multiset of [[S:..]]/[..]/<..>/%x),
keep the \\n count, and leave NO real English/Latin word (>=3 letters) except brand names.
A Norse-flavor line must be TRANSLITERATED into Hebrew letters (so it is Hebrew-script, not Latin).
Rejected lines stay un-merged (re-served next get_batch)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
batch = json.load(open(os.path.join(HERE, "current_batch.json"), encoding="utf-8"))
done_p = os.path.join(HERE, "done_translate.json")
done = json.load(open(done_p, encoding="utf-8")) if os.path.exists(done_p) else {}

BRANDS = {"sony","playstation","nvidia","dlss","amd","fsr","xess","dualsense","fidelityfx"}
def toks(s): return sorted(re.findall(r"\[\[S:[^\]]*\]\]|\[[^\]]*\]|<[^>]*>|%[a-zA-Z]", s or ""))
def strip_t(s): return re.sub(r"\[\[S:[^\]]*\]\]|\[[^\]]*\]|<[^>]*>|%[a-zA-Z]", "", s or "")
def latin_words(s): return [w for w in re.findall(r"[A-Za-zþðøæÞÐØÆ]{3,}", strip_t(s)) if w.lower() not in BRANDS]
def has_heb(s): return any(0x0590 <= ord(c) <= 0x05FF for c in s)
def nls(s): return (s or "").count("\\n")

ok = rej = 0; bad = []
for k, v in batch.items():
    en = v.get("en", ""); he = (v.get("he") or "").strip()
    if not he:
        continue
    reason = None
    if not has_heb(he): reason = "no-Hebrew"
    elif toks(he) != toks(en): reason = "tokens-changed"
    elif nls(he) != nls(en): reason = "newline-count"
    elif latin_words(he): reason = "latin-left:" + ",".join(latin_words(he)[:3])
    if reason:
        rej += 1; bad.append((k, reason)); continue
    done[k] = he; ok += 1
tmp = done_p + ".tmp"
json.dump(done, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.replace(tmp, done_p)
print("merged %d | rejected %d | total done %d / %d" % (ok, rej, len(done),
      len(json.load(open(os.path.join(HERE,'to_translate.json'),encoding='utf-8')))))
for k, r in bad[:25]:
    print("   REJECT id=%s (%s)" % (k, r))
