# Probe why a specific long line is rejected. Never prints the key.
import importlib.util, json, time
spec = importlib.util.spec_from_file_location("w", "w3ut_nim.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._KEYS = m.load_keys(); m._KI = 0
c = json.load(open("corpus.json", encoding="utf-8"))
for k in ["1208895", "1207967", "558389"]:
    if k not in c:
        print(k, "not in this slice"); continue
    v = c[k]; src = m.src_text(v); g = m.consensus_target(v) or ""
    to = min(300, 120 + m._tok(v)//8); mx = min(2500, m._tok(v)*2+120)
    payload = {k: {"en": m.clean_en(v.get("en","")), "ar": m._BIDICTL.sub("", v.get("ar","")).strip(),
                   "ru": v.get("ru",""), "es": v.get("es",""), "it": v.get("it",""),
                   "g": {"m":"masculine","f":"feminine","pl":"plural"}.get(g,"unknown")}}
    print(f"\n{k} srclen={len(src)} tok={m._tok(v)} to={to} mx={mx} g={g!r}")
    t = time.time()
    try:
        s1 = m.chat(m.S1, "Translate the MEANING:\n"+json.dumps(payload, ensure_ascii=False), timeout=to, max_tokens=mx)
    except Exception as e:
        print("  CHAT-ERR", type(e).__name__, str(e)[:120]); continue
    he = s1.get(k)
    if isinstance(he, dict): he = he.get("he") or he.get("hebrew") or ""
    he = (he or "").strip() if isinstance(he, str) else ""
    he2 = m.NIQ.sub("", m._BIDICTL.sub("", he))
    print(f"  [{round(time.time()-t,1)}s] raw_keys={list(s1.keys())[:3]} he_len={len(he2)}")
    print("  HE tail:", repr(he2[-50:]))
    print("  struct src:", sorted(m.STRUCT.findall(src)))
    print("  struct he :", sorted(m.STRUCT.findall(he2)))
    print("  struct match:", sorted(m.STRUCT.findall(he2))==sorted(m.STRUCT.findall(src)))
    print("  foreign:", bool(m.FOREIGN.search(he2)), " valid:", m.valid(he2, src))
