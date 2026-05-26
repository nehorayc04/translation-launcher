"""
cp2077_markup_analysis.py
=========================
Step 1 of the markup-aware translation effort.

Dissects the <kiroshi>, <mothertongue> and <Rich> markup in
localization_translated.json so the markup-aware translator is designed
against REAL data.

Key structural facts this surfaces:
  - <kiroshi>/<mothertongue> are self-closing tags whose ATTRIBUTE VALUES
    can contain nested <Rich> tags and backslash-escaped quotes (\\") — a
    naive `[^<>]` / `[^"]` regex shreds them. The parser here is escape-aware.
  - which attribute carries the player-visible English (the translate target)
    vs. the foreign text that must be preserved verbatim.
  - how many entries a past naive run already CORRUPTED (foreign text mangled).
  - leading CR2W control-byte (0x01-0x05) usage.

Read-only. Writes markup_analysis_report.txt.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
RES         = os.path.join(SCRIPTS_DIR, "תרגום_משחקים", "source", "resources")
TRANSLATED  = os.path.join(RES, "localization_translated.json")
REPORT      = os.path.join(SCRIPTS_DIR, "markup_analysis_report.txt")

HEB = re.compile(r"[֐-׿]")

# Escape-aware self-closing tag parsers. An attribute value is "..." where the
# body is any run of (escaped char \X) or (non-quote, non-backslash). This
# correctly skips over nested <Rich ...> tags and \" sequences inside a value.
KIRO_RE = re.compile(r'<kiroshi((?:\s+\w+="(?:\\.|[^"\\])*")*)\s*/?>')
MOTH_RE = re.compile(r'<mothertongue((?:\s+\w+="(?:\\.|[^"\\])*")*)\s*/?>')
ATTR_RE = re.compile(r'(\w+)="((?:\\.|[^"\\])*)"')
RICH_OPEN = re.compile(r'<Rich\b[^>]*>')

_LINES: list[str] = []


def out(line: str = "") -> None:
    print(line)
    _LINES.append(line)


def attrs(group: str) -> dict:
    return {k: v for k, v in ATTR_RE.findall(group or "")}


def lead_ctrl(s: str) -> int | None:
    return ord(s[0]) if s and 0x01 <= ord(s[0]) <= 0x05 else None


def analyze_attr_tag(name: str, tag_re: re.Pattern, entries: list,
                     foreign_attr: str, target_attrs: list[str]) -> None:
    """kiroshi / mothertongue: self-closing tags. `foreign_attr` must stay
    verbatim; `target_attrs` carry the player-visible English to translate."""
    out("=" * 78)
    out(f"  <{name}>  —  {len(entries):,} entries carrying the tag")
    out("=" * 78)

    parsed = unparsed = 0
    translated = corrupted = untranslated = 0
    attr_freq: Counter = Counter()
    ctrl: Counter = Counter()
    nested_rich = 0
    samples = {"translated": [], "corrupted": [], "untranslated": []}

    for sec, e in entries:
        fv = e.get("femaleVariant") or ""
        sk = e.get("secondaryKey") or ""
        c = lead_ctrl(sk)
        if c is not None:
            ctrl[f"0x{c:02x}"] += 1

        m = tag_re.search(fv) or tag_re.search(sk)
        if not m:
            unparsed += 1
            continue
        parsed += 1
        a = attrs(m.group(1))
        for k in a:
            attr_freq[k] += 1
        if "<Rich" in m.group(1):
            nested_rich += 1

        foreign_val = a.get(foreign_attr, "")
        target_text = " ".join(a.get(k, "") for k in target_attrs)
        if HEB.search(foreign_val):
            corrupted += 1
            bucket = "corrupted"
        elif HEB.search(target_text):
            translated += 1
            bucket = "translated"
        else:
            untranslated += 1
            bucket = "untranslated"
        if len(samples[bucket]) < 4:
            samples[bucket].append((sec, sk, fv))

    out(f"  parsed cleanly: {parsed:,}    unparsed: {unparsed:,}")
    out(f"  attributes: " + "  ".join(f"{k}({n:,})" for k, n in attr_freq.most_common()))
    out(f"  attribute values that embed a nested <Rich> tag: {nested_rich:,}")
    out(f"  leading CR2W control byte on the EN source: {sum(ctrl.values()):,}"
        f"  ({'  '.join(f'{b}:{n:,}' for b, n in ctrl.most_common())})")
    out("")
    out(f"  STATE (foreign attr '{foreign_attr}' must stay verbatim; "
        f"target {target_attrs} carries the English):")
    out(f"    correctly translated: {translated:,}")
    out(f"    CORRUPTED (foreign '{foreign_attr}' has Hebrew mixed in): {corrupted:,}")
    out(f"    still untranslated:   {untranslated:,}")
    out("")
    for bucket in ("untranslated", "translated", "corrupted"):
        if not samples[bucket]:
            continue
        out(f"  --- {bucket} samples ---")
        for sec, sk, fv in samples[bucket]:
            short = sec.split("/")[-1][:26]
            out(f"    [{short}] EN: {sk[:118]}")
            out(f"    {' ' * (len(short) + 6)}HE: {fv[:118]}")
        out("")


def analyze_rich(entries: list) -> None:
    out("=" * 78)
    out(f"  <Rich>  —  {len(entries):,} entries carrying the tag")
    out("=" * 78)
    # Standalone <Rich> (onscreens tooltips) vs <Rich> nested in another tag.
    standalone = nested = 0
    ctrl = 0
    rich_per: Counter = Counter()
    closer: Counter = Counter()
    placeholder = 0
    samples = []
    for sec, e in entries:
        fv = e.get("femaleVariant") or ""
        sk = e.get("secondaryKey") or ""
        # the markup-bearing text: femaleVariant when untranslated holds the
        # English; onscreens secondaryKey is only a category path.
        text = fv if "<Rich" in fv else sk
        if KIRO_RE.search(text) or MOTH_RE.search(text):
            nested += 1
        else:
            standalone += 1
        if lead_ctrl(text):
            ctrl += 1
        rich_per[min(len(RICH_OPEN.findall(text)), 5)] += 1
        closer["</>"] += text.count("</>")
        closer["</Rich>"] += text.count("</Rich>")
        if re.search(r"\{[^{}]+\}", text):
            placeholder += 1
        if len(samples) < 6 and not (KIRO_RE.search(text) or MOTH_RE.search(text)):
            samples.append((sec, text))

    out(f"  standalone <Rich> (onscreens tooltips etc.): {standalone:,}")
    out(f"  <Rich> nested inside <kiroshi>/<mothertongue>: {nested:,}")
    out(f"  leading control byte: {ctrl:,}")
    out(f"  <Rich> opens per entry: " +
        "  ".join(f"{k}:{v:,}" for k, v in sorted(rich_per.items())))
    out(f"  closer tokens: </> = {closer['</>']:,}   </Rich> = {closer['</Rich>']:,}")
    out(f"  entries that also contain a {{placeholder}}: {placeholder:,}")
    out("")
    out("  standalone <Rich> samples (text node between <Rich ...> and </> "
        "is the translate target; tags + {placeholders} preserved):")
    for sec, text in samples:
        out(f"    [{sec.split('/')[-1][:26]}] {text[:128]}")
    out("")


def main() -> int:
    print(f"[*] loading {TRANSLATED} ...")
    with open(TRANSLATED, "r", encoding="utf-8") as f:
        tr = json.load(f)

    fam: dict[str, list] = {"kiroshi": [], "mothertongue": [], "Rich": []}
    for sec, rows in tr.items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            blob = (e.get("secondaryKey") or "") + "\x00" + (e.get("femaleVariant") or "")
            for name in fam:
                if "<" + name in blob:
                    fam[name].append((sec, e))

    out("#" * 78)
    out("#  CYBERPUNK 2077 — SUBTITLE / TOOLTIP MARKUP ANALYSIS  (escape-aware)")
    out("#  basis for the markup-aware translator")
    out("#" * 78)
    out("")
    analyze_attr_tag("kiroshi", KIRO_RE, fam["kiroshi"],
                     foreign_attr="o", target_attrs=["t"])
    analyze_attr_tag("mothertongue", MOTH_RE, fam["mothertongue"],
                     foreign_attr="m", target_attrs=["b", "a"])
    analyze_rich(fam["Rich"])

    out("#" * 78)
    out("#  TRANSLATE-TARGET MAP (for the markup-aware translator)")
    out("#" * 78)
    out("  <kiroshi l o t b a/>   : translate t (+b/a if present); keep l, o verbatim")
    out("  <mothertongue l m b a/>: translate b, a; keep l, m (the foreign phrase)")
    out("  <Rich attr...>TEXT</>  : translate TEXT node(s); keep tags, attrs, </>")
    out("  ALWAYS preserve: leading 0x01-0x05 control byte, {placeholders}, \\\" escapes")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(_LINES) + "\n")
    print(f"\n[*] report -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
