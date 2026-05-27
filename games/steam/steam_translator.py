"""
Steam Hebrew localizer — hijacks the Arabic slot to inherit Steam's native RTL.

Modes:
    python steam_translator.py test    # only steampops_english-json.js
    python steam_translator.py all     # full sweep (modern + legacy)
    python steam_translator.py one <relpath>   # single file by relative Steam path

Output goes to ./steam_hebrew_output/<same relative path>, with `english` -> `arabic`.
Copy the result into Steam, then set Steam language to Arabic.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import requests

# ------------------------------------------------------------------ config

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "local-model"          # LM Studio ignores this when one model is loaded
BATCH_SIZE = 20                     # 20 keeps each LM Studio call short enough to finish inside REQUEST_TIMEOUT (30 was timing out)
NUM_WORKERS = 2                     # 2 saturates 27B Gemma on one GPU without cascading timeouts (4 was over-provisioned)
REQUEST_TIMEOUT = 240               # seconds
TEMPERATURE = 0.2

STEAM_DIR = Path(r"C:\Program Files (x86)\Steam")
OUTPUT_DIR = Path(__file__).parent / "steam_hebrew_output"

# ------------------------------------------------------------------ prompt

SYSTEM_PROMPT = """You are a professional Hebrew localizer for the Steam gaming client (desktop + Big Picture mode).
Translate the given English UI strings into natural, concise Hebrew suitable for gamers.

STRICT OUTPUT RULES:
1. Output ONLY a JSON array of strings, in the same order and length as the input. No prose, no markdown fences, no comments.
2. Use Hebrew letters and standard ASCII only. NEVER use Arabic, Cyrillic, Greek, CJK, Hangul, Thai, Devanagari, or any other script.
3. NEVER use Niqqud (Hebrew vowel points).
4. Preserve EXACTLY every placeholder: %s %d %i %f %1$s %2$d %.2f {0} {1} {name} %{var}% \\n \\t \\r.
5. Preserve EXACTLY every tag: HTML (<a>, </a>, <br/>, <b>, <i>), Steam BBCode ([h1], [/h1], [u], [/u], [url=...]).
6. Keep brand and proper names in English: Steam, Valve, Workshop, Big Picture, SteamOS, Steam Deck, Counter-Strike, Dota 2, CS2, TF2.
7. If a string is empty, a single symbol, a pure number, a URL, or contains zero translatable letters, return it UNCHANGED.

GLOSSARY (use these established Steam Hebrew terms):
  Library -> ספרייה   |   Store -> חנות         |   Community -> קהילה
  Friends -> חברים    |   Chat -> צ'אט           |   Profile -> פרופיל
  Achievements -> הישגים   |   Downloads -> הורדות   |   Settings -> הגדרות
  Cloud -> ענן        |   Workshop -> סדנה       |   Game -> משחק
  Play -> שחק          |   Install -> התקן        |   Uninstall -> הסר התקנה
  Update -> עדכן       |   Verify -> אמת           |   Launch -> הפעל
  Account -> חשבון     |   Wallet -> ארנק         |   Cart -> עגלה
  Wishlist -> רשימת משאלות   |   Review -> ביקורת   |   Recommended -> מומלץ
  Online -> מחובר      |   Offline -> מנותק       |   Away -> נעדר
  News -> חדשות        |   Events -> אירועים       |   Screenshot -> צילום מסך
  Broadcast -> שידור   |   Streaming -> סטרימינג
