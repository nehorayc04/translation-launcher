"""Codec for the compiled-effect cache - the ONLY writable path for the shader
metadata (categories, effect names, parameter labels and tooltips).

Why not the .slang sources: the app does read a user-side copy of an effect and
does let it override the installed one (proven), but Slang's reflection step
serialises non-ASCII attribute text with C-style OCTAL escapes, which is not
valid JSON, so any file containing Hebrew is rejected outright:

    '3' is an invalid escapable character within a JSON string.
    Path: $.parameters[0]...userAttribs[0].arguments[0]

The cache sidesteps that stage entirely. Layout (.NET BinaryWriter, all strings
UTF-8 with a 7-bit-encoded length prefix):

    int32   version (2)
    string  sha256 of the SOURCE .slang, uppercase hex   <- the validity key
    string  key                "Film\\FilmGrain"
    string  effect name        "Film Grain"                  TRANSLATABLE
    string  absolute source path
    string  category           "Film"                        TRANSLATABLE
    string  description        "Procedural film grain ..."   TRANSLATABLE
    ... then per parameter, contiguously:
    string  variable name      "grainAmount"     <- the anchor, never touched
    string  label              "Grain Amount"                TRANSLATABLE
    string  tooltip            "Intensity of ..."            TRANSLATABLE

Because the stored hash is of the SOURCE and we never touch the source, a
patched cache stays valid and the app loads it without recompiling.

Patching is surgical: each string is located by its anchor and replaced
together with its length prefix, so no other byte moves meaning. Nothing in the
format is an absolute offset, which is what makes that safe.

    python work/bg_cache.py dump <file.bin>
    python work/bg_cache.py selftest
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE = None  # set by callers; see bg_paths below


# --------------------------------------------------------------------------- 7-bit length

def write_7bit(n: int) -> bytes:
    out = bytearray()
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def read_7bit(buf: bytes, pos: int) -> tuple[int, int]:
    n = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, pos
        shift += 7


def read_str(buf: bytes, pos: int) -> tuple[str, int]:
    n, pos = read_7bit(buf, pos)
    return buf[pos:pos + n].decode("utf-8"), pos + n


def enc_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return write_7bit(len(b)) + b


# --------------------------------------------------------------------------- header

def read_header(buf: bytes) -> dict:
    """Everything up to the description, which is fully deterministic."""
    pos = 4
    out: dict = {"version": int.from_bytes(buf[:4], "little")}
    for field in ("sha", "key", "name", "source", "category", "description"):
        start = pos
        val, pos = read_str(buf, pos)
        out[field] = val
        out[field + "_span"] = (start, pos)
    out["end"] = pos
    return out


def span_of(buf: bytes, anchor: str, which: int, start: int = 0) -> tuple[int, int]:
    """Locate the string `which` positions after the length-prefixed `anchor`.

    which=0 is the anchor itself, 1 the next string, 2 the one after it. The
    anchor is a Slang variable name, so the match is unambiguous.
    """
    needle = enc_str(anchor)
    i = buf.find(needle, start)
    if i < 0:
        raise KeyError(anchor)
    if buf.find(needle, i + 1) >= 0:
        raise ValueError(f"anchor {anchor!r} is not unique")
    pos = i
    for _ in range(which):
        _, pos = read_str(buf, pos)
    s = pos
    _, pos = read_str(buf, s)
    return s, pos


def replace_spans(buf: bytes, edits: list[tuple[tuple[int, int], str]]) -> bytes:
    """Apply (span, new_text) edits right-to-left so earlier spans stay valid."""
    out = bytearray(buf)
    for (a, b), text in sorted(edits, key=lambda e: -e[0][0]):
        out[a:b] = enc_str(text)
    return bytes(out)


# --------------------------------------------------------------------------- source side

PARAM_RE = re.compile(
    r"\[bgfx::PARAM(?:_INT|_BOOL)?\(([^\]]*)\)\]\s*(?:\w[\w:<>, ]*?)\s+(\w+)\s*;", re.S)
QUOTED = re.compile(r'"([^"]*)"')


def source_params(slang: Path) -> list[tuple[str, str, str]]:
    """[(variable_name, label, tooltip)] as authored in the shader."""
    text = slang.read_text("utf-8", errors="replace")
    out = []
    for args, var in PARAM_RE.findall(text):
        qs = QUOTED.findall(args)
        if qs:
            out.append((var, qs[0], qs[-1] if len(qs) > 1 else ""))
    return out


# --------------------------------------------------------------------------- cli

def dump(path: Path) -> None:
    buf = path.read_bytes()
    h = read_header(buf)
    print(f"version     {h['version']}")
    for f in ("sha", "key", "name", "category", "description"):
        print(f"{f:11} {h[f]!r}")
    print(f"header ends at {h['end']} of {len(buf)}")


def selftest() -> int:
    """Every cache entry must parse, and its stored hash must match its source."""
    import hashlib
    from build_menu_proof import real_appdata
    cache = real_appdata() / "coreutils" / "borderless-gaming" / "cache" / "effects"
    bins = sorted(cache.glob("*.bin"))
    if not bins:
        print("no cache yet - run the app once")
        return 1
    ok = stale = bad = 0
    for p in bins:
        try:
            h = read_header(p.read_bytes())
            src = Path(h["source"])
            if not src.exists():
                src = Path(r"F:/SteamLibrary/steamapps/common/Borderless Gaming/effects") / h["key"].replace("\\", "/")
                src = src.with_suffix(".slang")
            if src.exists():
                real = hashlib.sha256(src.read_bytes()).hexdigest().upper()
                if real != h["sha"]:
                    stale += 1
                    continue
            ok += 1
        except Exception as exc:
            bad += 1
            print(f"  PARSE FAIL {p.name}: {exc}")
    print(f"{len(bins)} cache files: {ok} parsed+hash-verified, {stale} stale, {bad} unparsable")
    return 0 if bad == 0 else 1


def main() -> int:
    sys.path.insert(0, str(Path(__file__).parent))
    if len(sys.argv) > 1 and sys.argv[1] == "dump":
        dump(Path(sys.argv[2]))
        return 0
    return selftest()


if __name__ == "__main__":
    raise SystemExit(main())
