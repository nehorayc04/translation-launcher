# -*- coding: utf-8 -*-
"""THE DETERMINISTIC LOCALIZATION BRAIN — a persistent, self-improving knowledge layer that turns the
New-Era fleet from a per-line tool into an autonomous localization agent that learns as it goes.
GAME-AGNOSTIC. This is the deterministic CORE (no embeddings): a LAYERED glossary + term-injection at
dispatch + canon() re-apply at merge + a consistency auto-audit that emits LESSON candidates + a
PROMOTION GATE that keeps untrusted output out of the authoritative brain. Read/verify only; the fleet
does the translating ([[delegate-all-translation]]).

⚠️ THE CRITICAL DISCIPLINE: the brain learns from UNTRUSTED fleet output. A lesson NEVER enters the
authoritative glossary until it passes validate_lesson() AND is explicitly promoted (default reject).
Without the gate a single wrong term learned early poisons every future line and every future game.

LAYERS (most-specific wins on a canon conflict):  universal  <  game  <  run
Storage = versioned JSON (git-diffable, auditable). The RAG/pgvector layer is a SEPARATE later add-on.

Term entry (the hard glossary):
  {"en","he","kind":"term","aliases":[],"variants":[wrong Hebrew forms canon replaces],
   "do_not_translate":bool,"referent_gender":m|f|pl|obj|null,"register":FML|INF|null,
   "provenance","confidence":0..1,"examples":[],"scope":universal|game|run,"promoted":bool}
Repair entry (pure deterministic regex): {"kind":"repair","name","pattern","replace","scope","promoted"}
Rule entry  (descriptive guidance, injected as text, NOT auto-applied): {"kind":"rule","name","text",...}
"""
import json, os, re, hashlib, time

HEB = re.compile(r'[֐-׿]')
NIQ = re.compile(r'[֑-ׇֽֿׁׂׅׄ]')
FOREIGN = re.compile(r'[؀-ۿЀ-ӿ฀-๿぀-ヿ一-鿿가-힯]')
# 🔴 THE HEBREW-PREFIX TRAP. `ו` is BOTH the conjunction prefix ("and-") AND an ordinary stem
# letter, so treating a leading `ו` as a prefix re-prefixes an ALREADY-CORRECT token:
# `וולנטיין` (Valentine) -> `ווולנטיין`, `ווסט` (West) -> `וווסט`. Measured on the RDR2 bank:
# canon() corrupted 9 live lines this exact way. Two guards, both needed:
#   (a) `ו` is NOT a parseable prefix here (the W3 lesson — never parse a bare vav);
#   (b) `_canon_skip` below refuses any substitution whose match is already the canonical form.
PREFIX = 'הבלמכש'    # ה ב ל מ כ ש  (one attached Hebrew prefix; ו deliberately EXCLUDED)


def _norm_en(s): return re.sub(r'\s+', ' ', (s or '')).strip()


def _hash(*parts):
    return hashlib.sha1('␟'.join(str(p) for p in parts).encode('utf-8')).hexdigest()[:12]


