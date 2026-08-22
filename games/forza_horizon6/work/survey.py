"""Phase-1 survey: every language zip -> table count, entry count, id parity vs EN."""
import os, sys, zipfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import fh6_str as S

ST = r"C:\Games\Forza Horizon 6\media\Stripped\StringTables"


def load(lang):
    """{table: {IDS: value}} + the raw per-table byte blobs we could parse."""
    z = zipfile.ZipFile(os.path.join(ST, lang + ".zip"))
    out, broken = {}, []
    for i in z.infolist():
        if not S.is_table(i.filename):
            continue
        try:
            raw = z.read(i.filename)
        except Exception:
            broken.append(i.filename)
            continue
        out[i.filename] = S.parse(raw).as_dict()
    return out, broken


if __name__ == "__main__":
    langs = sorted(f[:-4] for f in os.listdir(ST) if f.endswith(".zip"))
    en, enbroken = load("EN")
    en_ids = {(t, k) for t, d in en.items() for k in d}
    print(f"EN: {len(en)} tables, {sum(len(d) for d in en.values())} entries, "
          f"{len(en_ids)} (table,id) pairs, broken={enbroken}")
    rows = []
    for L in langs:
        d, broken = load(L)
        ids = {(t, k) for t, dd in d.items() for k in dd}
        same = len(ids & en_ids)
        diff = sum(1 for t, k in (ids & en_ids) if d[t][k] != en[t][k])
        rows.append((L, len(d), len(ids), same, 100.0 * same / len(en_ids), diff, broken))
    print(f"\n{'lang':5s} {'tables':>6s} {'ids':>7s} {'shared':>7s} {'parity%':>8s} {'differs':>8s}  broken")
    for L, nt, ni, s, p, dif, br in rows:
        print(f"{L:5s} {nt:6d} {ni:7d} {s:7d} {p:8.2f} {dif:8d}  {','.join(br)}")
    json.dump({L: {"tables": nt, "ids": ni, "shared": s, "parity": p, "differs": dif}
               for L, nt, ni, s, p, dif, _ in rows},
              open(os.path.join(os.path.dirname(__file__), "..", "extract", "lang_survey.json"),
                   "w", encoding="utf-8"), indent=1)