"""

# ------------------------------------------------------------------ LM Studio

class TranslationError(RuntimeError):
    pass


def call_lm(strings: list[str]) -> list[str]:
    """Send a batch to LM Studio. Returns translated list. Raises on hard failure."""
    payload_in = json.dumps(strings, ensure_ascii=False)
    body = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content":
                "Translate this JSON array of English Steam UI strings into Hebrew. "
                "Return ONLY the JSON array, same length, same order:\n" + payload_in},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": -1,
        "stream": False,
    }
    last_err = None
    for attempt in range(1, 4):
        try:
            r = requests.post(LM_STUDIO_URL, json=body, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            # Strip markdown fences if the model added them
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            # Some models prefix "Output:" or similar
            m = re.search(r"\[.*\]", content, re.DOTALL)
            if m:
                content = m.group(0)
            arr = json.loads(content)
            if not isinstance(arr, list):
                raise TranslationError(f"expected JSON array, got {type(arr).__name__}")
            if len(arr) != len(strings):
                raise TranslationError(f"length mismatch: sent {len(strings)}, got {len(arr)}")
            return [str(x) for x in arr]
        except Exception as e:
            last_err = e
            print(f"    ! batch attempt {attempt}/3 failed: {e}")
            time.sleep(1.5)
    # Final fallback: per-item, single-shot, return original on failure
    print("    -> per-item fallback")
    out: list[str] = []
    for s in strings:
        try:
            single = call_lm_single(s)
            out.append(single)
        except Exception as e:
            print(f"      ! single failed, keeping original: {e}")
            out.append(s)
    return out


def call_lm_single(s: str) -> str:
    body = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content":
                'Translate this single string to Hebrew. Return ONLY a JSON array with one element:\n'
                + json.dumps([s], ensure_ascii=False)},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": -1,
        "stream": False,
    }
    r = requests.post(LM_STUDIO_URL, json=body, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    m = re.search(r"\[.*\]", content, re.DOTALL)
    if m:
        content = m.group(0)
    arr = json.loads(content)
    return str(arr[0])


# ------------------------------------------------------------------ skip rules

_PLACEHOLDER_RE = re.compile(
    r"%\d*\$?[\d.]*[sdifupxXc%]|\{\d+\}|\{[A-Za-z_]\w*\}|%\{[^}]+\}%|\\[nrt]"
)
_TAG_RE = re.compile(r"<[^>]+>|\[/?[A-Za-z][^\]]*\]")


def should_skip(value: str) -> bool:
    """True when the string has no real translatable content."""
    if not value or not value.strip():
        return True
    stripped = _PLACEHOLDER_RE.sub("", value)
    stripped = _TAG_RE.sub("", stripped)
    # Require at least one alphabetic letter to translate
    if not re.search(r"[A-Za-z]", stripped):
        return True
    return False


# ------------------------------------------------------------------ checkpoint

def checkpoint_path_for(out_path: Path) -> Path:
    """Sidecar checkpoint file: '<output>.partial.json' alongside the target."""
    return out_path.with_name(out_path.name + ".partial.json")


def load_checkpoint(ckpt: Path) -> dict[str, str]:
    """Load {key: hebrew} dict, or {} if the file is missing/corrupt."""
    if not ckpt.exists():
        return {}
    try:
        data = json.loads(ckpt.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError) as e:
        print(f"  ! checkpoint at {ckpt.name} unreadable ({e}), starting fresh")
    return {}


def save_checkpoint(ckpt: Path, state: dict[str, str]) -> None:
    """Atomic write: dump to .tmp then os.replace so a crash mid-write can't
    leave a partially-written checkpoint behind."""
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    tmp = ckpt.with_suffix(ckpt.suffix + ".tmp")
    tmp.write_text(
        json.dumps(state, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    tmp.replace(ckpt)


def translate_pairs(
    items: list[tuple[str, str]],
    label: str,
    *,
    ckpt_path: Path,
    initial: dict[str, str] | None = None,
) -> dict[str, str]:
    """items: list of (unique_key, english). Returns {unique_key: hebrew}.

    Resumes from `initial` (a prior checkpoint dict) — any items whose
    key is already present are skipped entirely. After every successful
    batch, the in-flight `out` dict is atomically written to `ckpt_path`,
    so a kill/crash at any point loses at most one batch (~30 strings)
    and the next run picks up from there.

    NUM_WORKERS concurrent HTTP calls to LM Studio. Batches are
    independent so order-of-completion doesn't matter."""
    out: dict[str, str] = dict(initial or {})
    pending = [(k, v) for k, v in items if k not in out]

    total_items = len(items)
    skipped = total_items - len(pending)
    if skipped:
        print(f"    [{label}] resumed — {skipped} keys already in checkpoint, {len(pending)} pending")
    if not pending:
        return out

    total = len(pending)
    batches: list[list[tuple[str, str]]] = [
        pending[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)
    ]

    done = 0
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
        future_to_batch = {
            pool.submit(call_lm, [v for _, v in b]): b for b in batches
        }
        for fut in as_completed(future_to_batch):
            batch = future_to_batch[fut]
            try:
                translated = fut.result()
            except Exception as e:
                print(f"    ! [{label}] batch failed entirely: {e}, keeping originals")
                translated = [v for _, v in batch]
            for (k, _), h in zip(batch, translated):
                out[k] = h
            done += len(batch)
            try:
                save_checkpoint(ckpt_path, out)
            except OSError as e:
                print(f"    ! checkpoint write failed: {e}")
            print(f"    [{label}] {done}/{total}  (ckpt: {len(out)} keys)")
    return out


# ------------------------------------------------------------------ JS bundle handler

JSON_PARSE_RE = re.compile(r"JSON\.parse\('(.+?)'\)", re.DOTALL)


