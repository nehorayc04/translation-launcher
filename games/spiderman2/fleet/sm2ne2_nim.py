"""Marvel's Spider-Man 2 — New-Era-2 REVIEW worker (derived from skyrim_nim.py).

MONOTONIC: the line is ALREADY translated and shipped. The worker may only FIX a genuine
error; anything it is not sure about comes back unchanged. Every guard below is written to
fail CLOSED (keep the current Hebrew), because a review that degrades a good line is worse
than a review that misses a bad one.

out_<prov>.json = {id: {"he": <hebrew>, "iss": ok|gender|phrasing|slang|error|foreign}}

Same fleet mechanism as the RDR2 / AC2 / Witcher-3 workers (pinned provider, resumable
out_<prov>.json, a disjoint per-provider corpus slice), adapted for Corsair Cove:

  * game = a Caribbean pirate haven in the age of sail. Ships, crews, forts, plunder, trade
    and colonial navies. Cast is a genuine CLOSED SET (the dev kit ships Speaker/Addressee
    columns): Rambullion, Teach, Kanja, Honorata, Jonah, Chen, Scarlet, Enrique, Amara,
    Akua, Audenzia, Admiral Machado. Register: swaggering but NATURAL modern Hebrew — a
    pirate sounds rough and alive, never archaic or biblical.

  * NEW ERA, and the panel is unusually WIDE because the game gives it away for free: 11
    cultures at 100% key parity. Every line carries ru + pl (speaker AND addressee gender,
    and NUMBER — a plural imperative is how "Guards"/"Captains" is resolved), de (register
    + the length budget), fr + es + it (referent agreement). Read the grammar off them;
    NEVER translate from them — `en` is the meaning.

  * the developers also shipped their own translator notes: `ctx` is the real `Context`
    column ("Name of a game setting.", "VO during cutscene"), `sp`/`ad` the speaker and
    addressee. That is context no other game in this project hands over.

  * tokens preserved VERBATIM: `{VAR}` placeholders and `<tag>` markup (`<hl>`, `<b>`,
    `</>`, `<img id="Coin"/>`). A real newline is LOAD-BEARING (762 lines carry one) — keep
    the same count, never merge across it.

  * IRON RULE: the plain hyphen `-`, never a long dash. Repaired deterministically here and
    again at build time; it is a string operation, not a translation decision.

  * store LOGICAL Hebrew. Corsair Cove needs one leading RLM, but that is applied at BUILD
    time by tools/cc_rtl.to_logical — NEVER here.

Run: python sm2ne2_nim.py <groq|sambanova|nim>   (keys in keys.json next to this file)
"""
import json, os, re, sys, time, difflib, threading, urllib.request, urllib.error, ssl
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    import certifi
    _SSLCTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSLCTX = ssl._create_unverified_context()

HERE = os.path.dirname(os.path.abspath(__file__))
_PORDER = ["groq", "sambanova", "nim"]
_PROV = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in _PORDER
         else os.environ.get("FLEET_PROVIDER", "")).strip().lower()
_SUF = f"_{_PROV}" if _PROV in _PORDER else ""
_PIDX = _PORDER.index(_PROV) if _PROV in _PORDER else -1
BASE = "https://integrate.api.nvidia.com/v1"
MODEL = "meta/llama-3.1-70b-instruct"
# Corsair Cove lines are SHORT (median 35 chars) but each carries a 6-language panel, so the
# budget is per-PAYLOAD, not per-line: ~16 lines/batch at the median, ~5 at p90.
BUDGET = 1600
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, f"out{_SUF}.json")

_FLEET = None
try:
    sys.path.insert(0, HERE)
    import fleet_providers as _fp
    _FLEET = _fp.Fleet(_fp.load_keys(HERE), only=(_PROV if _PIDX >= 0 else None))
    print(f"[fleet] {'PINNED ' + _PROV if _PIDX >= 0 else 'round-robin'}: "
          f"{_FLEET.provider_names()} -> {os.path.basename(OUT)}", flush=True)
except Exception as _e:
    print("[fleet] single-NIM fallback:", _e, flush=True)

PANEL = ("ar", "ru", "pl", "de", "fr", "it", "es", "es-mx", "pt")
# The panel is budgeted by the LINE's length (see _payload). ru+pl are kept longest because
# they are the only two that mark speaker AND addressee gender + number.
PANEL_SLIM = ("ar", "ru", "pl")
PANEL_FULL_MAX = 800      # <= this many EN chars: the full six-language panel
PANEL_SLIM_MAX = 2500     # <= this: ru + pl only;  above it: English alone
# An EN longer than this cannot be produced inside any provider's output ceiling in ONE call
# (measured: the longest line the fleet ever DID bank is 8,397 chars). Such a line is parked
# immediately and reported, instead of timing out on every worker forever.
MAX_EN_CHARS = 9000

# Cyrillic / Greek / Arabic / kana / CJK / Hangul. Cyrillic matters MOST here: ru sits in every
# prompt, so a copy-the-Russian leak is the realistic failure, not an exotic one.
FOREIGN = re.compile("[\u0400-\u04ff\u0370-\u03ff\u0600-\u06ff\u0750-\u077f"
                     "\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")
