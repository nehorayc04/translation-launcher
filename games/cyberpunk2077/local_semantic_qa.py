# -*- coding: utf-8 -*-
"""local_semantic_qa.py — semantic QA via the LOCAL model (gemma-4-31b-it), no
subscription. For each sampled translation: gemma JUDGES (OK / FIX:<hebrew>),
then a second gemma call ADVERSARIALLY VERIFIES its own fix (needed? correct?
minimal?). A fix is applied ONLY if judge+verify agree AND it passes hard
deterministic gates. Conservative by design — local models over-flag, so we
bias to OK and reject risky rewrites to avoid regressions.

Usage: python local_semantic_qa.py <batch_dir>
Reads games/cyberpunk2077/<batch_dir>/batch_*.json (the sampler's output).
Applies confirmed fixes to the base spine (backup + QA-lock + atomic), writes
local_semantic_subs.txt / local_semantic_onscreens.flag for the bake step, and
local_semantic_report.jsonl (every decision, for audit)."""
import os, sys, json, re, time, glob, shutil, difflib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

MODEL_ID = "gemma-4-31b-it"
TAG = re.compile(r"<[^>]*>|\{[^}]*\}")
ESC = re.compile(r"\\[nrt]")
HEB = re.compile(r"[א-ת]")
NIQQUD = re.compile(r"[֑-ׇ]")


def foreign(s):
    import unicodedata
    for ch in s:
        o = ord(ch)
        if o < 0x80 or 0x0590 <= o <= 0x05FF or 0x00C0 <= o <= 0x024F or 0x1E00 <= o <= 0x1EFF:
            continue
        if unicodedata.category(ch).startswith("L"):
            return True
    return False


JUDGE_SYS = (
    "You are a conservative Hebrew LQA judge for Cyberpunk 2077 (Hebrew via the Arabic slot). "
    "You get one translation: EN (English source) and HE (current Hebrew). Reply with EXACTLY one line:\n"
    "OK           — the Hebrew is acceptable (default; pick this unless there is a CLEAR defect).\n"
    "FIX: <line>  — ONLY for a clear, objective defect: an English/foreign word left untranslated mid-Hebrew, "
    "a broken/dropped <tag> {placeholder} or \\n, or a plain wrong gender/number/person that flips meaning. "
    "Output the FULL corrected Hebrew line, changing as LITTLE as possible. Preserve every <tag>, {placeholder} and "
    "literal \\n EXACTLY. Hebrew+English letters only, no vowel points. The name V stays Latin; keep brand/vehicle/"
    "weapon/acronym names in English; keep foreign audio inside <kiroshi o=\"...\">.\n"
    "Be decisive and stingy — most rows are OK."
)
VERIFY_SYS = (
    "You adversarially verify a proposed Hebrew fix for Cyberpunk 2077. Reply EXACTLY one word: YES or NO.\n"
    "YES = the fix is genuinely needed (the original had a clear objective defect) AND the fix is correct AND it changes "
    "as little as possible. NO = the original was already fine, OR the fix changes meaning/over-rewrites, OR it touches a "
    "brand name / transliteration / V / kiroshi audio. Default to NO when unsure."
)


def gates_ok(he_old, fixed, en):
    if not fixed or not HEB.search(fixed) or NIQQUD.search(fixed) or foreign(fixed):
        return False
    if TAG.findall(fixed) != TAG.findall(he_old):
        return False
    if ESC.findall(fixed) != ESC.findall(he_old):
        return False
    if fixed == he_old:
        return False
    # anti-hallucination: length sane vs the old Hebrew
    if not (0.5 <= len(fixed) / max(1, len(he_old)) <= 2.0):
        return False
    return True


def main():
    from openai import OpenAI
    client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
    bdir = sys.argv[1] if len(sys.argv) > 1 else "qa_batches_next"
    files = sorted(glob.glob(os.path.join(HERE, bdir, "batch_*.json")))
    rows = []
    for f in files:
        rows.extend(json.load(open(f, encoding="utf-8")))
    print(f"local QA over {len(rows)} rows from {bdir}", flush=True)

    def ask(sysmsg, usermsg, mx=700):
        r = client.chat.completions.create(
            model=MODEL_ID, temperature=0.1, max_tokens=mx, timeout=240,
            messages=[{"role": "system", "content": sysmsg}, {"role": "user", "content": usermsg}])
        return (r.choices[0].message.content or "").strip()

    fixes, report, okn, fixn, human = {}, [], 0, 0, 0
    for i, r in enumerate(rows, 1):
        en, he = r.get("english", ""), r.get("hebrew", "")
        sec, pk, fld = r["section"], r["pk"], r["field"]
        ref = f"{sec}|{pk}|{fld}"
        verdict = "OK"
        try:
            out = ask(JUDGE_SYS, f"EN: {en}\nHE: {he}")
            line = out.split("\n")[0].strip() if "\\n" not in out else out.strip()
            if line.upper().startswith("FIX:"):
                cand = line[4:].strip()
                if gates_ok(he, cand, en):
                    # adversarial self-verify
                    v = ask(VERIFY_SYS, f"EN: {en}\nOLD HE: {he}\nPROPOSED: {cand}", mx=8)
                    if v.strip().upper().startswith("YES"):
                        fixes[ref] = cand
                        verdict = "FIX"; fixn += 1
                    else:
                        verdict = "VERIFY_NO"; human += 1
                else:
                    verdict = "GATE_FAIL"; human += 1
            else:
                okn += 1
        except Exception as e:
            verdict = "ERR"; print("  err", repr(e)[:50], flush=True)
        report.append({"ref": ref, "verdict": verdict})
        if i % 25 == 0 or i == len(rows):
            print(f"  {i}/{len(rows)}  ok={okn} fix={fixn} reject={human}", flush=True)

    # apply
    data = json.load(open(G.BASE_TR, encoding="utf-8"))
    idx = {}
    for s, rs in data.items():
        if isinstance(rs, list):
            for e in rs:
                if isinstance(e, dict):
                    idx[(s, str(e.get("primaryKey") or e.get("stringId")))] = e
    touched_subs, ons = set(), False
    if not Q.acquire_lock("local_semantic"):
        sys.exit("[abort] lock")
    try:
        n = 0
        for ref, he in fixes.items():
            s, pk, fld = ref.split("|", 2)
            secs = [s]
            if s.startswith("onscreens"):
                secs = ["onscreens/onscreens.json", "onscreens/onscreens_final.json"]
            for ss in secs:
                e = idx.get((ss, pk))
                if e is not None and (e.get(fld) or "") != he:
                    e[fld] = he; n += 1
                    if ss.startswith("subtitles"):
                        touched_subs.add(ss)
                    elif ss.startswith("onscreens"):
                        ons = True
        bak = f"{G.BASE_TR}.bak.localqa.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(G.BASE_TR, bak)
        tmp = G.BASE_TR + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, G.BASE_TR)
        print(f"local QA: ok={okn} fix={fixn} reject={human}; applied {n} fields; backup {os.path.basename(bak)}", flush=True)
    finally:
        Q.release_lock()
    open(os.path.join(HERE, "local_semantic_subs.txt"), "w", encoding="utf-8").write("\n".join(sorted(touched_subs)))
    open(os.path.join(HERE, "local_semantic_onscreens.flag"), "w").write("1" if ons else "0")
    with open(os.path.join(HERE, "local_semantic_report.jsonl"), "w", encoding="utf-8") as f:
        for x in report:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"onscreens_touched={ons} touched_subs={len(touched_subs)}", flush=True)


if __name__ == "__main__":
    main()
