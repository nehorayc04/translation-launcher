# Deep probe: show WHY each remaining line is rejected. Never prints the key.
import importlib.util, json, time, re
spec = importlib.util.spec_from_file_location("w", "w3ut_nim.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._KEYS = m.load_keys(); m._KI = 0
c = json.load(open("corpus.json", encoding="utf-8"))
out = {}
try: out = json.load(open("out.json", encoding="utf-8"))
except Exception: pass
rem = [k for k in c if k not in out]
picks = []
for k in rem:
    if len(m.src_text(c[k])) > 25 and len(picks) < 4:
        picks.append(k)
print("remaining", len(rem), "picks", picks)
for k in picks:
    v = c[k]; src = m.src_text(v)
    g = m.consensus_target(v) or ""
    payload = {k: {"en": m.clean_en(v.get("en","")), "ar": m._BIDICTL.sub("", v.get("ar","")).strip(),
                   "ru": v.get("ru",""), "es": v.get("es",""), "it": v.get("it",""),
                   "g": {"m":"masculine","f":"feminine","pl":"plural"}.get(g,"unknown")}}
    hint = m._GTXT[g] if g in m._GTXT else ""
    t = time.time()
    try:
        s1 = m.chat(m.S1 + ((" " + hint) if hint else ""),
                    "Translate the MEANING (prefer 'en' if readable, else the Arabic; respect each 'g'):\n"
                    + json.dumps(payload, ensure_ascii=False),
                    timeout=180, max_tokens=800)
    except Exception as e:
        print(f"\n{k}: CHAT-ERR {type(e).__name__} {str(e)[:100]}"); continue
    he = s1.get(k)
    if isinstance(he, dict):
        he = he.get("he") or he.get("hebrew") or he.get("text") or he.get("translation") or ""
    he = (he or "").strip() if isinstance(he, str) else str(he)
    print(f"\n{k} [{round(time.time()-t,1)}s] g={g!r}")
    print("  src:", repr(src[:60]))
    print("  raw keys:", list(s1.keys())[:5])
    print("  HE :", repr(he[:70]))
    if not he:
        print("  -> EMPTY (parse miss)"); continue
    print("  valid.foreign:", bool(m.FOREIGN.search(he)), " valid.niq:", bool(m.NIQ.search(he)))
    print("  struct src:", sorted(m.STRUCT.findall(src)), " struct he:", sorted(m.STRUCT.findall(he)),
          " match:", sorted(m.STRUCT.findall(he)) == sorted(m.STRUCT.findall(src)))
    print("  he has Hebrew:", bool(m.HEB.search(he)))
    print("  he_gender:", m.he_gender(he), " target:", g, " guard_reject:",
          (g in ("m","f","pl") and m.he_gender(he) and m.he_gender(he) != g))
    print("  valid():", m.valid(he, src))