# ------------------------------------------------------------------ the brain
class Brain:
    """Merged view of the layered knowledge base. Load once, use across a whole fleet run."""

    def __init__(self):
        self.terms = []      # list of term dicts, later layers appended after earlier (game overrides universal)
        self.repairs = []
        self.rules = []
        self._by_en = {}     # normalized-en -> term (last layer wins)
        self._compiled = None

    # ---- loading ----
    def add_layer(self, scope, data):
        for t in data.get("terms", []):
            t = dict(t); t.setdefault("scope", scope); t.setdefault("kind", "term")
            t["en"] = _norm_en(t.get("en", ""))
            self.terms.append(t)
            if t["en"]:
                self._by_en[t["en"].lower()] = t          # most-specific layer wins
        for r in data.get("repairs", []):
            r = dict(r); r.setdefault("scope", scope); r.setdefault("kind", "repair")
            self.repairs.append(r)
        for r in data.get("rules", []):
            r = dict(r); r.setdefault("scope", scope); r.setdefault("kind", "rule")
            self.rules.append(r)
        self._compiled = None
        return self

    @classmethod
    def load(cls, *paths):
        """paths in priority order (universal first, game next, run last)."""
        b = cls()
        for i, p in enumerate(paths):
            if p and os.path.exists(p):
                scope = ("universal", "game", "run")[min(i, 2)]
                b.add_layer(scope, json.load(open(p, encoding="utf-8")))
        return b

    @classmethod
    def for_game(cls, game_fleet_dir, universal_path=None, run_path=None):
        here = os.path.dirname(os.path.abspath(__file__))
        uni = universal_path or os.path.join(here, "brain_universal.json")
        glo = os.path.join(game_fleet_dir, "brain_glossary.json")
        return cls.load(uni, glo, run_path)

    # ---- matching ----
    def _compile(self):
        # longest en first so "Gold Bar Reward" beats "Gold Bar"; match en + aliases
        pairs = []
        seen = set()
        for t in sorted(self.terms, key=lambda x: -len(x.get("en", ""))):
            for surface in [t.get("en", "")] + list(t.get("aliases", [])):
                surface = _norm_en(surface)
                if surface and surface.lower() not in seen:
                    seen.add(surface.lower())
                    pairs.append((re.compile(r'(?<![A-Za-z])' + re.escape(surface) + r'(?![A-Za-z])', re.I), t))
        self._compiled = pairs
        return pairs

    def terms_in(self, en):
        """Canonical terms whose English surface appears in `en` (longest-first, dedup by term)."""
        if self._compiled is None:
            self._compile()
        out, ids = [], set()
        for rx, t in self._compiled:
            key = t.get("en", "").lower()
            if key in ids:
                continue
            if rx.search(en or ""):
                out.append(t); ids.add(key)
        return out

    # ---- (2) term-injection at DISPATCH ----
    def inject_fragment(self, en, max_terms=14):
        """Compact Hebrew prompt fragment listing the canonical terms/DNT/gender for THIS line —
        injected into the worker's sys/src so the fleet is consistent + learns the brain live."""
        ts = self.terms_in(en)[:max_terms]
        if not ts:
            return ""
        parts = []
        for t in ts:
            if t.get("do_not_translate"):
                parts.append(f"{t['en']} → [שמור לטיני]")
            else:
                tag = ""
                if t.get("referent_gender"): tag += f" ({t['referent_gender']})"
                if t.get("register"): tag += f" [{t['register']}]"
                parts.append(f"{t['en']} → {t['he']}{tag}")
        return "מונחים קנוניים (חובה, בדיוק כך): " + " · ".join(parts)

    # ---- (3) canon() — re-apply at MERGE (retroactive, no re-translation) ----
    def canon(self, he, en=None):
        """Enforce canonical Hebrew for every glossary term in a banked line by replacing each known
        WRONG variant with the canonical he, prefix-aware. DNT terms are left untouched (a translate-time
        rule). Conservative: whole-word Hebrew boundary + one optional attached prefix letter."""
        if not he:
            return he
        out = he
        # only enforce terms relevant to this line (if en given) else all terms with variants
        cand = self.terms_in(en) if en else self.terms
        for t in cand:
            if t.get("do_not_translate") or not t.get("he"):
                continue
            for v in t.get("variants", []):
                if not v:
                    continue
                if v == t["he"]:
                    continue
                rx = re.compile(rf'(?<![֐-׿])([{PREFIX}]?){re.escape(v)}(?![֐-׿])')

                def _rep(m, canon=t["he"]):
                    # (b) never "fix" text that is ALREADY canonical: a variant can be a proper
                    # substring of its own canonical form (`ולנטיין` inside `וולנטיין`), so a
                    # match that reconstructs the canonical must be left exactly as it is.
                    whole = m.group(0)
                    if whole == canon or whole.endswith(canon) or canon.endswith(whole):
                        return whole
                    return m.group(1) + canon

                out = rx.sub(_rep, out)
        return out

    # ---- deterministic repairs (pure regex, e.g. niqqud strip) ----
    def repairs_apply(self, he):
        if not he:
            return he
        out = he
        for r in self.repairs:
            try:
                out = re.sub(r["pattern"], r.get("replace", ""), out)
            except re.error:
                pass
        return out

    # ---- rules text (descriptive guidance for the sys prompt) ----
    def rules_text(self, scope=None):
        rs = [r for r in self.rules if scope is None or r.get("scope") == scope]
        return " · ".join(r.get("text", "") for r in rs if r.get("text"))

    # ---- (4) consistency AUTO-AUDIT -> LESSON candidates (untrusted, go to the inbox) ----
    def audit_consistency(self, banked, min_group=2):
        """banked: {id: {"en":..., "he":...}}. Two deterministic findings ->
        candidate lessons (NOT promoted; the gate decides):
          divergence : same short English rendered with >1 distinct (canon-normalized) Hebrew
          term_absent: a glossary term's English is present but its canonical Hebrew (stem, one prefix)
                       is missing from the line's Hebrew (possible mistranslation/inconsistency)."""
        findings = []
        # (a) same-en divergence
        groups = {}
        for _id, row in banked.items():
            en = _norm_en(row.get("en", ""))
            he = (row.get("he") or "").strip()
            if not en or not he or len(en.split()) > 4:
                continue
            groups.setdefault(en.lower(), {"en": en, "renders": {}})
            key = self.canon(he, en)
            g = groups[en.lower()]["renders"]
            g[key] = g.get(key, 0) + 1
        for g in groups.values():
            renders = g["renders"]
            if len(renders) >= 2 and sum(renders.values()) >= min_group:
                majority = max(renders, key=renders.get)
                variants = [h for h in renders if h != majority]
                findings.append({
                    "kind": "term", "reason": "divergence",
                    "en": g["en"], "he": majority, "variants": variants,
                    "counts": renders, "confidence": renders[majority] / sum(renders.values()),
                })
        # (b) glossary term absent from a line's Hebrew
        for _id, row in banked.items():
            en = row.get("en", ""); he = (row.get("he") or "")
            if not en or not he:
                continue
            for t in self.terms_in(en):
                if t.get("do_not_translate") or not t.get("he"):
                    continue
                stem = t["he"]
                present = re.search(rf'(?<![֐-׿])[{PREFIX}]?{re.escape(stem)}', he) \
                    or any(re.search(re.escape(v), he) for v in t.get("variants", []))
                if not present:
                    findings.append({
                        "kind": "term_absent", "reason": "term-missing",
                        "term_en": t["en"], "term_he": t["he"], "id": _id,
                        "en": en, "he": he, "confidence": 0.5,
                    })
        return findings


