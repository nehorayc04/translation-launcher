"""Red Dead Redemption 2 NIM translator — New-Era: the game's own ARABIC is the oracle.

Same fleet mechanism as the AC2 / Witcher 3 workers (pinned provider, resumable out.json, a
disjoint corpus.json slice), adapted for RDR2:
  * game = the American West, 1899 — Arthur Morgan and the Van der Linde gang (Dutch, Hosea,
    Sadie, Micah, Sean, Charles, Lenny, John Marston), Valentine / Saint Denis / Blackwater /
    Rhodes. Register: period Western but NATURAL modern Hebrew — never archaic-sounding Hebrew.
  * NEW ERA, thin panel by necessity: RDR2's RPF8 table of contents is encrypted, so Rockstar's
    own French/Russian/… are unreadable and the public dump is English-only. What we DO have is
    Ko Games' professional ARABIC — and for Hebrew that is the STRONGEST possible single oracle,
    not a consolation: Arabic marks exactly what English drops and Hebrew must state
    (أنتَ/أنتِ/أنتم = אתה/את/אתם, gendered verbs, the feminine ـة). 100% of the corpus has it.
    Read the grammar off 'ar'; never translate FROM it.
  * tokens preserved VERBATIM: every ~...~ RAGE control — ~z~ (dialogue), ~n~ (line break),
    ~sl:a:b~ (subtitle timing), ~s~ ~o~ ~d~, ~1~ ~2~, ~COLOR_*~, ~INPUT_*~ — plus printf specs.
    ⚠️ ~n~ and ~sl:~ are ORDER-BEARING: keep them where they are or the lines swap in-game.
  * store LOGICAL Hebrew here. RDR2 is a store-VISUAL engine, but the reversal, the pre-wrap and
    the justification all happen at BUILD time in games/rdr2/work/rdr2_rtl.py — NEVER here.

Put the NVIDIA key in key.txt (nvapi-... line) or NVIDIA_API_KEY. Run: python rdr2_nim.py <provider>
It loops until corpus.json (its disjoint slice) is drained. out.json is pulled to the main PC.
"""
import json, os, re, sys, time, urllib.request, urllib.error, ssl
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    import certifi
    _SSLCTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSLCTX = ssl._create_unverified_context()

HERE = os.path.dirname(os.path.abspath(__file__))
# pinned single-provider mode: one worker per provider, disjoint 1/3 of the slice by md5.
_PORDER = ["groq", "sambanova", "nim"]
# provider from argv[1] (visible in the process command line, so self-heal can match each
# of the 3 instances separately) or env FLEET_PROVIDER.
_PROV = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in _PORDER
         else os.environ.get("FLEET_PROVIDER", "")).strip().lower()
_SUF = f"_{_PROV}" if _PROV in _PORDER else ""
_PIDX = _PORDER.index(_PROV) if _PROV in _PORDER else -1
BASE = "https://integrate.api.nvidia.com/v1"
MODEL = "meta/llama-3.1-70b-instruct"
# 🔴 THIS IS SIZED TO THE PAYLOAD, AND THE PAYLOAD CHANGED.
# 150 was right when a line shipped as {en, ar} (median ~30 tokens). Once the game's own
# archives gave us a 7-language New-Era panel the median became 107, so make_batches packed
# ~1.4 lines per call -- 920 API calls for 1,307 lines, ~15 lines/min across 21 streams.
# The panel is NOT the problem and must not be trimmed to chase speed (measured elsewhere:
# latency is queue variance, not prompt size); the PACKER was simply calibrated for a payload
# that no longer exists. Measured over this corpus: 150 -> 1.4 lines/call, 1800 -> 11.6.
# UNIVERSAL: whenever you widen what a batch carries, re-measure lines-per-call — a token
# budget is a property of the payload, and a stale one silently costs an order of magnitude.
BUDGET = 2000        # keep the OUTPUT reservation small: max_tokens is charged against TPM
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, f"out{_SUF}.json")

