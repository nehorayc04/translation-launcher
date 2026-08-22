# -*- coding: utf-8 -*-
"""final_cleanup.py — last targeted pass over the REAL remaining defects only.

Root-cause aware (does NOT touch intentional foreign-flavor gang dialogue):
  * seams  (mixed_script_word + corrupt_midword) -> a glued Hebrew+Latin token.
            Force ONE script. Brand/product -> full English (maqaf for a Hebrew
            one-letter prefix). Name -> Hebrew translit. scream -> all Hebrew.
  * foreign-leftover (long_latin_run + foreign_script) -> re-translate to Hebrew
            ONLY when the ENGLISH SOURCE is plain English (mostly Latin/ASCII).
            If the EN source is itself foreign (Spanish Valentinos / Creole
            Voodoo Boys flavor) we LEAVE it — that matches the original game.

Reads word_anomalies.jsonl + the language scan. Gemma-4 fixes, strict gate,
spine backup + QA-lock + atomic write. Collects touched onscreens / subtitles.
"""
import os, sys, json, re, time, shutil, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

MODEL_ID = "gemma-4-31b-it"
HEB = re.compile(r"[א-ת]")
# any letter that is NOT basic-Latin and NOT Hebrew = foreign script
FOREIGN = re.compile(r"[Ͱ-ϿЀ-ӿ֐-׿؀-ۿ"
                     r"ऀ-ॿঀ-৿฀-๿぀-ヿ"
                     r"一-鿿가-힯]")
HEB_RANGE = re.compile(r"[֐-׿]")  # Hebrew block alone (for FOREIGN exclusion)
NIQQUD = re.compile(r"[֑-ׇ]")
TAG = re.compile(r"<[^>]*>|\{[^}]*\}")
SEAM = re.compile(r"[א-ת][A-Za-z]|[A-Za-z][א-ת]")
LATIN = re.compile(r"[A-Za-z]")
# foreign-but-not-Hebrew detector used on the Hebrew value
FOREIGN_NONHEB = re.compile(r"[Ͱ-ϿЀ-ӿ؀-ۿ"
                            r"ऀ-ॿঀ-৿฀-๿"
                            r"぀-ヿ一-鿿가-힯]")

SYS_SEAM = (
    "You fix ONE Hebrew line from Cyberpunk 2077 that contains a BROKEN word — Hebrew "
    "letters glued directly to Latin letters in one token. Rewrite the WHOLE line so NO "
    "token mixes Hebrew and Latin, using the English source for meaning:\n"
    "- BRAND / PRODUCT / TECH name (MetalFX, CrystalCoat, Doomlauncher) -> write it FULLY "
    "in English; a Hebrew one-letter prefix attaches with a maqaf (ל-Quadra).\n"
    "- PERSON name -> full Hebrew transliteration.\n"
    "- scream / sound -> ALL Hebrew letters.\n"
    "Keep every <tag>, {placeholder} and literal \\n EXACTLY. No Arabic, no vowel points. "
    "Output ONLY the corrected Hebrew line."
)
SYS_TR = (
    "You are a professional Cyberpunk 2077 localizer. Translate the English line to natural "
    "modern Hebrew (Night City register). The current Hebrew draft accidentally left a run of "
    "untranslated foreign words — translate the WHOLE line properly to Hebrew. Keep brand / "
    "product / weapon / vehicle names and acronyms in English. Preserve every <tag>, "
    "{placeholder} and literal \\n EXACTLY. Hebrew + English letters only, no vowel points, "
    "no Arabic. Output ONLY the Hebrew translation."
)


def en_is_plain(en):
    """English source is plain English we can safely re-translate (not foreign flavor)."""
    core = TAG.sub(" ", en or "")
    if FOREIGN.search(core):
        return False
    letters = re.findall(r"[A-Za-zא-ת]", core)
    if not letters:
        return False
    # >=85% Latin among letters → treat as English
    lat = sum(1 for c in letters if "A" <= c <= "z" and (c.isalpha()))
    return lat / len(letters) >= 0.85


def gate_seam(he, en):
    if not he or not HEB.search(he) or FOREIGN_NONHEB.search(he) or NIQQUD.search(he):
        return False
    if SEAM.search(TAG.sub(" ", he)):
        return False
    if TAG.findall(he) != TAG.findall(en):
        return False
    return True


