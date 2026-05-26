"""
cp2077_qa_defects.py
====================
Shared defect-detection library for the Cyberpunk 2077 Hebrew QA tooling.

This is the SINGLE SOURCE OF TRUTH for "what counts as a bad line". The
one-shot QA sweep (cp2077_qa_sweep.py) and the background watchdog
(cp2077_qa_watchdog.py) both call scan_all() here, so they flag identically.

Four defect classes (per femaleVariant / maleVariant):
  foreign       a foreign script leaked into the Hebrew (Cyrillic/Arabic/CJK/...)
                or a banned Niqqud vowel-point.
  english_leak  untranslated English words sit inside an otherwise-Hebrew line.
  missing       an English source exists but the translation is blank / still
                English / still the raw Arabic skeleton.
  structural    the markup is damaged — parse_slots() rejects it, or the
                tag / placeholder brackets in the value are unbalanced.

Pure detection: no LM calls, no file writes. Reuses the project's existing,
proven helpers rather than re-implementing them:
  audit_translations.detect_scripts / has_hebrew   — foreign-script detector
  cp2077_status_report.classify / needs_translation — missing/blank classifier
  cp2077_markup_translate.parse_slots               — markup slot model

The English-leak check runs on the *translatable* text only — for a
<kiroshi>/<mothertongue>/<Rich> entry that is the TR slots (the player-visible
t/b/a attributes and <Rich> bodies), NOT the verbatim foreign o/m attributes.
So a Korean leak inside a kiroshi `t` is caught, while the legitimate Japanese
`o` audio transcript is never flagged.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import audit_translations as _audit          # detect_scripts, has_hebrew
import cp2077_status_report as _rep           # classify, needs_translation, paths
import cp2077_markup_translate as _markup     # parse_slots (FIXED/TRANS slot model)

# ── paths (reused verbatim so every tool agrees on the spine file) ──────────
TRANSLATED_FILE = _rep.TRANSLATED
EXPORT_FILE     = _rep.EXPORT
ONSCREENS_SECTIONS = {_rep.ONSCREENS_PRIMARY, _rep.ONSCREENS_MIRROR}

MARKUP_MARKERS = ("<kiroshi", "<mothertongue", "<Rich")

# ── whitelists for the English-leak heuristic ───────────────────────────────
# Lowercased. A word here is treated as legitimately-English and never flagged.
# Covers Night City proper nouns + their component words (so multi-word brands
# like "Night City" / "Kang Tao" don't read as an English run) and hardware.
BRAND_WHITELIST = {
    "night", "city", "watson", "kabuki", "japantown", "westbrook", "pacifica",
    "heywood", "santo", "domingo", "rancho", "coronado", "charter", "hill",
    "arasaka", "militech", "kang", "tao", "kiroshi", "netwatch", "trauma",
    "team", "zetatech", "biotechnica", "petrochem", "delamain", "afterlife",
    "maelstrom", "valentinos", "tyger", "claws", "voodoo", "boys", "animals",
    "moxes", "scavengers", "samurai", "johnny", "silverhand", "alt", "rogue",
    "kerry", "panam", "judy", "river", "takemura", "hanako", "yorinobu",
    "saburo", "evelyn", "dexter", "jackie", "misty", "viktor", "regina",
    "padre", "wakako", "placide", "brigitte", "adam", "smasher", "blackwall",
    "relic", "cyberpsycho", "ncpd", "max", "doc", "rog", "ally", "asus",
    "nvidia", "amd", "intel", "steam", "windows", "android", "ios",
}

# Common English words. A LONE non-allowed word is flagged only if it is one
# of these — a strong signal the line carries a stray untranslated word
# (a rare lone word is more likely a proper noun and is left alone).
COMMON_EN_WORDS = {
    # articles / conjunctions / prepositions
    "the", "and", "but", "for", "nor", "yet", "with", "without", "from",
    "into", "onto", "over", "under", "about", "after", "before", "between",
    "through", "during", "against", "above", "below", "than", "then",
    # pronouns / determiners
    "you", "your", "yours", "his", "her", "hers", "its", "our", "ours",
    "their", "theirs", "this", "that", "these", "those", "they", "them",
    "him", "she", "who", "whom", "whose", "which", "what", "all", "any",
    "some", "each", "every", "both", "few", "more", "most", "other",
    # common verbs
    "have", "has", "had", "will", "would", "shall", "should", "can",
    "could", "may", "might", "must", "are", "was", "were", "been", "being",
    "get", "got", "give", "given", "take", "taken", "make", "made", "find",
    "found", "come", "came", "go", "going", "gone", "see", "seen", "look",
    "want", "need", "know", "knew", "think", "thought", "say", "said",
    "tell", "told", "use", "used", "open", "close", "closed", "press",
    "hold", "enable", "enabled", "disable", "disabled", "select", "choose",
    "start", "started", "stop", "stopped", "continue", "complete",
    "completed", "failed", "loading", "wait", "show", "hide", "add",
    "remove", "delete", "save", "load", "exit", "quit", "return", "back",
    # common game / UI nouns
    "health", "damage", "armor", "armour", "weapon", "enemy", "enemies",
    "mission", "quest", "objective", "level", "skill", "ammo", "reload",
    "inventory", "item", "items", "money", "credits", "police", "danger",
    "warning", "error", "success", "ready", "active", "locked", "unlocked",
    "available", "unavailable", "required", "current", "next", "previous",
    "here", "there", "now", "soon", "again", "yes", "no", "left", "right",
    "up", "down", "new", "old", "good", "bad", "high", "low", "fast", "slow",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")
_TAGS_RE = re.compile(r"<[^<>]*>|\{[^{}]*\}")
# Like _TAGS_RE but the closing > / } is optional, so a TRUNCATED tag at the
# end of a damaged string (e.g. '...<Input actionName="next" color="') is also
# stripped — otherwise its attribute words leak into the english-leak check.
_STRIP_RE = re.compile(r"<[^<>]*>?|\{[^{}]*\}?|%[A-Za-z]")


@dataclass
class Defect:
    section:   str
    pk:        str
    field:     str          # 'femaleVariant' | 'maleVariant'
    kind:      str          # 'foreign' | 'english_leak' | 'missing' | 'structural'
    detail:    str          # human-readable specifics (offending fragment / scripts)
    value:     str          # the bad translated value
    english:   str          # the English source (for the fix loop)
    is_markup: bool         # entry carries <kiroshi>/<mothertongue>/<Rich>


# ── helpers ─────────────────────────────────────────────────────────────────

def is_markup(value: str) -> bool:
    return bool(value) and any(m in value for m in MARKUP_MARKERS)


def translatable_text(value: str):
    """The player-visible text to QA-check.

    Markup entry  -> the joined TR slots (kiroshi/mothertongue t/b/a + <Rich>
                     bodies); verbatim foreign o/m attributes are excluded.
    Plain entry   -> the value with any stray tags/placeholders stripped.
    Returns None  -> the markup is damaged (parse_slots rejected it) — itself
                     a structural defect the caller records.
    """
    if not value:
        return ""
    if is_markup(value):
        slots = _markup.parse_slots(value)
        if slots is None:
            return None
        return " ".join(t for kind, t in slots if kind == "TR")
    return _STRIP_RE.sub(" ", value)


def _is_hard_allowed(tok: str) -> bool:
    """Legitimate English regardless of context: short tokens, ALL-CAPS
    acronyms (RAM/FPS/DLC/NCPD), and whitelisted brand words."""
    if len(tok) <= 2:
        return True
    if tok.isupper():
        return True
    if tok.lower() in BRAND_WHITELIST:
        return True
    return False


def english_leak(text: str):
    """Detect an untranslated English fragment inside Hebrew text.

    `text` must be the translatable text (see translatable_text). Returns the
    offending fragment, or None. Only meaningful on a line that has Hebrew —
    an all-English line is a `missing` defect, not an english_leak.

    Night City is full of fictional brand / product names — "Nokota
    Manufacturing", "Street Queen", "Pixel Neige" — that legitimately stay in
    Latin script. Those are capitalised non-dictionary words. A genuinely
    untranslated *sentence* fragment instead carries real sentence structure:
    a lowercase common English word. So:
      * a run of 2+ consecutive non-allowed words is flagged only when the run
        contains a lowercase common English word (real English prose);
      * a lone non-allowed word is flagged only when it is a common English
        word and is not proper-noun-shaped.
    This deliberately tolerates a missed all-capitalised leak in exchange for
    never flagging — and endlessly re-translating — a brand name.
    """
    if not text or not _audit.has_hebrew(text):
        return None
    words = _WORD_RE.findall(text)
    if not words:
        return None

    run: list[str] = []
    for w in words:
        if _is_hard_allowed(w):
            run = []
            continue
        run.append(w)
        if len(run) >= 2 and any(rw.islower() and rw.lower() in COMMON_EN_WORDS
                                 for rw in run):
            return " ".join(run)

    for w in words:
        if _is_hard_allowed(w):
            continue
        if w[0].isupper() and w[1:].islower():      # lone proper noun — leave it
            continue
        if w.lower() in COMMON_EN_WORDS:
            return w
    return None


_DEV_JUNK = ("TO BE DELETED", "PLACEHOLDER", "DO NOT TRANSLATE",
             "DON'T TRANSLATE", "DONT TRANSLATE", "DEPRECATED", "DEBUG ONLY")


def _is_dev_junk(english: str) -> bool:
    """True for CDPR dev placeholders ("IGNORE, TO BE DELETED" etc.) — not real
    player content, so flagging them as 'missing' is pure noise."""
    up = (english or "").upper()
    return any(m in up for m in _DEV_JUNK)


def strip_foreign(text: str) -> str:
    """Remove foreign-script and Niqqud characters — a last-resort cleanup for
    contamination the LM could not sanitize. Hebrew, Latin, digits, markup and
    punctuation survive. Use only on non-<kiroshi>/<mothertongue> entries —
    their o/m attributes hold legitimate foreign text."""
    if not text:
        return text
    keep = []
    for ch in text:
        cp = ord(ch)
        if _audit.NIQQUD_RANGE[0] <= cp <= _audit.NIQQUD_RANGE[1]:
            continue
        if any(lo <= cp <= hi for lo, hi in _audit.SCRIPT_RANGES.values()):
            continue
        keep.append(ch)
    return "".join(keep)


def value_is_clean(value: str) -> bool:
    """True when a single translated value carries no foreign-script leak, no
    english-leak and reads as Hebrew. The fix loop applies this gate to a
    re-translation before writing it back, so a "fix" can never silently
    introduce a new defect class."""
    if not value:
        return False
    tt = translatable_text(value)
    if tt is None:
        return False
    if _audit.detect_scripts(tt):
        return False
    if english_leak(tt):
        return False
    return _audit.has_hebrew(tt)


def build_export_index(export: dict) -> dict:
    """(section, str(primaryKey)) -> English source text, from the English
    export. The fix loop needs the English source to re-translate cleanly."""
    idx: dict = {}
    for section, rows in (export or {}).items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict) or e.get("primaryKey") is None:
                continue
            eng = (e.get("femaleVariant") or e.get("maleVariant") or "")
            idx[(section, str(e["primaryKey"]))] = eng
    return idx


def english_for(section: str, entry: dict, export_idx: dict) -> str:
    """Best-available English source for one translated entry.

    Onscreens carry only a category path in secondaryKey, so their English is
    looked up by primaryKey in the export. Subtitles keep the English line in
    their own secondaryKey. The export is consulted first either way."""
    pk = str(entry.get("primaryKey"))
    hit = export_idx.get((section, pk))
    if hit:
        return hit
    if section in ONSCREENS_SECTIONS:
        return export_idx.get((_rep.ONSCREENS_PRIMARY, pk), "") \
            or export_idx.get((_rep.ONSCREENS_MIRROR, pk), "")
    return entry.get("secondaryKey") or ""


# ── scanning ────────────────────────────────────────────────────────────────

def scan_entry(section: str, entry: dict, export_idx: dict) -> list[Defect]:
    """All defects for one translated entry, across both variants.

    Every check is slot-aware (via translatable_text / parse_slots). A naive
    classify() or a `<` / `>` bracket count is NOT used: both would mis-judge
    <kiroshi>/<mothertongue> entries (whose Hebrew lives inside tag attributes)
    and any string carrying a literal `<` / `>` as text."""
    out: list[Defect] = []
    pk      = str(entry.get("primaryKey"))
    english = english_for(section, entry, export_idx)
    fv      = entry.get("femaleVariant") or ""
    mv      = entry.get("maleVariant") or ""
    markup  = is_markup(fv) or is_markup(mv)

    def mk(field, kind, detail, value):
        out.append(Defect(section, pk, field, kind, detail, value,
                           english, markup))

    # ── missing / untranslated — judged on the player-visible text ─────────
    # translatable_text() is slot-aware, so a <kiroshi>/<mothertongue> entry
    # whose Hebrew sits inside the tag's t/b/a attributes reads as TRANSLATED.
    primary = fv or mv
    if english and _rep.needs_translation(english) and not _is_dev_junk(english):
        if not primary.strip():
            mk("femaleVariant", "missing", "blank — English source exists",
               primary)
        else:
            tt = translatable_text(primary)
            if (tt is not None and not _audit.has_hebrew(tt)
                    and _markup.is_translatable(tt)):
                mk("femaleVariant", "missing", "untranslated — no Hebrew",
                   primary)

    # ── per-variant foreign-script / english-leak / structural checks ──────
    for field, value in (("femaleVariant", fv), ("maleVariant", mv)):
        if not value:
            continue
        tt = translatable_text(value)
        if tt is None:
            # the slot parser rejects the markup. A real structural defect
            # only when the English SOURCE parses cleanly — otherwise it is
            # bad game data (e.g. a lone "<"), not something we broke or can
            # fix by re-translating.
            if english and _markup.parse_slots(english) is not None:
                mk(field, "structural",
                   "damaged markup (parse_slots rejected)", value)
            continue
        hits = _audit.detect_scripts(tt)
        if hits:
            mk(field, "foreign", ",".join(sorted(hits)), value)
        leak = english_leak(tt)
        if leak:
            mk(field, "english_leak", leak, value)
    return out


def scan_all(translated: dict, export: dict) -> list[Defect]:
    """Every defect in localization_translated.json. `export` is the parsed
    localization_export.json (English source)."""
    export_idx = build_export_index(export)
    defects: list[Defect] = []
    for section, rows in (translated or {}).items():
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if isinstance(entry, dict):
                defects.extend(scan_entry(section, entry, export_idx))
    return defects


# ── write coordination ──────────────────────────────────────────────────────
# The QA sweep and the watchdog both rewrite localization_translated.json.
# This best-effort lock serialises them. A lock older than LOCK_STALE_SEC is
# treated as abandoned (its holder crashed) and stolen.
LOCK_FILE      = os.path.join(_HERE, "qa.lock")
LOCK_STALE_SEC = 3 * 3600


def acquire_lock(holder: str) -> bool:
    """Best-effort exclusive lock for QA writes. True if acquired."""
    import json
    import time
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)
            if time.time() - float(info.get("ts", 0)) < LOCK_STALE_SEC:
                return False                       # held and still fresh
        except Exception:
            pass                                   # corrupt lock -> steal it
    try:
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            json.dump({"holder": holder, "pid": os.getpid(),
                       "ts": time.time()}, f)
        return True
    except OSError:
        return False


def release_lock() -> None:
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def atomic_write_json(path: str, data, *, retries: int = 6) -> None:
    """Atomic JSON write that rides out transient Windows file locks — an
    antivirus or the search indexer can briefly hold the target file, making a
    bare os.replace fail with WinError 5. The rename is retried a few times."""
    import json
    import time
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    for attempt in range(retries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == retries - 1:
                raise
            time.sleep(1.5)


# ── CLI: standalone dry scan, no fixes ──────────────────────────────────────

def main() -> int:
    import json
    from collections import Counter

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print(f"[*] loading {TRANSLATED_FILE}")
    with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
        translated = json.load(f)
    print(f"[*] loading {EXPORT_FILE}")
    with open(EXPORT_FILE, "r", encoding="utf-8") as f:
        export = json.load(f)

    defects = scan_all(translated, export)
    by_kind = Counter(d.kind for d in defects)
    print(f"\n[*] {len(defects):,} defects")
    for kind in ("foreign", "english_leak", "missing", "structural"):
        print(f"      {kind:<14} {by_kind.get(kind, 0):>7,}")
    print("\n[*] english_leak samples:")
    shown = 0
    for d in defects:
        if d.kind != "english_leak":
            continue
        print(f"   [{d.section.split('/')[-1][:24]}:{d.pk}]  leak={d.detail!r}")
        print(f"      {d.value[:140]}")
        shown += 1
        if shown >= 25:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
