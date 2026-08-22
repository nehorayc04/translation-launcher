# -*- coding: utf-8 -*-
"""Game-AGNOSTIC multi-language review / translation corpus engine (New-Era doctrine).

Works for ANY game — one that is ALREADY translated (REVIEW mode) or one that is NOT YET
translated (TRANSLATE mode). Per-game code only has to produce a NORMALIZED panel + spine;
this module does everything else: for every line it builds the fleet-ready review row with the
DETERMINISTIC gender partition (union of the game's own languages that split fv!=mv), the
deterministic side-flags (niqqud/foreign/token-drop/bidi/leak), the reliable linguistic tags,
and the engine-layer tags (injected variables · plural attention · name injection · forced
line-breaks · overflow risk · lore terms). Read-only. See MULTILANG_REVIEW.md for the contract.

NORMALIZED INPUTS a per-game adapter must build (canonical language codes):
  panel : dict  id -> { lang: [femaleVariant, maleVariant] }   # EVERY shipped game language incl. "en"
  spine : dict  id -> (section, order, he_fv, he_mv)            # the Hebrew; empty he_* => TRANSLATE mode

OUTPUT: one JSONL row per line via build(); the fleet consumes it with NO further lookups.
"""
import json, os, re, collections
from dataclasses import dataclass, field

# ---- canonical languages + their New-Era gender roles (override per game via Cfg) ----
# A game ships a subset of these; the adapter maps its own loc-folder names -> these codes.
DEFAULT_LANGS = ["en", "ar", "ru", "pl", "cs", "es", "es-mx", "fr", "it", "pt", "de",
                 "ja", "ko", "zh-cn", "zh-tw", "tr", "th", "hu", "uk"]
# ADDRESSEE (2nd-person) gender: ar تستمرين/تستمر · pl -łaś/-łeś · cs -á/-ý  -> a split here = PLAYER gender
DEFAULT_ADDRESSEE = ("ar", "pl", "cs")
# SPEAKER gender: ru past tense -ла/-л (with no addressee-lang split) -> speaker, not addressee
DEFAULT_SPEAKER = ("ru",)
# any language whose fv!=mv split proves the line is gender-dependent (the anti-miss partition)
DEFAULT_GENDER = ("ar", "ru", "pl", "cs", "es", "es-es", "es-mx", "es-419", "fr", "it", "pt", "de")


@dataclass
class Cfg:
    """Per-game language configuration. A translated game and a new game share the same Cfg;
    only whether the spine carries Hebrew decides REVIEW vs TRANSLATE mode (per row)."""
    langs: list = field(default_factory=lambda: list(DEFAULT_LANGS))
    gender_langs: tuple = DEFAULT_GENDER
    addressee_langs: tuple = DEFAULT_ADDRESSEE
    speaker_langs: tuple = DEFAULT_SPEAKER


# ---- script / token detection (universal) ----
HEB = re.compile(r'[\u0590-\u05ff]')
NIQ = re.compile(r'[\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7]')  # niqqud+cantillation, not maqaf/paseq
FOREIGN = re.compile(r'[\u0600-\u06ff\u0400-\u04ff\u0e00-\u0e7f\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]')
BRACE = re.compile(r'\{[^{}]*\}')
LOCKEY = re.compile(r'LocKey#\d+')
CTRL = re.compile(r'^[\x00-\x08]+')
ENRUN = re.compile(r"(?:[A-Za-z][A-Za-z'\-]*[ ,.:;!?]+){2,}[A-Za-z][A-Za-z'\-]*")
VAR = re.compile(r'\{[^{}]*\}')
NL = re.compile(r'\\n|\n')
NUM = re.compile(r'\{(?:int|float|stat)_\d+\}|%[0-9.]*[di]')
NAME = re.compile(r'\{(?:Name|Surname|FirstName|LastName|nickname|playerName)\}', re.I)
CAPWORD = re.compile(r"\b[A-Z][A-Za-z][A-Za-z'\-]{1,}\b")
STOP = {"The", "This", "That", "You", "Your", "And", "But", "For", "With", "When",
        "What", "Where", "How", "Why", "Not", "Are", "Was"}

# ---- closed-set register pronouns (reliable morphology only) ----
DE_INF = re.compile(r'\b(du|dich|dir|deine?[mnrs]?)\b')
DE_FML = re.compile(r'(?<![a-zäöü])(Sie|Ihnen|Ihre[mnrs]?)\b')
FR_INF = re.compile(r'\b(tu|toi|ton|ta|tes)\b', re.I)
FR_FML = re.compile(r'\bvous\b', re.I)                       # also plural -> ambiguous
ES_INF = re.compile(r'\b(tú|te|ti|tuyo|contigo)\b', re.I)
ES_FML = re.compile(r'\busted\b', re.I)
RU_INF = re.compile(r'\bты\b', re.I)
RU_FML = re.compile(r'\bвы\b', re.I)                         # also plural -> ambiguous
PL2 = [re.compile(r'\b(vosotros|vosotras|ustedes|os)\b', re.I),
       re.compile(r'\b(ihr|euch|eure[mnrs]?)\b')]
