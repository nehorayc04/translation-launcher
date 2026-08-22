# -*- coding: utf-8 -*-
"""
Import a Gemini translation response into hebrew.json.

Usage:
  python gowr_batch_import.py 001          # reads prompts/batch_001_response.txt
  python gowr_batch_import.py 001 out.txt  # reads explicit file

The response file should contain the JSON object Gemini returned.
Everything outside the first { ... } block is ignored automatically.
"""
import os, sys, re, json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE  = os.path.dirname(os.path.abspath(__file__))
OUT_F = os.path.join(HERE, "hebrew.json")
EN_F  = os.path.join(HERE, "english.json")
AR_F  = os.path.join(HERE, "arabic.json")
PDIR  = os.path.join(HERE, "prompts")

# validation helpers
TOK_RE   = re.compile(r"\[\[S:[^\]]*\]\]|\[/?style[^\]]*\]|\[/?i\]|\[Icons:[^\]]*\]|\[[A-Za-z][^\]]*Button\]|%d|%s|\\n")
RUNE_RE  = re.compile(r"[ᚠ-᛿]")
NIQQUD   = re.compile(r"[֑-ׇ]")
FOREIGN  = re.compile(r"[؀-ۿЀ-ӿ一-鿿]")


def is_namey(v):
    return not re.search(r"[a-z]{2,}", v)


def validate(src, out):
    if not out or not out.strip():
        return False, "empty"
    if NIQQUD.search(out):
        return False, "niqqud"
    if FOREIGN.search(out):
        return False, "foreign script"
    if sorted(TOK_RE.findall(src)) != sorted(TOK_RE.findall(out)):
        return False, "tag mismatch"
    if sorted(RUNE_RE.findall(src)) != sorted(RUNE_RE.findall(out)):
        return False, "rune mismatch"
    if (not re.search(r"[א-ת]", out)
            and not is_namey(src)
            and not RUNE_RE.search(src)):
        return False, "no Hebrew"
    return True, "ok"


def extract_json(text):
    """Find the first {...} block in the response, even if wrapped in markdown."""
    # strip ```json fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    # find outermost { }
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None


def atomic_write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python gowr_batch_import.py <batch_num> [response_file]"); return 1

    num = sys.argv[1].zfill(3)
    if len(sys.argv) >= 3:
        resp_path = sys.argv[2]
    else:
        resp_path = os.path.join(PDIR, f"batch_{num}_response.txt")

    if not os.path.exists(resp_path):
        print(f"קובץ תשובה לא נמצא: {resp_path}")
        print(f"שמור את תשובת Gemini ל: {resp_path}")
        return 1

    en = json.load(open(EN_F, encoding="utf-8"))

    response_text = open(resp_path, encoding="utf-8").read()
    parsed = extract_json(response_text)
    if not parsed:
        print("לא הצלחתי לחלץ JSON מהתשובה. ודא שהתשובה מכילה { ... }"); return 1

    print(f"נמצאו {len(parsed):,} מחרוזות בתשובה")

    # load existing
    done = {}
    try:
        done = json.load(open(OUT_F, encoding="utf-8"))
    except (OSError, ValueError):
        pass

    added = skipped = invalid = 0
    for k, v in parsed.items():
        src = en.get(k, "")
        v = str(v).strip()
        ok, reason = validate(src, v)
        if ok:
            done[k] = v
            added += 1
        else:
            print(f"  דחיה [{reason}] id={k}: {v!r:.60}")
            invalid += 1

    atomic_write(OUT_F, done)

    print(f"\nנוספו: {added}  דחויות: {invalid}  כסה: {skipped}")
    print(f"סה\"כ ב-hebrew.json: {len(done):,}")
    print(f"\nכדי להמשיך לבאצ' הבא:")
    print(f"  python gowr_batch_export.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