# --- multi-provider fleet (Groq + SambaNova + NIM). FLEET_PROVIDER pins one provider
#     (3 parallel workers per machine); unset = round-robin. Falls back to NIM-only if
#     keys.json / fleet_providers.py are absent, so an un-migrated stream still runs. ---
_FLEET = None
_FLEET_ANY = None
try:
    sys.path.insert(0, HERE)
    import fleet_providers as _fp
    _keys = _fp.load_keys(HERE)
    _FLEET = _fp.Fleet(_keys, only=(_PROV if _PIDX >= 0 else None))
    # 🔑 SECOND, UNPINNED fleet used ONLY when the pinned provider has every key cooling.
    # Which slice a worker owns (`corpus_<prov>.json`) is INDEPENDENT of which endpoint
    # answers it — the provider name is just how the slices were cut. So a groq stream
    # sitting out a 60 s cooldown was pure idle time while sambanova/nim had headroom;
    # borrowing it converts that idle into throughput and cannot duplicate work, because
    # the slice is still disjoint. (Do not give this to the LEGACY path — see chat().)
    try:
        _FLEET_ANY = _fp.Fleet(_keys) if _PIDX >= 0 else None
    except Exception:
        _FLEET_ANY = None
    print(f"[fleet] {'PINNED ' + _PROV if _PIDX >= 0 else 'round-robin'}: "
          f"{_FLEET.provider_names()} -> {os.path.basename(OUT)}"
          f"{' | borrow: ' + ','.join(_FLEET_ANY.provider_names()) if _FLEET_ANY else ''}",
          flush=True)
except Exception as _e:
    print("[fleet] single-NIM fallback:", _e, flush=True)

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힯Ѐ-ӿ]')
NIQ = re.compile(r'[֑-ֽֿׁׂ]')
HEB = re.compile(r'[֐-׿]')
# RDR2 tokens are RAGE tilde controls, not markup. Unlike AC2 there is NO overloaded
# [bracket] syntax here, so the whole prose-vs-token bracket machinery is dropped: a
# bracket in RDR2 text is ordinary punctuation and is free to translate.
# ⚠️ ~n~ and ~sl:a:b~ are ORDER-BEARING separators — the guard compares the token multiset,
# and the BUILD keeps their positions, so a model that moves one is caught here.
STRUCT = re.compile(r'~[^~]*~|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+')


LOWER = re.compile(r'[a-z]{2,}')
_DIG = re.compile(r'\d+')
# ®/™/© belong to a PRODUCT NAME ("Assassin's Creed® II"), which must stay Latin. Without
# them here is_namey() fails, the copy-EN/no-Hebrew rule fires, and the only correct output
# (the title unchanged) is rejected forever — 7 title lines were stuck on exactly this.
# NOTE the CURLY apostrophe U+2019: the game's own product titles are typeset
# ("ASSASSIN’S CREED® II"), and omitting it made is_namey() refuse the only correct
# output for those lines — the title unchanged — as copy-EN, forever.
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'’/®™©]*$")
_CTRL = "".join(chr(c) for c in range(0x20))