IMP_EN = re.compile(r'^(?:[A-Z][a-z]+)(?:\s|$)')
IMP_STOP = {"The", "A", "An", "You", "I", "We", "They", "He", "She", "It", "This",
            "That", "Your", "My", "Our"}


# ---- helpers ----
def sc(s): return CTRL.sub('', s or '')
def braces(s): return collections.Counter(BRACE.findall(s or '') + LOCKEY.findall(s or ''))
def splits(pair):
    fv, mv = pair
    return bool(fv) and bool(mv) and fv != mv


def _txt(refs, *keys):
    """First present non-empty femaleVariant among the given language-code variants."""
    for k in keys:
        v = refs.get(k)
        if v and v[0]:
            return v[0]
    return ""


def det_flags(en, fv):
    """Deterministic side-flags on the Hebrew (the agent RE-checks; these only route attention)."""
    fvc = sc(fv); flags = {}
    if NIQ.search(fvc): flags["niqqud"] = True
    if FOREIGN.search(fvc): flags["foreign"] = True
    lost = braces(en) - braces(fv)
    if lost: flags["brace_dropped"] = list(lost)
    head = fvc.lstrip()
    if head and head[0].isascii() and head[0].isalpha() and HEB.search(fvc):
        flags["leading_latin"] = True
    if HEB.search(fvc):
        for m in ENRUN.finditer(fvc):
            r = m.group(0).strip()
            if len(r.split()) >= 3:
                flags["english_run"] = r[:60]; break
    return flags


def formality(refs):
    inf = fml = 0
    for pi, pf, t in ((DE_INF, DE_FML, _txt(refs, "de")),
                      (FR_INF, FR_FML, _txt(refs, "fr")),
                      (ES_INF, ES_FML, _txt(refs, "es", "es-es", "es-mx", "es-419")),
                      (RU_INF, RU_FML, _txt(refs, "ru"))):
        if not t: continue
        if pi.search(t): inf += 1
        elif pf.search(t): fml += 1
    if inf: return "INF"
    if fml: return "FML"
    return None


def number_plural(refs):
    for t in (_txt(refs, "es", "es-es", "es-mx", "es-419"), _txt(refs, "de")):
        if t and any(p.search(t) for p in PL2):
            return "P"
    return None


def imperative(en):
    en = (en or "").strip()
    if not en: return False
    first = en.split()[0].rstrip(".,:;!?")
    return bool(IMP_EN.match(en)) and first not in IMP_STOP and en[0].isupper()


def hom_candidate(refs, en):
    """Cheap polysemy proxy: >=3 distinct short Latin renderings for a short source (FENCE-like)."""
    en = en or ""
    if len(en.split()) > 3: return False
    words = {}
    for keys in (("es", "es-es", "es-mx", "es-419"), ("fr",), ("it",), ("de",), ("pt",)):
        t = _txt(refs, *keys).strip().lower().rstrip(".!?")
        if t and len(t.split()) <= 2:
            words[keys[0]] = t
    stems = {w[:4] for w in words.values() if len(w) >= 4}
    return len(stems) >= 3


def line_breaks(s): return len(NL.findall(s or ""))


def overflow(he, en, refs):
    hl = len(he or "")
    if hl < 15: return False
    others = [len(v[0]) for v in refs.values() if v and v[0]]
    ceiling = max(others + [len(en or "")]) if others else len(en or "")
    return hl > ceiling * 1.1


def lore_terms(en, refs):
    """Capitalized English words kept VERBATIM in >=6 language translations = proper noun / lore term."""
    out = []
    cands = [w for w in CAPWORD.findall(en or "") if w not in STOP]
    for w in dict.fromkeys(cands):
        kept = sum(1 for v in refs.values() if v and re.search(r'\b' + re.escape(w) + r'\b', v[0]))
        if kept >= 6:
            out.append(w)
    return out


def tag_linguistic(row, cfg):
    refs = row.get("refs", {}); split = row.get("split_langs", [])
    axis = []
    if any(l in split for l in cfg.addressee_langs): axis.append("P2")
    if any(l in split for l in cfg.speaker_langs) and not any(l in split for l in cfg.addressee_langs):
        axis.append("P1?")
    return {
        "axis": axis,
        "player_gender": row.get("he_split", False) or bool(split),
        "formality": formality(refs),
        "number": number_plural(refs),
        "imperative": imperative(row.get("en", "")),
        "hom_candidate": hom_candidate(refs, row.get("en", "")),
    }


