"""For each of the 31 variant blobs:
  - strip 36-byte header
  - parse as DAT1
  - pull section 0x70A382B8 (Values = translated strings, NULL-separated)
  - classify the language by Unicode-script ratio of the values
Prints a table that should make Arabic obvious."""
import os, sys, io, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))

import dat1lib, dat1lib.types.dat1

LOCS = os.path.join(ROOT, "games", "spiderman2", "extracted", "loc_variants")
fns = sorted(os.listdir(LOCS))

def classify(text_blob: bytes):
    """Decode + bucket characters by Unicode block."""
    try:
        s = text_blob.decode("utf-8", "ignore")
    except Exception:
        return {}
    buckets = {"latin": 0, "latin_ext": 0, "cyrillic": 0, "greek": 0,
               "arabic": 0, "hebrew": 0, "thai": 0, "devanagari": 0,
               "cjk": 0, "hiragana": 0, "katakana": 0, "hangul": 0,
               "ascii_printable": 0, "other": 0}
    for ch in s:
        cp = ord(ch)
        if cp < 0x80:
            if 0x20 <= cp <= 0x7E:
                buckets["ascii_printable"] += 1
        elif 0x80 <= cp <= 0x024F:
            buckets["latin_ext"] += 1
        elif 0x0370 <= cp <= 0x03FF:
            buckets["greek"] += 1
        elif 0x0400 <= cp <= 0x04FF:
            buckets["cyrillic"] += 1
        elif 0x0590 <= cp <= 0x05FF:
            buckets["hebrew"] += 1
        elif 0x0600 <= cp <= 0x06FF:
            buckets["arabic"] += 1
        elif 0x0900 <= cp <= 0x097F:
            buckets["devanagari"] += 1
        elif 0x0E00 <= cp <= 0x0E7F:
            buckets["thai"] += 1
        elif 0x3040 <= cp <= 0x309F:
            buckets["hiragana"] += 1
        elif 0x30A0 <= cp <= 0x30FF:
            buckets["katakana"] += 1
        elif 0xAC00 <= cp <= 0xD7AF:
            buckets["hangul"] += 1
        elif 0x4E00 <= cp <= 0x9FFF:
            buckets["cjk"] += 1
        else:
            buckets["other"] += 1
    return buckets

print("=== classification by ValuesSection content ===")
print(f"{'#':>2}  {'idx':>7}  {'size':>9}  {'lang-guess':>14}  scripts(top3)")
rows = []
for fn in fns:
    p = os.path.join(LOCS, fn)
    raw = open(p, "rb").read()
    payload = raw[36:]
    dat1 = dat1lib.types.dat1.DAT1(io.BytesIO(payload), None)
    values_section = next((sh for sh in dat1.header.sections if sh.tag == 0x70A382B8), None)
    if not values_section:
        print(f"  ?? {fn}: no Values section")
        continue
    text = payload[values_section.offset : values_section.offset + values_section.size]
    b = classify(text)
    top3 = sorted(((k,v) for k,v in b.items() if k != "ascii_printable" and v > 0),
                  key=lambda x: -x[1])[:3]
    # heuristic: a language is identified by its dominant non-Latin script,
    # falling back to ascii_printable for english.
    non_ascii_total = sum(v for k,v in b.items() if k not in ("ascii_printable",))
    if non_ascii_total < 1000:
        guess = "english"
    elif top3:
        guess = top3[0][0]
    else:
        guess = "?"

    # extract idx from filename
    idx = int(fn.split("idx")[1].split(".")[0])
    rows.append((fn, idx, len(text), guess, b))
    print(f"  {fns.index(fn):>2}  {idx:>7}  {len(text):>9}  {guess:>14}  "
          f"{[(k,v) for k,v in top3]}")

print()
print("=== unique language guesses ===")
from collections import Counter
c = Counter(r[3] for r in rows)
for lang, n in c.most_common():
    matching = [r[0] for r in rows if r[3] == lang]
    print(f"  {lang:>14}: {n} files -> {matching[:5]}{'...' if n>5 else ''}")
