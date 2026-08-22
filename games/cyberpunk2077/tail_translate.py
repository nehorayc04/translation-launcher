# -*- coding: utf-8 -*-
"""tail_translate.py — translate the 75 never-translated onscreens entries
(empty fv in spine -> Arabic skeleton showed in-game) via gemma-4, then write
them into the base spine (both onscreens.json + onscreens_final.json)."""
import os, sys, json, re, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

MODEL_ID = "gemma-4-31b-it"
HEB = re.compile(r"[א-ת]")
FOREIGN = re.compile(r"[؀-ۿ฀-๿぀-ヿ一-鿿가-힯Ѐ-ӿ]")
NIQQUD = re.compile(r"[ְ-ׇֽֿׁׂ]")
TAG = re.compile(r"<[^>]*>|\{[^}]*\}")
SYSTEM = (
    "You are a professional Cyberpunk 2077 game localizer translating English to Hebrew. "
    "Natural modern Hebrew, Night City register. Keep brand/product/weapon/vehicle names and "
    "acronyms in English (e.g. TKI-20, Self-ICE). Preserve every <tag>, {placeholder} and "
    "literal \\n EXACTLY. Hebrew+English letters only, no vowel points, no Arabic. "
    "Output ONLY the Hebrew translation."
)


def gate(he, en):
    if not he or not HEB.search(he) or FOREIGN.search(he) or NIQQUD.search(he):
        return False
    if TAG.findall(he) != TAG.findall(en):
        return False
    return True


def main():
    from openai import OpenAI
    client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
    rows = [json.loads(l) for l in open(os.path.join(HERE, "tail_queue.jsonl"), encoding="utf-8") if l.strip()]
    print(f"translating {len(rows)} tail entries")
    out = {}
    okn = 0
    for i, r in enumerate(rows, 1):
        en = r["english"]
        try:
            resp = client.chat.completions.create(
                model=MODEL_ID, temperature=0.2, max_tokens=900, timeout=240,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": en}])
            he = (resp.choices[0].message.content or "").strip()
            if gate(he, en):
                out[r["refs"][0].split("|")[2]] = he
                okn += 1
        except Exception as e:
            print("  err", repr(e)[:60])
        if i % 15 == 0 or i == len(rows):
            print(f"  {i}/{len(rows)}  ok={okn}", flush=True)

    # apply to spine
    data = json.load(open(G.BASE_TR, encoding="utf-8"))
    if not Q.acquire_lock("tail_translate"):
        sys.exit("[abort] lock")
    try:
        n = 0
        for sec in ("onscreens/onscreens.json", "onscreens/onscreens_final.json"):
            for e in data.get(sec, []):
                if not isinstance(e, dict):
                    continue
                pk = str(e.get("primaryKey"))
                if pk in out:
                    e["femaleVariant"] = out[pk]
                    n += 1
        bak = f"{G.BASE_TR}.bak.tail.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(G.BASE_TR, bak)
        tmp = G.BASE_TR + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, G.BASE_TR)
        print(f"translated {okn}/{len(rows)}; applied {n} spine fields; backup {os.path.basename(bak)}")
    finally:
        Q.release_lock()


if __name__ == "__main__":
    main()
