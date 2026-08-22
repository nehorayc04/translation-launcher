"""fix_truncated_onscreens.py — re-translate onscreens entries whose Hebrew
value is structurally BROKEN (truncated mid-<Rich>-tag) so the engine renders
the literal markup in-game.

ROOT CAUSE: localization_export.json (the spine's build source) was truncated
at ~127 chars, so long perk/cyberware descriptions were translated only up to
the cut — leaving a dangling '<Rich color=...' with no '>' that renders raw.
The FULL English text IS available in the game's lang_en_text.archive (freshly
extracted + serialized to $TEMP/en_onscreens_full/text/*.json).

FIX: for each entry where our Hebrew fails the slot parser (mk.parse_slots ->
None) BUT the full English parses cleanly, re-translate the FULL English via
the tested slot model (tags + {placeholders} kept verbatim, only human text
translated), validate the result parses cleanly, and write it to the spine.

Leading control byte (the markup-mode marker) is preserved from the English.

Safety: QA write-lock, spine backup, atomic write, per-entry validation
(a failed/contaminated piece -> entry is LEFT untouched, never half-written).
"""
import json, os, sys, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
UNIV = os.path.join(ROOT, "universal")
sys.path.insert(0, HERE); sys.path.insert(0, UNIV)
import cp2077_markup_translate as mk
import cp2077_qa_defects as Q
import get_next_audit_batch as G
from openai import OpenAI

SPINE = G.BASE_TR
TEMP = os.environ["TEMP"]
EN_PATHS = {
    "onscreens/onscreens.json":       os.path.join(TEMP, "en_onscreens_full", "text", "onscreens.json.json"),
    "onscreens/onscreens_final.json": os.path.join(TEMP, "en_onscreens_full", "text", "onscreens_final.json.json"),
}


def en_index(path):
    wkit = json.load(open(path, encoding="utf-8"))
    ents = wkit["Data"]["RootChunk"]["root"]["Data"]["entries"]
    return {str(e.get("primaryKey")): e for e in ents}


def split_lead(s):
    if s and ord(s[0]) < 0x20:
        return s[0], s[1:]
    return "", s


def translate_full(enfv):
    """Full English markup string -> full Hebrew, or None if unsafe."""
    lead, body = split_lead(enfv)
    slots = mk.parse_slots(body)
    if slots is None:
        return None
    tr_idx = [i for i, (k, _) in enumerate(slots) if k == "TR"]
    raw_pieces = [slots[i][1] for i in tr_idx]
    stripped = [p.strip() for p in raw_pieces]
    hebs = mk.translate_pieces(stripped) if stripped else []
    for n, i in enumerate(tr_idx):
        he = hebs[n] if n < len(hebs) else ""
        if not mk.valid_piece(stripped[n], he):
            return None                         # a piece failed -> skip entry
        raw = raw_pieces[n]                      # keep original spacing around tags
        lead_ws = raw[:len(raw) - len(raw.lstrip())]
        trail_ws = raw[len(raw.rstrip()):]
        slots[i] = ("TR", lead_ws + he + trail_ws)
    result = lead + mk.reassemble(slots)
    # final structural validation (re-parse without the lead byte)
    _, rbody = split_lead(result)
    if mk.parse_slots(rbody) is None:
        return None
    # require Hebrew ONLY when there was translatable text; pure placeholder /
    # code strings (e.g. "{Minutes}:{Seconds}") legitimately carry no Hebrew.
    if tr_idx and not mk.HEB.search(result):
        return None
    return result


def translate_full_retry(enfv, attempts=2):
    for _ in range(attempts):
        he = translate_full(enfv)
        if he is not None:
            return he
    return None


def main():
    mk.lm_client = OpenAI(base_url=mk.LM_URL, api_key="lm-studio", timeout=600)
    if not Q.acquire_lock("fix_truncated_onscreens"):
        sys.exit("[abort] QA lock held by another process.")
    try:
        spine = json.load(open(SPINE, encoding="utf-8"))
        eni = {sec: en_index(p) for sec, p in EN_PATHS.items()}

        # build work list
        work = []
        for sec, idx in eni.items():
            for e in spine[sec]:
                fv = e.get("femaleVariant") or ""
                if not fv or mk.parse_slots(fv) is not None:
                    continue                    # our HE already parses -> fine
                en = idx.get(str(e.get("primaryKey")))
                if not en:
                    continue
                enfv = en.get("femaleVariant") or ""
                if mk.parse_slots(split_lead(enfv)[1]) is None:
                    continue                    # EN itself damaged -> can't fix
                work.append((sec, e, enfv))
        print(f"truncated/broken entries to re-translate: {len(work)}")

        fixed = skipped = 0
        for n, (sec, e, enfv) in enumerate(work, 1):
            he = translate_full_retry(enfv)
            if he is None:
                skipped += 1
                continue
            e["femaleVariant"] = he
            # spine maleVariant is empty for these; bake backfills from fv.
            fixed += 1
            if n % 20 == 0:
                print(f"  {n}/{len(work)}  fixed={fixed} skipped={skipped}")

        stamp = time.strftime("%Y%m%d_%H%M%S")
        bak = f"{SPINE}.bak.trunc.{stamp}"
        shutil.copy2(SPINE, bak)
        tmp = SPINE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(spine, f, ensure_ascii=False)
        os.replace(tmp, SPINE)
        print(f"backup -> {os.path.basename(bak)}")
        print(f"DONE: fixed={fixed}  skipped={skipped}  (total {len(work)})")

        # verify residual broken
        spine2 = json.load(open(SPINE, encoding="utf-8"))
        residual = 0
        for sec, idx in eni.items():
            for e in spine2[sec]:
                fv = e.get("femaleVariant") or ""
                if fv and mk.parse_slots(fv) is None and idx.get(str(e.get("primaryKey"))):
                    enfv = idx[str(e.get("primaryKey"))].get("femaleVariant") or ""
                    if mk.parse_slots(split_lead(enfv)[1]) is not None:
                        residual += 1
        print(f"VERIFY residual fixable-broken: {residual}")
    finally:
        Q.release_lock()


if __name__ == "__main__":
    main()
