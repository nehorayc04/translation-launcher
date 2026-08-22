"""Canonical version model for the publish pipeline (Python side).

MIRRORS website/src/lib/version.ts, frontend/src/lib/version.ts and
main_eel.py:_parse_version. SemVer MAJOR.MINOR.PATCH + optional pre-release
stage suffix `-<stage>.<n>`; stages oldest→newest alpha → beta → rc → stable.

Verified equivalent to the launcher's comparator (universal across all three
TS/PY surfaces) — see the test in the project notes.
"""
from __future__ import annotations

import re

STAGE_RANK = {"alpha": 0, "beta": 1, "rc": 2, "stable": 3}
STAGE_ALIASES = {
    "alpha": "alpha", "a": "alpha", "pre": "alpha",
    "beta": "beta", "b": "beta",
    "rc": "rc", "release-candidate": "rc", "releasecandidate": "rc",
    "stable": "stable", "final": "stable", "release": "stable", "": "stable",
}
STAGES = ("alpha", "beta", "rc", "stable")


def parse(v: str) -> tuple:
    """'1.1.0-beta.2' → (scheme, major, minor, patch, stage_rank, pre)."""
    raw = (v or "").strip()
    body = raw.lstrip("vV")
    dash = body.find("-")
    core = body[:dash] if dash >= 0 else body
    pre_s = body[dash + 1:] if dash >= 0 else ""
    nums = []
    for part in core.split(".")[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    while len(nums) < 3:
        nums.append(0)
    major, minor, patch = nums[0], nums[1], nums[2]
    scheme = 0 if major >= 2000 else 1
    stage, pre = "stable", 0
    if pre_s:
        m = re.match(r"([a-zA-Z][a-zA-Z-]*)\.?(\d+)?", pre_s)
        if m:
            stage = STAGE_ALIASES.get(m.group(1).lower(), "stable")
            pre = int(m.group(2)) if m.group(2) else 0
    return (scheme, major, minor, patch, STAGE_RANK[stage], pre)


def is_newer(a: str, b: str) -> bool:
    return parse(a) > parse(b)


def stage_of(v: str) -> str:
    rank = parse(v)[4]
    for name, r in STAGE_RANK.items():
        if r == rank:
            return name
    return "stable"


def core_of(v: str) -> str:
    """'1.1.0-beta.2' → '1.1.0' (the MAJOR.MINOR.PATCH core, no suffix)."""
    _, ma, mi, pa, _, _ = parse(v)
    return f"{ma}.{mi}.{pa}"


def fmt(v: str) -> str:
    """Display: 'v1.1.0' / 'v1.1.0-beta.2'; placeholder (no digit) as-is."""
    raw = (v or "").strip()
    if not raw or not any(ch.isdigit() for ch in raw):
        return raw
    return "v" + raw.lstrip("vV")


def compose(base: str, stage: str, counter: int | None = None) -> str:
    """Build a canonical version string from a base core + stage (+ counter).

    compose('1.1.0', 'stable')        -> '1.1.0'
    compose('1.1.0', 'beta')          -> '1.1.0-beta'          (counter omitted)
    compose('1.1.0', 'beta', 2)       -> '1.1.0-beta.2'
    """
    core = core_of(base)
    stage = STAGE_ALIASES.get((stage or "stable").lower(), "stable")
    if stage == "stable":
        return core
    return f"{core}-{stage}" + (f".{counter}" if counter else "")


def next_counter(existing_versions: list[str], base: str, stage: str) -> int:
    """Next pre-release counter for (base core, stage). Scans existing version
    strings for matching `<core>-<stage>.N` and returns max(N)+1 (>=1)."""
    core = core_of(base)
    stage = STAGE_ALIASES.get((stage or "stable").lower(), "stable")
    hi = 0
    for v in existing_versions:
        p = parse(v)
        if f"{p[1]}.{p[2]}.{p[3]}" == core and STAGE_RANK.get(stage) == p[4]:
            hi = max(hi, p[5])
    return hi + 1