def js_decode(s: str) -> str:
    """Decode JS single-quoted string escapes back to the original payload."""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == "'":    out.append("'");  i += 2
            elif nxt == '"':  out.append('"');  i += 2
            elif nxt == "\\": out.append("\\"); i += 2
            elif nxt == "n":  out.append("\n"); i += 2
            elif nxt == "r":  out.append("\r"); i += 2
            elif nxt == "t":  out.append("\t"); i += 2
            elif nxt == "b":  out.append("\b"); i += 2
            elif nxt == "f":  out.append("\f"); i += 2
            elif nxt == "0":  out.append("\0"); i += 2
            elif nxt == "u" and i + 5 < n:
                out.append(chr(int(s[i + 2:i + 6], 16)));  i += 6
            elif nxt == "x" and i + 3 < n:
                out.append(chr(int(s[i + 2:i + 4], 16)));  i += 4
            else:
                out.append(nxt); i += 2
        else:
            out.append(c); i += 1
    return "".join(out)


def js_encode(s: str) -> str:
    """Escape a payload for embedding inside a JS single-quoted literal."""
    # backslash first, then single quote, then control chars
    return (s
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
            .replace(" ", "\\u2028")
            .replace(" ", "\\u2029"))


def translate_js_bundle(in_path: Path, out_path: Path) -> None:
    print(f"  reading {in_path}")
    text = in_path.read_text(encoding="utf-8")
    matches = list(JSON_PARSE_RE.finditer(text))
    if not matches:
        raise TranslationError("no JSON.parse('...') wrapper found")
    print(f"  found {len(matches)} JSON.parse block(s)")

    ckpt_path = checkpoint_path_for(out_path)
    ckpt = load_checkpoint(ckpt_path)
    if ckpt:
        print(f"  loaded checkpoint: {len(ckpt)} keys already translated")

    # Process in reverse so byte offsets stay valid as we splice
    for m_idx, m in enumerate(reversed(matches), 1):
        raw = m.group(1)
        try:
            payload = js_decode(raw)
            data = json.loads(payload)
        except Exception as e:
            print(f"  ! block {m_idx}: decode failed ({e}), skipping")
            continue
        if not isinstance(data, dict):
            print(f"  ! block {m_idx}: payload is {type(data).__name__}, skipping")
            continue
        # Collect translatable entries — key by the JSON property name
        # (unique per file, so it doubles as the checkpoint key).
        items: list[tuple[str, str]] = []
        for k, v in data.items():
            if k == "language":
                continue
            if not isinstance(v, str):
                continue
            if should_skip(v):
                continue
            items.append((k, v))
        print(f"  block {m_idx}: {len(items)} translatable / {len(data)} total")
        translated = translate_pairs(items, f"block{m_idx}", ckpt_path=ckpt_path, initial=ckpt)
        # Apply both freshly-translated AND previously-checkpointed values.
        for k, hebrew in translated.items():
            if k in data:
                data[k] = hebrew
        if "language" in data:
            data["language"] = "arabic"
        new_payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        new_raw = js_encode(new_payload)
        text = text[:m.start(1)] + new_raw + text[m.end(1):]
        ckpt = translated  # seed for next block (carries over)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"  wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    # File done — clear checkpoint so a future re-run starts fresh.
    if ckpt_path.exists():
        ckpt_path.unlink()
        print(f"  cleared checkpoint: {ckpt_path.name}")


# ------------------------------------------------------------------ VDF handler

# Captures one "key" "value" line with full value-escape handling.
VDF_KV_RE = re.compile(
    r'^(?P<indent>[ \t]*)'
    r'"(?P<key>[^"]+)"'
    r'(?P<sep>[ \t]+)'
    r'"(?P<val>(?:[^"\\]|\\.)*)"'
)


def vdf_decode(s: str) -> str:
    return s.replace('\\\\', '\x00').replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\x00', '\\')


