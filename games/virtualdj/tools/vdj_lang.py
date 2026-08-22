r"""
VirtualDJ language-file codec (read/write) + embedded languages.zip carver.

VirtualDJ 2026 (build 9482) ships a `languages.zip` embedded inside
`virtualdj.exe`, holding one XML per language (English.xml = source,
Arabic.xml = the RTL slot we hijack for Hebrew). Format is loose, plain
UTF-8 XML — NO offsets/checksums/compression → the easiest container class
in this project (like Plague Tale / Anno loose text).

Schema:
  <language lang="Arabic" iso="ar" author=".." version="8.2" build="9475">
    <Section><Key>value</Key> ... </Section>
    ...
  </language>

Keys (Section/Key) are IDENTICAL across languages -> map EN->HE by key.
Deploy = drop the built Arabic.xml into %LOCALAPPDATA%\VirtualDJ\Languages\
(overrides the embedded copy). Activation = Settings > Options > language =
Arabic. No repack, no font atlas, no anti-cheat.

CLI:
  python vdj_lang.py carve  <exe> <outdir>     # extract embedded languages.zip
  python vdj_lang.py dump   <xml> <out.json>   # {"Section/Key": text}
  python vdj_lang.py stats  <xml>
  python vdj_lang.py roundtrip <xml>           # parse -> build -> parse identity
"""
import io
import re
import os
import sys
import json
import struct
import zipfile
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------- carve zip ---
def carve_langzip(exe_path):
    """Find + extract the embedded languages.zip from virtualdj.exe.
    Returns {member_name: xml_bytes}. Locates the EOCD whose central dir
    lists the 12 language XMLs."""
    data = open(exe_path, "rb").read()
    for m in re.finditer(rb"PK\x05\x06", data):
        eocd = m.start()
        try:
            sig, d1, d2, n1, ntot, cdsize, cdoff, clen = struct.unpack(
                "<IHHHHIIH", data[eocd:eocd + 22])
        except struct.error:
            continue
        zip_start = eocd - (cdoff + cdsize)
        if zip_start < 0 or zip_start > len(data):
            continue
        blob = data[zip_start:eocd + 22 + clen]
        try:
            zf = zipfile.ZipFile(io.BytesIO(blob))
            names = zf.namelist()
        except Exception:
            continue
        if any(n.endswith("English.xml") for n in names) and \
           any(n.endswith("Arabic.xml") for n in names):
            return {n: zf.read(n) for n in names}
    raise RuntimeError("embedded languages.zip not found in exe")


# ------------------------------------------------------------------ codec -----
def parse(xml_bytes):
    """Parse a language XML.
    Returns (root_attrib: dict, sections: [(section, [(key, text), ...]), ...])
    preserving section + key order."""
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")
    root = ET.fromstring(xml_bytes)
    sections = []
    for sec in root:
        entries = [(e.tag, e.text or "") for e in sec]
        sections.append((sec.tag, entries))
    return dict(root.attrib), sections


def flatten(sections):
    """sections -> {"Section/Key": text} (order preserved via dict in py3.7+)."""
    out = {}
    for sec, entries in sections:
        for key, text in entries:
            out[f"{sec}/{key}"] = text
    return out


_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}


def _esc(s):
    return "".join(_ESC.get(c, c) for c in s)


def build(root_attrib, sections):
    """Serialize back to a VirtualDJ-parseable XML (compact, UTF-8),
    matching the shipped single-line layout."""
    attrs = " ".join(f'{k}="{_esc(v)}"' for k, v in root_attrib.items())
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n', f"<language {attrs}>"]
    for sec, entries in sections:
        parts.append(f"<{sec}>")
        for key, text in entries:
            parts.append(f"<{key}>{_esc(text)}</{key}>")
        parts.append(f"</{sec}>")
    parts.append("</language>")
    return "".join(parts).encode("utf-8")


def build_hebrew(arabic_xml_bytes, hebrew_map, lang_attrib_override=None):
    """Build the Hebrew Arabic-slot XML from the Arabic skeleton (all keys),
    overriding each value from hebrew_map {"Section/Key": he}. Keys not in
    hebrew_map keep the Arabic value (never blank)."""
    attrib, sections = parse(arabic_xml_bytes)
    if lang_attrib_override:
        attrib.update(lang_attrib_override)
    new_sections = []
    for sec, entries in sections:
        new_entries = []
        for key, ar_text in entries:
            he = hebrew_map.get(f"{sec}/{key}")
            new_entries.append((key, he if he is not None else ar_text))
        new_sections.append((sec, new_entries))
    return build(attrib, new_sections)


# -------------------------------------------------------------------- cli -----
def _cli():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "carve":
        exe, outdir = sys.argv[2], sys.argv[3]
        os.makedirs(outdir, exist_ok=True)
        members = carve_langzip(exe)
        for name, b in members.items():
            with open(os.path.join(outdir, name), "wb") as f:
                f.write(b)
        print(f"carved {len(members)} langs -> {outdir}: {sorted(members)}")
    elif cmd == "dump":
        xml, out = sys.argv[2], sys.argv[3]
        attrib, sections = parse(open(xml, "rb").read())
        flat = flatten(sections)
        json.dump(flat, open(out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        print(f"{xml}: {len(flat)} entries -> {out}  (lang={attrib.get('lang')})")
    elif cmd == "stats":
        xml = sys.argv[2]
        attrib, sections = parse(open(xml, "rb").read())
        tot = 0
        for sec, entries in sections:
            tot += len(entries)
            print(f"  {sec:20s} {len(entries):5d}")
        print(f"TOTAL {tot}  root={attrib}")
    elif cmd == "roundtrip":
        xml = sys.argv[2]
        raw = open(xml, "rb").read()
        a1, s1 = parse(raw)
        rebuilt = build(a1, s1)
        a2, s2 = parse(rebuilt)
        ok = (a1 == a2 and flatten(s1) == flatten(s2))
        print(f"roundtrip {'OK' if ok else 'FAIL'}: "
              f"{len(flatten(s1))} entries, rebuilt {len(rebuilt)} bytes")
        if not ok:
            sys.exit(1)
    else:
        print(__doc__)


if __name__ == "__main__":
    _cli()