S1 = ("You are a senior Hebrew localizer for Red Dead Redemption 2 — the American West, 1899: "
      "Arthur Morgan and the Van der Linde gang (Dutch, Hosea, Sadie, Micah, Sean, Charles, "
      "Lenny, John Marston), the towns of Valentine, Rhodes, Saint Denis and Blackwater, the "
      "Pinkertons closing in. Write natural, fluent, MODERN Hebrew with a period flavour — "
      "cowboys, outlaws, horses, revolvers, saloons — but never archaic or biblical-sounding "
      "Hebrew, and keep each character's voice (Arthur dry and weary, Dutch grandiose, Micah "
      "vicious, Sadie fierce, Uncle lazy). Crude language stays crude. "
      "Each input line has 'en' = the English MEANING to translate, plus THE SAME line as "
      "professionally localized by Rockstar into other languages — any of 'ar' (Arabic), 'ru' "
      "(Russian), 'pl' (Polish), 'de' (German), 'fr' (French), 'es' (Spanish), 'it' (Italian), "
      "'br' (Brazilian Portuguese). Translate the MEANING from 'en'. Use the others as the "
      "GENDER / NUMBER / REGISTER oracle, because English hides what Hebrew must state and they "
      "state it explicitly. Read them by strength: ru and pl mark the gender of BOTH the speaker "
      "and the person addressed (past tense -л/-ла, -łem/-łam), so they settle אתה vs את vs אתם and "
      "אמרתי vs אמרתני; ar does the same Semitically (أنتَ = אתה, أنتِ = את, أنتم = אתם, a verb "
      "ending ـين or a ـكِ suffix = spoken TO A WOMAN, the feminine ـة = a female referent); "
      "fr/es/it/br mark the referent's gender (-o/-a, -é/-ée); de marks register (du vs Sie). "
      "When they disagree, the majority wins. They also disambiguate the ENGLISH itself — if a "
      "word could mean two things, see which one they all chose. Do NOT translate FROM them and do "
      "NOT copy foreign words — 'en' is the meaning, the rest are grammar and meaning evidence. "
      "Keep every token VERBATIM from the English, same count and same position: the RAGE tilde "
      "controls ~z~ ~s~ ~o~ ~d~ ~n~ ~1~ ~2~ ~COLOR_*~ ~INPUT_*~ and the subtitle timing ~sl:a:b~, "
      "plus printf specs %d %s %i. ~n~ and ~sl:~ mark LINE BOUNDARIES — never move them, never "
      "merge the text across them, never add or remove one. "
      "No niqqud. Proper names (Arthur, Dutch, Sadie, Micah, John, Valentine, Saint Denis, "
      "Blackwater) use their accepted Hebrew transliteration; brand/code tokens stay Latin. "
      "If a line is an ALL-CAPS code, a file path or unreadable gibberish, return it UNCHANGED. "
      "Output JSON {id: hebrew} only, with exactly the same ids as the input.")


def _en(v):
    return v.get("en", "") if isinstance(v, dict) else (v or "")


# A URL / bare domain / email is content the game DISPLAYS but that must never be translated,
# and `is_namey` refuses it because it starts lowercase — so the guard rejected
# `wheelerrawson.com -> wheelerrawson.com`, and three strikes would have PARKED a line whose
# only correct answer is the passthrough it was already given.
_URLISH = re.compile(
    r"^(?:https?://\S+|www\.\S+|[\w.\-]+@[\w.\-]+\.\w{2,}|[\w\-]+(?:\.[\w\-]+)+)$", re.I)


def is_namey(en):
    en = (en or "").strip(); ws = en.split()
    if not ws:
        return False
    if len(ws) == 1 and _URLISH.match(ws[0]):
        return True
    # A multi-word PROPER NAME is allowed to carry the connectors real business and place
    # names use — `D.D. & Packenbush`, `La Capilla, Guarma`, `Smith and Sons`. Without this
    # the guard rejected the model's (correct) verbatim passthrough as `no-hebrew`, burned
    # three strikes and PARKED a place name that must stay Latin anyway. A connector is only
    # accepted BETWEEN capitalised words, so it can never turn a sentence into a "name".
    if len(ws) > 6:
        return False
    # connectors + the lowercase nobiliary particles real surnames use (`Van der Linde`)
    _PART = {"&", "and", "of", "the", "de", "del", "della", "di", "da", "dos", "das",
             "la", "le", "el", "los", "las", "y", "van", "von", "der", "den", "du", "ter"}
    core = [w for w in ws if w.lower() not in _PART]
    if not core or len(core) > 5:
        return False
    return all(_NAMEWORD.match(w.rstrip(",")) for w in core)


# ⚠️ DO NOT add a "this is a Caesar cipher, allow it unchanged" exemption to copy-EN.
# Two detectors were built and BOTH were measured against the real corpus before shipping,
# and both would have let untranslated English pass on hundreds of lines:
#   * caps-only + no common English word  -> matched 382 lines, 380 ALREADY correctly
#     translated ("SPRINT / FREE-RUN", "IL DUOMO'S SECRET", "CORE MEMORY MARKERS")
#   * zero professional reference (the game itself never localized it) -> 1,254, of
#     which 1,234 are already translated
# A handful of Subject-16 cipher lines striking out and parking is the CORRECT outcome;
# a loose exemption would be a fake 100%, which is far worse. Measure any such rule against
# the banked corpus first — if it matches lines that are already translated, it is wrong.
def normalize(s, en=""):
    """Deterministic clean-up of the model's raw output, applied BEFORE the guard.

    🔴 Niqqud must be REMOVED, never rejected. Stripping vowel points is a pure string
    operation with one correct answer — it is not a translation decision — so refusing
    the line instead of fixing it turns a good translation into a strike. Measured on
    the AC2 tail: 46 of 59 logged rejections (78%) were `niqqud` on perfectly fine Ezio
    dialogue, and three strikes then PARKED 78 ordinary lines. Same class as the 429 bug:
    the guard was right that the text was wrong, and wrong about whose fault it was.
    """
    return NIQ.sub("", s).strip()


