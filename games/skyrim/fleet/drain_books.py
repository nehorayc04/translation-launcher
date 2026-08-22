#!/usr/bin/env python3
"""drain_books.py — finish the Skyrim tail: mask the tokens, split the books, repair the
blank lines.

🔴 THE PROBLEM, measured 2026-08-09 from the three worker logs (last 125 rejections):

    token-mismatch  50 (40%)   <p align="center"> / </p> / <br> mangled inside a book page
    no-hebrew       33 (26%)   the line is ONLY markup -- no legal output exists, ever
    newline-count   23 (18%)   19 of 23 are +-2 blank lines in a page that has 216 of them
    empty           14
    copy-EN          4
    foreign-script   1

and, on top of that, `step1 fail (read operation timed out)` on the monsters: 190 of the
327 real remaining lines carry `[pagebreak]` and run to a 3,628-char median (max 40,131).

Three fixes, each of them the SAME principle -- a defect with exactly one correct answer is
REPAIRED or PREVENTED, never struck:

  1. MASK.  Every engine token becomes an opaque `⟦0⟧ ⟦1⟧` before the call and is restored
     after. The model cannot mangle what it never saw. This is the RDR2 fix
     (`games/rdr2/fleet/drain_tokenheavy.py`), where the identical wall took the same lines
     from `+0/13` to 40/40 accepted.
     ⚠️ `[pagebreak]` is NOT in the worker's STRUCT regex (that was measured on the UI
     corpus, where brackets are ordinary punctuation) yet it occurs 712 times in this tail.
     It is page structure: masked here, and CHECKED here, so it can no longer be silently
     translated or dropped.

  2. SPLIT.  A line is cut on `[pagebreak]` (and, if a page is still huge, on paragraph
     breaks) into segments that fit one call: 190 monsters become 680 pages at a 685-char
     median. Segments are translated independently and rejoined with the ORIGINAL delimiters
     byte-for-byte, so the page structure cannot drift.

  3. ALIGN.  Blank lines are layout, not content. If the English and the Hebrew have the
     same number of NON-EMPTY lines, the Hebrew is rebuilt onto the English's exact
     blank-line skeleton -- deterministic, one correct answer, and it can only make the
     counts agree. A different non-empty count is a real content failure and still rejects.

Markup-only lines (391 of them: `<p align='center'>\\r\\n</p>`, a page that is one `<img>`) can
never satisfy `no-hebrew`; they are written to `empty.json` for the reslice to exclude, the
same way `oversized.json` already works. They are NOT fake-banked. The same test is applied to
each SEGMENT (a doubled `[pagebreak]` carves out a deliberately blank page), which is echoed
verbatim rather than sent.

An adversarial audit of all three mechanisms (2026-08-09) confirmed three SILENT corruptions —
each one an output that was WRONG and that the guard ACCEPTED — and all three are fixed here:
the 80-char tag cap that hid 47 `<img>` paths from both the mask and the token check, the
content-free segments whose only accepted answer was invented text, and an align that turned a
merge+split reflow from a rejection into an acceptance. Each fix is marked 🔴🔴 below.

Runs as a SEPARATE process on purpose (the RDR2 precedent): the 3 desktop streams keep
running untouched, and this only ADDS a bank file. `banks/out_zzdrain.json` sorts LAST, so
the merge in pull_skyrim.sh gives it the final word.

    python drain_books.py                    # dry run: classify + show the masking/splitting
    python drain_books.py --apply [--max N]
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Paths default to this script's own directory but are overridable, because the script is
# RUN from the worker dir (C:/skyrimw -- that is where keys.json lives, and keys never go in
# the repo) while the full corpus + banks live in the repo tree.
FLEET = os.environ.get("SKYRIM_FLEET", HERE)


def _p(*a):
    return os.path.join(FLEET, *a)


# ── the token model ──────────────────────────────────────────────────────────────────────
# The worker's STRUCT plus `[pagebreak]`. Longest-first so `<p align="center">` is one token
# and never two.
#
# 🔴🔴 THE TAG BOUND IS 400, NOT THE WORKER'S 80 — an adversarial audit (2026-08-09) proved
# the 80-char cap INVERTS the guard. 47 `<img src='img://Textures/Interface/Books/….png'
# width='290' height='389'>` tags on 26 real lines have 81-110 inner chars, so STRUCT never
# matched them, and the SAME bound then broke three things in the same direction: mask() showed
# the raw path to the model, the token check compared [] to [] and saw nothing, and
# is_markup_only() left `img/Textures/png/width/height` behind as "words" so a pure-image page
# counted as real work. On all 24 pure-image pages the honest echo was REJECTED (`no-hebrew`)
# while Hebrew that DELETED the image was ACCEPTED — the only outputs the guard allowed were
# the corrupt ones. `[^<>]` still cannot cross a tag boundary, so a wider bound never
# over-matches; it just makes every tag both masked and checked.
STRUCT = re.compile(r"\[pagebreak\]|<[^<>]{1,400}>|\{[^{}]{0,80}\}")
MARK = re.compile(r"⟦(\d+)⟧")
NIQ = re.compile("[\u0591-\u05bd\u05bf\u05c1\u05c2\u05c7]")
HEB = re.compile("[\u05d0-\u05ea]")
FOREIGN = re.compile("[\u0400-\u04ff\u0370-\u03ff\u0600-\u06ff\u0750-\u077f"
                     "\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")
LOWER = re.compile(r"[a-z]{2,}")
WORD = re.compile(r"[A-Za-z\u05d0-\u05ea]")
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'\u2019/\u00ae\u2122\u00a9]*$")
_DASHES = str.maketrans({c: "-" for c in
                         "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
                         "\u2e3a\u2e3b\ufe58\ufe63\uff0d"})
_PREFIX_HYPHEN = re.compile("(?<![\u05d0-\u05ea])([\u05d5\u05d1\u05dc\u05de\u05d4\u05e9\u05db])"
                            "-(?=[\u05d0-\u05ea])")

# 🔑 SMALL SEGMENTS, because the segment size decides which PROVIDERS can serve it.
# `max_tokens` scales with the segment, and on a 2,500-char page that reservation is ~6k
# tokens — measured 2026-08-09: groq returns HTTP 429 (its per-minute budget is charged the
# RESERVATION, not the usage) and only nim answers, so the whole drain funnels through one
# provider at ~15 min per batch. At 900 chars the reservation lands near 3k, which is the
# window groq is documented to answer in, and all three providers become usable.
# It costs nothing in quality: the book lines are PARAGRAPHS, not hard wraps — measured, 94%
# of lines longer than 60 chars end in sentence punctuation — so a cut on a line boundary
# never splits a sentence.
SEG_MAX = 900
BUDGET = 1800          # chars of English per batch (segments are pre-sized, so this is safe)


def en_of(v) -> str:
    if isinstance(v, dict):
        return v.get("en") or ""
    return v or ""


def is_markup_only(s: str) -> bool:
    """No letter survives once the engine tokens are removed => nothing to translate.

    Deliberately strips ALL brackets, not just `[pagebreak]`: a line that is only
    `[illegible]` or only `<img src=...>` has no prose either way. A line with real words
    beside its markup is NOT caught here.
    """
    core = STRUCT.sub(" ", s)
    core = re.sub(r"\[[^\]]*\]", " ", core)
    return not WORD.search(core)


# ── 1. MASK ──────────────────────────────────────────────────────────────────────────────
def mask(en: str):
    toks: list[str] = []

    def _sub(m):
        toks.append(m.group(0))
        return f"⟦{len(toks) - 1}⟧"

    return STRUCT.sub(_sub, en), toks


def unmask(he: str, toks: list[str]) -> str:
    return MARK.sub(lambda m: toks[int(m.group(1))]
                    if int(m.group(1)) < len(toks) else m.group(0), he)


# ── 2. SPLIT ─────────────────────────────────────────────────────────────────────────────
def split_segments(en: str) -> list[str]:
    """Cut into translatable segments. Concatenating the result must reproduce `en` EXACTLY.

    First on `[pagebreak]` (kept as the head of the following segment), then, for any page
    still over SEG_MAX, on blank-line paragraph boundaries. The join is a plain `"".join`,
    so a bug here is caught by the round-trip assert below rather than shipping a mangled
    page.
    """
    if not en:
        return [en]                    # an empty line has one (empty) segment, never zero
    parts, buf = [], ""
    for piece in re.split(r"(\[pagebreak\])", en):
        if piece == "[pagebreak]":
            if buf:
                parts.append(buf)
            buf = piece
        else:
            buf += piece
    if buf:
        parts.append(buf)

    out: list[str] = []
    for p in parts:
        if len(p) <= SEG_MAX:
            out.append(p)
            continue
        # paragraph split, keeping the separators
        chunks = re.split(r"((?:\r?\n){2,})", p)
        cur = ""
        for ch in chunks:
            if cur and len(cur) + len(ch) > SEG_MAX:
                out.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            out.append(cur)

    # A page with NO blank lines can still be enormous (measured: one 17,672-char segment
    # survived the paragraph pass). Fall back to single line breaks — they are preserved as
    # delimiters, so the join stays exact and no sentence is cut in half.
    final: list[str] = []
    for p in out:
        if len(p) <= SEG_MAX or "\n" not in p:
            final.append(p)
            continue
        cur = ""
        for ln in re.split(r"(\r?\n)", p):
            if cur and len(cur) + len(ln) > SEG_MAX and not ln.startswith(("\r", "\n")):
                final.append(cur)
                cur = ln
            else:
                cur += ln
        if cur:
            final.append(cur)
    # last resort: a single unbroken line bigger than SEG_MAX is left whole — cutting
    # mid-sentence would be worse than one long call.
    assert "".join(final) == en, "segment split is not lossless"
    return final


# ── 3. ALIGN ─────────────────────────────────────────────────────────────────────────────
def align_blank_lines(he: str, en: str) -> str:
    """Rebuild `he` onto `en`'s exact line skeleton when the CONTENT lines line up 1:1.

    A book page's blank lines are vertical spacing; the model drifts by one or two and the
    guard then rejects a perfectly good translation (19 of 23 newline rejections were |Δ|<=2
    on pages with up to 216 newlines). If both sides have the same number of non-empty
    lines, the mapping is unambiguous, so this is a repair. If they differ, the structure
    really did change and the caller must reject.
    """
    if he.count("\n") == en.count("\n"):
        return he
    nl = "\r\n" if "\r\n" in en else "\n"
    en_lines = en.replace("\r\n", "\n").split("\n")
    he_lines = [l for l in he.replace("\r\n", "\n").split("\n") if l.strip()]
    en_content = [i for i, l in enumerate(en_lines) if l.strip()]
    if len(en_content) != len(he_lines):
        return he                      # genuine structure change -> let the guard refuse it
    rebuilt = list(en_lines)
    for pos, txt in zip(en_content, he_lines):
        rebuilt[pos] = txt
    # 🔴🔴 EQUAL COUNTS DO NOT IMPLY THE RIGHT MAPPING (adversarial audit, 2026-08-09). A model
    # that MERGES one pair of lines and SPLITS another keeps the content-line count identical,
    # so the count test passes and the text is re-laid onto the wrong lines — turning a
    # `newline-count` REJECTION into an ACCEPTANCE. Measured on the real pages: 737 of 1,096
    # eligible segments accepted a provably wrong mapping. The discriminator is clean, because
    # the drift this repair EXISTS for (blank lines only) never moves a token off its line:
    # require every rebuilt line to carry the same tokens as the English line it landed on.
    if ([sorted(STRUCT.findall(l)) for l in rebuilt]
            != [sorted(STRUCT.findall(l)) for l in en_lines]):
        return he                      # re-segmented content -> let the guard refuse it
    return nl.join(rebuilt)


def normalize(he: str, en: str) -> str:
    """Deterministic repairs, in the worker's own order, plus the blank-line alignment."""
    he = NIQ.sub("", he).translate(_DASHES)
    he = _PREFIX_HYPHEN.sub(r"\1", he)
    core = he.strip()
    lead = en[:len(en) - len(en.lstrip())]
    trail = en[len(en.rstrip()):]
    if "\r\n" in en and "\r\n" not in core and "\n" in core:
        core = core.replace("\n", "\r\n")
    he = lead + core + trail
    return align_blank_lines(he, en)