def gate_tr(he, en):
    if not he or not HEB.search(he) or FOREIGN_NONHEB.search(he) or NIQQUD.search(he):
        return False
    if TAG.findall(he) != TAG.findall(en):
        return False
    # must not still carry a long Latin run
    for m in re.finditer(r"[A-Za-z][A-Za-z '\-]{29,}", TAG.sub(" ", he)):
        if len(m.group(0).split()) >= 5:
            return False
    return True


def load_targets():
    """Build the fix queue from the scan outputs. ref = proj|section|pk|field."""
    anom = [json.loads(l) for l in open(os.path.join(HERE, "word_anomalies.jsonl"), encoding="utf-8") if l.strip()]
    seam_cats = {"mixed_script_word", "corrupt_midword"}
    leak_cats = {"long_latin_run", "foreign_script"}
    by_ref = {}
    for r in anom:
        cat = r["category"]
        kind = "seam" if cat in seam_cats else ("leak" if cat in leak_cats else None)
        if not kind:
            continue
        ref = f"{r['project']}|{r['section']}|{r['pk']}|{r['field']}"
        # seam wins over leak for the same ref
        if ref not in by_ref or kind == "seam":
            by_ref[ref] = {"ref": ref, "kind": kind, "section": r["section"],
                           "pk": r["pk"], "field": r["field"],
                           "hebrew": r["hebrew"], "english": r.get("english", "")}
    return list(by_ref.values())


def main():
    from openai import OpenAI
    client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

    # full spine so we read the COMPLETE current value (scan stored a 160-char clip)
    data = json.load(open(G.BASE_TR, encoding="utf-8"))
    idx = {}
    for sec, rs in data.items():
        if isinstance(rs, list):
            for e in rs:
                if isinstance(e, dict):
                    idx[(sec, str(e.get("primaryKey") or e.get("stringId")))] = e

    targets = load_targets()
    print(f"candidates: {len(targets)}", flush=True)
    fixes, human, skipped_flavor = {}, [], 0
    okn = 0
    for i, t in enumerate(targets, 1):
        e = idx.get((t["section"], t["pk"]))
        if e is None:
            continue
        fld = t["field"]
        cur = e.get(fld) or ""
        en = t["english"] or ""
        if not cur:
            continue
        if t["kind"] == "leak":
            # only re-translate when the EN source is plain English
            if not en_is_plain(en):
                skipped_flavor += 1
                continue
            sys_p, gate = SYS_TR, gate_tr
            user = en
        else:
            sys_p, gate = SYS_SEAM, gate_seam
            user = f"English source: {en}\nHebrew line: {cur}"
        try:
            resp = client.chat.completions.create(
                model=MODEL_ID, temperature=0.15, max_tokens=900, timeout=240,
                messages=[{"role": "system", "content": sys_p},
                          {"role": "user", "content": user}])
            raw = (resp.choices[0].message.content or "").strip()
            he = raw if "\\n" in raw else raw.split("\n")[0]
            if gate(he, en):
                fixes[t["ref"]] = he
                okn += 1
            else:
                human.append(t)
        except Exception as ex:
            human.append(t); print("  err", repr(ex)[:50], flush=True)
        if i % 15 == 0 or i == len(targets):
            print(f"  {i}/{len(targets)}  fixed={okn} human={len(human)} flavor-skip={skipped_flavor}", flush=True)

    # apply
    touched_subs = set()
    onscreens_touched = False
    if not Q.acquire_lock("final_cleanup"):
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
                elif sec.startswith("onscreens"):
                    onscreens_touched = True
        bak = f"{G.BASE_TR}.bak.finalcleanup.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(G.BASE_TR, bak)
        tmp = G.BASE_TR + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, G.BASE_TR)
        print(f"fixed {okn}; applied {n} fields; human {len(human)}; flavor-left {skipped_flavor}; backup {os.path.basename(bak)}", flush=True)
    finally:
        Q.release_lock()

    open(os.path.join(HERE, "final_cleanup_subs.txt"), "w", encoding="utf-8").write("\n".join(sorted(touched_subs)))
    open(os.path.join(HERE, "final_cleanup_onscreens.flag"), "w").write("1" if onscreens_touched else "0")
    with open(os.path.join(HERE, "final_cleanup_human.jsonl"), "w", encoding="utf-8") as f:
        for t in human:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"onscreens_touched={onscreens_touched} touched_subs={len(touched_subs)}", flush=True)


if __name__ == "__main__":
    main()
