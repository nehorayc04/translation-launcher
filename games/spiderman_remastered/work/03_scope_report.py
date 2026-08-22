"""MSMR — Playbook Stage-7 SCOPE REPORT for the English source (+ the chosen
hijack slot). READ-ONLY.

Reports, for the ENGLISH variant:
  * the THREE numbers the playbook demands:
      1. total RECORDS          (entry_count — key/value pairs)
      2. per-file UNIQUE values (distinct value strings inside this loc file)
      3. GLOBAL unique English  (MSMR ships ONE localization file per language,
                                 so #2 == #3 — stated explicitly, not assumed)
  * total character count + length histogram (<=25 / 26-140 / >140)
  * full token inventory (occurrences + distinct) for
      <tag>  {VALUE}  [TOKEN]  %printf  &entity;  \\n  and the <ts=...> timing marker
  * the UI vs SUBTITLE split derived from the ENGINE'S OWN METADATA:
      - a value carrying the Insomniac <ts="a;b"> VO timing marker  -> SUBTITLE
      - a key whose first token is one of the 544 speaker codes declared in the
        game's own NAME_SUBTITLE_<CODE> table                        -> SUBTITLE
      - CREDITS_* prefix                                             -> CREDITS
      - everything else                                              -> UI
    NO length heuristic is used for the UI/subtitle routing.
  * the language-invariant tail (entries whose value is byte-identical in EVERY
    one of the 20 translated languages) = strings that are NOT translatable.
"""
import os, sys, re, json, struct
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOCS = os.path.join(ROOT, "games", "spiderman_remastered", "extract", "loc_variants")
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import msmr_loc

EN_FILE = "variant_00_idx207368.localization"   # slot 0 / span 0 (see 02c)
UK_FILE = "variant_17_idx683222.localization"   # slot 19 / span 152 (UK English)

fns = sorted(f for f in os.listdir(LOCS) if f.endswith(".localization"))
EN = msmr_loc.Loc(os.path.join(LOCS, EN_FILE))
pairs = EN.pairs()
N = EN.n
keys = [k for k, _ in pairs]
vals = [v for _, v in pairs]

print("=" * 80)
print(f"MSMR SCOPE REPORT — source = {EN_FILE} (slot 0, span 0, ENGLISH)")
print("=" * 80)

# ------------------------------------------------------------------ 3 numbers
uniq_vals = set(vals)
uniq_nonempty = {v for v in uniq_vals if v.strip()}
print("\n--- THE THREE NUMBERS ---")
print(f"  1. total RECORDS (entry_count)            = {N:,}")
print(f"  2. per-file UNIQUE value strings          = {len(uniq_vals):,}"
      f"   ({len(uniq_nonempty):,} non-empty)")
print(f"  3. GLOBAL unique English strings          = {len(uniq_vals):,}")
print( "     ^ MSMR ships exactly ONE localization asset per language "
       "(localization/localization_all.localization),")
print( "       so there is no cross-file duplication: per-file uniques == global uniques.")
print(f"  duplicate ratio: {N - len(uniq_vals):,} records reuse an existing string "
      f"({100*(N-len(uniq_vals))/N:.1f}%)")

# ------------------------------------------------------------------ chars/len
chars = sum(len(v) for v in vals)
uchars = sum(len(v) for v in uniq_vals)
print("\n--- CHARACTERS ---")
print(f"  total chars over all {N:,} records          = {chars:,}")
print(f"  total chars over {len(uniq_vals):,} unique strings = {uchars:,}")

