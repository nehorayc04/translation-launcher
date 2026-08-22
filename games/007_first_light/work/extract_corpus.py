"""
extract_corpus.py — extract the FULL 007 First Light English translatable corpus from chunk0+chunk1
and categorise it (UI/LOCR vs subtitles/DLGE; visible -> less-visible), for the line-count report
and the community /translate upload.

Outputs (games/007_first_light/extract/):
  locr_en.json  {"<res_hex>:<lineHash:08X>": "english"}          UI strings
  dlge_en.json  [{"key","en","speaker","kind"}]                   subtitle lines (clean text)
  report.txt    the category counts
"""
import os
import sys
import re
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from gl_rpkg import RPKG
import gl_locr as L
import gl_dlge as D

GAME = r"F:\Game Lab\007 First Light"
CHUNKS = [os.path.join(GAME, "Runtime", "chunk0.rpkg"),
          os.path.join(GAME, "Runtime", "chunk1.rpkg")]
OUT = os.path.join(HERE, "..", "extract")
EN = 1   # language slot 1 = English (verified)

_META = re.compile(r"^(?://.*?\\\\)+")          # leading //...\\  metadata tokens
_SPEAKER = re.compile(r"^//\[([^\]]*)\]\\\\")   # first token = //[SPEAKER]\\


def clean_sub(s):
    """Strip the leading //...\\ metadata tokens -> (clean_text, speaker)."""
    sp = _SPEAKER.match(s)
    speaker = sp.group(1) if sp else ""
    return _META.sub("", s), speaker


def is_translatable(s):
    """Real translatable text: has a letter, not a pure code/number/token."""
    if not s or not s.strip():
        return False
    core = re.sub(r"[\W\d_]+", "", s, flags=re.UNICODE)
    return len(core) >= 2


def main():
    os.makedirs(OUT, exist_ok=True)
    locr = {}          # key -> en
    dlge = []          # {key,en,speaker,kind}
    dlge_seen = set()

    for path in CHUNKS:
        R = RPKG(path)
        # ---- LOCR (UI) ----
        for i in R.indices("LOCR"):
            r = R.resources[i]
            try:
                ver, langs = L.decode_locr(R.read(i))
            except Exception:
                continue
            block = langs[EN] if EN < len(langs) else None
            if not block:
                continue
            for lh, s in block:
                if is_translatable(s):
                    locr[f"{r.hex()}:{lh:08X}"] = s
        # ---- DLGE (subtitles) ----
        for i in R.indices("DLGE"):
            r = R.resources[i]
            try:
                wavs, ok = D.decode_dlge(R.read(i))
            except Exception:
                continue
            if not ok:
                continue
            for oi, w in enumerate(wavs):
                s = w["langs"].get("en")
                if not s:
                    continue
                clean, speaker = clean_sub(s)
                if not is_translatable(clean):
                    continue
                key = f"{r.hex()}:{oi}"
                dlge.append({"key": key, "en": clean, "speaker": speaker,
                             "soundtag": f"{w['soundtag']:08X}"})

    # dedup-by-text stats
    locr_uniq = set(locr.values())
    dlge_texts = [d["en"] for d in dlge]
    dlge_uniq = set(dlge_texts)

    json.dump(locr, open(os.path.join(OUT, "locr_en.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    json.dump(dlge, open(os.path.join(OUT, "dlge_en.json"), "w", encoding="utf-8"),
              ensure_ascii=False)

    lines = []
    lines.append("=== 007 First Light — translatable corpus ===")
    lines.append(f"UI (LOCR):        {len(locr):>7} strings   ({len(locr_uniq)} unique)")
    lines.append(f"Subtitles (DLGE): {len(dlge):>7} lines     ({len(dlge_uniq)} unique)")
    lines.append(f"TOTAL:            {len(locr)+len(dlge):>7}          ({len(locr_uniq)+len(dlge_uniq)} unique-ish)")
    rep = "\n".join(lines)
    open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8").write(rep)
    print(rep)
    # a few samples
    print("\nUI samples:", list(locr.values())[:4])
    print("SUB samples:", [(d["speaker"], d["en"][:40]) for d in dlge[:4]])


if __name__ == "__main__":
    main()
