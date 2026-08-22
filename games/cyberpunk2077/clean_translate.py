"""clean_translate.py — build a CLEAN work queue (only rows that need
translating / fixing, junk removed) and batch-send it to the LOCAL model so
the model never wastes time on file-paths, IDs, tags, numbers or already-good
lines.

Pipeline (all FREE / local LM Studio):
  1. enumerate the whole corpus (get_next_audit_batch.build_corpus)
  2. SKIP rows that need no AI  -> smart_filter_queue.skip_reason
     (empty / numbers-only / file-paths-IDs / code-tags-only / EN==HE)
  3. KEEP only rows that need WORK: untranslated (no Hebrew), or contaminated
     (foreign script / leftover English)         -> audit/qa detectors
  4. write them to ONE file  ->  translation_queue.jsonl
  5. --send : batch them to the local model (reuses translate_queue_fast.
     translate_batch — numbered multi-line prompt, single-mode fallback) and
     write translation_results.jsonl (id, english, hebrew).

Read-only on the source JSONs. Never writes the spine (a later, confirmed,
backed-up merge step does that).

Usage:
  python clean_translate.py                 # build the queue only
  python clean_translate.py --send          # build + translate via local model
  python clean_translate.py --send --limit 20   # quick end-to-end test
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
UNIV = os.path.join(ROOT, "universal")
sys.path.insert(0, HERE); sys.path.insert(0, UNIV)

import get_next_audit_batch as G
import audit_translations as A
import cp2077_qa_defects as Q
import smart_filter_queue as SF          # reuse the junk-skip rules

QUEUE_OUT = os.path.join(HERE, "translation_queue.jsonl")
RESULT_OUT = os.path.join(HERE, "translation_results.jsonl")
BATCH = 15


def needs_work(en: str, he: str) -> str | None:
    """Return a work-reason if this row needs translating/fixing, else None."""
    if not (he or "").strip() or not A.has_hebrew(he):
        return "untranslated"
    tt = Q.translatable_text(he)
    if tt is None:
        return None                       # markup the parser rejects — leave it
    if A.detect_scripts(tt):
        return "foreign_script"
    if Q.english_leak(tt):
        return "english_leak"
    return None                           # already good Hebrew — skip


def build_queue(limit: int = 0):
    corpus, _b, _d = G.build_corpus()
    work, skipped = [], 0
    for r in corpus:
        if SF.skip_reason(r.english, r.hebrew):     # path/id/tag/number/EN==HE
            skipped += 1
            continue
        why = needs_work(r.english, r.hebrew)
        if not why:
            continue
        work.append({"id": f"{r.project}|{r.section}|{r.pk}|{r.field}",
                     "source": f"{r.project}/{r.section}", "pk": r.pk, "field": r.field,
                     "english": r.english, "current_hebrew": r.hebrew, "reason": why})
        if limit and len(work) >= limit:
            break
    with open(QUEUE_OUT, "w", encoding="utf-8") as f:
        for w in work:
            f.write(json.dumps(w, ensure_ascii=False) + "\n")
    print(f"corpus {len(corpus):,} | junk-skipped {skipped:,} | "
          f"WORK QUEUE {len(work):,} -> {os.path.basename(QUEUE_OUT)}")
    return work


LM_URL = "http://127.0.0.1:1234/v1"
SYS = (
    "You are a professional Cyberpunk 2077 Hebrew localizer. Translate each "
    "numbered English line into natural, idiomatic Israeli Hebrew.\n"
    "HARD RULES:\n"
    "- Hebrew and Latin letters ONLY. NEVER output Cyrillic, Arabic, CJK, Thai "
    "or any other script.\n"
    "- NEVER use Niqqud vowel-points.\n"
    "- Keep tags (<Rich...>, <Input...>), {placeholders}, %s, digits and "
    "punctuation EXACTLY as given.\n"
    "- Keep brand names / acronyms / the protagonist's name 'V' in Latin "
    "(V, Arasaka, NCPD, RAM).\n"
    "OUTPUT: ONLY a numbered list, same numbers, one Hebrew line each, nothing "
    "else — no notes, no quotes."
)
import re as _re
_NUM = _re.compile(r"^\s*(\d+)\.\s*(.+)")


def _valid(en, he):
    he = (he or "").strip()
    return bool(he) and A.has_hebrew(he) and not A.detect_scripts(he) and he != (en or "").strip()


def _translate_batch(client, texts):
    user = "Translate these lines to Hebrew:\n" + "".join(
        f"{j + 1}. {t}\n" for j, t in enumerate(texts))
    out = list(texts)
    try:
        resp = client.chat.completions.create(
            model="local-model",
            messages=[{"role": "system", "content": SYS},
                      {"role": "user", "content": user}],
            temperature=0.2, max_tokens=2048)
        raw = (resp.choices[0].message.content or "")
        got = {}
        for ln in raw.splitlines():
            m = _NUM.match(ln.strip())
            if m:
                k = int(m.group(1)) - 1
                if 0 <= k < len(texts):
                    got[k] = m.group(2).strip()
        bad = [i for i in range(len(texts)) if not _valid(texts[i], got.get(i, ""))]
        for i in range(len(texts)):
            if i not in bad:
                out[i] = got[i]
        # single-mode fallback for the ones the batch missed
        for i in bad:
            try:
                r1 = client.chat.completions.create(
                    model="local-model",
                    messages=[{"role": "system", "content": SYS},
                              {"role": "user", "content": f"1. {texts[i]}"}],
                    temperature=0.2, max_tokens=512)
                m = _NUM.match((r1.choices[0].message.content or "").strip().splitlines()[0]
                               if (r1.choices[0].message.content or "").strip() else "")
                cand = m.group(2).strip() if m else (r1.choices[0].message.content or "").strip()
                if _valid(texts[i], cand):
                    out[i] = cand
            except Exception:
                pass
    except Exception as e:
        print(f"    [!] batch error: {e}", flush=True)
    return out


def send_to_model(work):
    from openai import OpenAI
    client = OpenAI(base_url=LM_URL, api_key="lm-studio", timeout=600)
    print(f"[*] sending {len(work):,} rows to local model in batches of {BATCH} …")
    done = ok = 0
    with open(RESULT_OUT, "w", encoding="utf-8") as f:
        for i in range(0, len(work), BATCH):
            chunk = work[i:i + BATCH]
            heb = _translate_batch(client, [w["english"] for w in chunk])
            for w, h in zip(chunk, heb):
                clean = _valid(w["english"], h)
                ok += clean
                f.write(json.dumps({"id": w["id"], "pk": w["pk"], "field": w["field"],
                                    "english": w["english"], "hebrew": h,
                                    "translated": clean}, ensure_ascii=False) + "\n")
            done += len(chunk)
            print(f"    {done:,}/{len(work):,}  ({ok:,} clean)", flush=True)
    print(f"[*] done -> {os.path.basename(RESULT_OUT)} ({ok:,}/{done:,} translated clean)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="also batch-translate via the local model")
    ap.add_argument("--limit", type=int, default=0, help="cap queue size (for a quick test)")
    args = ap.parse_args()
    work = build_queue(args.limit)
    if args.send and work:
        send_to_model(work)


if __name__ == "__main__":
    main()