def tag_engine(row):
    en = row.get("en", "") or ""; he = row["he"][0]; refs = row.get("refs", {})
    ev = VAR.findall(en)
    vars_ = ev + [v for v in VAR.findall(he) if v not in ev]
    return {
        "vars": sorted(set(vars_)),
        "number_inject": bool(NUM.search(en) or NUM.search(he)),
        "name_inject": bool(NAME.search(en) or NAME.search(he)),
        "line_breaks": line_breaks(he),
        "overflow_risk": overflow(he, en, refs),
        "lore_terms": lore_terms(en, refs),
    }


def corpus_row(id_, kind, section, order, en, panel_id, he, cfg):
    split_langs = [l for l in cfg.gender_langs if l in panel_id and splits(panel_id[l])]
    return {
        "id": id_, "kind": kind, "section": section, "order": order, "en": en,
        "refs": {l: [sc(panel_id[l][0]), sc(panel_id[l][1])]
                 for l in cfg.langs if l in panel_id and l != "en"},
        "he": list(he),
        "gendered": bool(split_langs),
        "split_langs": split_langs,
        "he_split": splits(tuple(he)),
        "det": det_flags(en, he[0]),
    }


def context_fragment(ctx, max_lines=5):
    """Format a sliding-window context list into a compact Hebrew prompt block so the worker sees the
    conversation, not an isolated bubble (register/tone/slang follow the scene)."""
    if not ctx:
        return ""
    lines = []
    for c in ctx[-max_lines:]:
        who = (c.get("speaker") or "").strip()
        txt = (c.get("he") or c.get("en") or "").strip().replace("\n", " ")
        if txt:
            lines.append((f"{who}: " if who else "") + txt)
    return ("הקשר השיחה (השורות שקדמו):\n" + "\n".join(lines)) if lines else ""


def build(kind, panel, spine, out_dir, cfg=None, n_context=0, speakers=None):
    """Build the fleet-ready corpus for one `kind` (e.g. onscreens/subtitles/ui/dialogue).
    panel : {id: {lang: [fv, mv]}}   spine : {id: (section, order, he_fv, he_mv)}
    n_context>0 attaches a SLIDING WINDOW of the previous n lines in the SAME section (+speaker from
    `speakers[id]` when given) as row["ctx"] — so a line is translated in conversational context, not
    as an isolated bubble. Writes <out_dir>/<kind>.final.jsonl, returns a stats dict. Handles REVIEW
    (Hebrew present) and TRANSLATE (Hebrew empty) per row. Read-only vs every game file."""
    cfg = cfg or Cfg()
    speakers = speakers or {}
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, kind + ".final.jsonl")
    recent = collections.defaultdict(lambda: collections.deque(maxlen=n_context)) if n_context else None
    st = {"n": 0, "gendered": 0, "covered": 0, "review": 0, "translate": 0,
          "vars": 0, "num": 0, "name": 0, "nl": 0, "ovf": 0, "ctx": 0, "out": out_path}
    with open(out_path, "w", encoding="utf-8") as f:
        for pk, meta in sorted(spine.items(), key=lambda kv: kv[1][1]):
            section, order, fv, mv = meta
            p = panel.get(pk, {})
            en = sc(p.get("en", ("", ""))[0]) if "en" in p else ""
            row = corpus_row(f"{section}:{pk}", kind, section, order, en, p, (fv, mv), cfg)
            row["mode"] = "review" if (fv or mv) else "translate"
            spk = speakers.get(pk)
            if spk:
                row["speaker"] = spk
            if n_context:
                win = list(recent[section])
                if win:
                    row["ctx"] = win; st["ctx"] += 1
                recent[section].append({"speaker": spk, "en": en, "he": fv})
            row["tags"] = tag_linguistic(row, cfg)
            row["engine"] = tag_engine(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            st["n"] += 1
            st[row["mode"]] += 1
            if row["gendered"]: st["gendered"] += 1
            if len(row["refs"]) >= 6: st["covered"] += 1
            e = row["engine"]
            if e["vars"]: st["vars"] += 1
            if e["number_inject"]: st["num"] += 1
            if e["name_inject"]: st["name"] += 1
            if e["line_breaks"]: st["nl"] += 1
            if e["overflow_risk"]: st["ovf"] += 1
    return st


def report(kind, st):
    mode = "REVIEW" if st["review"] >= st["translate"] else "TRANSLATE"
    cov = 100 * st["covered"] / max(1, st["n"])
    return (f"  {kind}: {st['n']:,} rows [{mode}: review {st['review']:,} / translate {st['translate']:,}]"
            f" | gendered {st['gendered']:,} | >=6 langs {cov:.1f}%\n"
            f"     engine: vars {st['vars']:,} | number {st['num']:,} | name {st['name']:,}"
            f" | line-breaks {st['nl']:,} | overflow {st['ovf']:,}\n"
            f"     -> {st['out']}")
