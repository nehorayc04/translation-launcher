# -*- coding: utf-8 -*-
"""The Witcher 3 — push live fleet translation progress to the hub home page.

60 s loop → POST /api/admin/progress (MONITOR_TOKEN from the repo-root .env). The homepage
ProgressDashboard `pickActiveSnapshot` surfaces the freshest live (meta.alive) snapshot. Reads the
NIM fleet's merged bank `fleet/hebrew.json` for the done-count; gameId MUST equal the Supabase
games.id ("witcher3"). Cloud NIM → no local GPU.

COUNT BY SENTENCES, not lines (2026-07-07, user request). A corpus "line" is uneven — one line can be
a whole book paragraph of 20 sentences while another is a 2-word button. So progress is measured in
SENTENCES: each line's English is split into sentences and that weight is what's counted done/total/
rate. This gives a fairer picture than counting lines (the few long lore/book lines carry their real
weight). `unit="משפטים"` so the dashboard labels read "משפטים". Everything (percent bar, done,
remaining, rate, ETA) is sentence-based and consistent.
"""
import os, re, sys, json, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BANK = os.path.join(HERE, "hebrew.json")
CORPUS = os.path.join(HERE, "..", "extract", "ct_strings.json")
SENT_HIST = os.path.join(HERE, "w3_progress_sent.json")     # [[ts, done_sentences], ...] for the rate

GAME_ID = "witcher3"                       # MUST match Supabase games.id
AI_MODEL = "llama-3.1-70b (NIM cloud, 7-stream fleet)"
GPU_MODEL = ""                             # cloud NIM — no local GPU
INTERVAL = 60
API = "https://hebrew-translation-hub.com"
UNIT = "משפטים"                            # counting sentences → the dashboard says "משפטים"

# A sentence = a run of text ending in . ! ? … (any number of terminators). Every non-empty line is
# at least 1 sentence. STRUCT tokens (<br>, {curly}, tags) are stripped first so a tag's punctuation
# never inflates the count.
_TERM = re.compile(r'[.!?…]+')
_STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')


def _sentences(en):
    en = _STRUCT.sub(" ", en or "").strip()
    if not en:
        return 0
    return max(1, len(_TERM.findall(en)))


def _load_env(path):
    env = {}
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def _sent_map():
    """key -> sentence-count (built ONCE from the corpus). Returns ({}, 0) on error so the pusher
    still runs (it would then report 0 total → the site keeps the previous snapshot)."""
    try:
        rows = json.load(open(CORPUS, encoding="utf-8"))
    except (OSError, ValueError):
        return {}, 0
    m, total = {}, 0
    for r in rows:
        try:
            k = str(r["string_key"]); n = _sentences(r.get("source_en", ""))
        except (KeyError, TypeError):
            continue
        m[k] = n; total += n
    return m, total


def _done_sentences(bank_keys, sent):
    return sum(sent.get(str(k), 1) for k in bank_keys)


def _sent_rate(done_sent):
    """sentences/hour from a small persisted history (the pull updates the bank every ~3 min while
    this fires every 60 s, so a push-to-push delta is 0 between pulls; a windowed history gives a
    steady rate). Appends (ts, done_sent), keeps ~last 65 min, measures over the last 25 min."""
    hist = []
    try:
        hist = json.load(open(SENT_HIST, encoding="utf-8"))
    except (OSError, ValueError):
        hist = []
    now = time.time()
    hist.append([now, done_sent])
    hist = [p for p in hist if now - p[0] <= 3900][-80:]
    try:
        json.dump(hist, open(SENT_HIST, "w", encoding="utf-8"))
    except OSError:
        pass
    win = [p for p in hist if now - p[0] <= 1500] or hist[-2:]
    if len(win) < 2:
        return 0.0
    (t0, c0), (t1, c1) = win[0], win[-1]
    if t1 <= t0 or c1 < c0:
        return 0.0
    return (c1 - c0) / ((t1 - t0) / 3600.0)


def push(token, processed, total, rate):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "translation", "phaseLabelHe": "תרגום",
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": UNIT, "meta": {"alive": True, "streams": 7, "countUnit": "sentences"},
        "aiModel": AI_MODEL, "gpuModel": GPU_MODEL,
    }).encode("utf-8")
    req = urllib.request.Request(API + "/api/admin/progress", body,
                                 {"Content-Type": "application/json",
                                  "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    env = _load_env(os.path.join(ROOT, ".env"))
    token = env.get("MONITOR_TOKEN", "")
    if not token:
        print("no MONITOR_TOKEN in root .env — exiting"); return 1
    sent, total_sent = _sent_map()
    if total_sent <= 0:
        print("could not build the sentence map (corpus missing?) — exiting"); return 1
    print(f"W3 progress pusher: {len(sent):,} lines = {total_sent:,} sentences, "
          f"every {INTERVAL}s -> {API}")
    while True:
        try:
            bank = json.load(open(BANK, encoding="utf-8"))
        except (OSError, ValueError):
            bank = {}
        done_sent = min(_done_sentences(bank.keys(), sent), total_sent)  # cap at 100%
        rate = _sent_rate(done_sent)
        try:
            st = push(token, done_sent, total_sent, rate)
            print(f"pushed {done_sent:,}/{total_sent:,} sentences "
                  f"({100*done_sent/total_sent:.1f}%) rate={int(rate)}/h "
                  f"[lines {len(bank):,}] -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
