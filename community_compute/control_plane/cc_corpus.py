# -*- coding: utf-8 -*-
"""UNIVERSAL corpus builder for the community-compute queue.

Format-agnostic: the caller decodes its own game's text with its own tools and
hands this module already-decoded {id: text} maps. Works for ANY game, ANY set
of reference languages, and BOTH modes:

  * mode="translate" — produce Hebrew from a New-Era reference panel
    (the game's OWN official translations in several languages) instead of the
    English alone ([[new-era-doctrine]]).
  * mode="review"    — a QA pass: an EXISTING Hebrew line is given; the worker
    reviews it against the panel and FIXES only real errors, else returns it
    unchanged (monotonic).

Output = {"items": {id: panel_text}, "sys": <system prompt>} — exactly the shape
`seed_jobs.py` consumes. The worker app is generic (it runs the job's `sys` over
the line's `src`), so a new game/language-set/mode needs NO app change — only a
new seed. The queue can hold many games/modes at once; the worker groups a
provider call by identical `sys`, so tasks never mix.

Usage (per game):
    import cc_corpus
    en   = decode_my_game(source_variant)          # {id: english}
    refs = {"FR": decode(fr), "DE": decode(de), "RU": decode(ru), ...}
    out  = cc_corpus.build_items(en, refs, mode="translate")
    # for review: pass current_he={id: existing_hebrew}, mode="review"
    json.dump(out, open("corpus.json", "w"), ensure_ascii=False)
"""

_TOKENS = "<tag>, <br>, {value}, %s/%d and [TOKEN]"

SYS_TRANSLATE = (
    "You are a professional game localizer translating into Hebrew. Each VALUE is a "
    "REFERENCE PANEL: the first line 'EN:' is the English source; the lines below are the "
    "game's OWN official translations in other languages (each labeled, e.g. FR/DE/IT/ES/"
    "RU/PL). Decide the most natural, correct Hebrew by weighing ALL of them together — "
    "meaning from the Romance/Germanic lines, gender and number from the Slavic lines "
    "(RU/PL/CS), register from DE — NOT from the English alone. Do NOT translate the panel "
    "literally and do NOT output any language label. Keep every " + _TOKENS + " EXACTLY as "
    "in the EN line. Proper names of people/places stay as-is. NO niqqud. Return ONLY a JSON "
    "object {id: hebrew_translation} and nothing else."
)

SYS_REVIEW = (
    "You are a senior Hebrew game-localization editor. Each VALUE is a REFERENCE PANEL: "
    "'EN:' is the English source, the other 'XX:' lines are the game's official translations "
    "in various languages, and 'CURRENT:' is an EXISTING Hebrew translation to REVIEW. If "
    "CURRENT is already correct, fluent and complete, return it UNCHANGED. Otherwise FIX only "
    "genuine errors: wrong meaning, wrong gender/number (verify against RU/PL/CS), a broken or "
    "missing token (" + _TOKENS + "), foreign-script leakage, niqqud, or unnatural phrasing. "
    "Never introduce niqqud. Keep all tokens EXACTLY. Return ONLY a JSON object "
    "{id: corrected_or_unchanged_hebrew} and nothing else."
)


def panel(en, refs, current_he=None):
    """Build one line's reference-panel text. `refs` = {label: value} (label→string)."""
    lines = [f"EN: {en}"]
    e = (en or "").strip()
    for lbl, val in refs.items():
        v = (val or "").strip()
        if v and v != e:                       # skip empties + copies of English
            lines.append(f"{lbl}: {v}")
    if current_he is not None and str(current_he).strip():
        lines.append(f"CURRENT: {current_he}")
    return "\n".join(lines)


def build_items(source, ref_maps, mode="translate", current_he=None, order=None):
    """source = {id: english}; ref_maps = {label: {id: value}}; current_he = {id: hebrew}.
    `order` = optional iterable of ids to preserve a visibility order (else source order)."""
    if mode not in ("translate", "review"):
        raise ValueError("mode must be 'translate' or 'review'")
    if mode == "review" and not current_he:
        raise ValueError("review mode needs current_he={id: existing_hebrew}")
    ids = list(order) if order is not None else list(source)
    items = {}
    for k in ids:
        en = source.get(k, "")
        if not str(en).strip():
            continue
        if mode == "review" and not str(current_he.get(k, "")).strip():
            continue                            # nothing to review
        refs = {lbl: m.get(k, "") for lbl, m in ref_maps.items()}
        items[k] = panel(en, refs, current_he.get(k) if mode == "review" else None)
    return {"items": items, "sys": SYS_TRANSLATE if mode == "translate" else SYS_REVIEW}
