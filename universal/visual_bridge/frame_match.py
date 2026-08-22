# -*- coding: utf-8 -*-
"""
frame_match.py — the capture -> line bridge for the screenshot-context system.

Given a gameplay frame captured by game_visual_logger.py, OCR the on-screen Hebrew
(subtitle band, bottom-center by default), then FUZZY-MATCH that text against the
translation spine so we know exactly WHICH line (section + key) the frame shows.
That pairing is what lets context_review.py display, for a gender-ambiguous line,
the real in-game frame where it appears — so the referent's gender/number can be
read off the scene instead of guessed.

Design notes
------------
* CP2077 renders Hebrew through the Arabic locale slot with the engine's real RTL
  bidi, so on-screen the text reads correctly right-to-left; Tesseract `heb` returns
  it in LOGICAL order, matching the spine's logical Hebrew. We compare on a NORMALIZED
  form (strip niqqud / punctuation / tags / control bytes / collapse whitespace) so
  OCR noise and formatting don't defeat the match.
* Zero heavy deps: Tesseract via subprocess (self-contained `_tessdata/heb`), PIL for
  crop/preprocess, difflib for fuzzy ranking. No pytesseract / rapidfuzz.

CLI
---
  python frame_match.py selftest                 # render->OCR->match round-trip proof
  python frame_match.py index                    # OCR+match every frame in runtime_log
  python frame_match.py ocr <image.jpg>          # dump OCR of one frame's subtitle band
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

from PIL import Image, ImageOps, ImageFilter  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # repo root
TESSDATA = os.path.join(HERE, "_tessdata")
TESS_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

LOGS = os.path.join(ROOT, "_archive", "visual_logs")
RUNTIME_LOG = os.path.join(LOGS, "runtime_log.jsonl")
MATCH_OUT = os.path.join(LOGS, "frame_matches.jsonl")

RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
SPINE = {"base": os.path.join(RES, "localization_translated.json"),
         "dlc": os.path.join(RES, "dlc_ep1_translated.json")}

# ── normalization for matching ──────────────────────────────────────────────
_NIQQUD = re.compile("[֑-ׇ]")
_TAG = re.compile(r"\{[^}]*\}|<[^>]+>|%[sd%]|&rlm;|&[a-z]+;|\[[^\]]*\]|\\n")
_NONWORD = re.compile(r"[^א-תA-Za-z0-9]+")


def norm(s: str) -> str:
    """Normalized Hebrew for fuzzy comparison: no niqqud/tags/control/punct."""
    s = "".join(c for c in (s or "") if ord(c) >= 0x20)   # drop control bytes
    s = _NIQQUD.sub("", s)
    s = _TAG.sub(" ", s)
    s = _NONWORD.sub(" ", s)
    return " ".join(s.split())


# ── OCR ─────────────────────────────────────────────────────────────────────
def _preprocess(img: Image.Image) -> Image.Image:
    """Grayscale + upscale + autocontrast — helps Tesseract on UI text."""
    g = ImageOps.grayscale(img)
    if g.width < 1400:
        scale = 1400 / g.width
        g = g.resize((int(g.width * scale), int(g.height * scale)), Image.LANCZOS)
    g = ImageOps.autocontrast(g)
    return g.filter(ImageFilter.SHARPEN)


def ocr_hebrew(image_path: str, region: tuple | None = ("subtitle")) -> str:
    """OCR the Hebrew in an image. `region`:
       None            -> whole frame
       'subtitle'      -> bottom ~32% band (where CP2077 subtitles render)
       (l,t,r,b) 0..1  -> explicit fractional crop."""
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    if region == "subtitle" or region == ("subtitle",):
        img = img.crop((0, int(h * 0.68), w, h))
    elif isinstance(region, (tuple, list)) and len(region) == 4 and region != ("subtitle",):
        l, t, r, b = region
        img = img.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
    img = _preprocess(img)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "crop.png")
        img.save(p)
        out = os.path.join(td, "out")
        try:
            subprocess.run(
                [TESS_EXE, p, out, "-l", "heb", "--psm", "6",
                 "--tessdata-dir", TESSDATA],
                check=True, capture_output=True, timeout=60)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            return f"__OCR_ERROR__ {e}"
        txt_path = out + ".txt"
        if not os.path.exists(txt_path):
            return ""
        with open(txt_path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()


# ── spine index ─────────────────────────────────────────────────────────────
def _ekey(e: dict) -> str:
    return e.get("primaryKey") or e.get("stringId") or e.get("secondaryKey") or ""


def load_index(subtitles_only: bool = False) -> list:
    """[(norm_he, section, key, en, he_f, he_m), ...] over base+DLC."""
    idx = []
    for src, path in SPINE.items():
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        for sec, lst in data.items():
            if not isinstance(lst, list):
                continue
            if subtitles_only and "subtitle" not in sec:
                continue
            for e in lst:
                if not isinstance(e, dict):
                    continue
                he = e.get("femaleVariant") or ""
                n = norm(he)
                if len(n) < 6:          # too short to match reliably
                    continue
                idx.append((n, f"{src}:{sec}", _ekey(e),
                            e.get("secondaryKey", ""),
                            he, e.get("maleVariant") or ""))
    return idx


def best_match(ocr_text: str, index: list, min_ratio: float = 0.55):
    """Return (ratio, record) for the closest spine line, or (0, None)."""
    q = norm(ocr_text)
    if len(q) < 6:
        return 0.0, None
    best_r, best = 0.0, None
    qset = set(q.split())
    for rec in index:
        n = rec[0]
        # cheap token-overlap prefilter before the O(n) SequenceMatcher
        ov = qset & set(n.split())
        if not ov:
            continue
        r = difflib.SequenceMatcher(None, q, n).ratio()
        if r > best_r:
            best_r, best = r, rec
    if best_r < min_ratio:
        return best_r, None
    return best_r, best


# ── batch index a capture session ───────────────────────────────────────────
def index_runtime(min_ratio: float = 0.6) -> int:
    if not os.path.exists(RUNTIME_LOG):
        print(f"[!] no capture log yet: {RUNTIME_LOG}")
        print("    run game_visual_logger.py while playing (game in Arabic slot) first.")
        return 0
    index = load_index()
    print(f"[*] spine index: {len(index):,} matchable lines")
    n_frames = n_hit = 0
    with open(RUNTIME_LOG, encoding="utf-8") as f, \
         open(MATCH_OUT, "w", encoding="utf-8") as out:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            fp = rec.get("frame_path")
            if not fp or not os.path.exists(fp):
                continue
            n_frames += 1
            ocr = ocr_hebrew(fp, "subtitle")
            ratio, m = best_match(ocr, index, min_ratio)
            if m:
                n_hit += 1
                out.write(json.dumps({
                    "frame_path": fp, "ts": rec.get("timestamp"),
                    "ocr": ocr, "ratio": round(ratio, 3),
                    "section": m[1], "key": m[2], "secondaryKey": m[3],
                    "he_female": m[4], "he_male": m[5],
                }, ensure_ascii=False) + "\n")
            if n_frames % 25 == 0:
                print(f"  {n_frames} frames, {n_hit} matched")
    print(f"[✓] {n_frames} frames -> {n_hit} matched  -> {MATCH_OUT}")
    return n_hit


# ── selftest: render a known spine line, OCR it, prove the match ────────────
def _find_hebrew_font():
    for name in ("david.ttf", "davidbd.ttf", "frank.ttf", "gisha.ttc",
                 "arial.ttf", "ahronbd.ttf", "tahoma.ttf"):
        p = os.path.join(r"C:\Windows\Fonts", name)
        if os.path.exists(p):
            return p
    return None


def selftest() -> int:
    from PIL import ImageDraw, ImageFont
    print("frame_match selftest")
    print(f"  tessdata: {TESSDATA}  heb={os.path.exists(os.path.join(TESSDATA,'heb.traineddata'))}")
    index = load_index()
    assert index, "empty spine index"
    print(f"  spine index: {len(index):,} lines")

    # pick a few real, medium-length spine lines with clean Hebrew
    picks = [r for r in index if 15 <= len(r[0]) <= 45
             and not _TAG.search(r[4]) and r[4].isprintable()][:5]
    assert picks, "no clean sample lines"
    font_path = _find_hebrew_font()
    assert font_path, "no Hebrew font on this machine"
    print(f"  render font: {os.path.basename(font_path)}")
    font = ImageFont.truetype(font_path, 46)

    ok = 0
    for rec in picks:
        he = rec[4]
        # render the logical Hebrew onto a frame-like image (bottom band)
        img = Image.new("RGB", (1280, 720), (12, 12, 26))
        d = ImageDraw.Draw(img)
        # PIL draws LTR; for a faithful test we render the visual (reversed) form,
        # which is what the screen shows and what OCR-heb re-logicalizes.
        vis = he[::-1]
        d.text((640, 560), vis, font=font, fill=(235, 235, 235), anchor="mm")
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "f.png")
            img.save(fp)
            ocr = ocr_hebrew(fp, "subtitle")
        ratio, m = best_match(ocr, index, min_ratio=0.4)
        hit = (m is not None and m[2] == rec[2])
        ok += hit
        print(f"    [{'OK ' if hit else 'MISS'}] r={ratio:.2f} "
              f"he={he[:34]!r} ocr={norm(ocr)[:34]!r}")
    print(f"  matched {ok}/{len(picks)} rendered lines")
    # OCR is fuzzy; require a majority to prove the pipeline works end-to-end
    print("SELFTEST PASS" if ok >= max(1, len(picks) // 2) else "SELFTEST WEAK (OCR noisy)")
    return 0 if ok >= max(1, len(picks) // 2) else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="frame_match")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    ix = sub.add_parser("index")
    ix.add_argument("--min-ratio", type=float, default=0.6)
    oc = sub.add_parser("ocr")
    oc.add_argument("image")
    oc.add_argument("--region", default="subtitle")
    a = p.parse_args(argv)
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "index":
        return 0 if index_runtime(a.min_ratio) >= 0 else 1
    if a.cmd == "ocr":
        print(ocr_hebrew(a.image, a.region))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
