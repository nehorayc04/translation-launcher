"""Rebuild the public cyberpunk /translate pool with the full dual-gender dataset.
DELETE the old cyberpunk translation_strings (verified 0 submissions/approvals/claims), then
bulk-INSERT cp2077_dualgender.json. Field mapping (keeps translation_progress accurate):
  source_en · he_female · he_male · approved_text=he_female (canonical current) ·
  current_he=before (small note) · status='approved' · section (drives category trigger).
"""
import json, os, sys, urllib.request, urllib.error, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
def env(k):
    for l in open(os.path.join(HERE, "..", "..", "website", ".env"), encoding="utf-8"):
        if l.startswith(k + "="): return l.split("=", 1)[1].strip().strip('"')
URL = env("SUPABASE_URL"); KEY = env("SUPABASE_SERVICE_ROLE_KEY")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(URL + "/rest/v1/" + path, data=data, method=method,
                               headers={**H, **(headers or {})})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.status, resp.read()

data = json.load(open(os.path.join(HERE, "cp2077_dualgender.json"), encoding="utf-8"))
print("rows to upload:", len(data))

# 1. delete old cyberpunk rows
print("deleting old cyberpunk rows...")
st, _ = req("DELETE", "translation_strings?game_id=eq.cyberpunk", None, {"Prefer": "return=minimal"})
print("  delete status", st)

# 2. bulk insert
rows = []
for i, (k, v) in enumerate(data.items()):
    hf = v["he_female"]; hm = v["he_male"]
    # AI/team SEED (not community-approved): status='translated', current_he=the translation
    # (so translation_progress counts it), he_before=the pre-fleet Hebrew shown small.
    rows.append({
        "game_id": "cyberpunk", "string_key": k, "source_en": v["source_en"],
        "he_female": hf, "he_male": hm,
        "current_he": hf, "he_before": v.get("current_he", "") or "",
        "approved_text": None, "status": "translated",
        "section": v.get("section", ""), "order_index": i,
    })
CH = 1000; done = 0; t0 = time.time()
for i in range(0, len(rows), CH):
    chunk = rows[i:i + CH]
    for attempt in range(3):
        try:
            st, _ = req("POST", "translation_strings", chunk, {"Prefer": "return=minimal"})
            done += len(chunk); break
        except urllib.error.HTTPError as e:
            if attempt == 2: print("  CHUNK FAIL", i, e.code, e.read()[:200]); raise
            time.sleep(2)
    if done % 20000 < CH: print(f"  {done}/{len(rows)}  ({time.time()-t0:.0f}s)")
print(f"DONE uploaded {done} in {time.time()-t0:.0f}s")
# verify count
st, body = req("GET", "translation_strings?game_id=eq.cyberpunk&select=id&limit=1", None, {"Prefer": "count=exact"})
