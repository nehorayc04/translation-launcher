# -*- coding: utf-8 -*-
"""universal/qa_review.py — game-agnostic, RESUMABLE translation QA helper for an
external review agent (Google/Antigravity). The agent NEVER calls a local model/API;
it reviews the Hebrew itself and writes corrections. A checkpoint of reviewed keys
makes the loop resumable: a fresh agent with the SAME instruction continues exactly
where the previous one stopped.

Config: a JSON file `qa_review_config.json` in the CURRENT directory (or pass a path
as the 3rd arg). Shape:
{
  "en_file":      "english.json",                 // {key: english_string}  (the source)
  "spine_files":  ["subtitles_he.json", "dialogue_he.json"],  // {key: hebrew}; LATER file wins
  "skip_keys_file": "sm2_translate_skip.json",    // optional: keys to ignore (list or dict)
  "min_words":    3,                               // skip EN with fewer real words (deterministic tools' job)
  "glossary":     {"Venom": "ונום", "drone": "רחפן"}   // optional locked terms (shown to the agent)
}

Commands (run from the same dir as the config):
  python qa_review.py get [N]   -> writes qa_review_batch.json = {key:{en,he,fix}}  (N default 30)
  python qa_review.py put       -> applies non-empty `fix` values (structural-validated),
                                   marks the whole batch reviewed (checkpoint advances),
                                   logs applied fixes -> qa_review_fixes.jsonl,
                                   logs rejected fixes -> qa_review_rejected.jsonl
  python qa_review.py status    -> reviewed / remaining / applied counts

State files (created next to the config; safe to delete to restart):
  qa_review_checkpoint.json  (reviewed keys + stats)   qa_review_batch.json  (current batch)
  qa_review_fixes.jsonl      qa_review_rejected.jsonl
"""
from __future__ import annotations
import json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from rtl_anchor import anchor_value, strip_rlm   # optional RTL punctuation anchoring
except Exception:
    anchor_value = strip_rlm = None

HERE = os.getcwd()
CONFIG = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "qa_review_config.json")

TS_RE   = re.compile(r'<ts="[^"]*">')
TS_PH   = re.compile(r'@@TS(\d+)@@')
PH_RE   = re.compile(r'\[[A-Z0-9_]+\]|\{[A-Za-z0-9_]+\}')      # [TOKEN] / {VALUE}
SPEC_RE = re.compile(r'%[a-zA-Z]|%%')                          # %d %s %ls %%
BAD     = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]')               # Arabic/Cyrillic/Greek/Thai/Deva/CJK/Hangul
NIQQUD  = re.compile(r'[֑-ׇ]')
HEB     = re.compile(r'[א-ת]')


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def to_display(s):
    """<ts="..."> -> @@TSn@@ so the agent edits a quote-free string."""
    n = [0]
    def repl(_m):
        n[0] += 1
        return f"@@TS{n[0]}@@"
    return TS_RE.sub(repl, s)


def reattach(en, he):
    tags = TS_RE.findall(en)
    return TS_PH.sub(lambda m: tags[int(m.group(1)) - 1] if 1 <= int(m.group(1)) <= len(tags) else m.group(0), he)


def real_words(en):
    core = TS_RE.sub("", en)
    core = PH_RE.sub("", core)
    core = re.sub(r'&[a-zA-Z#0-9]+;|<[^>]+>', '', core)
    return re.findall(r"[A-Za-z][A-Za-z'\-]{1,}", core)


def is_namey(en):
    w = real_words(en)
    return bool(w) and len(w) <= 4 and all(x[0].isupper() for x in w)


