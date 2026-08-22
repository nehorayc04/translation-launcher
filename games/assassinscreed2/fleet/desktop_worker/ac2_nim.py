"""Assassin's Creed II NIM translator — New-Era: every shipped language is the oracle.

Same fleet mechanism as the Witcher 3 / Plague Tale workers (per-source-IP NIM quota, resumable
via out.json, a disjoint corpus.json slice), adapted for AC2:
  * game = Renaissance Italy 1476-1499 (Firenze, Venezia, Monteriggioni, Forli, Roma) — Ezio
    Auditore da Firenze, the Assassins vs the Templars, Leonardo da Vinci, the Pazzi and Borgia.
    Register: period-flavoured but natural modern Hebrew; the Animus/Abstergo frame is sci-fi.
  * NEW ERA — English drops gender/number/register, so each line carries 'refs': the SAME line as
    professionally localized into up to 9 shipped languages. Use them by STRENGTH:
      pl  (Polish)      -> speaker AND addressee gender (past tense -l / -la, adjectives)
      it/es/fr          -> referent + addressee gender (-o/-a), and formal vs familiar address
      de                -> register (du/Sie) and noun gender
      nl/da/no/sv       -> number + definiteness cross-check
    >=2 languages agreeing wins; never translate FROM a ref, only read the grammar off it.
  * tokens preserved VERBATIM: <br> / <BR> line breaks, <font ...> spans, [A] [B] [X] [Y] [LS] [RT]
    button glyphs, [beat] [LAUGH] audio cues, {CUT} {TBD} markers, printf %d %i %s %ls.
  * store LOGICAL Hebrew here; the RTL VISUAL transform happens at BUILD time in
    games/assassinscreed2/work/, NEVER in the worker.

Put the NVIDIA key in key.txt (nvapi-... line) or NVIDIA_API_KEY. Run: python ac2_nim.py
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
BUDGET = 150
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, f"out{_SUF}.json")

# --- multi-provider fleet (Groq + SambaNova + NIM). FLEET_PROVIDER pins one provider
#     (3 parallel workers per machine); unset = round-robin. Falls back to NIM-only if
#     keys.json / fleet_providers.py are absent, so an un-migrated stream still runs. ---
_FLEET = None
try:
    sys.path.insert(0, HERE)
    import fleet_providers as _fp
    _FLEET = _fp.Fleet(_fp.load_keys(HERE), only=(_PROV if _PIDX >= 0 else None))
    print(f"[fleet] {'PINNED ' + _PROV if _PIDX >= 0 else 'round-robin'}: "
          f"{_FLEET.provider_names()} -> {os.path.basename(OUT)}", flush=True)
except Exception as _e:
    print("[fleet] single-NIM fallback:", _e, flush=True)

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힯Ѐ-ӿ]')
NIQ = re.compile(r'[֑-ֽֿׁׂ]')
HEB = re.compile(r'[֐-׿]')
# AC2 tokens: markup spans, bracket button/audio cues, brace markers, printf specs.
#
# NOT every [bracket] is an engine token. AC2's script uses the SAME syntax for two
# completely different things:
#   ENGINE TOKEN  - a controller/nav button or an audio cue: [X] [Y] [LS] [RT] [Start]
#                   [Back] [LAUGH]. Must survive verbatim or the prompt breaks in-game.
#   TRANSLATOR PROSE - a stage direction or the English gloss of an Italian line:
#                   [sigh] [realizing] [sound of pain] [Whores!] [Home sweet home.]
#                   [A hand drawn map of Cyprus.]  -> this is TEXT THE PLAYER READS and
#                   it must become Hebrew.
# Comparing the second class verbatim made the guard reject every faithful translation
# of those lines, so 38 real dialogue/codex lines were struck out and parked as if they
# were untranslatable. Measured over the whole corpus the split is clean: 685 token
# occurrences (64 distinct, all buttons/cues) vs 111 prose occurrences (94 distinct,
# zero buttons). So: a bracket is a TOKEN only when its content is a single
# Capitalised/CamelCase word or an ALL-CAPS cue; anything else is prose.
_BR_TOKEN = r'\[(?:[A-Z][A-Za-z0-9_]*|[A-Z0-9][A-Z0-9 _\-]*)\]'
STRUCT = re.compile(r'<[^>]+>|\{[^}]*\}|' + _BR_TOKEN + r'|%%|%[#0-9.*\-+]*[a-zA-Z]+')
# Prose brackets are free to translate, but their COUNT must survive: a gloss dropped
# instead of translated ("Puttane! [Whores!]" -> "פוטאנה!") silently loses content.
_BR_ANY = re.compile(r'\[[^\]]*\]')

def _prose_brackets(s):
    return len(_BR_ANY.findall(s)) - len(re.findall(_BR_TOKEN, s))
LOWER = re.compile(r'[a-z]{2,}')
# ®/™/© belong to a PRODUCT NAME ("Assassin's Creed® II"), which must stay Latin. Without
# them here is_namey() fails, the copy-EN/no-Hebrew rule fires, and the only correct output
# (the title unchanged) is rejected forever — 7 title lines were stuck on exactly this.
# NOTE the CURLY apostrophe U+2019: the game's own product titles are typeset
# ("ASSASSIN’S CREED® II"), and omitting it made is_namey() refuse the only correct
# output for those lines — the title unchanged — as copy-EN, forever.
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'’/®™©]*$")
_CTRL = "".join(chr(c) for c in range(0x20))

S1 = ("You are a senior Hebrew localizer for Assassin's Creed II — Renaissance Italy, 1476-1499 "
      "(Firenze, Venezia, Monteriggioni, Forli, Roma): Ezio Auditore da Firenze, the Assassins "
      "against the Templars, Leonardo da Vinci, the Pazzi and the Borgia; framed by the modern-day "
      "Animus/Abstergo sci-fi story. Write natural, fluent Hebrew — period-flavoured for the "
      "historical scenes, plain modern Hebrew for the Animus/menu text. "
      "Each input line has 'en' = the English MEANING to translate, and 'refs' = THE SAME line "
      "already professionally localized into other languages. Translate the MEANING from 'en'. "
      "Use 'refs' ONLY as the GENDER / NUMBER / REGISTER oracle, because English hides what Hebrew "
      "must state. Read them by strength: 'pl' (Polish) shows the SPEAKER's and the ADDRESSEE's "
      "gender in past-tense verbs and adjectives; 'it', 'es', 'fr' show the referent's and the "
      "addressee's gender (-o/-a endings) and whether the address is formal or familiar; 'de' shows "
      "register (du/Sie) and noun gender; 'nl','da','no','sv' confirm singular vs plural. When two "
      "or more refs agree, follow them: a line spoken TO a woman gets את and feminine verbs, to a "
      "man אתה, to a group אתם. Do NOT translate FROM any ref and do NOT copy foreign words — 'en' "
      "is the meaning, refs are only grammar hints. "
      "Keep every token VERBATIM from the English, same count and positions: <br> and <BR> line "
      "breaks, <font ...> spans, [A] [B] [X] [Y] [LS] [RT] and other bracket button glyphs, "
      "[beat] [LAUGH] audio cues, {CUT} {TBD} markers, and printf specs %d %i %s %ls. "
      "No niqqud. Proper names (Ezio, Altair, Desmond, Leonardo, Firenze, Venezia, Monteriggioni, "
      "Borgia, Pazzi) use their accepted Hebrew transliteration; brand/code tokens stay Latin. "
      # The single biggest cause of a rejected line in the tail: AC2 writes an Italian line
      # followed by its English gloss in brackets, and the model MERGES them into one Hebrew
      # sentence, dropping the bracket. Keep the shape — the game displays both.
      "SHAPE RULE — when the line is a foreign phrase followed by a bracketed English gloss "
      "('Portatemi la sua testa! [Bring me his head!]', 'canaglia [scoundrel]'), KEEP the "
      "foreign phrase EXACTLY as it is and translate ONLY the text inside the brackets, keeping "
      "the brackets: 'Portatemi la sua testa! [הביאו לי את ראשו!]'. Never merge the two into one "
      "sentence and never drop a bracket — the bracket count must match the English exactly. "
      # Subject-16 puzzle text is a Caesar cipher; 'translating' it destroys the puzzle.
      "If a line is unreadable ALL-CAPS gibberish (a cipher, e.g. 'M LEZI XLI ERWAIV RSA'), "
      "return it COMPLETELY UNCHANGED. "
      "Output JSON {id: hebrew} only, with exactly the same ids as the input.")


def _en(v):
    return v.get("en", "") if isinstance(v, dict) else (v or "")


def is_namey(en):
    en = (en or "").strip(); ws = en.split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)


# ⚠️ DO NOT add a "this is a Caesar cipher, allow it unchanged" exemption to copy-EN.
# Two detectors were built and BOTH were measured against the real corpus before shipping,
# and both would have let untranslated English pass on hundreds of lines:
#   * caps-only + no common English word  -> matched 382 lines, 380 ALREADY correctly
#     translated ("SPRINT / FREE-RUN", "IL DUOMO'S SECRET", "CORE MEMORY MARKERS")
#   * zero professional refs (the game itself never localized it) -> matched 1,254, of
#     which 1,234 are already translated
# A handful of Subject-16 cipher lines striking out and parking is the CORRECT outcome;
# a loose exemption would be a fake 100%, which is far worse. Measure any such rule against
# the banked corpus first — if it matches lines that are already translated, it is wrong.
def _restore_bracket_tokens(new, en):
    """Put back an ENGINE-TOKEN bracket the model translated. Deterministic repair, not a guard.

    The corpus convention is 100% consistent across every banked line: an audio/stage cue or a
    one-word English gloss written as a Capitalised bracket ([Laugh] [Laughs] [Sigh] [Gasp]
    [Good] [Sir]) stays LATIN — 15 banked lines, no exceptions. The model nevertheless keeps
    translating it ('[Laughs]' -> '[צוחק]'), which trips token-mismatch and, after 3 strikes,
    PARKS a perfectly good translation of the whole sentence. That is the niqqud mistake again
    (SILENT-FAILURE CLASS #5): the guard was right that the text was wrong and wrong about whose
    fault it was. Restoring the token is a pure string operation with exactly one correct answer.

    Positional restore, and ONLY when the bracket COUNT matches — then the mapping is unambiguous.
    A dropped or invented bracket is a REAL structural failure and must still reach the guard.
    Never touches a PROSE bracket (an English gloss like "[It's nothing!]"), which must be Hebrew.
    """
    en_br = _BR_ANY.findall(en)
    if not en_br: return new
    new_br = _BR_ANY.findall(new)
    if len(new_br) != len(en_br) or new_br == en_br: return new
    i = 0
    def _swap(mm):
        nonlocal i
        e = en_br[i]; i += 1
        return e if re.fullmatch(_BR_TOKEN, e) else mm.group(0)
    return _BR_ANY.sub(_swap, new)


def normalize(s, en=""):
    """Deterministic clean-up of the model's raw output, applied BEFORE the guard.

    🔴 Niqqud must be REMOVED, never rejected. Stripping vowel points is a pure string
    operation with one correct answer — it is not a translation decision — so refusing
    the line instead of fixing it turns a good translation into a strike. Measured on
    the AC2 tail: 46 of 59 logged rejections (78%) were `niqqud` on perfectly fine Ezio
    dialogue, and three strikes then PARKED 78 ordinary lines. Same class as the 429 bug:
    the guard was right that the text was wrong, and wrong about whose fault it was.
    """
    s = NIQ.sub("", s).strip()
    return _restore_bracket_tokens(s, en) if en else s


def why_invalid(new, en):
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
    if _prose_brackets(new) != _prose_brackets(en):
        return f"prose-bracket-count {_prose_brackets(en)} -> {_prose_brackets(new)}"
    core = STRUCT.sub(" ", en); bare = new.lstrip(_CTRL).strip()
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en.strip() and is_namey(en)): return "no-hebrew"
    if len(en) >= 12 and bare == en.strip() and not is_namey(en): return "copy-EN"
    return ""


def valid(new, en):
    return not why_invalid(new, en)


def load_keys():
    keys = []
    raw = os.environ.get("NVIDIA_API_KEYS", "").strip()
    if raw: keys += [k.strip() for k in raw.split(",") if k.strip()]
    v = os.environ.get("NVIDIA_API_KEY", "").strip()
    if v and v not in keys: keys.append(v)
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
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    for _ in range(12):
        try:
            os.replace(tmp, path); return
        except PermissionError:
            time.sleep(0.3)
    os.replace(tmp, path)


# --- the New-Era prompt payload: send the refs ordered by oracle strength, capped -------------
REF_ORDER = ["pl", "it", "es", "fr", "de", "nl", "da", "no", "sv"]
MAX_REFS = 4


def _payload(v):
    if not isinstance(v, dict): return {"en": v or ""}
    refs = v.get("refs") or {}
    keep = {}
    for c in REF_ORDER:
        if c in refs and refs[c]:
            keep[c] = refs[c]
            if len(keep) >= MAX_REFS: break
    return {"en": v.get("en", ""), "refs": keep} if keep else {"en": v.get("en", "")}


def _tok(v):
    p = _payload(v)
    return (len(p["en"]) + sum(len(x) for x in p.get("refs", {}).values())) // 3 + 8


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
    to = min(300, 120 + sum(_tok(v) for _, v in sub) // 8)
    mx = min(2500, sum(_tok(v) for _, v in sub) * 2 + 120)
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
        bad = why_invalid(he, _en(v))
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
            return "ac2_nim" in (out or "")
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


def _load_skip():
    """Parked keys + per-key failure counts.

    A line the guard rejects MUST leave the queue after MAX_STRIKES. Without a
    park it is re-served on every pass forever and crowds out real work (the
    SM2 lesson). Each key belongs to exactly one (machine, provider) slice
    (md5 % 3), so a per-stream file has no write race.
    """
    try:
        d = json.load(open(SKIP, encoding="utf-8"))
        return set(d.get("skip", [])), dict(d.get("strikes", {})), list(d.get("token_only", []))
    except Exception:
        return set(), {}, []


def _save_skip(skip, strikes, token_only=None):
    """Never let bookkeeping kill the run — a failed save just costs a re-try later."""
    try:
        d = {"skip": sorted(skip), "strikes": strikes}
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
    if not os.path.exists(CORPUS):
        print(f"[X] corpus.json not found ({CORPUS})."); return
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    if _PIDX >= 0:
        import hashlib
        corpus = {k: v for k, v in corpus.items()
                  if int(hashlib.md5(k.encode()).hexdigest(), 16) % 3 == _PIDX}
        print(f"[fleet] pinned 1/3 slice: {len(corpus)} lines for {_PROV}", flush=True)
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    skip, strikes, _parked_tokonly = _load_skip()
    print(f"AC2 New-Era worker | slice {len(corpus)} lines | already done {len(out)} | "
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
            skip.update(tokonly); _save_skip(skip, strikes, tokonly)
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
            answered = set()
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
            # Strike only a line the provider ANSWERED and the guard still refused
            # (or that the model silently dropped from its JSON). At MAX_STRIKES it
            # is parked so the queue can move on instead of re-serving it forever.
            parked = 0
            for k, _v in sub:
                if k in res:
                    strikes.pop(k, None)
                elif k in answered:
                    strikes[k] = strikes.get(k, 0) + 1
                    if strikes[k] >= MAX_STRIKES:
                        skip.add(k); strikes.pop(k, None); parked += 1
            _save_skip(skip, strikes)
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