def why_invalid(new, en, ar=""):
    """The reason `valid` refuses, or '' if it accepts.

    A guard that cannot say WHY it refused is undebuggable from the outside: a whole
    session was spent inferring rejection causes from a bare '+0/1' in the log. Keep
    this in lockstep with valid() — valid() is literally `not why_invalid()`.
    """
    if not new or not new.strip(): return "empty"
    if FOREIGN.search(new): return "foreign-script"
    if NIQ.search(new): return "niqqud"
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)):
        return f"token-mismatch {sorted(STRUCT.findall(en))} -> {sorted(STRUCT.findall(new))}"
    core = STRUCT.sub(" ", en); bare = new.lstrip(_CTRL).strip()
    # 🔴 AN ENGLISH ORDINAL IS CORRECTLY ANSWERED WITH A BARE NUMERAL. Hebrew writes the
    # ordinal as the digits alone (`6th` -> `6`), so the model's answer is RIGHT and the
    # `no-hebrew` rule was rejecting it — three strikes each, a singleton API retry every
    # time, on every pass, in every stream. The merge already fills these deterministically,
    # so the fleet was burning calls to re-derive an answer it was going to overwrite anyway.
    m_ord = re.match(r"^(\d+)(?:st|nd|rd|th)$", en.strip(), re.I)
    if m_ord:
        return "" if bare == m_ord.group(1) else "ordinal-mismatch"
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en.strip() and is_namey(en)): return "no-hebrew"
    if len(en) >= 12 and bare == en.strip() and not is_namey(en): return "copy-EN"
    # 🔴 An INVENTED digit is a hallucination, and it is the one hallucination class a guard
    # can prove. Measured on the first 1,421 banked lines: exactly one ("Inflamed" -> "מודל 13",
    # a horse-coat name answered with "model 13"), i.e. the model occasionally answers a
    # DIFFERENT line. A number the source never had can never be a translation choice, so this
    # is a hard reject, not a repair. Engine tokens are stripped first (~1~ carries its own digits).
    if set(_DIG.findall(STRUCT.sub(" ", new))) - set(_DIG.findall(core)):
        return "invented-number"
    g = gender_conflict(new, ar)
    if g: return g
    return ""


def valid(new, en, ar=""):
    return not why_invalid(new, en, ar)



# ── canonical glossary + the Arabic gender oracle ────────────────────────────────────────────
# Both exist because a fleet turns ONE wrong choice into tens of thousands of lines. The glossary
# is sent PER BATCH (only the terms that actually occur in it, so it is free on lines that need
# none) and re-applied at merge; the gender check turns the Arabic from a hint the model may
# ignore into something the guard can actually verify.
_GLOSS = {}
try:
    _reg = json.load(open(os.path.join(HERE, "name_registry.json"), encoding="utf-8"))
    for _grp in ("characters", "places", "factions", "systems", "gear"):
        # ⚠️ NOT `for _en, _he in ...` — that rebinds the module-level _en() helper to a str
        # and every later call dies with "'str' object is not callable".
        for _term, _heb in (_reg.get(_grp) or {}).items():
            if _term and _heb: _GLOSS[_term] = _heb
except Exception as _e:
    print("[gloss] none:", _e, flush=True)
# longest first so "Dutch van der Linde" wins over "Dutch", "Gold Bars" over "Gold Bar"
_GLOSS_ORDER = sorted(_GLOSS, key=len, reverse=True)


def glossary_for(batch):
    """The canonical terms that occur in THIS batch, as 'English = Hebrew' lines."""
    hay = " ".join(_en(v) for _k, v in batch)
    hit, seen = [], set()
    for t in _GLOSS_ORDER:
        if t in hay and not any(t in s for s in seen):
            hit.append(f"{t} = {_GLOSS[t]}"); seen.add(t)
        if len(hit) >= 24: break
    return hit