class Cfg:
    def __init__(self, path):
        c = load(path, None)
        if c is None:
            sys.exit(f"FATAL: config not found: {path}\nCreate qa_review_config.json (see the docstring).")
        base = os.path.dirname(os.path.abspath(path))
        self.base = base
        self.en_file = os.path.join(base, c["en_file"])
        self.spine_files = [os.path.join(base, p) for p in c["spine_files"]]
        self.skip_file = os.path.join(base, c["skip_keys_file"]) if c.get("skip_keys_file") else None
        self.min_words = int(c.get("min_words", 3))
        self.glossary = c.get("glossary", {})
        # show the agent CLEAN Hebrew (strip &rlm;) and RE-ANCHOR its fixes on put,
        # so the resumable QA loop can never break the RTL punctuation anchoring.
        self.anchor = bool(c.get("anchor_rtl_punct", False)) and anchor_value is not None
        self.checkpoint = os.path.join(base, "qa_review_checkpoint.json")
        self.batch = os.path.join(base, "qa_review_batch.json")
        self.fixes = os.path.join(base, "qa_review_fixes.jsonl")
        self.rejected = os.path.join(base, "qa_review_rejected.jsonl")


def merged_spine(cfg):
    """Merge spine files; LATER file wins. Returns {key: he} and {key: file_path_that_holds_it (all)}."""
    he = {}
    holders = {}
    for p in cfg.spine_files:
        d = load(p, {})
        for k, v in d.items():
            he[k] = v
            holders.setdefault(k, []).append(p)
    return he, holders


def skip_set(cfg):
    if not cfg.skip_file:
        return set()
    s = load(cfg.skip_file, [])
    return set(s if isinstance(s, list) else list(s))


def validate(en, he):
    """Structural gate (mirrors translator/server). Returns (ok, reason)."""
    if not he or not he.strip():
        return False, "empty"
    if "@@TS" in he:
        return False, "unresolved @@TS marker"
    if NIQQUD.search(he):
        return False, "niqqud"
    if BAD.search(he):
        return False, "foreign script"
    if sorted(TS_RE.findall(en)) != sorted(TS_RE.findall(he)):
        return False, "ts tag multiset changed"
    if sorted(PH_RE.findall(en)) != sorted(PH_RE.findall(he)):
        return False, "[TOKEN]/{VALUE} multiset changed"
    if sorted(SPEC_RE.findall(en)) != sorted(SPEC_RE.findall(he)):
        return False, "%-spec multiset changed"
    if not HEB.search(he) and not (is_namey(en) or not re.search(r'[a-z]{2,}', TS_RE.sub("", en))):
        return False, "no Hebrew (and source is not a name/code)"
    return True, ""


def cmd_get(cfg, n):
    en = load(cfg.en_file, {})
    he, _ = merged_spine(cfg)
    ck = load(cfg.checkpoint, {"reviewed": [], "stats": {}})
    reviewed = set(ck.get("reviewed", []))
    skip = skip_set(cfg)

    pool = [k for k in en
            if k in he and he[k] and k not in reviewed and k not in skip
            and len(real_words(en[k])) >= cfg.min_words]
    batch_keys = pool[:n]
    if not batch_keys:
        print("All done!  (no more comparable, unreviewed entries)")
        if os.path.exists(cfg.batch):
            os.remove(cfg.batch)
        return
    disp_he = (lambda s: to_display(strip_rlm(s))) if cfg.anchor else to_display
    batch = {k: {"en": to_display(en[k]), "he": disp_he(he[k]), "fix": ""} for k in batch_keys}
    save_atomic(cfg.batch, batch)
    print(f"Remaining to review: {len(pool)}")
    print(f"Batch size: {len(batch_keys)}  ->  {os.path.basename(cfg.batch)}")
    print("For each entry: compare `en` vs `he`. If the Hebrew is WRONG, put the corrected")
    print("Hebrew in `fix` (keep @@TSn@@ markers + every [TOKEN]/{VALUE}/%spec). If it's FINE,")
    print("leave fix empty. Then run:  python qa_review.py put")
    if cfg.glossary:
        print(f"Glossary (locked terms): {json.dumps(cfg.glossary, ensure_ascii=False)}")


