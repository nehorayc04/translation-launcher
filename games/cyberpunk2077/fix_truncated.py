"""
fix_truncated.py — repair the ~816 TRUNCATED onscreens translations.

Root cause: localization_export.json (the EN source used for translation) is
itself truncated for these rows, so the Hebrew was translated truncated and
even ends mid-<Input ...> tag — rendering broken in-game. The FULL English
lives in the game's lang_en_text.archive.

Stages:
  extract  — WolvenKit-extract + serialize lang_en_text onscreens -> full EN per pk
  queue    — find broken-tag spine entries, pair with FULL EN -> truncated_queue.jsonl
  translate— local LM Studio, tag-preserving (tags verbatim, text runs translated)
  merge    — gate + backup + atomic-write into the spine

All free/local. Subsequent onscreens bake ships it.
"""
import os, sys, json, re, time, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))

CLI  = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME = os.path.join(ROOT, "Game Lab", "Cyberpunk 2077")
LANG_EN = os.path.join(GAME, r"archive\pc\content\lang_en_text.archive")
SPINE = os.path.join(ROOT, "תרגום_משחקים", "source", "resources", "localization_translated.json")

WORK = r"c:\tmp\fix_truncated"
EXTRACT = os.path.join(WORK, "en_pristine")
TEXT = os.path.join(WORK, "en_text")
QUEUE = os.environ.get("FT_QUEUE", os.path.join(HERE, "truncated_queue.jsonl"))
RESULTS = os.environ.get("FT_RESULTS", os.path.join(HERE, "truncated_results.jsonl"))

TAG = re.compile(r"<[^>]*>|\{[^}]*\}")
HEB = re.compile(r"[א-ת]")
CTRL = "\x01\x02\x03\x04\x05"


def run(args, timeout=900):
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def broken(v):
    vis = TAG.sub("", v or "")
    return "<" in vis or ">" in vis


def val(x):
    return x.get("value") if isinstance(x, dict) else x


# ── stage: extract ──────────────────────────────────────────────────────────
def stage_extract():
    for d in (EXTRACT, TEXT):
        os.makedirs(d, exist_ok=True)
    for fn in ("onscreens.json", "onscreens_final.json"):
        print(f"extract+serialize {fn} from lang_en_text.archive ...")
        run([CLI, "extract", LANG_EN, "-o", EXTRACT, "-w", f"*{fn}*"])
        src = os.path.join(EXTRACT, "base", "localization", "en-us", "onscreens", fn)
        if not os.path.exists(src):
            sys.exit(f"FATAL: extract missing {src}")
        run([CLI, "convert", "serialize", src, "-o", TEXT])
        out = os.path.join(TEXT, fn + ".json")
        print(f"  -> {out} ({os.path.getsize(out):,} bytes)")


def load_full_en():
    """pk -> full English femaleVariant from the serialized EN CR2W."""
    en = {}
    for fn in ("onscreens.json", "onscreens_final.json"):
        data = json.load(open(os.path.join(TEXT, fn + ".json"), encoding="utf-8"))
        sec = f"onscreens/{fn}"
        try:
            entries = data["Data"]["RootChunk"]["root"]["Data"]["entries"]
        except (KeyError, TypeError):
            sys.exit(f"FATAL: bad structure in {fn}")
        for e in entries:
            pk = val(e.get("primaryKey"))
            fv = val(e.get("femaleVariant")) or val(e.get("maleVariant")) or ""
            if pk is not None:
                en[(sec, str(pk))] = fv
    return en


# ── stage: queue ────────────────────────────────────────────────────────────
def stage_queue():
    en = load_full_en()
    spine = json.load(open(SPINE, encoding="utf-8"))
    rows = []
    for sec in ("onscreens/onscreens.json", "onscreens/onscreens_final.json"):
        for e in spine.get(sec, []):
            if not isinstance(e, dict):
                continue
            pk = str(e.get("primaryKey"))
            for fld in ("femaleVariant", "maleVariant"):
                v = e.get(fld)
                if not v or len(v.strip()) <= 2 or not broken(v):
                    continue
                full = (en.get((sec, pk)) or "").lstrip(CTRL)
                if not full or broken(full):
                    continue  # even the game EN is odd — skip
                rows.append({"id": f"{sec}|{pk}|{fld}", "english": full, "old_hebrew": v})
    with open(QUEUE, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"queued {len(rows)} truncated entries -> {QUEUE}")


# ── stage: translate (tag-preserving, local LM) ────────────────────────────
SYSTEM = (
    "You are a professional Cyberpunk 2077 game localizer translating English to Hebrew. "
    "Rules: natural modern Hebrew, Night City register. Use ONLY Hebrew and English letters "
    "(no Arabic/Cyrillic/Thai/CJK, no Niqqud). Translate the text EXACTLY, no additions. "
    "Output ONLY the Hebrew translation."
)