def histo(seq, label):
    a = sum(1 for v in seq if len(v) <= 25)
    b = sum(1 for v in seq if 25 < len(v) <= 140)
    c = sum(1 for v in seq if len(v) > 140)
    t = max(1, len(seq))
    ln = sorted(len(v) for v in seq)
    med = ln[len(ln) // 2] if ln else 0
    p90 = ln[int(len(ln) * 0.9)] if ln else 0
    print(f"  {label}: <=25 {a:,} ({100*a/t:.1f}%) | 26-140 {b:,} ({100*b/t:.1f}%) | "
          f">140 {c:,} ({100*c/t:.1f}%)   median={med} p90={p90} max={ln[-1] if ln else 0}")

print("\n--- LENGTH HISTOGRAM ---")
histo(vals, "by RECORD ")
histo(sorted(uniq_vals), "by UNIQUE ")

# ------------------------------------------------------------------ tokens
print("\n--- TOKEN INVENTORY (over all records) ---")
PATS = [
    ("<ts=...>  VO timing marker", re.compile(r"<ts=[^>]*>")),
    ("<span ...>                ", re.compile(r"<span[^>]*>")),
    ("</span>                   ", re.compile(r"</span>")),
    ("<br> / <br/>              ", re.compile(r"<br\s*/?>")),
    ("ANY <tag>                 ", re.compile(r"<[^<>]+>")),
    ("{VALUE}                   ", re.compile(r"\{[^{}]*\}")),
    ("[TOKEN]                   ", re.compile(r"\[[^\[\]]*\]")),
    ("%printf spec              ", re.compile(r"%[-+ #0-9.]*[a-zA-Z%]")),
    ("&entity;                  ", re.compile(r"&[A-Za-z#0-9]{1,8};")),
    ("literal backslash-n       ", re.compile(r"\\n")),
    ("real newline 0x0A         ", re.compile(r"\n")),
    ("real tab 0x09             ", re.compile(r"\t")),
]
tok_report = {}
for name, rx in PATS:
    occ, dis, lines = 0, Counter(), 0
    for v in vals:
        m = rx.findall(v)
        if m:
            occ += len(m); lines += 1
            for x in m:
                dis[x] += 1
    tok_report[name.strip()] = dict(occurrences=occ, distinct=len(dis), records=lines,
                                    top=dis.most_common(6))
    print(f"  {name}  occ={occ:>7}  distinct={len(dis):>6}  in {lines:>6} records")

print("\n  most common distinct forms:")
for name, rx in PATS:
    d = tok_report[name.strip()]
    if d["occurrences"] and name.strip() not in ("real newline 0x0A", "real tab 0x09"):
        print(f"    {name.strip():28} {[t for t, _ in d['top'][:5]]}")

print("\n  sample values carrying a <ts=...> marker:")
shown = 0
for k, v in pairs:
    if "<ts=" in v and 40 < len(v) < 150:
        print(f"    {k:22} {v!r}")
        shown += 1
        if shown >= 3:
            break

# ------------------------------------------------------------------ UI/SUBS
speakers = {k[len("NAME_SUBTITLE_"):]: v for k, v in pairs
            if k.startswith("NAME_SUBTITLE_") and v.strip()}
SPEAKER_CODES = set(speakers)
TS = re.compile(r"<ts\s*=")
MARKUP = re.compile(r"<[^<>]+>|\{[^{}]*\}|\[[^\[\]]*\]|&[A-Za-z#0-9]{1,8};|%[-+ #0-9.]*[a-zA-Z%]|\\n")
WORDY = re.compile(r"[A-Za-zÀ-ɏ]")

def first_tok(k):
    return k.split("_", 1)[0].upper()

def classify(k, v):
    vis = MARKUP.sub("", v).strip()
    if not vis or not WORDY.search(vis):
        return "skip"                                # empty / pure markup / numbers
    if TS.search(v):
        return "subtitle"                            # engine's own VO timing marker
    ft = first_tok(k)
    if ft == "CREDITS":
        return "credits"
    if ft in SPEAKER_CODES:
        return "subtitle"                            # key owned by a declared speaker
    if k.startswith("NAME_SUBTITLE_"):
        return "ui"                                  # the speaker-name table itself
    return "ui"

buckets = Counter()
bpref = defaultdict(Counter)
bchars = Counter()
buniq = defaultdict(set)
for k, v in pairs:
    c = classify(k, v)
    buckets[c] += 1
    bpref[c][first_tok(k)] += 1
    bchars[c] += len(v)
    buniq[c].add(v)

print("\n" + "=" * 80)
print("UI vs SUBTITLE SPLIT — from the ENGINE'S OWN METADATA (no length heuristic)")
print("=" * 80)
print(f"  discriminators used:")
print(f"    * <ts=...> VO timing marker present in {sum(1 for v in vals if TS.search(v)):,} values")
print(f"    * {len(SPEAKER_CODES)} speaker codes declared by the game in NAME_SUBTITLE_<CODE>")
print(f"    * CREDITS_ key prefix")
print()
for b in ("ui", "subtitle", "credits", "skip"):
    print(f"  {b:9} records={buckets[b]:>7} ({100*buckets[b]/N:5.1f}%)  "
          f"unique={len(buniq[b]):>7}  chars={bchars[b]:>9,}")
transl = buckets["ui"] + buckets["subtitle"] + buckets["credits"]
tuniq = len(buniq["ui"] | buniq["subtitle"] | buniq["credits"])
print(f"\n  TRANSLATABLE (ui+subtitle+credits) records={transl:,}  unique={tuniq:,}")
print(f"  SKIP                                records={buckets['skip']:,}")

print("\n  top key prefixes per bucket:")
for b in ("ui", "subtitle", "credits", "skip"):
    print(f"    {b:9} " + ", ".join(f"{p}({c})" for p, c in bpref[b].most_common(12)))

print("\n  length histogram per bucket (records):")
for b in ("ui", "subtitle", "credits"):
    histo([v for k, v in pairs if classify(k, v) == b], f"  {b:9}")

# ------------------------------------------------------------------ invariant
print("\n" + "=" * 80)
print("LANGUAGE-INVARIANT TAIL (value byte-identical in EVERY translated language)")
print("=" * 80)
others = [msmr_loc.Loc(os.path.join(LOCS, f)) for f in fns
          if f not in (EN_FILE, UK_FILE, "variant_01_idx239528.localization")]
print(f"  comparing English against {len(others)} translated variants ...", flush=True)
ovals = []
for L in others:
    vb = L.seg(msmr_loc.T_VALUES)
    vo = struct.unpack(f"<{N}I", L.seg(msmr_loc.T_VAL_OFFS))
    cur = []
    for o in vo:
        e = vb.find(b"\x00", o)
        cur.append(vb[o: e if e >= 0 else len(vb)])
    ovals.append(cur)
env = [v.encode("utf-8") for v in vals]
invariant = [i for i in range(N) if all(ov[i] == env[i] for ov in ovals)]
inv_set = set(invariant)
print(f"  entries identical in ALL {len(others)} translated languages: {len(invariant):,} "
      f"({100*len(invariant)/N:.1f}%)")
inv_b = Counter(classify(keys[i], vals[i]) for i in invariant)
print(f"  of those, by bucket: " + ", ".join(f"{k}={v}" for k, v in inv_b.items()))
print("  20 samples (these are effectively NOT translatable content):")
shown = 0
for i in invariant:
    if vals[i].strip() and shown < 20:
        print(f"    {keys[i][:36]:36} = {vals[i][:60]!r}")
        shown += 1

real = [i for i in range(N) if i not in inv_set and classify(keys[i], vals[i]) != "skip"]
real_u = {vals[i] for i in real}
print(f"\n  ==> REAL translatable records (translatable AND not language-invariant) "
      f"= {len(real):,}")
print(f"  ==> REAL translatable UNIQUE strings                                    "
      f"= {len(real_u):,}")
print(f"  ==> characters in those unique strings                                  "
      f"= {sum(len(v) for v in real_u):,}")
rb = Counter(classify(keys[i], vals[i]) for i in real)
print(f"      split: " + ", ".join(f"{k}={v:,}" for k, v in rb.most_common()))

# ------------------------------------------------------------------ UK slot
print("\n" + "=" * 80)
print("HIJACK-SLOT DATA (there is NO Arabic text slot — see 02b)")
print("=" * 80)
UK = msmr_loc.Loc(os.path.join(LOCS, UK_FILE))
ukv = [v for _, v in UK.pairs()]
diff = sum(1 for a, b in zip(ukv, vals) if a != b)
print(f"  slot 0/1  (span 0 / 8)   ENGLISH (US)  — byte-identical to each other")
print(f"  slot 19   (span 152)     ENGLISH (UK)  — differs from US in {diff:,}/{N:,} "
      f"records ({100*diff/N:.1f}%)")
print( "  => the same near-duplicate-English pattern as Forza Horizon 6: hijacking the")
print( "     DEFAULT English slot costs the user ZERO actions, and the UK slot remains a")
print( "     ~87%-identical complete English escape hatch.")

out = os.path.join(LOCS, "_scope.json")
json.dump(dict(
    source=EN_FILE, records=N, unique_values=len(uniq_vals),
    chars_records=chars, chars_unique=uchars,
    buckets={b: dict(records=buckets[b], unique=len(buniq[b]), chars=bchars[b])
             for b in ("ui", "subtitle", "credits", "skip")},
    translatable_records=transl, translatable_unique=tuniq,
    language_invariant=len(invariant),
    real_translatable_records=len(real), real_translatable_unique=len(real_u),
    tokens=tok_report, speaker_codes=len(SPEAKER_CODES),
    uk_diff_records=diff,
), open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n[+] wrote {out}")