def why_invalid(he: str, en: str) -> str:
    if not he or not he.strip():
        return "empty"
    if FOREIGN.search(he):
        return "foreign-script"
    if NIQ.search(he):
        return "niqqud"
    if MARK.search(he) or "⟦" in he:
        # invisible to the token check (a marker is not STRUCT), so it would ship as literal
        # junk on screen.
        return "marker-leak"
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(en)):
        return "token-mismatch"
    if en.count("\n") != he.count("\n"):
        return f"newline-count {en.count(chr(10))} -> {he.count(chr(10))}"
    core = STRUCT.sub(" ", en)
    same = he.strip() == en.strip()
    # A proper NOUN or a code legitimately comes back unchanged — the worker allows exactly
    # this, and the drain must not be STRICTER than the worker or it re-rejects lines the
    # fleet would have accepted.
    namey = bool(core.split()) and len(core.split()) <= 4 and all(
        _NAMEWORD.match(w) for w in core.split())
    if LOWER.search(core) and not HEB.search(he):
        if not (same and namey):
            return "no-hebrew"
    if len(en) >= 12 and same and not namey:
        return "copy-EN"
    return ""


# ── the run ──────────────────────────────────────────────────────────────────────────────
def load_done() -> set:
    done = set()
    import glob
    for f in glob.glob(_p("banks", "out_*.json")):
        try:
            done |= set(json.load(open(f, encoding="utf-8")))
        except Exception:
            pass
    return done


