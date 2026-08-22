"""Crimson Desert translator worker — דור 3, seven-language panel.

The PROVEN Corsair Cove worker retargeted: pinned provider, resumable out_<prov>.json, a
disjoint per-provider slice, strike/park + an omit ceiling, a PID+cmdline singleton and atomic
per-PID writes all carry over unchanged. What is Crimson-Desert-specific:

  * game = a grounded medieval-fantasy war epic on the continent of Pywel. Kliff and the
    Greymanes, feuding kingdoms, sieges, monsters, the Abyss. Register: serious epic fantasy
    in NATURAL modern Hebrew — never archaic, never slang.

  * the panel is FREE and wide: the game ships 14 languages at 100% key parity. Every line
    carries ru + pl (speaker AND addressee gender + number), de (register + length budget)
    and fr/es/it/pt (referent agreement). Read the grammar off them; NEVER translate from
    them — `en` is the meaning.

  * `addressee_gender`/`speaker_gender` are DETERMINISTIC, derived from the game's own Russian
    by universal/gender_oracle.py (a CLOSED set) in the דור-3 adapter — not guessed here.

  * the glossary is the דור-3 BRAIN (`brain_glossary.json`): terms decided by the game's own
    Russian and validated to EXIST in the corpus, injected PER BATCH and re-applied at merge
    so a later correction costs no re-translation.

  * tokens preserved VERBATIM: `{...}` placeholders (`{staticInfo:...}`) and `<br/>`.

  * IRON RULE: the plain hyphen `-`, never a long dash. Repaired deterministically here and
    again at build time.

  * store LOGICAL Hebrew. Crimson Desert renders in STORAGE order (bidi=VISUAL, proven
    in-game), but that transform belongs to the BUILD — never to this worker.

Run: python cd_nim.py <groq|sambanova|nim>   (keys in keys.json next to this file)
"""
import json, os, re, sys, time, threading, urllib.request, urllib.error, ssl
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
# Measured on the real corpus: median 26 chars, p90 139, max 1,774 — short, but every line
# carries a 7-language panel, so the budget is per-PAYLOAD, not per-line.
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

PANEL = ("ru", "pl", "de", "fr", "es", "it", "pt")

# Cyrillic / Greek / Arabic / kana / CJK / Hangul. Cyrillic matters MOST here: ru sits in every
# prompt, so a copy-the-Russian leak is the realistic failure, not an exotic one.
FOREIGN = re.compile("[\u0400-\u04ff\u0370-\u03ff\u0600-\u06ff\u0750-\u077f"
                     "\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")
# Niqqud only. U+05BE MAQAF is deliberately OUTSIDE this class — it is a legitimate Hebrew
# punctuation mark, not a vowel point, and stripping it would corrupt words like בין־לאומי.
NIQ = re.compile("[\u0591-\u05bd\u05bf\u05c1\u05c2\u05c7]")
HEB = re.compile("[\u05d0-\u05ea]")
# 🔴 CRIMSON DESERT OVERLOADS `[...]` — MEASURED, not assumed (the AC2 trap). 5,329 bracket
# occurrences / 175 distinct, and the game's OWN Russian settles each class:
#   * PROSE  `[Crafting Method]` -> ru `[Способ изготовления]`  = a translated section HEADER
#     (also [Recipe] [Effect] [How to Use] [Supply Contract]...). Must stay TRANSLATABLE, so
#     it is deliberately NOT in STRUCT — putting it there would make the guard reject every
#     correct translation of a crafting tooltip.
#   * TOKEN  `[EMPTY]` (2,639) -> ru keeps it VERBATIM = an engine sentinel.
#   * TOKEN  `%0#`/`%1#` (285) -> ru keeps them VERBATIM = engine placeholders. Note this is
#     NOT C printf (`%s`/`%d`: 0 occurrences) — the `#` form is Pearl Abyss's own.
# Line breaks are `<br/>` (23,751); there is not a single real newline in the corpus, so the
# newline guard is inert here and the <br/> count is what the token multiset protects.
STRUCT = re.compile(r"<[^<>]{1,80}>|\{[^{}]{0,80}\}|\[EMPTY\]|%\d+#")
# a Hebrew letter touching a Latin one with nothing between them = a half-transliteration
SEAM = re.compile(r"[א-ת][A-Za-z]|[A-Za-z][א-ת]")
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