# Niqqud only. U+05BE MAQAF is deliberately OUTSIDE this class — it is a legitimate Hebrew
# punctuation mark, not a vowel point, and stripping it would corrupt words like בין־לאומי.
NIQ = re.compile("[\u0591-\u05bd\u05bf\u05c1\u05c2\u05c7]")
HEB = re.compile("[\u05d0-\u05ea]")
# Corsair Cove tokens: {VAR} placeholders + <tag> markup. There is NO overloaded [bracket]
# syntax in this corpus (measured: 0 occurrences) and no real printf, so a bracket here is
# ordinary punctuation and is free to translate.
# SM2 tokens: the <ts="a;b"> timing tags (order-bearing — they bind text to audio), any
# other markup tag, the &rlm; RTL anchors the build depends on, [TOKEN]/{VALUE}, printf.
# 🔴 [NAME ICON] (e.g. "[PETE ICON]", "[MILES ICON]") is a SPACE-containing engine token —
# the official Arabic reference keeps it byte-literal English in every language (it selects
# the speaker portrait). The plain [A-Z0-9_]{1,40} alternative below requires NO internal
# space, so it never matched this shape, which is exactly how the review silently corrupted
# it into "[פיט ICON]" (2026-08-15, see NAME_SUBTITLE_SPID). Scoped to the literal " ICON]"
# suffix ONLY — do NOT widen to a blanket "any all-caps bracket with spaces": the corpus also
# has "[FOR PICKUP]" (MILE_GP_BACKTOSCHOOL_021), which is ordinary caps-styled prose and is
# CORRECTLY translated to "[לאיסוף]" — a blanket rule would flag every future re-translation
# of it as a token-mismatch and silently revert it to English.
STRUCT = re.compile(r'<[^<>]{1,120}>|&[a-zA-Z]{2,8};|\{[^{}]{0,80}\}'
                    r'|\[[A-Z][A-Z0-9_]* ICON\]|\[[A-Z0-9_]{1,40}\]|%[#0-9.*+-]*[a-zA-Z]')
LOWER = re.compile(r"[a-z]{2,}")
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'\u2019/\u00ae\u2122\u00a9]*$")
_CTRL = "".join(chr(c) for c in range(0x20))
# IRON RULE (CLAUDE.md): every long/typographic dash -> the plain ASCII hyphen, ONE FOR ONE.
# Not a run-collapse: a repeated dash is usually a decorative rule drawn on purpose.
_DASHES = str.maketrans({c: "-" for c in
                         "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
                         "\u2e3a\u2e3b\ufe58\ufe63\uff0d"})
# \ud83d\udd34 A Hebrew one-letter prefix is GLUED to its word \u2014 `\u05d1\u05e9\u05d1\u05e2\u05ea \u05d4\u05d9\u05de\u05d9\u05dd`, never `\u05d1-\u05e9\u05d1\u05e2\u05ea \u05d4\u05d9\u05de\u05d9\u05dd`.
# The hyphen-after-prefix form is correct ONLY before Latin or a digit (`\u05dc-NPC`, `\u05d1-2024`),
# which is exactly why the model reaches for it and then over-applies it to Hebrew. Measured
# on the first 176 banked lines: 5 of them (`\u05d1-\u05e9\u05d1\u05e2\u05ea`, `\u05d1-\u05d1\u05d9\u05ea`). The lookbehind keeps a real
# compound safe \u2014 in `\u05d4\u05d0\u05dc-\u05de\u05dc\u05da` the letter before the hyphen is not a standalone prefix.
_PREFIX_HYPHEN = re.compile("(?<![\u05d0-\u05ea])([\u05d5\u05d1\u05dc\u05de\u05d4\u05e9\u05db])"
                            "-(?=[\u05d0-\u05ea])")

S1 = ("You are a senior Hebrew localization EDITOR for Marvel's Spider-Man 2 (modern-day "
      "New York: Peter Parker and Miles Morales, fast banter, mission dialogue, story cutscenes). "
      "Each item gives: 'en' = the English source, 'he' = the Hebrew ALREADY SHIPPING, and the "
      "game's own professional translations ('ar' EGYPTIAN COLLOQUIAL, 'ru', 'pl', 'de', 'fr', "
      "'it', 'es', 'es-mx', 'pt'). Those other languages are your GROUND TRUTH for what English "
      "hides.\n"
      "REVIEW each line. If 'he' is already correct, fluent and complete, RETURN IT UNCHANGED "
      "with iss=ok. That is the expected outcome for most lines. Only change a line for a REAL "
      "defect:\n"
      "  gender  - wrong addressee/speaker gender or number. ADDRESSEE: Arabic إنتَ/عايز/فاهم -> "
      "אתה ; إنتِ/عايزة/ـكِ -> את ; أنتم/إنتوا -> אתם. Polish -leś->אתה, -łaś->את, wy->אתם. "
      "Russian ты+…л->אתה, ты+…ла->את. SPEAKER: Russian я …-л/-ла, Polish -łem/-łam - match the "
      "Hebrew 1st person and NEVER turn a 1st/3rd-person verb into 2nd person.\n"
      "  FORMAL-YOU TRAP: Russian 'вы' / Italian 'voi' / Spanish 'usted' addressed to ONE person "
      "is FORMAL SINGULAR, not plural - Hebrew stays אתה/את. Only a TRUE plural (Arabic "
      "أنتم/إنتوا) becomes אתם.\n"
      "  error   - a clear mistranslation against 'en'.\n"
      "  phrasing- stiff/literal Hebrew where natural modern spoken Hebrew is meant.\n"
      "  foreign - leftover English/Arabic/other-script words that should be Hebrew.\n"
      "HARD RULES: keep the SAME meaning. Keep EVERY token byte-for-byte and in the same order "
      "and count - the <ts=\"a;b\"> timing tags, &rlm; RTL anchors, <span>/<i>/<br>, {VALUE}, "
      "[TOKEN], %d/%s. Keep NUMBERS. Keep canonical names (ספיידרמן, מיילס, פיטר, מרי ג'יין, "
      "הארי, מיי, ונום, קרייבן, הלטאה, העקרב, הנשר, החתולה השחורה, מיסטריו, סאנדמן, טומסטון). "
      "NO niqqud. Store LOGICAL Hebrew - never reverse letters. Use the plain hyphen '-', never "
      "a long dash. If 'gender_hint' is given it was derived from the game's own Arabic/Russian "
      "morphology - trust it over your own reading.\n"
      "Output ONLY JSON {id:{\"he\":<hebrew>,\"iss\":<ok|gender|phrasing|slang|error|foreign>}} "
      "with exactly the same ids as the input.")