# --- Arabic addressee, HIGH PRECISION only (universal/gender_oracle.ar_addressee_strict) ------
# Pronouns + VOCALISED ـكَ/ـكِ + plural only. The generic ت…ين verb heuristic is deliberately NOT
# here: on unvocalised Arabic it false-fires on masdars (تحسين), plurals (تنانين) and object
# suffixes (تسامحني), and a WRONG gender verdict would create exactly the debt this prevents.
_AR_YOU_PL = re.compile(r'(?<![ء-ي])(?:أنتم|انتم|أنتن|انتن|أنتما)(?![ء-ي])')
_AR_YOU_F  = re.compile(r'(?<![ء-ي])(?:أنتِ|إنتِ)(?![ء-ي])')
_AR_YOU_M  = re.compile(r'(?<![ء-ي])(?:أنتَ|إنتَ)(?![ء-ي])')
_AR_KF     = re.compile(r'كِ(?![ء-ي])')      # ـكِ  kasra  = to a woman
_AR_KM     = re.compile(r'كَ(?![ء-ي])')      # ـكَ  fatha  = to a man


def ar_addressee(t):
    if not t: return None
    if _AR_YOU_PL.search(t): return "pl"
    f = bool(_AR_YOU_F.search(t) or _AR_KF.search(t))
    m = bool(_AR_YOU_M.search(t) or _AR_KM.search(t))
    if f and not m: return "f"
    if m and not f: return "m"
    return None


_HE_PL = re.compile(r'(?<![א-ת])את[םן](?![א-ת])')
_HE_M  = re.compile(r'(?<![א-ת])אתה(?![א-ת])')
_HE_F  = re.compile(r'(?<![א-ת])את(?![א-ת])')
# 'את' is ALSO the accusative particle ("קח את זה"), so a bare את only counts as "you-fem"
# when a feminine 2nd-person verb backs it up.
_HE_VF = re.compile(r'(?<![א-ת])(?:צריכה|יכולה|יודעת|מוכנה|חייבת|תוכלי|בואי|קחי|תעשי|'
                    r'לכי|בטוחה|מבינה|שומעת|תגידי|רוצה|עושה|הולכת|נראית)(?![א-ת])')


def he_addressee(t):
    if not t: return None
    if _HE_PL.search(t): return "pl"
    if _HE_M.search(t): return "m"
    if _HE_F.search(t) and _HE_VF.search(t): return "f"
    if _HE_VF.search(t): return "f"
    return None


def gender_conflict(new, ar):
    """'' or the reason — set only when the Arabic is UNAMBIGUOUS and the Hebrew contradicts it."""
    a = ar_addressee(ar)
    if not a: return ""
    h = he_addressee(new)
    if not h or h == a: return ""
    return f"gender {h} vs arabic {a}"


def load_keys():
    keys = []
    raw = os.environ.get("NVIDIA_API_KEYS", "").strip()
    if raw: keys += [k.strip() for k in raw.split(",") if k.strip()]
    v = os.environ.get("NVIDIA_API_KEY", "").strip()
    if v and v not in keys: keys.append(v)
    # 🔴 keys.json is the multi-provider file, and its nim key must ALSO feed this legacy
    # single-provider list. Without it _KEYS is empty, and the moment the fleet call fails
    # (a plain 429) the fallback dies in _pick_key with "min() iterable argument is empty" —
    # an error that MASKS the real provider error and reads like a broken worker.
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


def _one_call(key, sysmsg, usermsg, timeout=180, max_tokens=2500):
    payload = {"model": MODEL, "temperature": 0.2, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": sysmsg},
                            {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload).encode(),
                                 method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout, context=_SSLCTX).read()
                      .decode())["choices"][0]["message"]["content"]