def lm_translate(texts, client):
    """Translate a list of plain-text runs; returns list of Hebrew strings."""
    out = []
    for t in texts:
        t_str = t.strip()
        if not t_str or not re.search(r"[A-Za-z]", t_str):
            out.append(t)  # nothing to translate (punctuation/space run)
            continue
        try:
            r = client.chat.completions.create(
                model=MODEL_ID,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": t_str}],
                temperature=0.2, max_tokens=900, timeout=240,
            )
            he = (r.choices[0].message.content or "").strip()
            ok = HEB.search(he) and not re.search(r"[؀-ۿ฀-๿぀-ヿ一-鿿가-힯Ѐ-ӿ]", he)
            out.append(he if ok else None)
        except Exception as e:
            global LAST_ERR
            LAST_ERR = repr(e)[:200]
            out.append(None)
    return out


# gemma-4-31b-it — the user's chosen stronger model (2026-06-12); slower
# (~20s/call, partial RAM spill on the 16GB RX 9070) but better Hebrew.
# IMPORTANT: load it ALONE — `lms unload --all && lms load gemma-4-31b-it -y
# --gpu max --context-length 8192 --parallel 1` (multiple loaded models split
# VRAM and slowed gemma-2 30x on 2026-06-11).
MODEL_ID = "gemma-4-31b-it"
LAST_ERR = ""


def stage_translate():
    from openai import OpenAI
    client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
    rows = [json.loads(l) for l in open(QUEUE, encoding="utf-8") if l.strip()]
    done_ids = set()
    if os.path.exists(RESULTS):
        for l in open(RESULTS, encoding="utf-8"):
            try:
                done_ids.add(json.loads(l)["id"])
            except Exception:
                pass
    todo = [r for r in rows if r["id"] not in done_ids]
    print(f"translating {len(todo)} (resume: {len(done_ids)} already done)")
    fout = open(RESULTS, "a", encoding="utf-8")
    okn = 0
    for i, r in enumerate(todo, 1):
        en = r["english"]
        # split into tag/text runs; translate text runs only
        parts = TAG.split(en)            # text runs
        tags = TAG.findall(en)           # tags, verbatim
        he_parts = lm_translate(parts, client)
        if any(p is None for p in he_parts):
            fout.write(json.dumps({"id": r["id"], "translated": False,
                                   "err": LAST_ERR}, ensure_ascii=False) + "\n")
        else:
            # reassemble: text/tag interleaved (split yields n+1 parts for n tags)
            heb = he_parts[0]
            for tag, part in zip(tags, he_parts[1:]):
                heb += tag + part
            ok = HEB.search(heb) and not broken(heb)
            fout.write(json.dumps({"id": r["id"], "translated": bool(ok),
                                   "hebrew": heb if ok else None}, ensure_ascii=False) + "\n")
            okn += bool(ok)
        if i % 10 == 0 or i == len(todo):
            fout.flush()
            print(f"  {i}/{len(todo)}  ({okn} clean)", flush=True)
    fout.close()
    print(f"done -> {RESULTS}")


# ── stage: merge ────────────────────────────────────────────────────────────
def pad_tag_seams(v):
    """Ensure a space between visible text and tags (the LM strips run edges,
    so reassembly can glue an icon tag to a word)."""
    v = re.sub(r"([א-תA-Za-z0-9.,!?])(<[^/>][^>]*>)", r"\1 \2", v)
    v = re.sub(r"(</?>|</[^>]+>)([א-תA-Za-z0-9])", r"\1 \2", v)
    return v


def stage_merge():
    import cp2077_qa_defects as Q
    rows = [json.loads(l) for l in open(RESULTS, encoding="utf-8") if l.strip()]
    good = {}
    for r in rows:
        if not (r.get("translated") and r.get("hebrew")):
            continue
        rid = r["id"]
        parts = rid.split("|")
        if len(parts) == 4:           # project|section|pk|field (corrupt queue)
            parts = parts[1:]
        sec, pk, fld = parts[0], parts[1], parts[2]
        good[(sec, pk, fld)] = pad_tag_seams(r["hebrew"])
    spine = json.load(open(SPINE, encoding="utf-8"))
    if not Q.acquire_lock("fix_truncated"):
        sys.exit("[abort] QA lock held")
    try:
        n = 0
        for sec, entries in spine.items():
            if not isinstance(entries, list):
                continue
            for e in entries:
                if not isinstance(e, dict):
                    continue
                pk = str(e.get("primaryKey") or e.get("stringId"))
                for fld in ("femaleVariant", "maleVariant"):
                    he = good.get((sec, pk, fld))
                    if he and not broken(he) and HEB.search(he):
                        e[fld] = he
                        n += 1
        bak = f"{SPINE}.bak.truncfix.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(SPINE, bak)
        tmp = SPINE + ".tmp"
        json.dump(spine, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, SPINE)
        print(f"merged {n} repaired translations; backup {os.path.basename(bak)}")
    finally:
        Q.release_lock()


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "extract"
    {"extract": stage_extract, "queue": stage_queue,
     "translate": stage_translate, "merge": stage_merge}[stage]()