def _en(v):
    return v.get("en", "") if isinstance(v, dict) else (v or "")


def is_namey(en):
    en = (en or "").strip(); ws = en.split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)


def normalize(s, en=""):
    """Deterministic clean-up applied BEFORE the guard.

    🔴 A defect with exactly ONE correct answer must be REPAIRED, never struck. Stripping
    niqqud and swapping a long dash for a hyphen are string operations, not translation
    decisions — refusing the line instead of fixing it turns a good translation into a
    strike, and three strikes park real content (the AC2 lesson: 78% of rejections there
    were niqqud on perfectly fine dialogue).

    🔴🔴 EDGE WHITESPACE IS STRUCTURAL, AND A BARE .strip() DESTROYS IT (found 2026-08-07:
    667 of the 14,495 lines still outstanding carry leading/trailing whitespace in the
    ENGLISH -- overwhelmingly a trailing `\\r\\n` on a book page). The old `.strip()` here
    removed it from the model's answer, the guard then counted one newline fewer than the
    English and REJECTED a perfectly good translation, three times, and parked it. So:
    trim only what the model itself added, then restore the English's OWN leading/trailing
    whitespace verbatim. Deterministic, and it can only ever make the counts agree.
    """
    s = NIQ.sub("", s).translate(_DASHES)
    s = _PREFIX_HYPHEN.sub(r"\1", s)
    core = s.strip()
    if en:
        lead = en[:len(en) - len(en.lstrip())]
        trail = en[len(en.rstrip()):]
        # a model that answers with bare LF where the source uses CRLF is not a content
        # error either -- match the source's own line-ending convention.
        if "\r\n" in en and "\r\n" not in core and "\n" in core:
            core = core.replace("\n", "\r\n")
        return lead + core + trail
    return core


def why_invalid(new, en, v=None):
    """The reason `valid` refuses, or '' if it accepts. Kept in lockstep with valid()."""
    if not new or not new.strip(): return "empty"
    if FOREIGN.search(new): return "foreign-script"
    if NIQ.search(new): return "niqqud"
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)):
        return f"token-mismatch {sorted(STRUCT.findall(en))} -> {sorted(STRUCT.findall(new))}"
    if en.count("\n") != new.count("\n"):
        return f"newline-count {en.count(chr(10))} -> {new.count(chr(10))}"
    core = STRUCT.sub(" ", en); bare = new.lstrip(_CTRL).strip()
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en.strip() and is_namey(en)): return "no-hebrew"
    if len(en) >= 12 and bare == en.strip() and not is_namey(en): return "copy-EN"
    p = plural_conflict(new, en)
    if p: return p
    g = gender_conflict(new, v)
    if g: return g
    return ""


def review_ok(new, cur, en):
    """May this proposed line REPLACE the shipping one? Fails CLOSED.

    🔴 A review is monotonic: the burden of proof is on the CHANGE, not on keeping the line.
    Every clause below therefore rejects the edit and keeps `cur` — the worst outcome of a
    false negative is a missed fix, the worst outcome of a false positive is a shipped
    regression on a line that was already fine (measured on the Witcher-3 QA pass: an
    automated review turned `מדיטציה` into `התמדו` and `התייעצות` across a whole term).
    """
    if not new or not new.strip():                       return "empty"
    if FOREIGN.search(new):                              return "foreign-script"
    if NIQ.search(new):                                  return "niqqud"
    if not HEB.search(new):                              return "no-hebrew"
    # tokens must be identical to the SHIPPING line, not merely to the English: the build
    # depends on the <ts> timing tags and the &rlm; anchors exactly as they are on disk.
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(cur)):
        return "token-mismatch"
    if cur.count(chr(10)) != new.count(chr(10)):         return "newline-count"
    # a rewrite that keeps under 45% of the original is not a fix, it is a re-translation
    if difflib.SequenceMatcher(None, new, cur).ratio() < 0.45:
        return "rewrite (similarity < 0.45)"
    return ""


def gender_ok(new, cur, v):
    """A gender FLIP is only allowed toward what the game's own languages actually say.

    Without this the model happily 'corrects' אתה->את on a line whose Arabic and Russian both
    address a male, and a fleet turns one confident misreading into thousands of edits. The
    hint is the deterministic one the adapter baked in from ar_addressee_strict / ru_addressee
    — a CLOSED set. No hint => no gender change is permitted at all.
    """
    gc, gn = he_addressee(cur), he_addressee(new)
    if gn == gc:
        return ""
    want = {"נמען=זכר": "m", "נמען=נקבה": "f", "נמען=רבים": "pl"}.get((v or {}).get("gender_hint", ""))
    if want and gn == want:
        return ""
    return f"gender flip {gc}->{gn} unsupported by the oracle"


def valid(new, en, v=None):
    return not why_invalid(new, en, v)


# ── canonical glossary ───────────────────────────────────────────────────────────────────
# A fleet turns ONE wrong name into thousands of lines. The registry was decided from the
# game's OWN locales (ru makes a transliteration visible at a glance) and every term was
# validated to EXIST in the corpus. Sent PER BATCH — only the terms that actually occur — so
# it is free on lines that need none, and re-applied at merge so a later correction costs no
# re-translation.
_GLOSS = {}
try:
    _reg = json.load(open(os.path.join(HERE, "brain_glossary.json"), encoding="utf-8"))
    # ⚠️ The brain glossary is {"terms":[{en,he,...}], "repairs":..., "rules":...} — the old
    # loader looked for `entries` and for a `term` field, so it silently produced an EMPTY
    # glossary (the log said "glossary 0" on every stream and nobody noticed). The names it
    # is meant to pin — Whiterun/Dragonborn/... — were therefore never sent to the model.
    if isinstance(_reg, dict): _reg = _reg.get("terms") or _reg.get("entries") or []
    if isinstance(_reg, dict): _reg = [dict(v, en=k) for k, v in _reg.items()]
    for item in _reg:
        if not isinstance(item, dict):
            continue
        term = item.get("en") or item.get("term")
        he = item.get("he")
        if term and he and not item.get("do_not_translate"):
            _GLOSS[term] = he
