"""restore_markup_bytes.py — NO-AI deterministic fix for in-game RAW <Rich>
markup (skill-tree / cyberware / perk descriptions showing the literal tag
text instead of styled words).

ROOT CAUSE (measured 2026-06-14): CP2077 onscreen rich-text strings begin
with a leading CONTROL byte (\\x01..\\x1f) in the English source. The engine
needs it to PARSE the <Rich .../> markup; without it the tag renders RAW.
An old translation pass STRIPPED that leading byte from ~8,816 onscreens
femaleVariant values. Where the value carries markup, the tag now shows raw.

Evidence the restore is safe: in every entry where our Hebrew KEPT a leading
byte it was byte-IDENTICAL to the English byte (285/285, 0 diffs). The byte
is a per-string structural marker independent of content, so prepending the
exact English byte is faithful.

FIX (conservative — root-cause-targeted):
  * Restore the leading control byte ONLY on entries whose value carries
    markup ('<' tag or '{' placeholder) AND that lost it. Plain text (no
    markup) renders fine without the byte and is LEFT UNTOUCHED.
  * Bonus deterministic word fix: '[Take shower]' interaction prompt was
    mistranslated 'להתגלח' (shave) -> 'להתקלח' (shower).

maleVariant is empty in the spine for these entries; the bake
(cp2077_apply_translations_to_wkit_json.py) backfills it from the now-fixed
femaleVariant, so a male-V player gets the corrected, byte-prefixed string.

Safety: QA write-lock, per-file backup, atomic write, re-verify.
"""
import os, sys, json, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
UNIV = os.path.join(ROOT, "universal")
sys.path.insert(0, HERE); sys.path.insert(0, UNIV)
import cp2077_qa_defects as Q
import get_next_audit_batch as G

RES = os.path.dirname(G.BASE_TR)
SPINE  = G.BASE_TR
EXPORT = os.path.join(RES, "localization_export.json")
ONSCREENS = ("onscreens/onscreens.json", "onscreens/onscreens_final.json")

# The [Take shower] interaction prompt — mistranslated shave->shower.
SHOWER_SEC = "subtitles/quest/mq000/mq000_01_apartment.json"
SHOWER_PK  = 2028737051734482948
SHOWER_BAD = "להתגלח"
SHOWER_GOOD = "להתקלח"


def is_markup(s: str) -> bool:
    return ("<" in s) or ("{" in s)


def lead_ctrl(s: str):
    """Return the leading control byte char if s starts with one, else None."""
    if s and ord(s[0]) < 0x20:
        return s[0]
    return None


def _atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    if not Q.acquire_lock("restore_markup_bytes"):
        sys.exit("[abort] QA lock held by another process — not safe to write.")
    try:
        spine  = json.load(open(SPINE,  encoding="utf-8"))
        export = json.load(open(EXPORT, encoding="utf-8"))

        restored_fv = restored_mv = 0
        for sec in ONSCREENS:
            en_by_pk = {e.get("primaryKey"): e
                        for e in export.get(sec, []) if e.get("primaryKey") is not None}
            for e in spine.get(sec, []):
                en = en_by_pk.get(e.get("primaryKey"))
                if not en:
                    continue
                # canonical leading byte from the English source (female var).
                en_byte = lead_ctrl(en.get("femaleVariant") or "")
                if en_byte is None:
                    continue
                for fld, counter in (("femaleVariant", "fv"), ("maleVariant", "mv")):
                    v = e.get(fld) or ""
                    if not v or not is_markup(v):
                        continue
                    if lead_ctrl(v) is not None:
                        continue                      # already has its byte
                    e[fld] = en_byte + v              # restore exact English byte
                    if fld == "femaleVariant":
                        restored_fv += 1
                    else:
                        restored_mv += 1

        # ── shower word fix ──
        shower_fixed = 0
        for e in spine.get(SHOWER_SEC, []):
            if str(e.get("primaryKey")) != str(SHOWER_PK):
                continue
            for fld in ("femaleVariant", "maleVariant"):
                v = e.get(fld) or ""
                if SHOWER_BAD in v:
                    e[fld] = v.replace(SHOWER_BAD, SHOWER_GOOD)
                    shower_fixed += 1

        stamp = time.strftime("%Y%m%d_%H%M%S")
        bak = f"{SPINE}.bak.markupbytes.{stamp}"
        shutil.copy2(SPINE, bak)
        _atomic(SPINE, spine)
        print(f"backup -> {os.path.basename(bak)}")
        print(f"RESTORED leading byte: femaleVariant={restored_fv}  maleVariant={restored_mv}")
        print(f"SHOWER fix (להתגלח->להתקלח): {shower_fixed}")

        # ── re-verify ──
        spine2 = json.load(open(SPINE, encoding="utf-8"))
        residual = 0
        for sec in ONSCREENS:
            en_by_pk = {e.get("primaryKey"): e
                        for e in export.get(sec, []) if e.get("primaryKey") is not None}
            for e in spine2.get(sec, []):
                en = en_by_pk.get(e.get("primaryKey"))
                if not en:
                    continue
                if lead_ctrl(en.get("femaleVariant") or "") is None:
                    continue
                v = e.get("femaleVariant") or ""
                if v and is_markup(v) and lead_ctrl(v) is None:
                    residual += 1
        bad_shower = any(SHOWER_BAD in (e.get("femaleVariant") or "") or
                         SHOWER_BAD in (e.get("maleVariant") or "")
                         for e in spine2.get(SHOWER_SEC, [])
                         if str(e.get("primaryKey")) == str(SHOWER_PK))
        print(f"VERIFY: residual markup-without-byte={residual} (expect 0)  "
              f"shower-still-bad={bad_shower} (expect False)")
    finally:
        Q.release_lock()


if __name__ == "__main__":
    main()