# ------------------------------------------------------------------ lessons inbox + promotion gate
class LessonInbox:
    """Untrusted candidate lessons (from audit_consistency OR emitted by workers/reviewers).
    Nothing here is authoritative until validate_lesson() passes AND promote() is called explicitly."""

    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def _read(self):
        if not os.path.exists(self.path):
            return []
        return [json.loads(l) for l in open(self.path, encoding="utf-8") if l.strip()]

    def _write(self, rows):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)

    def add(self, lesson, source="audit"):
        rows = self._read()
        lid = _hash(lesson.get("kind"), lesson.get("en") or lesson.get("term_en"),
                    lesson.get("he") or lesson.get("term_he"), lesson.get("reason"))
        if any(r["id"] == lid for r in rows):
            return lid  # dedup
        rec = dict(lesson)
        rec.update({"id": lid, "status": "pending", "source": source, "added_at": int(time.time())})
        rows.append(rec)
        self._write(rows)
        return lid

    def add_all(self, lessons, source="audit"):
        return [self.add(l, source) for l in lessons]

    def pending(self):
        return [r for r in self._read() if r.get("status") == "pending"]

    def set_status(self, lid, status, note=""):
        rows = self._read()
        for r in rows:
            if r["id"] == lid:
                r["status"] = status
                if note:
                    r["note"] = note
                r["decided_at"] = int(time.time())
        self._write(rows)


def validate_lesson(lesson):
    """Deterministic PRE-FILTER before the gate (catches obvious junk). Returns (ok, reason).
    A pass here is NECESSARY, not sufficient — an approver (Claude / adversarial verify) still decides."""
    kind = lesson.get("kind")
    if kind == "repair":
        try:
            re.compile(lesson.get("pattern", ""))
        except re.error as e:
            return False, f"bad-regex:{e}"
        return True, "ok"
    if kind == "rule":
        return (bool(lesson.get("text")), "ok" if lesson.get("text") else "empty-rule")
    # term / term_absent
    he = lesson.get("he") or lesson.get("term_he") or ""
    en = lesson.get("en") or lesson.get("term_en") or ""
    if not en:
        return False, "no-english"
    if lesson.get("do_not_translate"):
        return True, "ok"
    if not he:
        return False, "no-hebrew"
    if not HEB.search(he):
        return False, "hebrew-has-no-hebrew-letters"
    if NIQ.search(he):
        return False, "niqqud"
    if FOREIGN.search(he):
        return False, "foreign-script"
    return True, "ok"