def vdf_encode(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')


def translate_vdf(in_path: Path, out_path: Path) -> None:
    """Steam VDF lives in TWO encodings in the wild:
      - UTF-16 LE + BOM (older clients, some `*_english.txt` files)
      - UTF-8 + BOM     (current Steam, observed 2026 on all four legacy paths)
    We sniff the BOM and write back using whichever encoding the source used."""
    print(f"  reading {in_path}")
    raw = in_path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        encoding = "utf-16-le"
        body = raw[2:]
    elif raw.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8"
        body = raw[3:]
    else:
        # No BOM — default to UTF-8 (will surface any odd bytes immediately)
        encoding = "utf-8"
        body = raw
    print(f"  encoding: {encoding}")
    text = body.decode(encoding)
    lines = text.splitlines(keepends=True)

    ckpt_path = checkpoint_path_for(out_path)
    ckpt = load_checkpoint(ckpt_path)
    if ckpt:
        print(f"  loaded checkpoint: {len(ckpt)} keys already translated")

    in_tokens = False
    items: list[tuple[str, str]] = []                       # (vdf_key, decoded value)
    spans: dict[str, tuple[int, int, int]] = {}             # vdf_key -> (line_idx, val_start, val_end)

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '"Tokens"':
            in_tokens = True
            continue
        m = VDF_KV_RE.match(line)
        if not m:
            continue
        key = m.group("key")
        val_start = m.start("val")
        val_end = m.end("val")
        raw_val = m.group("val")

        if key.lower() == "language":
            # Hijack: announce Arabic so Steam links the file to the Arabic
            # slot. The "Language" key is a SIBLING of "Tokens" — it sits
            # OUTSIDE (before) the Tokens block, so this check must run
            # regardless of `in_tokens`.
            lines[idx] = line[:val_start] + "Arabic" + line[val_end:]
            continue

        # Token strings only exist inside the "Tokens" block.
        if not in_tokens:
            continue

        decoded = vdf_decode(raw_val)
        if should_skip(decoded):
            continue
        items.append((key, decoded))
        spans[key] = (idx, val_start, val_end)

    print(f"  {len(items)} translatable token lines")
    translated = translate_pairs(items, "vdf", ckpt_path=ckpt_path, initial=ckpt)

    # Apply substitutions — both freshly-translated and checkpointed.
    for vdf_key, hebrew in translated.items():
        if vdf_key not in spans:
            continue                                         # checkpoint entry no longer present in source
        line_idx, s_, e_ = spans[vdf_key]
        original_line = lines[line_idx]
        lines[line_idx] = original_line[:s_] + vdf_encode(hebrew) + original_line[e_:]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(lines).encode(encoding)
    bom = b"\xff\xfe" if encoding == "utf-16-le" else b"\xef\xbb\xbf"
    out_path.write_bytes(bom + encoded)
    print(f"  wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    # File done — clear checkpoint so a future re-run starts fresh.
    if ckpt_path.exists():
        ckpt_path.unlink()
        print(f"  cleared checkpoint: {ckpt_path.name}")


# ------------------------------------------------------------------ targets

MODERN_FILES = [
    "steamui/localization/steamui_english-json.js",
    "steamui/localization/shared_english-json.js",
    "steamui/localization/friendsui_english-json.js",
    "steamui/localization/steampops_english-json.js",
]

LEGACY_FILES = [
    "resource/vgui_english.txt",
    "resource/overlay_english.txt",
    "resource/platform_english.txt",
    "friends/trackerui_english.txt",
]


def english_to_arabic_path(rel: str) -> str:
    if rel.endswith("_english-json.js"):
        return rel[: -len("_english-json.js")] + "_arabic-json.js"
    if rel.endswith("_english.txt"):
        return rel[: -len("_english.txt")] + "_arabic.txt"
    raise ValueError(f"unrecognized filename: {rel}")


def dispatch(rel_in: str) -> None:
    in_path = STEAM_DIR / rel_in
    out_path = OUTPUT_DIR / english_to_arabic_path(rel_in)
    if not in_path.exists():
        raise FileNotFoundError(in_path)
    t0 = time.time()
    if rel_in.endswith(".js"):
        translate_js_bundle(in_path, out_path)
    elif rel_in.endswith(".txt"):
        translate_vdf(in_path, out_path)
    else:
        raise ValueError(f"unknown file type: {rel_in}")
    print(f"  done in {time.time() - t0:.1f}s")


# ------------------------------------------------------------------ health

def check_lm_studio() -> None:
    try:
        r = requests.get(LM_STUDIO_URL.replace("/chat/completions", "/models"), timeout=5)
        r.raise_for_status()
        models = [m.get("id", "?") for m in r.json().get("data", [])]
        print(f"  LM Studio OK. Loaded: {models or '(none reported)'}")
    except Exception as e:
        raise SystemExit(f"LM Studio unreachable at {LM_STUDIO_URL}: {e}")


# ------------------------------------------------------------------ main

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    mode = sys.argv[1]
    check_lm_studio()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if mode == "test":
        print("[TEST] steampops_english-json.js")
        dispatch("steamui/localization/steampops_english-json.js")
    elif mode == "one":
        if len(sys.argv) < 3:
            raise SystemExit("usage: steam_translator.py one <relative-steam-path>")
        rel = sys.argv[2].replace("\\", "/")
        print(f"[ONE] {rel}")
        dispatch(rel)
    elif mode == "all":
        for rel in MODERN_FILES:
            print(f"\n[MODERN] {rel}")
            dispatch(rel)
        for rel in LEGACY_FILES:
            print(f"\n[LEGACY] {rel}")
            dispatch(rel)
    else:
        print(__doc__)
        sys.exit(1)

    print("\nDone.")
    print(f"Output dir: {OUTPUT_DIR}")
    print("To activate: copy *_arabic-json.js into Steam\\steamui\\localization\\,")
    print("             copy *_arabic.txt into Steam\\resource\\ (and friends\\),")
    print("             restart Steam with language = Arabic.")


if __name__ == "__main__":
    main()
