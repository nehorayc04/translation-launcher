"""Scope report for the SECOND text surface: the shader metadata.

The effect editor's category names, effect names, parameter labels and
parameter tooltips do NOT come from languages/<code>.json - they are authored
as attributes inside the .slang shader sources in the install folder:

    [bgfx::EFFECT("CRT Easymode", 2)]
    [bgfx::CATEGORY("CRT")]
    [bgfx::DESCRIPTION("...")]
    [bgfx::PARAM("Sharpness Horizontal", 0.5, 0.0, 1.0, "Controls ...")]

    python work/scan_effects.py            # counts
    python work/scan_effects.py --dump     # write extract/effects_en.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent.parent
EFFECTS = Path(r"F:/SteamLibrary/steamapps/common/Borderless Gaming/effects")

ATTR = re.compile(r"\[bgfx::(EFFECT|CATEGORY|DESCRIPTION|PASS|PARAM|PARAM_INT|PARAM_BOOL)\(([^\]]*)\)\]", re.S)
QUOTED = re.compile(r'"([^"]*)"')


def scan(root: Path) -> dict[str, dict[str, list[str]]]:
    """kind -> {string: [files it appears in]}"""
    out: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for f in sorted(root.rglob("*.slang")):
        rel = f.relative_to(root).as_posix()
        text = f.read_text("utf-8", errors="replace")
        for kind, args in ATTR.findall(text):
            qs = QUOTED.findall(args)
            if not qs:
                continue
            if kind in ("EFFECT", "CATEGORY", "DESCRIPTION", "PASS"):
                out[kind][qs[0]].append(rel)
            else:  # PARAM*: first quote = label, last = tooltip (when present)
                out["PARAM_LABEL"][qs[0]].append(rel)
                if len(qs) > 1:
                    out["PARAM_DESC"][qs[-1]].append(rel)
    return out


def main() -> int:
    data = scan(EFFECTS)
    files = len(list(EFFECTS.rglob("*.slang")))
    total = chars = 0
    print(f"{files} .slang files in {EFFECTS}\n")
    print(f"{'kind':14}{'unique':>8}{'chars':>9}")
    for kind in ("CATEGORY", "EFFECT", "DESCRIPTION", "PASS", "PARAM_LABEL", "PARAM_DESC"):
        vals = data.get(kind, {})
        c = sum(len(v) for v in vals)
        total += len(vals)
        chars += c
        print(f"{kind:14}{len(vals):>8}{c:>9}")
    print(f"{'TOTAL':14}{total:>8}{chars:>9}")

    print("\ncategories (the tree headers in the screenshot):")
    for cat in sorted(data["CATEGORY"]):
        print(f"   {cat:18} {len(data['CATEGORY'][cat]):>3} effects")

    if "--dump" in sys.argv:
        out = HERE / "extract" / "effects_en.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(
            {k: {s: sorted(set(v)) for s, v in sorted(d.items())} for k, d in sorted(data.items())},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
