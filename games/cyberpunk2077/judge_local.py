"""
judge_local.py — local-LM judgment of the remaining claude_queue.jsonl rows.

Rows already judged by Claude (claude_judgments.jsonl) are skipped. For each
remaining row gemma answers: OK / FIX <full corrected Hebrew line> / HUMAN.
Local judgment is weaker than Claude's, so every FIX must pass HARD
deterministic gates or it is demoted to HUMAN:
  - tags <...>/{...} and literal \\n sequences preserved exactly (count+order)
  - contains Hebrew; no foreign scripts; no niqqud
  - the originally-flagged pattern is actually GONE from the fixed text
  - length within 0.4x-3x of EN (anti-hallucination)

Output: local_judgments.jsonl ({n, verdict, fixed?, note?, judge:"gemma"}).
Resumable. Apply happens later via a separate merge step alongside Claude's.
"""
import os, sys, json, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.environ.get("JL_QUEUE", os.path.join(HERE, "claude_queue.jsonl"))
CLAUDE = os.path.join(HERE, "claude_judgments.jsonl")
OUT = os.environ.get("JL_OUT", os.path.join(HERE, "local_judgments.jsonl"))

MODEL_ID = "gemma-4-31b-it"   # the stronger model (see fix_truncated.py note)
TAG = re.compile(r"<[^>]*>|\{[^}]*\}")
ESC = re.compile(r"\\[nrt]")
HEB = re.compile(r"[א-ת]")
NIQQUD = re.compile(r"[ְ-ׇֽֿׁׂ]")


def foreign(s):
    import unicodedata
    for ch in s:
        o = ord(ch)
        if o < 0x80 or 0x0590 <= o <= 0x05FF or 0x00C0 <= o <= 0x024F or 0x1E00 <= o <= 0x1EFF:
            continue
        if unicodedata.category(ch).startswith("L"):
            return True
    return False


SYSTEM = (
    "You are a Hebrew LQA judge for the Cyberpunk 2077 Hebrew translation. "
    "You get one flagged row: CATEGORY (why flagged), WORD (suspicious token), HE (current Hebrew), EN (English source). "
    "Reply with EXACTLY ONE line:\n"
    "OK            — if the flagged pattern is fine in context (laughter/interjections, brand/character names in English, "
    "keybind letters, abbreviations, list letters, \\n codes).\n"
    "FIX: <line>   — if it is a real defect AND you can output the FULL corrected Hebrew line. Preserve every <tag>, "
    "{placeholder} and literal \\n EXACTLY. Hebrew+English letters only, no vowel points. The name V stays Latin.\n"
    "HUMAN: <why>  — if you are not sure.\n"
    "Be decisive. Most flagged rows are actually OK."
)


def gates_ok(row, fixed):
    he, en, word, cat = row["hebrew"], row.get("english", ""), row.get("word", ""), row["category"]
    if not HEB.search(fixed) or NIQQUD.search(fixed) or foreign(fixed):
        return False
    if TAG.findall(fixed) != TAG.findall(he):          # tags must survive verbatim
        return False
    if ESC.findall(fixed) != ESC.findall(he):          # \n codes must survive
        return False
    if word and cat in ("single_hebrew_letter", "single_latin_letter",
                        "punct_inside_word", "hebrew_digit_word"):
        # the flagged token should no longer appear as a standalone word
        if re.search(rf"(?<![A-Za-zא-ת0-9]){re.escape(word)}(?![A-Za-zא-ת0-9])", TAG.sub(" ", fixed)):
            return False
    if en and not (0.4 * len(en) <= len(fixed) <= 3 * len(en) + 20):
        return False
    return True


def main():
    rows = [json.loads(l) for l in open(QUEUE, encoding="utf-8") if l.strip()]
    done = set()
    for p in (CLAUDE, OUT):
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                try:
                    done.add(json.loads(l)["n"])
                except Exception:
                    pass
    todo = [r for r in rows if r["n"] not in done]
    print(f"local-judging {len(todo)} rows (skipping {len(done)} already judged)")

    from openai import OpenAI
    client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
    fout = open(OUT, "a", encoding="utf-8")
    counts = {"ok": 0, "fix": 0, "human": 0}
    for i, r in enumerate(todo, 1):
        user = (f"CATEGORY: {r['category']}\nWORD: {r.get('word','')}\n"
                f"HE: {r['hebrew']}\nEN: {r.get('english','')}")
        rec = {"n": r["n"], "judge": "gemma"}
        try:
            resp = client.chat.completions.create(
                model=MODEL_ID, temperature=0.1, max_tokens=700, timeout=240,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": user}])
            ans = (resp.choices[0].message.content or "").strip()
            first = ans.splitlines()[0] if ans else ""
            if first.upper().startswith("OK"):
                rec["verdict"] = "ok"
            elif first.upper().startswith("FIX:"):
                fixed = ans.split(":", 1)[1].strip()
                if gates_ok(r, fixed):
                    rec.update(verdict="fix", fixed=fixed)
                else:
                    rec.update(verdict="human", note="gemma fix failed gates")
            elif first.upper().startswith("HUMAN"):
                rec.update(verdict="human", note=first[6:].strip(" :"))
            else:
                rec.update(verdict="human", note="unparseable local answer")
        except Exception as e:
            rec.update(verdict="human", note=f"lm error {repr(e)[:80]}")
        counts[rec["verdict"]] += 1
        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if i % 25 == 0 or i == len(todo):
            fout.flush()
            print(f"  {i}/{len(todo)}  ok={counts['ok']} fix={counts['fix']} human={counts['human']}", flush=True)
    fout.close()
    print(f"done -> {OUT}")


if __name__ == "__main__":
    main()
