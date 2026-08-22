"""Extract the full EN source + AR skeleton corpus from every .w3strings into extract/.

Output (keyed by decimal str_id, globally merged across all content+dlc files):
  extract/en.json   {str_id: english_text}   -- translation SOURCE
  extract/ar.json   {str_id: arabic_text}     -- reference skeleton (leading U+202E kept)
  extract/index.json {str_id: "relpath"}      -- which file each id came from (first seen)
Also prints a UI-length-heuristic split and any cross-file id collisions.
"""
import os, glob, json, collections
import w3strings as W

GAME = r"D:\Games\The Witcher 3 - Complete Edition"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "extract")
os.makedirs(OUT, exist_ok=True)


def collect(lang):
    files = sorted(glob.glob(os.path.join(GAME, "content", "content*", f"{lang}.w3strings")) +
                   glob.glob(os.path.join(GAME, "dlc", "*", "content", f"{lang}.w3strings")))
    m, index = {}, {}
    collisions = 0
    for p in files:
        d = W.decode(open(p, "rb").read())
        rel = os.path.relpath(p, GAME)
        for e in d["entries"]:
            sid = e["str_id"]
            if sid in m and m[sid] != e["text"]:
                collisions += 1
            if sid not in m:
                index[sid] = rel
            m[sid] = e["text"]
    return m, index, collisions, len(files)


def main():
    en, index, col_en, nfe = collect("en")
    ar, _, col_ar, nfa = collect("ar")
    json.dump({str(k): v for k, v in en.items()}, open(os.path.join(OUT, "en.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({str(k): v for k, v in ar.items()}, open(os.path.join(OUT, "ar.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({str(k): v for k, v in index.items()}, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False)

    # crude UI-vs-dialogue heuristic by english length (labels are short, dialogue long)
    lens = [len(v) for v in en.values()]
    short = sum(1 for x in lens if x <= 40)
    mid = sum(1 for x in lens if 40 < x <= 120)
    long = sum(1 for x in lens if x > 120)
    print(f"EN: {len(en):,} unique ids from {nfe} files ({col_en} cross-file text collisions)")
    print(f"AR: {len(ar):,} unique ids from {nfa} files ({col_ar} collisions)")
    print(f"only-in-EN (untranslated in AR slot): {len(set(en) - set(ar)):,}")
    print(f"length heuristic (EN): <=40 chars={short:,} (label/UI-ish)  41-120={mid:,}  >120={long:,} (dialogue-ish)")
    print(f"wrote extract/en.json extract/ar.json extract/index.json")


if __name__ == "__main__":
    main()
