"""Borderless Gaming language-file codec.

Format: plain UTF-8 JSON, 2-space indent, nested objects, leading "$schema".
Validated by languages/schema.json (additionalProperties:false everywhere), so
the key set must stay EXACTLY the same as en-US.json - never add/drop a key.

Only the STRING LEAVES are translated; the tree shape is copied verbatim.

CLI:
    python bg_lang.py flatten <lang.json> <out.json>   # {"A.B.C": "text"}
    python bg_lang.py build <en-US.json> <hebrew.json> <out he-IL.json>
    python bg_lang.py selftest
"""
from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCHEMA_KEY = "$schema"


def load(path: str | Path) -> "OrderedDict[str, object]":
    return json.loads(Path(path).read_text("utf-8"), object_pairs_hook=OrderedDict)


def flatten(obj, prefix: str = "") -> "OrderedDict[str, str]":
    """Nested dict -> {"Dotted.Path": "leaf string"}. Skips $schema."""
    out: "OrderedDict[str, str]" = OrderedDict()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not prefix and k == SCHEMA_KEY:
                continue
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, str):
        out[prefix] = obj
    else:  # numbers/bools/null are not translatable content
        pass
    return out


def unflatten(tree, flat: dict, prefix: str = ""):
    """Rebuild the ORIGINAL tree, replacing leaves present in `flat`."""
    if isinstance(tree, dict):
        out = OrderedDict()
        for k, v in tree.items():
            if not prefix and k == SCHEMA_KEY:
                out[k] = v
                continue
            out[k] = unflatten(v, flat, f"{prefix}.{k}" if prefix else k)
        return out
    if isinstance(tree, str):
        return flat.get(prefix, tree)
    return tree


def dump(obj, path: str | Path) -> None:
    """Write exactly like the shipped files: 2-space indent, UTF-8 (no BOM),
    CRLF line endings, non-ASCII literal (ar-SA.json stores Arabic literally).
    With these settings an identity rebuild of en-US.json is BYTE-IDENTICAL."""
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    Path(path).write_text(text, encoding="utf-8", newline="\r\n")


def build_hebrew(en_path: str | Path, hebrew: dict, code: str = "he-IL",
                 name: str = "עברית") -> "OrderedDict[str, object]":
    """en-US tree + Hebrew leaves -> a he-IL language file.

    Untranslated leaves fall back to the English text (never blank).
    """
    tree = load(en_path)
    out = unflatten(tree, hebrew)
    out[SCHEMA_KEY] = "./schema.json"
    out["Language"]["Name"] = name
    out["Language"]["Code"] = code
    return out


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    src = OrderedDict([
        (SCHEMA_KEY, "./schema.json"),
        ("Language", OrderedDict([("Name", "English"), ("Code", "en-US")])),
        ("A", OrderedDict([("B", "hello {0}"), ("C", OrderedDict([("D", "bye")]))])),
        ("N", 5),
    ])
    flat = flatten(src)
    assert list(flat) == ["Language.Name", "Language.Code", "A.B", "A.C.D"], flat
    assert flat["A.B"] == "hello {0}"
    # identity
    assert unflatten(src, flat) == src, "identity round-trip failed"
    # partial replace keeps untouched leaves + key order + non-strings
    out = unflatten(src, {"A.B": "שלום {0}"})
    assert out["A"]["B"] == "שלום {0}" and out["A"]["C"]["D"] == "bye"
    assert list(out) == list(src) and out["N"] == 5
    print("selftest OK")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "selftest":
        return selftest()
    if cmd == "flatten":
        dump(flatten(load(argv[2])), argv[3])
        print("wrote", argv[3])
        return 0
    if cmd == "build":
        heb = json.loads(Path(argv[3]).read_text("utf-8"))
        dump(build_hebrew(argv[2], heb), argv[4])
        print("wrote", argv[4])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