def main() -> int:
    apply = "--apply" in sys.argv
    cap = 10 ** 9
    if "--max" in sys.argv:
        cap = int(sys.argv[sys.argv.index("--max") + 1])

    # `--slot i/n`: one PROCESS per provider, partitioned by LINE. A single client is
    # generation-bound (~2 min per batch measured), so three pinned processes are ~3x — and
    # partitioning by LINE, not by segment, is what keeps every segment of a page in the same
    # process so it can still reassemble. Pin with FLEET_PROVIDER=<groq|sambanova|nim>.
    slot, nslots = 0, 1
    if "--slot" in sys.argv:
        slot, nslots = (int(x) for x in sys.argv[sys.argv.index("--slot") + 1].split("/"))
    prov = os.environ.get("FLEET_PROVIDER", "").strip().lower()
    # the SLOT is always in the bank name: several slots may legitimately be pinned to the
    # SAME provider (measured 2026-08-09 — groq 429s on a book-sized output while nim answers
    # 4/4, so all three slots run on nim), and two processes must never share a bank file.
    tag = f"_{prov or 'x'}{slot}" if nslots > 1 else ""

    corpus = json.load(open(_p("corpus.json"), encoding="utf-8"))
    done = load_done()
    out_path = _p("banks", f"out_zzdrain{tag}.json")
    have = {}
    if os.path.exists(out_path):
        try:
            have = json.load(open(out_path, encoding="utf-8"))
        except Exception:
            have = {}

    # decided by the game's OWN translators: every shipped locale left these byte-identical,
    # so they are editor identifiers, not text. See reslice_equal.py for the full note.
    try:
        noncontent = set(json.load(open(_p("noncontent.json"), encoding="utf-8")))
    except Exception:
        noncontent = set()

    import hashlib
    todo, markup = [], []
    for k, v in corpus.items():
        if k in done or k in have or k in noncontent:
            continue
        en = en_of(v)
        if is_markup_only(en):
            markup.append(k)
        elif nslots == 1 or int(hashlib.md5(k.encode()).hexdigest(), 16) % nslots == slot:
            todo.append((k, en))

    # markup-only -> excluded, reported, never sent and never fake-banked. Slot 0 owns the
    # file so three concurrent processes cannot race on it.
    if slot == 0:
        json.dump(sorted(markup), open(_p("empty.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"corpus {len(corpus):,}  banked {len(done):,}  drained {len(have):,}"
          + (f"   [slot {slot}/{nslots} {prov or ''}]" if nslots > 1 else ""))
    print(f"markup-only -> empty.json: {len(markup)}   real work (this slot): {len(todo)}")

    # build the segment work list
    segs = []          # (segkey, linekey, idx, en_segment)
    per_line = {}
    seg_he: dict[str, str] = {}
    free_slots = 0
    for k, en in todo:
        parts = split_segments(en)
        per_line[k] = len(parts)
        for i, p in enumerate(parts):
            # 🔴🔴 THE SAME markup-only RULE MUST APPLY ONE LEVEL DOWN (adversarial audit,
            # 2026-08-09). The line filter above sends no markup-only LINE to the model, but
            # the split then CARVES 52 content-free SEGMENTS out of 51 real pages — 49 of them
            # a bare `[pagebreak]\r\n` produced by a doubled `[pagebreak]\r\n[pagebreak]`, i.e.
            # a deliberately BLANK page. For such a slot the honest echo is refused (copy-EN)
            # while any invented Hebrew is accepted, at the segment gate AND at the whole-line
            # gate — so the model gets three chances to hallucinate text onto a blank page and
            # none to be right. Echo it verbatim instead: the join is byte-exact, so page
            # structure needs no translation, and 52 calls are saved.
            if is_markup_only(p):
                seg_he[f"{k}\x1f{i}"] = p
                free_slots += 1
                continue
            segs.append((f"{k}\x1f{i}", k, i, p))
    print(f"segments: {len(segs)} to translate from {len(todo)} lines "
          f"(max {max(per_line.values()) if per_line else 0} per line; "
          f"{free_slots} markup-only slots echoed verbatim)")

    if not apply:
        for k, en in todo[:3]:
            parts = split_segments(en)
            m, toks = mask(parts[0])
            print(f"\n--- {k}  ({len(en)} chars -> {len(parts)} segments)")
            print("   EN  :", repr(parts[0][:160]))
            print("   MASK:", repr(m[:160]))
            print("   toks:", toks[:6])
        print("\n(dry run — pass --apply to translate)")
        return 0

    import skyrim_nim as W   # provider fleet, keys, chat()

    S = ("You are a senior Hebrew localizer for The Elder Scrolls V: Skyrim Anniversary "
         "Edition — a high-fantasy Nordic world of dragons, Jarls, hold guards, magic and "
         "the Imperial/Stormcloak civil war. Write natural, fluent, MODERN Hebrew with a "
         "high-fantasy flavour; slightly formal for nobles and books, never biblical.\n"
         "The text contains markers of the form ⟦0⟧ ⟦1⟧ ⟦2⟧ — they stand for engine code and "
         "page markup.\n"
         "1. Copy every ⟦n⟧ EXACTLY as it is, with the same number and the same number of "
         "occurrences. Never translate one, never invent one, never change its digits.\n"
         "2. Keep the SAME number of line breaks as the English, in the same places. Blank "
         "lines are page layout — keep them.\n"
         "3. Address the player in masculine singular (אתה), consistently.\n"
         "4. Never put a hyphen between a Hebrew prefix and a Hebrew word (בשבעת הימים, not "
         "ב-שבעת הימים). Use the plain hyphen '-', never a long dash. No niqqud. No Cyrillic "
         "or other foreign letters.\n"
         "5. Proper names take their accepted Hebrew form (וייטראן for Whiterun, אלדוין for "
         "Alduin).\n"
         "Output JSON {id: hebrew} only, with exactly the same ids as the input.")

    rejected: dict[str, str] = {}
    state = {"have": have}
    t0 = time.time()

    # A line banked by an EARLIER run was validated by an EARLIER guard. Re-check it against
    # the current one and drop anything that no longer passes, so a guard fix retroactively
    # cleans the bank instead of leaving a line the audit has since proven corrupt.
    stale = [k for k, he in state["have"].items()
             if k in corpus and why_invalid(he, en_of(corpus[k]))]
    if stale:
        for k in stale:
            state["have"].pop(k, None)
        print(f"dropped {len(stale)} previously-banked line(s) that fail the CURRENT guard")

    def flush():
        """Reassemble every line whose segments are ALL in hand, validate the WHOLE line
        against the WHOLE English, and persist. Called after each batch, so a kill loses at
        most one call."""
        banked = dict(state["have"])
        for k, n in per_line.items():
            if k in banked:
                continue
            keys = [f"{k}\x1f{i}" for i in range(n)]
            if not all(kk in seg_he for kk in keys):
                continue
            full = "".join(seg_he[kk] for kk in keys)
            en_full = en_of(corpus[k])
            bad = why_invalid(full, en_full)
            if bad:
                rejected[k] = "reassembled:" + bad
                continue
            banked[k] = full
        if banked != state["have"]:
            state["have"] = banked
            tmp = out_path + ".tmp"
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            json.dump(banked, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
            os.replace(tmp, out_path)

    def run_batch(sub, label):
        # 🔴 THE ID THE MODEL SEES MUST BE SHORT AND SAFE. The internal segment key is
        # `skyrim:skyrim|1994\x1f3` — it carries a raw 0x1F control character (and a `|` and
        # `:`), which json.dumps emits as `` and no model reliably echoes back. Every
        # such id then reads as "the model omitted this line", which is indistinguishable
        # from a real dropout and costs a whole retry pass. Send `s0, s1, …` and map back
        # locally; the ids also stop eating output tokens.
        payload, masks, alias = {}, {}, {}
        for n, (segkey, _k, _i, en) in enumerate(sub):
            alias[f"s{n}"] = segkey
            m, toks = mask(en)
            masks[segkey] = (toks, en)
            p = {"en": m}
            # 🔑 The New-Era panel still applies to a line that fits in ONE segment: the
            # smoke test produced `אתה` in a letter addressed to Priestess Velothi, which
            # ru/pl would have settled. It is dropped for a SPLIT line on purpose — the refs
            # belong to the whole page, so pasting them beside one segment is misleading,
            # and a narrative book page has no addressee to gender anyway.
            if per_line.get(_k) == 1 and len(en) <= 2500:
                refs = (corpus[_k].get("refs") or {}) if isinstance(corpus[_k], dict) else {}
                for L in ("ru", "pl"):
                    pair = refs.get(L)
                    if isinstance(pair, list) and pair:
                        val = (pair[1] if len(pair) > 1 and pair[1] else pair[0]) or ""
                        # the reference carries the SAME engine tokens, so it must show the
                        # SAME markers — otherwise the panel teaches a second spelling of
                        # the very thing we are hiding.
                        if val:
                            p[L] = STRUCT.sub(
                                lambda mm: f"⟦{toks.index(mm.group(0))}⟧"
                                if mm.group(0) in toks else "⟦?⟧", val)
            payload[f"s{n}"] = p
        chars = sum(len(en) for _, _, _, en in sub)
        mx = min(16000, 1200 + chars * 2)
        # A healthy 1,800-char batch answers in ~1-2 min; 300 s only ever bought dead air on
        # a call that was never going to return, and the pass loop re-serves it anyway.
        to = min(180, 60 + chars // 12)
        # Call the fleet DIRECTLY (not W.chat) so the RAW reply is visible: "raw 173ch
        # parsed 0" names a truncated / wrong-shaped answer instantly, while a bare "+0/6"
        # cannot tell that apart from a rate limit or a genuine model dropout.
        try:
            raw = W._FLEET.complete(S, "Translate:\n" + json.dumps(payload, ensure_ascii=False),
                                    retries=1, timeout=to, max_tokens=mx, max_attempts=3)
        except Exception as e:
            print(f"  {label} transport fail ({e}) — skip", flush=True)
            return 0
        r = {alias.get(k, k): v for k, v in (W._parse(raw) or {}).items()}
        if not r:
            print(f"  {label} +0/{len(sub)}  [raw {len(raw or '')}ch parsed 0]", flush=True)
            return 0
        ok = 0
        for segkey, (toks, en) in masks.items():
            he = r.get(segkey)
            if isinstance(he, dict):
                he = he.get("he") or he.get("hebrew") or he.get("text") or ""
            if not isinstance(he, str) or not he.strip():
                continue                       # omitted by the model — blameless, retried
            he = normalize(unmask(he, toks), en)
            bad = why_invalid(he, en)
            if bad:
                rejected[segkey] = bad
                continue
            seg_he[segkey] = he
            ok += 1
        print(f"  {label} +{ok}/{len(sub)}  segments {len(seg_he)}/{len(segs)}  "
              f"lines {len(state['have'])}/{len(todo)}", flush=True)
        flush()
        return ok

    # 🔴 PASSES, not one shot. A segment that fails once (a throttled provider, a dropped id,
    # one bad answer) must come back — a line is banked only when EVERY one of its segments
    # is in hand, so a single unlucky segment otherwise strands the whole book page. Each
    # later pass re-batches only what is still missing and shrinks the batch, because a solo
    # re-ask has the highest hit rate (the RDR2 omit-recovery lesson).
    for attempt in (1, 2, 3):
        pending = [s for s in segs if s[0] not in seg_he]
        if not pending or len(state["have"]) >= cap:
            break
        budget = {1: BUDGET, 2: BUDGET // 3, 3: 1}[attempt]
        batches, cur, ct = [], [], 0
        for s in pending:
            if cur and ct + len(s[3]) > budget:
                batches.append(cur); cur, ct = [], 0
            cur.append(s); ct += len(s[3])
        if cur:
            batches.append(cur)
        print(f"\npass {attempt}: {len(pending)} segments pending, {len(batches)} batches",
              flush=True)
        rejected.clear()      # a reason from an earlier pass is stale, not evidence
        for bi, sub in enumerate(batches, 1):
            if len(state["have"]) >= cap:
                break
            run_batch(sub, f"[{attempt}.{bi}/{len(batches)}]")

    import collections
    have = state["have"]
    stranded = [k for k, n in per_line.items()
                if k not in have and any(f"{k}\x1f{i}" not in seg_he for i in range(n))]
    print(f"\ndone in {int(time.time()-t0)}s   lines banked {len(have)}/{len(todo)}   "
          f"segments {len(seg_he)}/{len(segs)}   stranded lines {len(stranded)}")
    if rejected:
        print("last-pass rejections:", collections.Counter(
            v.split()[0] for v in rejected.values()).most_common())
        json.dump(rejected, open(_p("drain_rejected.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
