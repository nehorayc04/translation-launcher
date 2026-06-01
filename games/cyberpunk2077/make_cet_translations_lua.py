"""
Convert localization_translated.json to a Lua-loadable lookup table for the
Hebrew Translator CET mod.

Output structure:
  return {
      entries = {
          { en = "Files", he = "קבצים", pk = "41" },
          ...
      },
      en_index = { ["files"] = {1, 17, ...}, ... },  -- lowercase EN -> indices
  }
"""
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SRC = r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים\source\resources\localization_translated.json"
DST_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator\Game Lab\Cyberpunk 2077\bin\x64\plugins\cyber_engine_tweaks\mods\hebrew_translator"
DST = os.path.join(DST_DIR, "translations.lua")

HEBREW_RE = re.compile(r"[֐-׿]")
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

ALLOWED_KEYS = {"onscreens/onscreens.json", "onscreens/onscreens_final.json"}


def lua_escape(s):
    """Escape a string for Lua single-quoted literal."""
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return s


def main():
    print(f"Loading {SRC}...")
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(DST_DIR, exist_ok=True)

    # Collect entries: deduplicate by (en, he) pair so we don't bloat the table
    seen = set()
    entries = []
    for fp, ents in data.items():
        if fp not in ALLOWED_KEYS:
            continue
        for e in ents:
            en = (e.get("femaleVariant") or e.get("maleVariant") or "").strip()
            he = (e.get("femaleVariant") or "").strip()  # We don't have separate orig+trans here
            # The JSON's femaleVariant IS the Hebrew (we replaced the English with Hebrew)
            # We don't have the original English in this JSON. So we'll use secondaryKey as the EN-side hint.
            sec = e.get("secondaryKey", "")
            if not he or not HEBREW_RE.search(he):
                continue
            key = (sec, he)
            if key in seen:
                continue
            seen.add(key)
            entries.append({
                "sec": sec,
                "he": he,
                "pk": str(e.get("primaryKey", "")),
            })

    print(f"  {len(entries):,} unique entries to export")

    # Build keyword index: lowercase tokens from secondaryKey -> entry indices
    en_index = {}
    for i, e in enumerate(entries, 1):
        for tok in TOKEN_RE.findall(e["sec"]):
            tok = tok.lower()
            if len(tok) < 3:
                continue
            en_index.setdefault(tok, []).append(i)
    print(f"  {len(en_index):,} index tokens")

    # Write Lua file
    print(f"Writing {DST}...")
    with open(DST, "w", encoding="utf-8") as f:
        f.write("-- Auto-generated Hebrew translations data for CET mod\n")
        f.write("-- Format: { entries = {{sec, he, pk}, ...}, en_index = {token = {idx,...}} }\n")
        f.write("return {\n")
        f.write("  entries = {\n")
        for e in entries:
            f.write(f"    {{sec='{lua_escape(e['sec'])}', he='{lua_escape(e['he'])}', pk='{lua_escape(e['pk'])}'}},\n")
        f.write("  },\n")
        f.write("  en_index = {\n")
        # Limit index to keep file reasonable
        for tok, idxs in sorted(en_index.items()):
            if len(idxs) > 500:
                idxs = idxs[:500]  # cap per-token
            joined = ",".join(str(i) for i in idxs)
            f.write(f"    ['{lua_escape(tok)}'] = {{{joined}}},\n")
        f.write("  },\n")
        f.write("}\n")

    print(f"  [OK] Wrote {os.path.getsize(DST):,} bytes")


if __name__ == "__main__":
    main()
