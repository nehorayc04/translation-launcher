"""Post-run QA sweep over all 8 translated Steam files.

For each file: confirms the language slot was hijacked to Arabic, counts
Hebrew coverage, and flags entries left as untranslated English."""
import json
import re
from pathlib import Path

OUT = Path("steam_hebrew_output")
HEB = re.compile(r"[֐-׿]")

JS_FILES = [
    "steamui/localization/steamui_arabic-json.js",
    "steamui/localization/shared_arabic-json.js",
    "steamui/localization/friendsui_arabic-json.js",
    "steamui/localization/steampops_arabic-json.js",
]
VDF_FILES = [
    "resource/vgui_arabic.txt",
    "resource/overlay_arabic.txt",
    "resource/platform_arabic.txt",
    "friends/trackerui_arabic.txt",
]


def js_decode(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nx = s[i + 1]
            if   nx == "'":  out.append("'");  i += 2
            elif nx == '"':  out.append('"');  i += 2
            elif nx == "\\": out.append("\\"); i += 2
            elif nx == "n":  out.append("\n"); i += 2
            elif nx == "r":  out.append("\r"); i += 2
            elif nx == "t":  out.append("\t"); i += 2
            elif nx == "u" and i + 5 < n:
                out.append(chr(int(s[i + 2:i + 6], 16))); i += 6
            else:
                out.append(nx); i += 2
        else:
            out.append(c); i += 1
    return "".join(out)


def check_js(rel: str) -> dict:
    p = OUT / rel
    text = p.read_text(encoding="utf-8")
    # Greedy: the payload runs from the first ('  to the LAST ') in the
    # file. Non-greedy would stop at the first ') that a Hebrew value
    # happens to contain.
    m = re.search(r"JSON\.parse\('(.+)'\)", text, re.DOTALL)
    data = json.loads(js_decode(m.group(1)))
    vals = [v for k, v in data.items() if k != "language" and isinstance(v, str) and v.strip()]
    heb = [v for v in vals if HEB.search(v)]
    eng = [v for v in vals if not HEB.search(v) and re.search(r"[A-Za-z]{3,}", v)]
    return {
        "file": rel.split("/")[-1],
        "size": p.stat().st_size,
        "slot": data.get("language"),
        "total": len(data),
        "heb": len(heb),
        "eng_only": len(eng),
    }


def check_vdf(rel: str) -> dict:
    p = OUT / rel
    raw = p.read_bytes()
    enc = "utf-16-le" if raw[:2] == b"\xff\xfe" else "utf-8"
    body = raw[3:] if raw[:3] == b"\xef\xbb\xbf" else (raw[2:] if raw[:2] == b"\xff\xfe" else raw)
    text = body.decode(enc)
    lang = re.search(r'"Language"\s+"([^"]+)"', text)
    kv = re.findall(r'^[ \t]*"([^"]+)"[ \t]+"((?:[^"\\]|\\.)*)"', text, re.MULTILINE)
    vals = [v for k, v in kv if k.lower() != "language" and v.strip()]
    heb = [v for v in vals if HEB.search(v)]
    eng = [v for v in vals if not HEB.search(v) and re.search(r"[A-Za-z]{3,}", v)]
    return {
        "file": rel.split("/")[-1],
        "size": p.stat().st_size,
        "slot": lang.group(1) if lang else "(none)",
        "total": len(kv),
        "heb": len(heb),
        "eng_only": len(eng),
    }


rows = []
for f in JS_FILES:
    rows.append(check_js(f))
for f in VDF_FILES:
    rows.append(check_vdf(f))

print(f"{'file':<28}{'size':>10}{'slot':>10}{'total':>9}{'hebrew':>9}{'eng-only':>10}")
print("-" * 76)
t_total = t_heb = t_eng = 0
for r in rows:
    slot = str(r["slot"])
    print(f"{r['file']:<28}{r['size']:>10,}{slot:>10}{r['total']:>9,}{r['heb']:>9,}{r['eng_only']:>10,}")
    t_total += r["total"]; t_heb += r["heb"]; t_eng += r["eng_only"]
print("-" * 76)
print(f"{'TOTAL':<28}{'':<10}{'':<10}{t_total:>9,}{t_heb:>9,}{t_eng:>10,}")
print(f"\nHebrew coverage: {100 * t_heb / max(1, t_heb + t_eng):.2f}%  (eng-only includes brand names / acronyms)")

# A None slot is fine — some bundles (e.g. steamui) carry no `language`
# key at all and Steam matches them purely by filename. Only a slot that
# is present AND not "arabic" is a real failure.
bad = [r for r in rows if r["slot"] is not None and str(r["slot"]).lower() != "arabic"]
print("slot check:", "ALL OK" if not bad else f"FAIL — {[r['file'] for r in bad]}")