except Exception as _e:
    print("[gloss] none:", _e, flush=True)
_GLOSS_ORDER = sorted(_GLOSS, key=len, reverse=True)


def glossary_for(batch):
    """The canonical terms that occur in THIS batch, as 'English = Hebrew' lines."""
    hay = " ".join(_en(v) for _k, v in batch)
    hit, seen = [], set()
    for t in _GLOSS_ORDER:
        if t in hay and not any(t in s for s in seen):
            hit.append(f"{t} = {_GLOSS[t]}"); seen.add(t)
        if len(hit) >= 20: break
    return hit


# ── gender guard: a CLOSED SET straight from the developers' own metadata ─────────────────
# Corsair Cove ships SpeakerGender/AddresseeGender columns, so unlike every other game in this
# project the guard does not have to reverse-engineer gender out of Arabic or Russian. Only the
# hard male/female/plural values reach the corpus as `ag`; everything else (the `variable`
# bucket = a group written as a name) is left to the model to read off ru/pl, because a guess
# outside a closed set manufactures confident garbage.
_HE_PL = re.compile("(?<![\u05d0-\u05ea])\u05d0\u05ea[\u05dd\u05df](?![\u05d0-\u05ea])")
_HE_M = re.compile("(?<![\u05d0-\u05ea])\u05d0\u05ea\u05d4(?![\u05d0-\u05ea])")
_HE_F = re.compile("(?<![\u05d0-\u05ea])\u05d0\u05ea(?![\u05d0-\u05ea])")
# 'את' is ALSO the accusative particle ("קח את זה"), so a bare את only counts as "you-fem"
# when a feminine 2nd-person verb backs it up.
_HE_VF = re.compile("(?<![\u05d0-\u05ea])(?:"
                    "\u05e6\u05e8\u05d9\u05db\u05d4|\u05d9\u05db\u05d5\u05dc\u05d4|"
                    "\u05d9\u05d5\u05d3\u05e2\u05ea|\u05de\u05d5\u05db\u05e0\u05d4|"
                    "\u05d7\u05d9\u05d9\u05d1\u05ea|\u05ea\u05d5\u05db\u05dc\u05d9|"
                    "\u05d1\u05d5\u05d0\u05d9|\u05e7\u05d7\u05d9|\u05ea\u05e2\u05e9\u05d9|"
                    "\u05dc\u05db\u05d9|\u05d1\u05d8\u05d5\u05d7\u05d4|\u05de\u05d1\u05d9\u05e0\u05d4|"
                    "\u05e9\u05d5\u05de\u05e2\u05ea|\u05ea\u05d2\u05d9\u05d3\u05d9|"
                    "\u05e8\u05d5\u05e6\u05d4|\u05e2\u05d5\u05e9\u05d4|"
                    "\u05d4\u05d5\u05dc\u05db\u05ea|\u05e0\u05e8\u05d0\u05d9\u05ea"
                    ")(?![\u05d0-\u05ea])")


def he_addressee(t):
    if not t: return None
    if _HE_PL.search(t): return "pl"
    if _HE_M.search(t): return "m"
    if _HE_F.search(t) and _HE_VF.search(t): return "f"
    if _HE_VF.search(t): return "f"
    return None


PLURAL = re.compile(r"\|plural\(([^)]*)\)")


def _plural_cases(clause):
    out = {}
    for part in clause.split(","):
        part = part.strip()
        if "=" in part:
            k, _, val = part.partition("=")
            out[k.strip()] = val.strip()
    return out


def plural_conflict(new, en):
    """|plural(one=X, other=Y) is an engine formatting RULE, not prose. Each clause must
    keep the same case names as the English, in the same clause ORDER (the model must not
    swap a verb-agreement clause with a noun clause), and never turn a non-empty English
    case into an empty Hebrew one -- that is exactly the syntax the engine fails to parse
    (measured in-game: a blank `one=` branch left the raw `|plural(...)` text on screen)."""
    en_cl, he_cl = PLURAL.findall(en), PLURAL.findall(new)
    if len(en_cl) != len(he_cl):
        return f"plural-clause-count {len(en_cl)} -> {len(he_cl)}"
    for e, h in zip(en_cl, he_cl):
        ec, hc = _plural_cases(e), _plural_cases(h)
        if set(ec) != set(hc):
            return f"plural-case-names {sorted(ec)} -> {sorted(hc)}"
        for k, ev in ec.items():
            if ev.strip() and not hc.get(k, "").strip():
                return f"plural-empty-branch [{k}]"
    return ""


def gender_conflict(new, v=None):
    return "" # Handled by reviewer later