def cmd_put(cfg):
    batch = load(cfg.batch, None)
    if not batch:
        print("No batch file. Run `get` first.")
        return
    en = load(cfg.en_file, {})
    ck = load(cfg.checkpoint, {"reviewed": [], "stats": {}})
    reviewed = set(ck.get("reviewed", []))
    he, holders = merged_spine(cfg)

    spine_data = {p: load(p, {}) for p in cfg.spine_files}
    applied, rejected, reviewed_now = 0, 0, 0
    fix_log, rej_log = [], []

    for k, item in batch.items():
        reviewed.add(k); reviewed_now += 1
        fix = (item or {}).get("fix", "")
        if not isinstance(fix, str) or not fix.strip():
            continue
        if k not in en:
            rej_log.append({"key": k, "reason": "key not in EN source"}); rejected += 1; continue
        new_he = reattach(en[k], fix)
        if cfg.anchor:
            new_he = anchor_value(new_he)        # re-add the RTL &rlm; anchors the agent didn't type
        ok, why = validate(en[k], new_he)
        if not ok:
            rej_log.append({"key": k, "reason": why, "en": en[k], "fix": new_he}); rejected += 1; continue
        # write into whichever spine file(s) currently hold k; if new key, the LAST file (wins at build)
        targets = holders.get(k) or [cfg.spine_files[-1]]
        for p in targets:
            spine_data[p][k] = new_he
        fix_log.append({"key": k, "old": he.get(k, ""), "new": new_he}); applied += 1

    # persist spine edits
    for p, d in spine_data.items():
        if any(e["key"] in d for e in fix_log):
            save_atomic(p, d)
    # persist checkpoint + logs
    ck["reviewed"] = sorted(reviewed)
    ck.setdefault("stats", {})
    ck["stats"]["reviewed"] = len(reviewed)
    ck["stats"]["applied"] = ck["stats"].get("applied", 0) + applied
    ck["stats"]["rejected"] = ck["stats"].get("rejected", 0) + rejected
    save_atomic(cfg.checkpoint, ck)
    with open(cfg.fixes, "a", encoding="utf-8") as f:
        for e in fix_log: f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(cfg.rejected, "a", encoding="utf-8") as f:
        for e in rej_log: f.write(json.dumps(e, ensure_ascii=False) + "\n")
    if os.path.exists(cfg.batch):
        os.remove(cfg.batch)
    print(f"reviewed this batch: {reviewed_now}   fixes applied: {applied}   rejected: {rejected}")
    print(f"total reviewed: {len(reviewed)}   total applied: {ck['stats']['applied']}")
    if rej_log:
        print("rejected (kept original; see qa_review_rejected.jsonl):")
        for e in rej_log[:10]:
            print(f"  {e['key']}: {e['reason']}")
    print("Run `python qa_review.py get` for the next batch (or it prints 'All done!').")


def cmd_status(cfg):
    en = load(cfg.en_file, {})
    he, _ = merged_spine(cfg)
    ck = load(cfg.checkpoint, {"reviewed": [], "stats": {}})
    reviewed = set(ck.get("reviewed", []))
    skip = skip_set(cfg)
    pool = [k for k in en if k in he and he[k] and k not in skip and len(real_words(en[k])) >= cfg.min_words]
    remaining = [k for k in pool if k not in reviewed]
    print(f"comparable entries: {len(pool)}")
    print(f"reviewed:           {len(reviewed & set(pool))}")
    print(f"remaining:          {len(remaining)}")
    print(f"fixes applied:      {ck.get('stats', {}).get('applied', 0)}")
    print(f"fixes rejected:     {ck.get('stats', {}).get('rejected', 0)}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python qa_review.py <get [N] | put | status> [config_path]")
        return 1
    cfg = Cfg(CONFIG)
    cmd = sys.argv[1].lower()
    if cmd == "get":
        cmd_get(cfg, int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 30)
    elif cmd == "put":
        cmd_put(cfg)
    elif cmd == "status":
        cmd_status(cfg)
    else:
        print(f"Unknown command: {cmd}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
