# -*- coding: utf-8 -*-
"""TRANSLATION MEMORY with cross-language fuzzy matching — runs BEFORE the API call so the fleet
reuses past work instead of re-translating (consistency + big API saving). GAME-AGNOSTIC.

Two wins:
  EXACT (100%)  — an approved line whose English AND the game's other languages are IDENTICAL →
                  reuse its Hebrew verbatim, NO API call.
  FUZZY (>=thr) — a near-identical approved line → reuse its Hebrew as a TEMPLATE. If the ONLY
                  difference is a CLOSED-SET swappable token (a number, a {var}, or a brain glossary
                  term), swap it deterministically and return the Hebrew (still no API). Otherwise
                  return a HINT (the approved Hebrew + the diff) for the worker to ADAPT.

⚠️ THE CROSS-LANGUAGE GUARD (the decisive rule): a fuzzy ENGLISH match is reusable only if the game's
OTHER languages ALSO match the gender/meaning SHAPE — an identical English line can mean or gender
DIFFERENTLY (the dedup-safety lesson). So a match is accepted only when `split_langs` agree; otherwise
it is demoted to a hint, never an auto-reuse.

⚠️ AUTO-SWAP IS DELIBERATELY LIMITED to numbers / {vars} / glossary terms — tokens that carry NO
Hebrew agreement. An adjective swap (red→blue = אדומה→כחולה) needs gender/number agreement, so it is
NEVER auto-applied; it becomes a fuzzy-hint the worker/verifier confirms. Do not put agreement-
sensitive words in the auto-swap glossary.
"""
import re, difflib

TOKEN = re.compile(r'^(?:\{[^{}]*\}|%[0-9.]*[a-zA-Z]|LocKey#\d+|\d+(?:[.,]\d+)?)$')  # a swappable structural
_FLOOR = 0.5   # min char-ratio to even consider a candidate; a clean closed-set swap auto-applies above it


def _norm(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def _words(s):
    return re.findall(r"\{[^{}]*\}|%[0-9.]*[a-zA-Z]|LocKey#\d+|[^\s]+", _norm(s))


def ratio(a, b):
    return difflib.SequenceMatcher(None, _norm(a).lower(), _norm(b).lower()).ratio()


def _diff_swaps(a_words, b_words):
    """Return [(old, new)] iff a and b differ ONLY by equal-length single-token REPLACES.
    Any insert/delete/uneven span => None (not a clean template swap)."""
    sm = difflib.SequenceMatcher(None, a_words, b_words)
    swaps = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1):
                swaps.append((a_words[i1 + k], b_words[j1 + k]))
        else:
            return None
    return swaps


class TM:
    def __init__(self, approved, gender_langs=("ar", "ru", "pl", "cs", "es", "es-es", "es-mx",
                                               "fr", "it", "pt", "de")):
        """approved: {id: {"en","refs":{lang:[fv,mv]},"he":str|[fv,mv],"split_langs":[...]}}"""
        self.gender_langs = tuple(gender_langs)
        self._exact = {}          # exact_key -> he
        self._block = {}          # blocking_key -> [(en, he, split_langs)]
        for _id, r in approved.items():
            en = _norm(r.get("en", ""))
            he = r.get("he")
            if isinstance(he, (list, tuple)):
                he = he[0] or (he[1] if len(he) > 1 else "")
            if not en or not he:
                continue
            refs = r.get("refs", {})
            split = tuple(sorted(r.get("split_langs", [])))
            self._exact.setdefault(self._exact_key(en, refs), he)
            self._block.setdefault(self._block_key(en), []).append((en, he, split))

    # ---- keys ----
    def _exact_key(self, en, refs):
        sig = [_norm(en).lower()]
        for l in self.gender_langs:
            v = refs.get(l)
            if v:
                sig.append(f"{l}={_norm(v[0]).lower()}|{_norm(v[1]).lower()}")
        return "␟".join(sig)

    def _block_key(self, en):
        w = _words(en)
        return (len(w), (w[0].lower() if w else ""), (w[-1].lower() if w else ""))

    # ---- lookup ----
    def lookup(self, en, refs=None, split_langs=None, brain=None, threshold=0.9):
        """Returns one of:
          ("exact",      he,   {})                        -> reuse verbatim, no API
          ("fuzzy-auto", he,   {"ratio","from","swaps"})  -> template swap applied, no API
          ("fuzzy-hint", he,   {"ratio","from","diff"})   -> strong hint; worker adapts (agreement!)
          None                                            -> send to the fleet normally"""
        en = _norm(en); refs = refs or {}
        split = tuple(sorted(split_langs or []))

        ek = self._exact_key(en, refs)
        if ek in self._exact:
            return ("exact", self._exact[ek], {})

        # fuzzy: candidates from adjacent blocking buckets (word-count ±1, same first OR last word)
        wc, fw, lw = self._block_key(en)
        cands = []
        for k, rows in self._block.items():
            if abs(k[0] - wc) <= 1 and (k[1] == fw or k[2] == lw):
                cands.extend(rows)
        # keep the best shape-matching candidate above a low retrieval FLOOR; the auto/hint decision
        # below uses the CLEANNESS of the diff (a closed-set swap is safe even at a low ratio, because
        # a single big word-change on a short line drops char-ratio well below `threshold`).
        best = None
        for a_en, a_he, a_split in cands:
            if a_split != split:            # CROSS-LANGUAGE GUARD: gender/meaning shape must match
                continue
            r = ratio(en, a_en)
            if r >= _FLOOR and (best is None or r > best[0]):
                best = (r, a_en, a_he)
        if not best:
            return None

        r, a_en, a_he = best
        meta = {"ratio": round(r, 3), "from": a_en}
        # a HINT is only offered on a genuinely high-similarity line; a closed-set AUTO swap may fire lower.
        hint = ("fuzzy-hint", a_he, {**meta, "diff": None}) if r >= threshold else None

        swaps = _diff_swaps(_words(a_en), _words(en))
        if swaps is None:
            return hint
        if not swaps:                                          # identical English, matching shape
            return ("fuzzy-auto", a_he, {**meta, "swaps": []})

        # strategy A — all diffs are pure structural tokens (numbers / {vars} / LocKey): swap literally
        if all(TOKEN.match(o) and TOKEN.match(n) for o, n in swaps):
            he = a_he; applied = []
            for old, new in swaps:
                rx = re.compile(r'(?<!\w)' + re.escape(old) + r'(?!\w)')
                if not rx.search(he):
                    return hint
                he = rx.sub(new, he, count=1); applied.append((old, new))
            return ("fuzzy-auto", he, {**meta, "swaps": applied})

        # strategy B — exactly ONE glossary term replaced by another (handles multi-word terms):
        # swap the removed term's Hebrew for the added term's Hebrew. No agreement risk (nouns/names).
        if brain is not None:
            ta = brain.terms_in(a_en); tb = brain.terms_in(en)
            aset = {t["en"].lower() for t in ta}; bset = {t["en"].lower() for t in tb}
            removed = [t for t in ta if t["en"].lower() not in bset]
            added = [t for t in tb if t["en"].lower() not in aset]
            if (len(removed) == 1 and len(added) == 1 and removed[0].get("he")
                    and added[0].get("he") and removed[0]["he"] in a_he):
                he = a_he.replace(removed[0]["he"], added[0]["he"], 1)
                return ("fuzzy-auto", he, {**meta, "swaps": [(removed[0]["he"], added[0]["he"])]})

        # otherwise: agreement-sensitive (adjective, reorder, unknown word) -> the worker adapts
        return ("fuzzy-hint", a_he, {**meta, "diff": swaps}) if r >= threshold else None
