# -*- coding: utf-8 -*-
"""corrective_fix.py — DIRECTIVE fix of the 189 mixed-script words that gemma-4
mis-judged as "ok". Each word glues Hebrew+Latin in one token; force it to ONE
script. Strict seam gate rejects any still-mixed result -> human review.
Applies to the spine (onscreens + subtitles), collects touched sub sections."""
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
SEAM = re.compile(r"[א-ת][A-Za-z]|[A-Za-z][א-ת]")   # Hebrew glued to Latin = still broken

SYSTEM = (
    "You fix ONE Hebrew line from Cyberpunk 2077 that contains a BROKEN word — Hebrew "
    "letters glued directly to Latin letters in a single token (a half-transliterated "
    "name, a brand with a glued Hebrew prefix, or an onomatopoeia). Rewrite the WHOLE line "
    "so NO token mixes Hebrew and Latin letters, using the English source for meaning:\n"
    "- PERSON name -> full Hebrew transliteration (João Guilherme -> ז'ואו גילרמה).\n"
    "- BRAND / PRODUCT / TECH / PLACE / CAR name that stays English -> write it FULLY in "
    "English; if a Hebrew one-letter prefix (ל/ב/ה/מ/ו/ש/כ) attaches, separate with a "
    "maqaf (לQuadra -> ל-Quadra, קריסטלCoat -> CrystalCoat).\n"
    "- scream / laugh / sound -> ALL Hebrew letters (אארגghh -> אאאררגגחחח).\n"
    "Keep every <tag>, {placeholder} and literal \\n EXACTLY. No Arabic, no vowel points. "
    "Output ONLY the corrected Hebrew line, nothing else."
)


def gate(he, en):
    if not he or not HEB.search(he) or FOREIGN.search(he) or NIQQUD.search(he):
        return False
    if SEAM.search(TAG.sub(" ", he)):          # the whole point: no glued seam left
        return False
    if TAG.findall(he) != TAG.findall(en):
        return False
    if "\\n" in en and he.count("\\n") != en.count("\\n"):
        return False
    return True


def main():
    from openai import OpenAI
    client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
    rows = [json.loads(l) for l in open(os.path.join(HERE, "corrective_queue.jsonl"), encoding="utf-8") if l.strip()]
    print(f"correcting {len(rows)} mixed-script entries")
    fixes = {}        # ref -> fixed
    human = []
    okn = 0
    for i, r in enumerate(rows, 1):
        user = f"Broken word: {r['word']}\nEnglish source: {r['english']}\nHebrew line: {r['hebrew']}"
        try:
            resp = client.chat.completions.create(
                model=MODEL_ID, temperature=0.15, max_tokens=900, timeout=240,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": user}])
            he = (resp.choices[0].message.content or "").strip().split("\n")[0] \
                if "\\n" not in (resp.choices[0].message.content or "") \
                else (resp.choices[0].message.content or "").strip()
            if gate(he, r["english"]):
                for ref in r["refs"]:
                    fixes[ref] = he
                okn += 1
            else:
                human.append(r)
        except Exception as e:
            human.append(r); print("  err", repr(e)[:50])
        if i % 15 == 0 or i == len(rows):
            print(f"  {i}/{len(rows)}  fixed={okn} human={len(human)}", flush=True)

    # apply
    data = json.load(open(G.BASE_TR, encoding="utf-8"))
    idx = {}
    for sec, rs in data.items():
        if isinstance(rs, list):
            for e in rs:
                if isinstance(e, dict):
                    idx[(sec, str(e.get("primaryKey") or e.get("stringId")))] = e
    touched_subs = set()
    if not Q.acquire_lock("corrective"):
        sys.exit("[abort] lock")
    try:
        n = 0
        for ref, he in fixes.items():
            proj, sec, pk, fld = ref.split("|", 3)
            e = idx.get((sec, pk))
            if e is not None:
                e[fld] = he
                n += 1
                if sec.startswith("subtitles"):
                    touched_subs.add(sec)
        bak = f"{G.BASE_TR}.bak.corrective.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(G.BASE_TR, bak)
        tmp = G.BASE_TR + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, G.BASE_TR)
        print(f"corrected {okn}; applied {n} fields; human {len(human)}; backup {os.path.basename(bak)}")
    finally:
        Q.release_lock()
    open(os.path.join(HERE, "corrective_sub_sections.txt"), "w", encoding="utf-8").write(
        "\n".join(sorted(touched_subs)))
    with open(os.path.join(HERE, "corrective_human.jsonl"), "w", encoding="utf-8") as f:
        for r in human:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"touched subtitle sections: {len(touched_subs)}")


if __name__ == "__main__":
    main()