def _parse(txt):
    m = re.search(r'\{.*\}', txt, re.S)
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
        # 🔴 NEVER fall through to the legacy NVIDIA path on a PINNED worker. `_KEYS` holds
        # whatever this machine's key file gave us, so a groq-pinned stream was posting a
        # groq key to integrate.api.nvidia.com and logging `HTTP Error 401: Unauthorized` —
        # a wasted call per failure AND a misleading error that hides the real fleet reason
        # (it looked like a revoked key; all 10 groq keys tested OK/429). Returning {} here
        # is honest: do_batch already treats an empty multi-line reply as "nobody replied".
        if _PIDX >= 0:
            # ...but before giving the batch up, BORROW a provider that still has headroom.
            if _FLEET_ANY is not None:
                try:
                    r = _parse(_FLEET_ANY.complete(sysmsg, usermsg, retries=2,
                                                   timeout=timeout, max_tokens=max_tokens))
                    if r:
                        return r
                except Exception:
                    pass
            return {}
    if not _KEYS:
        # The fleet already tried every configured provider and none answered. There is no
        # legacy NVIDIA key to fall back to, so report "nobody replied" — an empty result is
        # blameless (429/timeout) and must never let the caller strike the lines.
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
    # PER-PID temp name: each provider worker writes only its OWN out_<prov>.json, but a stray
    # duplicate or the pull's scp can hold the file, so a SHARED ".tmp" name let two writers race
    # and one died with WinError 5. A unique temp + a longer backoff makes the replace robust and
    # never leaves a foreign .tmp behind.
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


# --- the New-Era prompt payload: RDR2's panel is one language, and it is the right one -------
def _payload(v):
    """en + every reference language we have for that line.

    The original RDR2 corpus carried a single 'ar'. Unpacking the game's archives gave us
    its OWN 12 professional localizations, so a line now ships with `refs` = up to 7 of
    them -- the same New-Era panel the other games get, instead of English alone.
    """
    if not isinstance(v, dict): return {"en": v or ""}
    p = {"en": v.get("en", "")}
    ar = (v.get("ar") or "").strip()
    if ar: p["ar"] = ar
    for lang, s in (v.get("refs") or {}).items():
        if s: p[lang] = s
    return p


def _tok(v):
    return sum(len(s) for s in _payload(v).values()) // 3 + 8


