# -*- coding: utf-8 -*-
"""Build a NEW-ERA corpus for R&C Rift Apart to seed into the community-compute queue.

Instead of English-only, every line's `src` is a REFERENCE PANEL made of the
game's OWN official translations (EN + FR/DE/IT/ES/RU/PL), and the `sys` prompt
tells the volunteer's LLM to decide the Hebrew against ALL of them (meaning from
the Romance/German lines, gender+number from RU/PL, register from DE) — the
[[new-era-doctrine]] method, not a raw EN→He guess.

Output: games/ratchet_rift_apart/extract/newera_corpus.json  ({"items":{key:panel}, "sys":...})
Then:   python seed_jobs.py <that> --game ratchet-rift-apart
"""
import io, json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
RC   = os.path.join(REPO, "games", "ratchet_rift_apart")
LOCS = os.path.join(RC, "extracted", "loc_variants")
CT   = os.path.join(RC, "extract", "ct_upload.json")
OUT  = os.path.join(RC, "extract", "newera_corpus.json")
sys.path.insert(0, os.path.join(REPO, "games", "spiderman2", "tools", "ALERT"))
sys.path.insert(0, HERE)
import dat1lib, dat1lib.types.dat1
import cc_corpus   # universal panel/prompt builder (any game, any langs, translate|review)

TAG_VALUES, TAG_KEYS = 0x70A382B8, 0x4D73CEBD
TAG_TEXT_OFFSETS, TAG_KEY_OFFSETS, TAG_ENTRY_COUNT = 0xF80DEEB4, 0xA4EA55B2, 0xD540A903

# reference languages (New-Era panel) → variant index
REFS = [("FR", 6), ("DE", 7), ("IT", 8), ("ES", 15), ("RU", 14), ("PL", 12)]


def variant_path(n):
    for fn in os.listdir(LOCS):
        if fn.startswith(f"variant_{n:02d}_"):
            return os.path.join(LOCS, fn)
    raise FileNotFoundError(f"variant_{n:02d}")


def decode(path):
    raw = open(path, "rb").read(); pay = raw[36:]
    d = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
    secs = {sh.tag: (sh.offset, sh.size) for sh in d.header.sections}
    def sb(t): o, s = secs[t]; return pay[o:o + s]
    cnt = struct.unpack("<I", sb(TAG_ENTRY_COUNT))[0]
    kb, vb = sb(TAG_KEYS), sb(TAG_VALUES)
    ko = list(struct.unpack(f"<{cnt}I", sb(TAG_KEY_OFFSETS)))
    to = list(struct.unpack(f"<{cnt}I", sb(TAG_TEXT_OFFSETS)))
    def cs(b, o): e = b.find(b"\x00", o); return b[o:(e if e >= 0 else len(b))]
    out = {}
    for i in range(cnt):
        k = cs(kb, ko[i]).decode("utf-8", "replace")
        v = cs(vb, to[i]).decode("utf-8", "replace")
        if k and k not in out:
            out[k] = v
    return out


def main():
    rows = json.load(open(CT, encoding="utf-8"))          # ordered, filtered, categorized
    order = [r["string_key"] for r in rows]               # visibility order
    en = {r["string_key"]: r["source_en"] for r in rows}
    ref_maps = {lbl: decode(variant_path(n)) for lbl, n in REFS}
    print("decoded refs:", {lbl: len(m) for lbl, m in ref_maps.items()})

    # universal builder — swap mode="review" + current_he={id:he} for a QA pass
    out = cc_corpus.build_items(en, ref_maps, mode="translate", order=order)

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    items = out["items"]
    avg_refs = sum(s.count("\n") for s in items.values()) / max(1, len(items))
    print(f"built {len(items)} New-Era lines  avg refs/line={avg_refs:.1f}  -> {OUT}")
    sk = next(iter(items))
    print("sample:\n" + items[sk][:400])


if __name__ == "__main__":
    main()