def promote(lesson, glossary_path, approved_by):
    """THE GATE. Add a validated+approved lesson into a glossary layer as an authoritative term.
    Refuses on validation failure or a missing approver. divergence -> term with variants; term_absent
    is advisory only (no auto-term; a human/agent decides the real canonical). Returns (ok, msg)."""
    if not approved_by:
        return False, "refused: no approver (default reject)"
    ok, why = validate_lesson(lesson)
    if not ok:
        return False, f"refused: validation {why}"
    if lesson.get("kind") == "term_absent":
        return False, "refused: term_absent is advisory (fix the line or add a real term)"
    data = {"terms": [], "repairs": [], "rules": []}
    if os.path.exists(glossary_path):
        data = json.load(open(glossary_path, encoding="utf-8"))
        for k in ("terms", "repairs", "rules"):
            data.setdefault(k, [])
    kind = lesson.get("kind", "term")
    if kind == "repair":
        data["repairs"].append({"kind": "repair", "name": lesson.get("name", ""),
                                "pattern": lesson["pattern"], "replace": lesson.get("replace", ""),
                                "scope": "game", "promoted": True, "approved_by": approved_by})
    elif kind == "rule":
        data["rules"].append({"kind": "rule", "name": lesson.get("name", ""),
                              "text": lesson["text"], "scope": "game", "promoted": True,
                              "approved_by": approved_by})
    else:
        en = _norm_en(lesson["en"])
        existing = next((t for t in data["terms"] if _norm_en(t.get("en", "")).lower() == en.lower()), None)
        variants = sorted(set((lesson.get("variants") or [])) |
                          set(existing.get("variants", []) if existing else []))
        entry = {"en": en, "he": lesson["he"], "kind": "term", "aliases": lesson.get("aliases", []),
                 "variants": variants, "do_not_translate": bool(lesson.get("do_not_translate")),
                 "referent_gender": lesson.get("referent_gender"), "register": lesson.get("register"),
                 "provenance": lesson.get("provenance", "consistency-audit"),
                 "confidence": lesson.get("confidence", 1.0), "examples": lesson.get("examples", []),
                 "scope": "game", "promoted": True, "approved_by": approved_by}
        if existing:
            existing.update(entry)
        else:
            data["terms"].append(entry)
    tmp = glossary_path + ".tmp"
    os.makedirs(os.path.dirname(os.path.abspath(glossary_path)), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, glossary_path)
    return True, f"promoted {kind}: {lesson.get('en') or lesson.get('name')}"


# ------------------------------------------------------------------ legacy migration
def ingest_name_registry(registry_path, fixes_path, glossary_path):
    """Migrate an existing per-game name_registry.json (en->he) + name_fixes.json (wrong->right)
    into a brain glossary. Fixes become the `variants` canon() enforces. Idempotent-ish (merges)."""
    reg = json.load(open(registry_path, encoding="utf-8")) if os.path.exists(registry_path) else {}
    fixes = json.load(open(fixes_path, encoding="utf-8")) if os.path.exists(fixes_path) else {}

    # 🔴 A per-game registry is written by hand, so its SHAPE varies: RDR2 nests 125 terms under
    # 6 category keys ({"characters": {...}, "places": {...}}) and its fixes file is
    # {"_doc": [...], "pairs": [[wrong, right], ...]}. Iterating `.items()` blindly does not
    # error — it yields 6 garbage terms whose "he" is a stringified dict, 0 variants, and
    # reports `6` as if it worked. Exactly the failure that made `pull_missing.sh`'s name-canon
    # a silent no-op for a whole run. Accept every shape, and RECURSE one level.
    def _flat(d, out=None):
        out = {} if out is None else out
        for k, v in (d or {}).items():
            if str(k).startswith("_"):
                continue
            if isinstance(v, dict):
                _flat(v, out)
            elif isinstance(v, str) and v:
                out[str(k)] = v
        return out

    reg = _flat(reg)
    if isinstance(fixes, dict) and isinstance(fixes.get("pairs"), list):
        pairs = [(str(a), str(b)) for a, b in fixes["pairs"] if a and b]
    elif isinstance(fixes, list):
        pairs = [(str(a), str(b)) for a, b in fixes if a and b]
    else:
        pairs = [(k, v) for k, v in (fixes or {}).items()
                 if isinstance(v, str) and not str(k).startswith("_")]

    # invert fixes: canonical_he -> [wrong_he ...]
    var_by_he = {}
    for wrong, right in pairs:
        var_by_he.setdefault(right, []).append(wrong)
    terms = []
    for en, he in reg.items():
        terms.append({"en": _norm_en(en), "he": he, "kind": "term",
                      "variants": sorted(set(var_by_he.get(he, []))),
                      "do_not_translate": bool(HEB.search(he) is None and en == he),
                      "provenance": "name_registry", "confidence": 1.0, "scope": "game", "promoted": True})
    data = {"terms": [], "repairs": [], "rules": []}
    if os.path.exists(glossary_path):
        data = json.load(open(glossary_path, encoding="utf-8"))
        for k in ("terms", "repairs", "rules"):
            data.setdefault(k, [])
    have = {_norm_en(t.get("en", "")).lower() for t in data["terms"]}
    for t in terms:
        if t["en"].lower() not in have:
            data["terms"].append(t)
    tmp = glossary_path + ".tmp"
    os.makedirs(os.path.dirname(os.path.abspath(glossary_path)), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, glossary_path)
    return len(terms)