S1 = ("You are a senior Hebrew localizer for Crimson Desert - a grounded medieval-fantasy "
      "war epic on the continent of Pywel: mercenary companies, feuding kingdoms and clans, "
      "sieges and hunts, monsters and the Abyss. The player is Kliff, captain of the Greymanes. "
      "Recurring proper names include Pywel, Hernand, Delesyia, Calphade, Varnia, Pailune, "
      "Solumen, Demeniss, Marni and the Abyss. Write natural, fluent, MODERN Hebrew with a "
      "serious epic-fantasy voice - never archaic or biblical-sounding, never modern slang. "
      "Keep each speaker's voice; rough language stays rough. UI labels, item names and "
      "tooltips stay terse and functional, like real game menus. "
      "Each input line gives 'en' = the English MEANING to translate, plus the SAME line as the "
      "game's own professional translators shipped it: 'ru' 'pl' 'de' 'fr' 'es' 'it' 'pt'. "
      "Translate the MEANING from 'en'. Use the other languages ONLY as the grammar oracle, "
      "because English hides what Hebrew must state: ru and pl mark the SPEAKER's and the "
      "ADDRESSEE's gender and NUMBER (a plural imperative there means address a GROUP - "
      "atem and plural verbs), fr/es/it/pt mark the referent's gender, de shows the register. "
      "Follow them: a woman gets את and feminine verbs, a man אתה, a group אתם. Do NOT "
      "translate from those languages and NEVER copy a foreign word - Cyrillic, Greek, Turkish "
      "or CJK characters in your output are always a bug. "
      "'addressee_gender'/'speaker_gender' when present are DETERMINISTIC facts read off the "
      "game's own Russian - obey them over your own reading. "
      "ADDRESS THE PLAYER IN MASCULINE SINGULAR by default, consistently: an objective, a "
      "tooltip or a menu instruction is בנה / השלם / קנה / דבר / שלך - never the plural "
      "בנו / השלימו, and never a plural verb with a singular possessive in the same line. "
      "Only address a GROUP with אתם when the line really is spoken to several people "
      "(ru/pl will show a plural there). "
      "Never put a hyphen between a Hebrew prefix and a Hebrew word: write בשבעת הימים, not "
      "ב-שבעת הימים. A hyphen after a prefix is only for Latin or digits (ל-NPC, ב-2024). "
      "Keep every token VERBATIM from the English, same count and same position: the {..} "
      "placeholders (for example {staticInfo:...}) and the <br/> line-break tags. Keep the "
      "SAME number of <br/> tags and never merge text across one. "
      "Use the plain hyphen '-'. Never use a long dash. No niqqud. "
      "Proper names use their accepted Hebrew form; brand/code tokens stay Latin. "
      "If a line is an ALL-CAPS code, a file path or unreadable gibberish, return it UNCHANGED. "
      "Output JSON {id: hebrew} only, with exactly the same ids as the input.")


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
    """
    s = NIQ.sub("", s).translate(_DASHES)
    return _PREFIX_HYPHEN.sub(r"\1", s).strip()


def why_invalid(new, en, v=None):
    """The reason `valid` refuses, or '' if it accepts. Kept in lockstep with valid()."""
    if not new or not new.strip(): return "empty"
    if FOREIGN.search(new): return "foreign-script"
    if NIQ.search(new): return "niqqud"
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)):
        return f"token-mismatch {sorted(STRUCT.findall(en))} -> {sorted(STRUCT.findall(new))}"
    if en.count("\n") != new.count("\n"):
        return f"newline-count {en.count(chr(10))} -> {new.count(chr(10))}"
    s = SEAM.search(new)
    if s:
        # A Hebrew letter GLUED to a Latin one is never valid output. It is the signature of a
        # half-transliteration - `בדropkick`, `ביachע` - which passes every other rule here:
        # Latin is legal (brands must stay Latin), the tokens match, there IS Hebrew, and it is
        # not a copy of the English. Measured on 469 accepted lines: 4 hits, all genuine
        # defects, while all 24 lines that legitimately carry Latin (`ענף נשמה של Shadowleaf`,
        # `מגדל השידור של מרני A`) pass untouched - a real brand is separated by a space.
        return f"hebrew-latin-seam '{s.group(0)}'"
    core = STRUCT.sub(" ", en); bare = new.lstrip(_CTRL).strip()
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en.strip() and is_namey(en)): return "no-hebrew"
    if len(en) >= 12 and bare == en.strip() and not is_namey(en): return "copy-EN"
    p = plural_conflict(new, en)
    if p: return p
    g = gender_conflict(new, v)
    if g: return g
    return ""


def valid(new, en, v=None):
    return not why_invalid(new, en, v)


# ── canonical glossary ───────────────────────────────────────────────────────────────────
# A fleet turns ONE wrong name into thousands of lines. The registry was decided from the
# game's OWN locales (ru makes a transliteration visible at a glance) and every term was
# validated to EXIST in the corpus. Sent PER BATCH — only the terms that actually occur — so
# it is free on lines that need none, and re-applied at merge so a later correction costs no
# re-translation.
_GLOSS = {}
_RULES = []
try:
    _reg = json.load(open(os.path.join(HERE, "brain_glossary.json"), encoding="utf-8"))
    for _t in (_reg.get("terms") or []):
        if isinstance(_t, dict) and _t.get("en") and _t.get("he"):
            _GLOSS[_t["en"]] = _t["he"]
    _RULES = [r for r in (_reg.get("rules") or []) if isinstance(r, str)]
    print(f"[brain] {len(_GLOSS)} terms, {len(_RULES)} rules", flush=True)
except Exception as _e:
    print("[brain] none:", _e, flush=True)
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
# Crimson Desert ships no gender metadata, so `ag`/`sg` are derived in the דור-3 adapter from
# the game's own RUSSIAN via universal/gender_oracle.py — pronouns and past-tense morphology,
# a CLOSED set. 6,324 of 184,993 lines get a hard fact; the rest carry the raw ru/pl for the
# model to read. A hint is NEVER guessed from an open class: a wrong one creates exactly the
# gender debt it exists to prevent. [[gender-hint-needs-closed-set]]
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


def gender_conflict(new, v):
    """'' or the reason — set only when the dev kit is UNAMBIGUOUS and the Hebrew contradicts it."""
    a = (v or {}).get("ag") if isinstance(v, dict) else None
    if not a: return ""
    h = he_addressee(new)
    if not h or h == a: return ""
    return f"gender {h} vs devkit {a}"


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
        err = None
        try:
            r = _parse(_FLEET.complete(sysmsg, usermsg, retries=max(retries, 4),
                                       timeout=timeout, max_tokens=max_tokens))
            if r:
                return r
        except Exception as e:
            err = e
        # 🔴 A PINNED worker must NOT fall through to the legacy single-provider path.
        # `_KEYS` then holds the PINNED provider's keys, and the legacy path posts them
        # to NVIDIA - so a groq key comes back "401 Unauthorized", which is a lie: it
        # hides the real reason the fleet call failed (nearly always a 429, because
        # max_tokens is RESERVED against groq's per-minute budget). Chasing a key that
        # was never broken is the exact cost of swallowing this.
        if _PROV:
            if err:
                raise err
            return {}
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
    # 🔴 A LOOKUP ON CORPUS DATA MUST NEVER BE A BARE `[...]`. `gender_oracle` returns "pl" for
    # plural on BOTH axes, and the inherited speaker map had only m/f — so the first line with
    # a plural SPEAKER killed the worker with `KeyError: 'pl'`. All 18 streams died within
    # seconds of launch while the deploy reported "RESTARTED" for every machine.
    _G = {"m": "male", "f": "female", "pl": "plural"}
    if v.get("ag") in _G: p["addressee_gender"] = _G[v["ag"]]
    if v.get("sg") in _G: p["speaker_gender"] = _G[v["sg"]]
    for L in PANEL:
        if v.get(L): p[L] = v[L]
    return p


def _tok(v):
    p = _payload(v)
    return sum(len(str(x)) for x in p.values()) // 3 + 10


# 🔴 BATCH SIZE IS PER PROVIDER, because their limits differ in KIND. Measured on a real
# 8-line batch of this corpus: groq answers in 3.5s (fast, but TPM-capped — a huge batch
# reserves enough tokens to 429 the key instantly), sambanova 10.5s, nim 37s (generous quota,
# slow per call — a 43-line batch simply blew the worker's own 150s ceiling and every call
# came back `read operation timed out`, i.e. +0/N forever). A token budget ALONE is not
# enough: it happily packs 40 two-word UI labels into one call.
MAXLINES = {"groq": 20, "sambanova": 14, "nim": 10}.get(_PROV, 16)


def make_batches(todo):
    batches, cur, ct = [], [], 0
    for k, v in todo:
        t = _tok(v)
        if cur and (ct + t > BUDGET or len(cur) >= MAXLINES):
            batches.append(cur); cur, ct = [], 0
        cur.append((k, v)); ct += t
        if ct >= BUDGET or len(cur) >= MAXLINES:
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
    # 🔴 max_tokens must budget for REASONING, not just for the answer. Groq's
    # openai/gpt-oss-120b is a reasoning model and its thinking counts against this ceiling:
    # measured live, a 6-line batch at max_tokens=720 came back TRUNCATED after 2.5 lines
    # (173 chars of JSON) and the other 4 keys read as "the model omitted them" — which the
    # omit/strike path would eventually PARK as unfixable content. Budget generously:
    # the JSON keys are long here (`ST_Achievements|NAME_ACH_...` ~44 chars each), Hebrew
    # tokenizes at roughly a token per character, and the reasoning preamble is a flat few
    # hundred tokens on top.
    mx = min(4000, 1000
             + sum(len(k) for k, _ in sub) // 2
             + sum(len(_en(v)) for _, v in sub) * 2)
    gl = glossary_for(sub)
    sysmsg = S1 + ("\nGame rules:\n" + "\n".join(_RULES) if _RULES else "")
    msg = "Translate:\n" + json.dumps({k: _payload(v) for k, v in sub}, ensure_ascii=False)
    if gl:
        msg = ("Canonical Hebrew for the names in this batch — use EXACTLY these:\n"
               + "\n".join(gl) + "\n\n" + msg)
    try:
        s1 = chat(sysmsg, msg, timeout=to, max_tokens=mx)
    except Exception as e:
        # TRANSPORT failure: the provider never answered, so this says NOTHING about the
        # lines. Report it so the caller can tell "rejected" from "nobody replied" — a bare
        # {} made the caller strike every line and 3 throttled batches parked real dialogue.
        print(f"  step1 fail ({e}) — skip batch"); return {}, False, set()
    res, seen = {}, set()
    for k, v in sub:
        he = s1.get(k)
        if isinstance(he, dict):
            he = he.get("he") or he.get("hebrew") or he.get("text") or he.get("translation") or ""
        if not isinstance(he, str): continue
        he = normalize(he, _en(v))
        if not he: continue
        # `seen` = the model actually produced a candidate. Only such a key can earn a
        # strike: a key silently OMITTED is a model dropout, as blameless as a 429.
        seen.add(k)
        bad = why_invalid(he, _en(v), v)
        if not bad:
            res[k] = he
        elif len(sub) == 1:
            print(f"    REJECT {k} [{bad}] en={_en(v)[:60]!r} he={he[:60]!r}", flush=True)
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
            return "cd_nim" in (out or "")
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
SKIP = os.path.join(HERE, f"cd_skip{_SUF}.json")


def _load_skip():
    """Parked keys + per-key failure counts.

    A line the guard rejects MUST leave the queue after MAX_STRIKES, or it is re-served every
    pass forever and crowds out real work. `omits` is a SEPARATE counter: a key the model
    silently DROPS from its JSON can never be struck by the reject path, so without a ceiling
    it loops "pass: N left" indefinitely with strikes stuck at 0.
    """
    try:
        d = json.load(open(SKIP, encoding="utf-8"))
        return (set(d.get("skip", [])), dict(d.get("strikes", {})),
                list(d.get("token_only", [])), dict(d.get("omits", {})))
    except Exception:
        return set(), {}, [], {}


def _save_skip(skip, strikes, token_only=None, omits=None):
    """Never let bookkeeping kill the run — a failed save just costs a re-try later."""
    try:
        d = {"skip": sorted(skip), "strikes": strikes, "omits": omits or {}}
        prev = []
        try:
            prev = list(json.load(open(SKIP, encoding="utf-8")).get("token_only", []))
        except Exception:
            pass
        d["token_only"] = sorted(set(prev) | set(token_only or []))
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
    skip, strikes, _parked_tokonly, omits = _load_skip()
    print(f"Crimson Desert דור-3 worker | slice {len(corpus)} lines | already done {len(out)} | "
          f"parked {len(skip)} | glossary {len(_GLOSS)} | keys {len(_KEYS)}")
    idle = 0
    while True:
        todo = [(k, v) for k, v in corpus.items() if k not in out and k not in skip]
        # A line whose text is 100% engine tokens is UNWINNABLE: translating breaks the token
        # multiset and returning it unchanged trips copy-EN. Park it (never fake-bank the
        # English — that would show a false 100%).
        tokonly = [k for k, v in todo if _en(v).strip() and not STRUCT.sub("", _en(v)).strip()]
        if tokonly:
            skip.update(tokonly); _save_skip(skip, strikes, tokonly, omits)
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
                    strikes.pop(k, None); omits.pop(k, None)
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
            _save_skip(skip, strikes, omits=omits)
            done = len(out); pct = 100.0 * done / max(1, len(corpus))
            print(f"  [{bi}/{len(batches)}] +{len(res)}/{len(sub)}"
                  f"{f' park+{parked}' if parked else ''}  total {done}/{len(corpus)} ({pct:.1f}%)",
                  flush=True)
        if not got_any:
            idle += 1
            if idle >= 3:
                print("3 passes with zero output — sleeping 120s"); time.sleep(120); idle = 0
        else:
            idle = 0


if __name__ == "__main__":
    main()
