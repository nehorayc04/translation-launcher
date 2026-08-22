"""
deterministic_polish.py — NO-AI corpus-wide polish (EN-aware). v2

Per visible-text token, judged against the row's ENGLISH source:
  A. Half-flipped word (first letter transliterated to Hebrew):
       בITCH (EN has BITCH) -> BITCH      מIMI (EN has MIMI) -> MIMI
       SCSמ (EN has SCSM)   -> SCSM       קAMILA -> KAMILA
     Names/brands stay English per project rule — restore the EN word.
  B. Hebrew prefix glued to a standalone Latin acronym/number that exists
     in EN on its own:  בNC -> ב-NC,  ב2077 -> ב-2077,  לNPC -> ל-NPC
  C. Latin acronym + glued Hebrew PLURAL suffix (whitelist ים/ות/יות):
       NPCים -> NPC-ים
  D. Double spaces -> single.

Lowercase half-words (גlitch, אaarghh) are NOT touched — they are being
retranslated by the LM corrupt-queue run. Tag/placeholder spans untouched.

Usage: python deterministic_polish.py [--dry-run] [--dlc]
"""
import os, sys, json, re, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

TAG = re.compile(r"(<[^>]*>|\{[^}]*\})")
DSPACE = re.compile(r"  +")
# Hebrew letter -> Latin letter candidates (for reconstructing a flipped head)
TRANSLIT = {
    "א": "AEIOU", "ב": "B", "ג": "G", "ד": "D", "ה": "H", "ו": "VWU",
    "ז": "Z", "ח": "H", "ט": "T", "י": "YI", "כ": "CK", "ל": "L",
    "מ": "M", "נ": "N", "ס": "S", "ע": "AE", "פ": "PF", "צ": "C",
    "ק": "KCQ", "ר": "R", "ש": "S", "ת": "T",
}
PREFIXES = set("ובלכמהש")
SUFFIX_WL = ("ים", "ות", "יות")
# token: 1-2 Hebrew letters + UPPERCASE-led Latin run (the בITCH/בNC family)
PRE_TOK = re.compile(r"(?<![א-תA-Za-z0-9-])([א-ת]{1,2})([A-Z][A-Za-z0-9]*)(?![א-תa-z])")
# token: Latin run + trailing Hebrew letters (the NPCים/SCSמ family)
SUF_TOK = re.compile(r"(?<![א-תA-Za-z0-9-])([A-Z][A-Za-z0-9]*)([א-ת]{1,4})(?![א-תA-Za-z])")
NUM_PRE = re.compile(r"(?<![א-תA-Za-z0-9-])([א-ת])([0-9]{2,})(?![0-9א-תA-Za-z])")
# orphaned vav: "ו מכדורים" -> "ומכדורים" (ו never stands alone in Hebrew)
VAV_ALONE = re.compile(r"(?<![א-תA-Za-z0-9\"'־-])ו (?=[א-ת]{2,})")


def en_find(en, word):
    """Return the word AS WRITTEN in EN (original casing), or None."""
    m = re.search(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", en, re.IGNORECASE)
    return m.group(0) if m else None


def fix_text(t, en, log):
    def pre_repl(m):
        heb, lat = m.group(1), m.group(2)
        # A) half-flipped: translit(last heb char)+lat is a word in EN -> restore EN word
        for c in TRANSLIT.get(heb[-1], ""):
            found = en_find(en, c + lat)
            if found:
                fixed = (heb[:-1] + found) if len(heb) > 1 else found
                log.append((m.group(0), fixed)); return fixed
        # B) prefix + standalone acronym known to EN -> maqaf
        if heb[-1] in PREFIXES and lat.isupper() and en_find(en, lat):
            fixed = f"{heb}-{lat}"
            log.append((m.group(0), fixed)); return fixed
        return m.group(0)

    def suf_repl(m):
        lat, heb = m.group(1), m.group(2)
        # A) flipped tail: lat+translit(first heb char) in EN -> restore
        if len(heb) == 1:
            for c in TRANSLIT.get(heb[0], ""):
                found = en_find(en, lat + c)
                if found:
                    log.append((m.group(0), found)); return found
        # C) plural suffix whitelist -> maqaf
        if heb in SUFFIX_WL and lat.isupper():
            fixed = f"{lat}-{heb}"
            log.append((m.group(0), fixed)); return fixed
        return m.group(0)

    def num_repl(m):
        heb, num = m.group(1), m.group(2)
        if heb in PREFIXES and en_find(en, num):
            fixed = f"{heb}-{num}"
            log.append((m.group(0), fixed)); return fixed
        return m.group(0)

    t = PRE_TOK.sub(pre_repl, t)
    t = SUF_TOK.sub(suf_repl, t)
    t = NUM_PRE.sub(num_repl, t)
    n = VAV_ALONE.sub("ו", t)
    if n != t:
        log.append(("ו [orphan]", "ו+word")); t = n
    return DSPACE.sub(" ", t)


def fix_value(v, en, log):
    parts = TAG.split(v)
    return "".join(p if TAG.fullmatch(p) else fix_text(p, en or "", log) for p in parts)


def main():
    dry = "--dry-run" in sys.argv
    want_dlc = "--dlc" in sys.argv
    path = G.DLC_TR if want_dlc else G.BASE_TR
    corpus, _, _ = G.build_corpus()
    # (section, pk, field) -> english
    en_by = {(r.section, str(r.pk), r.field): (r.english or "") for r in corpus}
    data = json.load(open(path, encoding="utf-8"))
    changed = 0
    tok_log = []
    for sec, rows in data.items():
        is_dlc = sec.startswith("ep1")
        if want_dlc != is_dlc and not want_dlc:
            pass  # base file may hold ep1 overflow sections; polish them too
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            pk = str(e.get("primaryKey") or e.get("stringId"))
            for fld in ("femaleVariant", "maleVariant"):
                v = e.get(fld)
                if not v:
                    continue
                log = []
                nv = fix_value(v, en_by.get((sec, pk, fld), ""), log)
                if nv != v:
                    changed += 1
                    tok_log.extend(log[:2])
                    if not dry:
                        e[fld] = nv
    print(f"{'DRY-RUN ' if dry else ''}changed values: {changed}")
    import collections
    cnt = collections.Counter(tok_log)
    for (a, b), n in cnt.most_common(25):
        print(f"  {a!r} -> {b!r}  ×{n}")
    if dry or not changed:
        return
    if not Q.acquire_lock("deterministic_polish"):
        sys.exit("[abort] QA lock held")
    try:
        bak = f"{path}.bak.polish.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(path, bak)
        tmp = path + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, path)
        print(f"saved; backup {os.path.basename(bak)}")
    finally:
        Q.release_lock()


if __name__ == "__main__":
    main()