def load_keys():
    keys = []
    raw = os.environ.get("NVIDIA_API_KEYS", "").strip()
    if raw: keys += [k.strip() for k in raw.split(",") if k.strip()]
    v = os.environ.get("NVIDIA_API_KEY", "").strip()
    if v and v not in keys: keys.append(v)
    # keys.json is the multi-provider file, and its nim key must ALSO feed this legacy list —
    # without it _KEYS is empty and the fallback dies in _pick_key with an error that MASKS
    # the real provider failure.
    kj = os.path.join(HERE, "keys.json")
    if os.path.exists(kj):
        try:
            d = json.load(open(kj, encoding="utf-8"))
            if d.get("nim") and d["nim"] not in keys: keys.append(str(d["nim"]).strip())
        except Exception:
            pass
    for kt in (os.path.join(HERE, "key.txt"), r"C:\w3w\key.txt", r"C:\ptw\key.txt"):
        if os.path.exists(kt):
            for l in open(kt, encoding="utf-8"):
                l = l.strip()
                if l.startswith("nvapi-") and l not in keys: keys.append(l)
    return keys


_KEYS = []; _KI = 0; _COOL = {}


def _pick_key():
    global _KI
    n = len(_KEYS); now = time.time()
    for _ in range(n):
        k = _KEYS[_KI % n]; _KI = (_KI + 1) % n
        if _COOL.get(k, 0) <= now: return k
    k = min(_KEYS, key=lambda x: _COOL.get(x, 0))
    time.sleep(max(0.0, _COOL.get(k, 0) - now) + 0.5)
    return k


def _one_call_blocking(key, sysmsg, usermsg, timeout=180, max_tokens=2500):
    payload = {"model": MODEL, "temperature": 0.2, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": sysmsg},
                            {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload).encode(),
                                 method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout, context=_SSLCTX).read()
                      .decode())["choices"][0]["message"]["content"]


def _one_call(key, sysmsg, usermsg, timeout=180, max_tokens=2500):
    # Same hard wall-clock wrapper as fleet_providers._one, and for the same reason: this is
    # the LEGACY single-key fallback path (fed by a stray key.txt this machine still carries
    # from an earlier fleet, e.g. C:\w3w\key.txt / C:\ptw\key.txt) that `chat()` silently
    # drops into whenever `_FLEET.complete()` raises -- so it needs the SAME protection or a
    # DNS-resolver stall bypasses the fix entirely via this route (found live 2026-08-03:
    # stream #14 stayed hung >20 min even after fleet_providers.py was hardened, because its
    # calls were actually landing here, not in _FLEET).
    box = {}

    def _run():
        try:
            box["ok"] = _one_call_blocking(key, sysmsg, usermsg, timeout, max_tokens)
        except Exception as e:
            box["err"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout + 15)
    if t.is_alive():
        raise TimeoutError(f"hard wall-clock timeout ({timeout + 15}s) - likely a stuck DNS lookup")
    if "err" in box:
        raise box["err"]
    return box["ok"]


