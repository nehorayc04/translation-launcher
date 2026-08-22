"""FH6 Phase-1 scope report — built from the hash-VERIFIED-pristine EN.zip.

Reports the three numbers the playbook demands (records / per-table uniques /
GLOBAL uniques), the token inventory, the length distribution, and a
UI-vs-subtitle split derived from the engine's OWN table names.
"""
import os, sys, re, json, zipfile, collections

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import fh6_str as S

ST = r"C:\Games\Forza Horizon 6\media\Stripped\StringTables"
OUT = os.path.join(os.path.dirname(__file__), "..", "extract")

# --- engine tokens that MUST survive a translation verbatim -----------------
TOKENS = [
    ("{n}",        re.compile(r"\{\d+\}")),                 # positional
    ("{Name}",     re.compile(r"\{[A-Za-z_][^}]*\}")),      # named / formatted
    ("[TOKEN]",    re.compile(r"\[[^\]\s]+\]")),
    ("<tag>",      re.compile(r"<[^>]+>")),
    ("printf",     re.compile(r"%[-+ #0]*[\d.*]*(?:hh|h|ll|l|L|z|j|t)?[diouxXeEfgGaAcspn%]")),
    ("&entity;",   re.compile(r"&[A-Za-z#0-9]+;")),
    ("\\n",        re.compile(r"\\n")),
    ("newline",    re.compile(r"\n")),
]

HEB = re.compile(r"[\u0590-\u05FF]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def load(lang):
    z = zipfile.ZipFile(os.path.join(ST, lang + ".zip"))
    out = {}
    for i in z.infolist():
        if not S.is_table(i.filename):
            continue
        out[i.filename[:-4]] = S.parse(z.read(i.filename)).as_dict()
    return out


def main():
    en = load("EN")
    records = sum(len(d) for d in en.values())
    per_table_uniq = sum(len(set(d.values())) for d in en.values())
    allvals = [v for d in en.values() for v in d.values()]
    global_uniq = len(set(allvals))

    print("=" * 74)
    print("FORZA HORIZON 6 — EN string tables (xxh128-verified pristine)")
    print("=" * 74)
    print(f"  tables                     {len(en):>10,}")
    print(f"  records (table,id)         {records:>10,}")
    print(f"  per-table unique values    {per_table_uniq:>10,}")
    print(f"  GLOBAL unique values       {global_uniq:>10,}   <-- the real workload")
    chars = sum(len(v) for v in set(allvals))
    print(f"  chars (global unique)      {chars:>10,}")

    # translatable filter: must contain a real word once tokens are stripped
    strip = re.compile(r"<[^>]+>|\{[^}]*\}|\[[^\]\s]+\]|%[\d.*]*[a-zA-Z]|&[A-Za-z#0-9]+;|\\n")
    junk = 0
    real = set()
    for v in set(allvals):
        core = strip.sub(" ", v)
        if LATIN_WORD.search(core):
            real.add(v)
        else:
            junk += 1
    print(f"  ...of which real prose     {len(real):>10,}   (dropped {junk:,} token/number/code-only)")

    # --- length distribution ------------------------------------------------
    L = sorted(len(v) for v in real)
    def pct(p):
        return L[int(len(L) * p)] if L else 0
    print(f"\n  length  median {pct(.5)}  p90 {pct(.9)}  p99 {pct(.99)}  max {L[-1] if L else 0}")
    buckets = collections.Counter()
    for n in L:
        buckets["<=25" if n <= 25 else "26-140" if n <= 140 else ">140"] += 1
    for k in ("<=25", "26-140", ">140"):
        print(f"    {k:>7s} {buckets[k]:>8,}")

    # --- token inventory ----------------------------------------------------
    print("\n  tokens (occurrences / distinct / strings affected)")
    for name, rx in TOKENS:
        occ = distinct = collections.Counter()
        occ = 0
        dis = collections.Counter()
        aff = 0
        for v in real:
            m = rx.findall(v)
            if m:
                occ += len(m)
                aff += 1
                dis.update(m)
        print(f"    {name:<10s} {occ:>8,} / {len(dis):>6,} / {aff:>7,}   e.g. "
              + ", ".join(repr(x) for x, _ in dis.most_common(4)))

    # --- surface split by TABLE NAME (the engine's own grouping) ------------
    SUBT = ("Dialogue", "Subtitle", "VO", "Anna", "Campaign", "Cutscene",
            "Narrative", "Story", "Radio", "DJ")
    groups = collections.Counter()
    tbl_sizes = []
    for t, d in en.items():
        n = len(set(d.values()) & real)
        tbl_sizes.append((n, t))
        g = "dialogue/VO" if any(s.lower() in t.lower() for s in SUBT) else "UI / content"
        groups[g] += n
    print("\n  surface split (by table name)")
    for k, v in groups.most_common():
        print(f"    {k:<14s} {v:>8,}")

    print("\n  biggest tables")
    for n, t in sorted(tbl_sizes, reverse=True)[:15]:
        print(f"    {t:<45s} {n:>7,}")

    os.makedirs(OUT, exist_ok=True)
    json.dump({t: d for t, d in en.items()},
              open(os.path.join(OUT, "en.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print(f"\n  -> extract/en.json written ({records:,} records)")


if __name__ == "__main__":
    main()