# A token budget alone is not enough: 28k of these lines are 2-3 word UI labels, so a
# 1800-token batch can hold 90 of them -- and the model must echo 90 ten-character ids
# VERBATIM before it writes a word of Hebrew. Past ~25 ids the omission rate climbs and every
# omitted key costs a separate single-line re-ask, which eats the gain. Cap both.
#   PER PROVIDER, because their limits differ in KIND, not just in degree:
#   * nim  — generous quota, slow per call -> big batches are pure win (24/24 accepted live)
#   * sambanova — mid
#   * groq — a small tokens-per-minute budget, and `max_tokens` counts against it as a
#            RESERVATION. A 24-line batch reserves enough to 429 the key immediately, so the
#            fast provider was contributing the LEAST. Smaller batches keep it under the cap.
MAXLINES = {"groq": 10, "sambanova": 16}.get(_PROV, 20)


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
    # FAIL-FAST timeout: a doomed/throttled call must fail in tens of seconds, not
    # minutes. The old ceiling (300s, base 120s) combined with fleet_providers'
    # old 4-attempt single-key retry to let ONE stuck batch block a whole worker
    # for up to ~20 minutes with zero output - indistinguishable from "dead" on the
    # dashboard. Every provider's real median (~1s groq, ~3s sambanova, ~16s nim)
    # fits comfortably under 90s; a call that needs longer than that is not coming
    # back soon, and fleet_providers now cools the provider down and moves on.
    # 🔴 FAIL FAST. A free-tier call that has not answered in ~a minute is queued behind
    # everything, and the adapter takes up to 5 attempts — at the old 150 s cap ONE doomed
    # batch could hold a stream for 12 minutes. Measured 2026-08-07: nim was banking a single
    # batch per 4 minutes while answering a direct probe in 16 s. Dropping a slow call early
    # and retrying on the NEXT key is strictly better than waiting it out.
    to = min(70, 45 + sum(_tok(v) for _, v in sub) // 20)
    # 🔴 The OUTPUT budget must be derived from the KEYS + the ENGLISH, never from the whole
    # panel: the model writes Hebrew for the English only, but it must echo every id verbatim,
    # and a REASONING model spends its thinking against the same max_tokens (measured on
    # gpt-oss-120b: a 6-line batch truncated at 720 after 2.5 lines, and the missing keys are
    # simply ABSENT from the JSON — which reads as model dropout, not as truncation).
    # 🔴🔴 ON GROQ, `max_tokens` IS ITSELF A RATE-LIMIT COST — it is RESERVED against the
    # tokens-per-minute budget whether or not it is used. Measured on the live key: the same
    # 6-line batch returned 429 at mx=4000, at 12000 and at 16000, while a 200-token "Say OK"
    # answered in 0.4s. So the instinct to "give the reasoning model more room" is exactly
    # backwards here: a bigger reservation buys a faster 429. Keep it tight and let the
    # single-line re-ask handle the rare genuine truncation.
    # (gpt-oss-120b also returns its thinking in a separate `reasoning` field and leaves
    # `content` EMPTY until the reasoning finishes — so a too-small budget yields a valid
    # response with no answer at all, which reads as model dropout.)
    # 🔴🔴 MEASURED 2026-08-07 ON THE LIVE POOL, and it re-decides the constant: a 13-line
    # batch answered **13/13 in 2.0 s at max_tokens=800**, and returned **429 on every key at
    # 1200, 1800, 2500 and 4000**. The reservation is charged against tokens-per-minute whether
    # or not it is used, so a generous ceiling does not buy safety — it buys a guaranteed 429,
    # which surfaces as `step1 empty` and looks exactly like model dropout.
    # Size it to the ANSWER: the ids echoed back (~1 token per 3 chars) plus Hebrew at roughly
    # 1.2 tokens per English character, and cap it low. A genuine truncation is rare and the
    # single-line re-ask already covers it — a 429 covers nothing.
    mx = min(1600, 150 + sum(len(k) for k, _ in sub) // 3
             + int(sum(len(_en(v)) for _, v in sub) * 1.2))
    try:
        s1 = chat(S1, "Translate:\n" + json.dumps({k: _payload(v) for k, v in sub}, ensure_ascii=False),
                  timeout=to, max_tokens=mx)
    except Exception as e:
        # TRANSPORT failure (429 / timeout / HTTP): the provider never answered, so
        # this says NOTHING about the lines. Returning a bare {} made the caller
        # charge every line in the batch a strike, and 3 rate-limited batches in a
        # row permanently parked perfectly ordinary dialogue ("Ha, awesome.",
        # "Ah! There you are. Is it done?"). Report the failure so the caller can
        # tell "the model rejected it" from "nobody replied".
        print(f"  step1 fail ({e}) — skip batch"); return {}, False, set()
    # 🔴 `chat()` SWALLOWS a provider exception and returns a bare {} — so a 429 never reaches
    # the except above and the caller was told `ok=True, answered=0`, i.e. "the model replied
    # and dropped every key". That charges an omit to each line and MAX_OMITS then parks
    # perfectly good content. An empty reply to a MULTI-line batch is never a real answer:
    # treat it as "nobody replied", which is blameless and re-serves the lines.
    if not s1 and len(sub) > 1:
        print(f"  step1 empty ({len(sub)} lines) — treating as no-reply", flush=True)
        return {}, False, set()
    res, seen = {}, set()
    for k, v in sub:
        he = s1.get(k)
        if isinstance(he, dict):
            he = he.get("he") or he.get("hebrew") or he.get("text") or he.get("translation") or ""
        if not isinstance(he, str): continue
        he = normalize(he, _en(v))
        if not he: continue
        # `seen` = the model actually produced a candidate for this key. Only such a key
        # can earn a strike: a key the model silently OMITTED from its JSON is a model
        # dropout, exactly as blameless as a 429, and striking it parked 82 lines of
        # ordinary dialogue ("Access Lorenzo's secret hideout.").
        seen.add(k)
        bad = why_invalid(he, _en(v), (v.get("ar", "") if isinstance(v, dict) else ""))
        if not bad:
            res[k] = he
        elif len(sub) == 1:
            # single-line batches ARE the tail: log exactly why it was refused, so a
            # stuck line is diagnosable from the log instead of by re-deriving it.
            print(f"    REJECT {k} [{bad}] en={_en(v)[:60]!r} he={he[:60]!r}", flush=True)
    return res, True, seen


LOCK = os.path.join(HERE, f"worker{_SUF}.lock")


def _alive(pid):
    """Is a WORKER still running under that pid?

    🔴 A bare "does this pid exist" check is WRONG: Windows recycles pids, so a dead
    worker's pid gets reused by an unrelated process and the lock never goes stale.
    Seen live on vm3 — the lock held pid 3672, which by then was `svchost`, so the nim
    stream could never start again and 1/3 of that machine's capacity was silently
    lost with a perfectly reassuring "another worker is already running" in the log.
    Match the COMMAND LINE too: only another ac2_nim counts.
    """
    try:
        if os.name == "nt":
            import subprocess
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\").CommandLine"],
                capture_output=True, text=True, timeout=20).stdout
            return "rdr2_nim" in (out or "")
        os.kill(pid, 0); return True
    except Exception:
        return False