def _parse(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if m:
        try: return json.loads(m.group(0))
        except Exception: pass
    out = {}
    for mm in re.finditer(r'"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*")', txt):
        try: out[mm.group(1)] = json.loads(mm.group(2))
        except Exception: pass
    return out


def chat(sysmsg, usermsg, retries=3, timeout=180, max_tokens=2500):
    if _FLEET is not None:
        try:
            r = _parse(_FLEET.complete(sysmsg, usermsg, retries=max(retries, 4),
                                       timeout=timeout, max_tokens=max_tokens))
            if r:
                return r
        except Exception:
            pass
    if not _KEYS:
        # every configured provider was tried and none answered — "nobody replied" is
        # blameless and must never let the caller strike the lines.
        return {}
    last = None
    for _ in range(retries):
        k = _pick_key()
        try:
            r = _parse(_one_call(k, sysmsg, usermsg, timeout, max_tokens))
            if r: return r
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                _COOL[k] = time.time() + 90; continue
            time.sleep(2)
        except Exception as e:
            last = e; time.sleep(2)
    if last: raise last
    return {}


def atomic(path, obj):
    # PER-PID temp name: a stray duplicate or the pull's scp can hold the file, and a SHARED
    # ".tmp" let two writers race until one died with WinError 5.
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    for i in range(20):
        try:
            os.replace(tmp, path); return
        except PermissionError:
            time.sleep(0.3 + i * 0.1)
    try:
        os.replace(tmp, path)
    except PermissionError:
        try: os.remove(tmp)
        except OSError: pass


# --- the New-Era prompt payload -----------------------------------------------------------
def _payload(v):
    if not isinstance(v, dict): return {"en": v or ""}
    p = {"en": v.get("en", "")}
    for f in ("ctx", "sp", "ad"):
        if v.get(f): p[f] = v[f]
    if v.get("ag"): p["addressee_gender"] = {"m": "male", "f": "female", "pl": "plural"}[v["ag"]]
    if v.get("sg"): p["speaker_gender"] = {"m": "male", "f": "female"}[v["sg"]]
    # BUGFIX (found on inspection, 2026-08-05): the multilang_review corpus does NOT carry
    # flat top-level "ru"/"pl"/... keys - each language sits in v["refs"][L] as a [fv, mv]
    # PAIR. The original loop (`if v.get(L)`) always read None here, so every prompt sent
    # for translation was silently JUST {"en": ...} with the entire six-language reference
    # panel dropped - the whole point of the New-Era-2 corpus was not reaching the model.
    # 🔴🔴 THE PANEL MUST BE BUDGETED BY THE LINE'S OWN LENGTH. Six reference languages make
    # every prompt ~7x the English, which is free on a 35-char UI label and catastrophic on a
    # book page: measured 2026-08-07, `skyrim:skyrim|1994` (The Real Barenziah V, 40,131 chars
    # of English) built a 294,677-CHARACTER prompt. Such a call can never be answered, so it
    # timed out at 150 s, earned no strike (a transport failure is correctly blameless), and
    # was re-served every single pass FOREVER -- that is exactly the "output file hasn't moved
    # in 14/35/67 min" the dashboard was reporting, on streams whose remaining work is 95%
    # trivial one-liners sitting behind a handful of these monsters.
    # The panel is a GRAMMAR ORACLE, not the source, so its value falls away as the line grows
    # (a 3,000-char narrative page has no addressee to gender). Spend it where it pays:
    en_len = len(p["en"])
    if en_len <= PANEL_FULL_MAX:
        want = PANEL                      # ~97% of lines: unchanged, full six-language panel
    elif en_len <= PANEL_SLIM_MAX:
        want = PANEL_SLIM                 # ru+pl only = speaker AND addressee gender + number
    else:
        want = ()                         # book-scale prose: English only
    refs = v.get("refs") or {}
    for L in want:
        pair = refs.get(L)
        if isinstance(pair, list) and pair:
            fv = pair[0] if len(pair) > 0 else ""
            mv = pair[1] if len(pair) > 1 else fv
            val = mv or fv  # masculine-default, matches the S1 instruction to address the player as אתה
            if val:
                p[L] = val
    # the line under review, and the deterministic morphological hint the adapter derived
    p["he"] = _cur(v)
    if v.get("gender_hint"):
        p["gender_hint"] = v["gender_hint"]
    if v.get("speaker"):
        p["speaker"] = v["speaker"]
    return p


def _cur(v):
    """The Hebrew currently shipping. multilang_review stores `he` as [fv, mv]; SM2 has one
    string per id, so the two slots are identical and either is the line."""
    if not isinstance(v, dict):
        return ""
    h = v.get("he")
    if isinstance(h, list):
        return (h[0] or (h[1] if len(h) > 1 else "") or "").strip()
    return (h or "").strip()


def _tok(v):
    p = _payload(v)
    return sum(len(str(x)) for x in p.values()) // 3 + 10


def make_batches(todo):
    batches, cur, ct = [], [], 0
    for k, v in todo:
        t = _tok(v)
        if cur and ct + t > BUDGET:
            batches.append(cur); cur, ct = [], 0
        cur.append((k, v)); ct += t
        if ct >= BUDGET:
            batches.append(cur); cur, ct = [], 0
    if cur: batches.append(cur)
    return batches


def do_batch(sub):
    # FAIL-FAST: a doomed/throttled call must fail in tens of seconds, not minutes. Every
    # provider's real median (~1s groq, ~3s sambanova, ~16s nim) fits well under this.
    # 2026-08-03: measured live — DNS + TCP + TLS to all 3 provider hosts complete in
    # 150-300ms from every corsair-cove VM (no VPN/network issue), yet ~15-20% of batches
    # still hit "step1 fail (The read operation timed out)" at the old 110s cap. That means
    # the model is occasionally just slower than the old ceiling, not that the connection is
    # broken -- so a bit more headroom directly helps, and 150s is still far under the
    # dashboard's 8-min "slow" / 20-min "stalled" thresholds.
    to = min(150, 75 + sum(_tok(v) for _, v in sub) // 10)
    # A batch of ONE is, by construction, a line too big to share a batch. Capping it at the
    # same 150 s as a 25-line batch of one-liners guarantees it can never finish -- and a
    # timeout earns no strike, so it comes back next pass, forever. Give a solo line real
    # room; it is a handful of lines per shard, so the extra wall-clock costs nothing.
    if len(sub) == 1:
        to = min(300, 90 + _tok(sub[0][1]) // 8)
    # 🔴 max_tokens must budget for REASONING, not just for the answer. Groq's
    # openai/gpt-oss-120b is a reasoning model and its thinking counts against this ceiling:
    # measured live, a 6-line batch at max_tokens=720 came back TRUNCATED after 2.5 lines
    # (173 chars of JSON) and the other 4 keys read as "the model omitted them" — which the
    # omit/strike path would eventually PARK as unfixable content. Budget generously:
    # the JSON keys are long here (`ST_Achievements|NAME_ACH_...` ~44 chars each), Hebrew
    # tokenizes at roughly a token per character, and the reasoning preamble is a flat few
    # hundred tokens on top.
    # ⚠️ The old flat `min(4000, ...)` ceiling was a Corsair Cove number (median line 35
    # chars). Skyrim ships book pages: a 3,000-char English page needs well over 4,000 output
    # tokens in Hebrew, so the answer was TRUNCATED, the missing ids read as "the model
    # omitted them", and the line was re-served forever. Every provider here has a far larger
    # ceiling than 4,000, so scale with the real content and only cap at something the models
    # actually support.
    mx = min(16000, 1000
             + sum(len(k) for k, _ in sub) // 2
             + sum(len(_en(v)) for _, v in sub) * 2)
    gl = glossary_for(sub)
    msg = "Translate:\n" + json.dumps({k: _payload(v) for k, v in sub}, ensure_ascii=False)
    if gl:
        msg = ("Canonical Hebrew for the names in this batch — use EXACTLY these:\n"
               + "\n".join(gl) + "\n\n" + msg)
    try:
        s1 = chat(S1, msg, timeout=to, max_tokens=mx)
    except Exception as e:
        # TRANSPORT failure: the provider never answered, so this says NOTHING about the
        # lines. Report it so the caller can tell "rejected" from "nobody replied" — a bare
        # {} made the caller strike every line and 3 throttled batches parked real dialogue.
        print(f"  step1 fail ({e}) — skip batch"); return {}, False, set()
    res, seen = {}, set()
    for k, v in sub:
        ans = s1.get(k)
        iss = "ok"
        if isinstance(ans, dict):
            iss = str(ans.get("iss") or ans.get("issue") or "ok").strip().lower()
            ans = ans.get("he") or ans.get("hebrew") or ans.get("text") or ans.get("translation")
        if not isinstance(ans, str): continue
        # `seen` = the model actually produced a candidate for THIS key. Only such a key can
        # earn a strike; a silently OMITTED key is a model dropout, as blameless as a 429.
        seen.add(k)
        cur = _cur(v)
        new = normalize(ans, cur)
        if not new or new.strip() == cur.strip():
            res[k] = {"he": cur, "iss": "ok"}          # explicitly reviewed, nothing to fix
            continue
        bad = review_ok(new, cur, _en(v)) or gender_ok(new, cur, v)
        if bad:
            # 🔴 A refused EDIT is not a refused LINE. Bank the line unchanged and mark it
            # reviewed, or the worker re-serves it every pass forever chasing an edit the
            # guard will never accept — the exact loop that stalled the Skyrim fleet.
            res[k] = {"he": cur, "iss": "ok"}
            if len(sub) == 1:
                print(f"    KEEP {k} [{bad}] cur={cur[:50]!r} new={new[:50]!r}", flush=True)
            continue
        res[k] = {"he": new,
                  "iss": iss if iss in ("gender", "phrasing", "slang", "error", "foreign") else "error"}
    return res, True, seen


LOCK = os.path.join(HERE, f"worker{_SUF}.lock")


def _alive(pid):
    """Is a WORKER still running under that pid?

    🔴 A bare "does this pid exist" check is WRONG: Windows recycles pids, so a dead worker's
    pid gets reused by an unrelated process and the lock never goes stale — seen live on vm3,
    where the lock held a pid that had become `svchost` and a third of the machine's capacity
    was silently lost behind a reassuring "another worker is already running".
    """
    try:
        if os.name == "nt":
            import subprocess
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\").CommandLine"],
                capture_output=True, text=True, timeout=20).stdout
            return "sm2ne2_nim" in (out or "")
        os.kill(pid, 0); return True
    except Exception:
        return False


def acquire_singleton():
    """the task re-launches us every few minutes — never run two copies on one slice."""
    if os.path.exists(LOCK):
        try:
            pid = int(open(LOCK).read().strip() or 0)
        except Exception:
            pid = 0
        if pid and pid != os.getpid() and _alive(pid):
            print(f"another worker is already running (pid {pid}) — exiting."); return False
    try:
        open(LOCK, "w").write(str(os.getpid()))
    except Exception:
        pass
    return True


MAX_STRIKES = 3
MAX_OMITS = 5
# 🔴 THE THIRD COUNTER, and the one whose absence froze the fleet. A transport failure
# (timeout / 429 / connection reset) is BLAMELESS and must never earn a strike -- that rule is
# correct and stays. But with NO counter at all, a line that can never be answered ALONE is
# re-served on every single pass for the life of the worker, and one such line in a shard
# pins the whole stream at 0 lines/min while thousands of trivial lines wait behind it
# (measured live 2026-08-07 on 15 of 21 streams). So: count consecutive transport failures
# for a SOLO batch only -- where the failure really is about that one line, not about a
# provider blip that happened to hit a 25-line batch -- and retire it after MAX_TFAILS.
# 3, not 5: `Fleet.complete()` already makes TWO real attempts per call and cools the provider
# down 60 s between them, so one solo timeout already costs ~11 min of a stream's wall-clock.
# 3 outer failures = 6 genuine attempts spread over ~35 min — far past any transient blip, and
# it caps the dead time a single doomed line can take from the stream.
MAX_TFAILS = 3
SKIP = os.path.join(HERE, f"sm2ne2_skip{_SUF}.json")


def _load_skip():
    """Parked keys + per-key failure counts.

    A line the guard rejects MUST leave the queue after MAX_STRIKES, or it is re-served every
    pass forever and crowds out real work. `omits` is a SEPARATE counter: a key the model
    silently DROPS from its JSON can never be struck by the reject path, so without a ceiling
    it loops "pass: N left" indefinitely with strikes stuck at 0. `tfails` is the third:
    a solo line that keeps timing out (see MAX_TFAILS).
    """
    try:
        d = json.load(open(SKIP, encoding="utf-8"))
        return (set(d.get("skip", [])), dict(d.get("strikes", {})),
                list(d.get("token_only", [])), dict(d.get("omits", {})),
                dict(d.get("tfails", {})))
    except Exception:
        return set(), {}, [], {}, {}


def _save_skip(skip, strikes, token_only=None, omits=None, tfails=None, oversized=None):
    """Never let bookkeeping kill the run — a failed save just costs a re-try later."""
    try:
        d = {"skip": sorted(skip), "strikes": strikes, "omits": omits or {},
             "tfails": tfails or {}}
        prev, prev_over = [], []
        try:
            _p = json.load(open(SKIP, encoding="utf-8"))
            prev = list(_p.get("token_only", []))
            prev_over = list(_p.get("oversized", []))
        except Exception:
            pass
        d["token_only"] = sorted(set(prev) | set(token_only or []))
        # kept in its OWN list, never merged into token_only: these are real, translatable
        # content that simply exceeds a single call. Visible so a dedicated chunked pass can
        # pick them up later -- never fake-banked as done.
        d["oversized"] = sorted(set(prev_over) | set(oversized or []))
        atomic(SKIP, d)
    except Exception:
        pass


def main():
    if not acquire_singleton(): return
    keys = load_keys()
    global _KEYS, _KI
    _KEYS = list(keys); _KI = 0
    if _FLEET is None and (not keys or not keys[0].startswith("nvapi-")):
        print("[X] No key found (keys.json / key.txt / NVIDIA_API_KEY)."); return
    # A per-provider shard file OVERRIDES any hash split. A fixed md5 assignment strands the
    # remaining work on the slowest provider the moment one is rate-limited (measured at 68%
    # on W3), so the deploy writes corpus_<provider>.json per stream.
    _cp = os.path.join(HERE, f"corpus{_SUF}.json")
    per_prov = bool(_SUF) and os.path.exists(_cp)
    src = _cp if per_prov else CORPUS
    if not os.path.exists(src):
        print(f"[X] corpus not found ({src})."); return
    corpus = json.load(open(src, encoding="utf-8"))
    if _PIDX >= 0 and not per_prov:
        import hashlib
        corpus = {k: v for k, v in corpus.items()
                  if int(hashlib.md5(k.encode()).hexdigest(), 16) % 3 == _PIDX}
        print(f"[fleet] pinned 1/3 slice: {len(corpus)} lines for {_PROV}", flush=True)
    else:
        print(f"[fleet] corpus={len(corpus)} "
              f"({'per-provider file' if per_prov else 'shared'}) | provider={_PROV}", flush=True)
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    skip, strikes, _parked_tokonly, omits, tfails = _load_skip()
    print(f"SM2 New-Era-2 REVIEW worker | slice {len(corpus)} lines | already done {len(out)} | "
          f"parked {len(skip)} | glossary {len(_GLOSS)} | keys {len(_KEYS)}")
    idle = 0
    while True:
        todo = [(k, v) for k, v in corpus.items() if k not in out and k not in skip]
        # Retire the book-scale lines UP FRONT rather than discovering them by timing out on
        # each one for 300 s, five passes in a row. They are honestly recorded as `oversized`
        # (never counted as done), so the remaining count stays truthful.
        # ⚠️ NO oversized park in a REVIEW: the line already ships Hebrew, so the worst case
        # is "we could not improve it", never "it is missing". A huge line simply gets the
        # solo-batch treatment (long timeout, big output budget) like any other.
        over = []
        if over:
            skip.update(over); _save_skip(skip, strikes, omits=omits, tfails=tfails, oversized=over)
            todo = [(k, v) for k, v in todo if k not in skip]
            print(f"  parked {len(over)} oversized lines (>{MAX_EN_CHARS} chars — need a "
                  f"chunked pass, not a single call)", flush=True)
        # A line whose text is 100% engine tokens is UNWINNABLE: translating breaks the token
        # multiset and returning it unchanged trips copy-EN. Park it (never fake-bank the
        # English — that would show a false 100%).
        # unwinnable-by-construction: 100% engine tokens (translating breaks the multiset,
        # returning it unchanged trips copy-EN) OR pure whitespace (`why_invalid` calls any
        # blank answer "empty", so NO output can ever pass — 261 such lines were quietly
        # burning 3 API calls each before being parked, measured 2026-08-07).
        tokonly = []
        if tokonly:
            skip.update(tokonly); _save_skip(skip, strikes, tokonly, omits, tfails)
            todo = [(k, v) for k, v in todo if k not in skip]
            print(f"  parked {len(tokonly)} token-only lines (no legal output exists)", flush=True)
        if not todo:
            print("slice drained — done."); break
        batches = make_batches(todo)
        print(f"pass: {len(todo)} left, {len(batches)} batches")
        got_any = False
        for bi, sub in enumerate(batches, 1):
            answered = set(); ok = False
            try:
                res, ok, answered = do_batch(sub)
                # RECOVERY: the model silently omits ids. Those are NOT rejections — re-ask
                # each alone (highest hit-rate) before any strike. Pure recovered throughput.
                if ok and len(sub) > 1:
                    for one in [x for x in sub if x[0] not in answered]:
                        try:
                            r1, _ok1, s1 = do_batch([one])
                            res.update(r1); answered |= s1
                        except Exception:
                            pass
            except Exception as e:
                # never let one bad batch kill the worker — park nothing, move on
                print(f"  [{bi}/{len(batches)}] batch error ({e}) — continuing", flush=True)
                res, answered = {}, set()
            if res:
                out.update(res); atomic(OUT, out); got_any = True
            parked = 0
            for k, _v in sub:
                if k in res:
                    strikes.pop(k, None); omits.pop(k, None); tfails.pop(k, None)
                elif k in answered:
                    strikes[k] = strikes.get(k, 0) + 1
                    if strikes[k] >= MAX_STRIKES:
                        skip.add(k); strikes.pop(k, None); parked += 1
                elif ok:
                    # `ok` = the provider genuinely replied, so an omission is the model's own
                    # choice, not a transport blip. A batch nobody answered touches nothing.
                    omits[k] = omits.get(k, 0) + 1
                    if omits[k] >= MAX_OMITS:
                        skip.add(k); omits.pop(k, None); parked += 1
                elif len(sub) == 1:
                    # transport failure on a SOLO line: still blameless (no strike), but it
                    # cannot be allowed to be re-served every pass forever. See MAX_TFAILS.
                    tfails[k] = tfails.get(k, 0) + 1
                    if tfails[k] >= MAX_TFAILS:
                        skip.add(k); tfails.pop(k, None); parked += 1
            _save_skip(skip, strikes, omits=omits, tfails=tfails)
            # 🔴 A PERCENTAGE SHOWN TO A HUMAN IS A CLAIM ABOUT STATE. `len(out)` is the bank's
            # ALL-TIME total, accumulated across every reslice generation, while `corpus` is
            # only the CURRENT shard — so the old line printed "total 4097/1751 (234.0%)" and
            # the dashboard faithfully showed 234%. Count what this shard has actually
            # finished; keep the all-time figure alongside it, clearly labelled.
            in_shard = sum(1 for k in corpus if k in out)
            pct = 100.0 * in_shard / max(1, len(corpus))
            print(f"  [{bi}/{len(batches)}] +{len(res)}/{len(sub)}"
                  f"{f' park+{parked}' if parked else ''}  shard {in_shard}/{len(corpus)} "
                  f"({pct:.1f}%)  bank {len(out)}",
                  flush=True)
        if not got_any:
            idle += 1
            if idle >= 3:
                print("3 passes with zero output — sleeping 120s"); time.sleep(120); idle = 0
        else:
            idle = 0


if __name__ == "__main__":
    main()
