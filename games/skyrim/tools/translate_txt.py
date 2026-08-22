"""Codec for Skyrim's interface/translate_<language>.txt UI string table.

UTF-16LE **with BOM**, CRLF line endings, one `$key<TAB>value` per line.
649 entries in translate_english.txt. This is a SEPARATE surface from the
.STRINGS tables: the main menu / settings / HUD labels live here, the game
content (items, dialogue, books, quests) lives in Strings/*.

Duplicate keys exist in the shipped file ($Download twice) -- `parse` keeps the
LAST, `build` preserves the original line order and rewrites values in place, so
a round-trip is byte-identical.
"""
from __future__ import annotations

from pathlib import Path

BOM = "﻿"


def parse(data: bytes) -> dict[str, str]:
    text = data.decode("utf-16-le").lstrip(BOM)
    out: dict[str, str] = {}
    for line in text.split("\r\n"):
        if "\t" in line:
            k, v = line.split("\t", 1)
            out[k] = v
    return out


def build(original: bytes, overrides: dict[str, str]) -> bytes:
    """Rewrite only the values of keys present in `overrides`; keep everything else."""
    text = original.decode("utf-16-le")
    lead = BOM if text.startswith(BOM) else ""
    lines = text.lstrip(BOM).split("\r\n")
    out = []
    for line in lines:
        if "\t" in line:
            k, v = line.split("\t", 1)
            if k in overrides:
                v = overrides[k]
            out.append(f"{k}\t{v}")
        else:
            out.append(line)
    return (lead + "\r\n".join(out)).encode("utf-16-le")


def load(path) -> dict[str, str]:
    return parse(Path(path).read_bytes())


def roundtrip(path) -> bool:
    raw = Path(path).read_bytes()
    return build(raw, {}) == raw