def acquire_singleton():
    """the task re-launches us every few minutes - never run two copies on one slice."""
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
SKIP = os.path.join(HERE, f"ac2_skip{_SUF}.json")


MAX_OMITS = 5


def _load_skip():
    """Parked keys + per-key failure counts.

    A line the guard rejects MUST leave the queue after MAX_STRIKES. Without a
    park it is re-served on every pass forever and crowds out real work (the
    SM2 lesson). Each key belongs to exactly one (machine, provider) slice
    (md5 % 3), so a per-stream file has no write race.

    `omits` is a SEPARATE counter from `strikes`: a key the model silently
    DROPS from its JSON (never appears in `answered`) can never be struck by
    the reject-path logic below - "answered but rejected" and "never
    answered at all" are different failure modes with the same symptom (the
    key never leaves the queue). Seen live on desktop/nim: a handful of
    lines with a corrupted `~COLOR_...~` reference or a stray U+FFFD in the
    source looped "pass: 3 left" for 100+ passes because the model never
    once produced a candidate for them, so strikes stayed at 0 forever.
    MAX_OMITS gives that chronic case a ceiling too.
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
    # A per-provider shard file OVERRIDES the md5%3 split. The hash split is a FIXED
    # assignment, so the moment one provider is rate-limited its third falls behind while
    # the others finish and exit — measured at 68% of the remaining work stranded on the
    # slowest stream. `fleet_reslice_equal.py` writes corpus_<provider>.json instead.
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
    print(f"RDR2 New-Era worker | slice {len(corpus)} lines | already done {len(out)} | "
          f"parked {len(skip)} | keys {len(_KEYS)}")
    idle = 0
    while True:
        todo = [(k, v) for k, v in corpus.items() if k not in out and k not in skip]
        # A line whose text is 100% engine tokens ("{CUT} {MAILS}") is UNWINNABLE:
        # translating breaks the token multiset (guard 3) and returning it unchanged
        # trips the copy-EN rule (guard 5) — no output can ever pass. Park it in a
        # dedicated list (never fake-bank the English, which would show a false 100%)
        # so it leaves the queue and a later targeted pass can handle it.
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
            # `answered` = the lines for which the provider actually replied. Only
            # those can earn a strike; a 429/timeout is an infrastructure problem
            # and must never park real content.
            answered = set(); ok = False
            try:
                res, ok, answered = do_batch(sub)
                # RECOVERY: the model silently omits ids from its JSON. Those keys are
                # NOT rejections — re-ask each one alone (highest hit-rate) before any
                # strike. This converts pure loss into throughput and is what keeps a
                # blameless line out of the park list.
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
            # Strike a line the provider ANSWERED and the guard still refused; MAX_STRIKES
            # parks it. A line the model NEVER answers (omitted from every JSON, incl. the
            # single-retry) can't be struck this way — that's `omits`, below — since
            # "answered but rejected" and "never answered at all" are different failures
            # that would otherwise both loop forever with the same "pass: N left" symptom.
            parked = 0
            for k, _v in sub:
                if k in res:
                    strikes.pop(k, None); omits.pop(k, None)
                elif k in answered:
                    strikes[k] = strikes.get(k, 0) + 1
                    if strikes[k] >= MAX_STRIKES:
                        skip.add(k); strikes.pop(k, None); parked += 1
                elif ok:
                    # `ok` means the FIRST call to the provider genuinely succeeded (it
                    # replied with parseable JSON) - so an omission here is the model's
                    # own choice, not a transport blip. A batch/retry that never got a
                    # reply at all (ok=False) touches nothing, same as the strike branch.
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
