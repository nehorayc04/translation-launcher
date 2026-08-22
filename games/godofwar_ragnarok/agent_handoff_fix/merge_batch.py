"""Validate + merge the agent-filled current_batch.json into done_translate.json.
Anti-cheat: a translated line MUST have Hebrew letters, keep the [[S:...]] cue and
the \\n count of the Arabic source, and contain NO Arabic letters (fully Hebrew).
Rejected lines are reported and stay un-merged (re-served next get_batch)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
batch = json.load(open(os.path.join(HERE, "current_batch.json"), encoding="utf-8"))
done = json.load(open(os.path.join(HERE, "done_translate.json"), encoding="utf-8"))

def cue(s):
    m = re.match(r"(\[\[S:[^\]]*\]\])", s or "")
    return m.group(1) if m else ""
def has_heb(s): return any(0x0590 <= ord(c) <= 0x05FF for c in s)
def has_ara(s): return any(0x0600 <= ord(c) <= 0x06FF or 0xFB50 <= ord(c) <= 0xFEFF for c in s)
def nls(s): return (s or "").count("\\n")

ok = rej = 0; bad = []
for k, v in batch.items():
    ar = v.get("ar", ""); he = (v.get("he") or "").strip()
    if not he:
        continue
    reason = None
    if not has_heb(he): reason = "no-Hebrew"
    elif has_ara(he): reason = "Arabic-left"
    elif cue(ar) and cue(ar) not in he: reason = "cue-dropped"
    elif nls(ar) != nls(he): reason = "newline-count"
    if reason:
        rej += 1; bad.append((k, reason)); continue
    done[k] = he; ok += 1
json.dump(done, open(os.path.join(HERE, "done_translate.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("merged %d | rejected %d | total done %d" % (ok, rej, len(done)))
for k, r in bad[:20]:
    print("   REJECT id=%s (%s)" % (k, r))
